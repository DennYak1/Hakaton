#!/usr/bin/env python3
"""
Модуль загрузки файлов из базы данных
Интегрирован с основным проектом обработки документов
"""

import os
import sys
from pathlib import Path
import concurrent.futures
from typing import List, Dict, Any, Optional
import requests
import psycopg2
from datetime import datetime
import logging
from urllib.parse import urljoin



logger = logging.getLogger(__name__)

class FileDownloader:
    def __init__(self):
        self.config = {
            'db_name': os.getenv('POSTGRES_DB', 'documents'),
            'db_user': os.getenv('POSTGRES_USER', 'admin'),
            'db_password': os.getenv('POSTGRES_PASSWORD', 'secret'),
            'db_host': os.getenv('PG_HOST', 'db'),
            'db_port': '5432',
            'download_dir': '/app/data/downloaded_files',
            'base_download_url': os.getenv('BASE_DOWNLOAD_URL', 'https://hackaton.hb.ru-msk.vkcloud-storage.ru/media')
        }
        self.download_dir = Path(self.config['download_dir'])
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def db_connection(self):
        return psycopg2.connect(
            dbname=self.config['db_name'],
            user=self.config['db_user'],
            password=self.config['db_password'],
            host=self.config['db_host'],
            port=self.config['db_port']
        )

    def download_file(self, file_url, file_name):
        file_path = self.download_dir / file_name
        
        if not file_url.startswith(('http://', 'https://')):
            file_url = f"{self.config['base_download_url']}/{file_url}"
        logger.debug(f"Попытка загрузки файла: {file_name}, URL: {file_url}, путь: {file_path}")
        if file_path.exists():
            logger.info(f"Файл уже существует: {file_path}")
            return file_path
        if not file_url:
            logger.error(f"URL отсутствует для файла: {file_name}")
            raise FileNotFoundError(f"URL отсутствует для файла: {file_name}")
        try:
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"Успешно загружен файл: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Ошибка загрузки {file_name}: {str(e)}")
            raise

    def download_files(self):
        with self.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'storage_storageobject')")
            table_exists = cursor.fetchone()[0]
            if not table_exists:
                logger.error("Таблица storage_storageobject не найдена в базе данных")
                return
            cursor.execute("SELECT id, file_name, file_url FROM storage_storageobject")
            logger.debug("Выполнен SQL-запрос: SELECT id, file_name, file_url FROM storage_storageobject")
            files = cursor.fetchall()
            logger.info(f"Найдено {len(files)} файлов для загрузки")
            for file_id, file_name, file_url in files:
                if len(file_name) > 255:
                    logger.warning(f"Пропущен файл с длинным именем: {file_name}")
                    continue
                try:
                    logger.debug(f"Обработка файла: id={file_id}, name={file_name}, url={file_url}")
                    self.download_file(file_url, file_name)
                except Exception as e:
                    logger.error(f"Критическая ошибка: {file_name} - {str(e)}")

    def get_file_list(self, conn: psycopg2.extensions.connection) -> List[Dict[str, str]]:
        """Получение списка файлов для загрузки"""
        files = []
        if not conn:
            return files

        query = """
            SELECT so.name, sv.link
            FROM storage_storageobject AS so
            JOIN storage_version AS sv ON so.version_id = sv.id
            WHERE so.type = 1 
              AND sv.link IS NOT NULL 
              AND sv.link <> ''
              AND lower(so.name) LIKE ANY(%s)
        """
        
        patterns = [f"%{ext}" for ext in self.allowed_extensions]

        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (patterns,))
                files = [{'name': row[0], 'link': row[1]} for row in cursor.fetchall()]
                logger.info(f"Найдено {len(files)} файлов для загрузки")
        except psycopg2.Error as e:
            logger.error(f"Ошибка при запросе к БД: {e}")
            conn.rollback()
        
        return files

    def process_files(self) -> Dict[str, Any]:
        """Основной процесс загрузки файлов"""
        stats = {
            'total': 0,
            'success': 0,
            'skipped': 0,
            'errors': 0,
            'error_list': []
        }

        conn = self.get_db_connection()
        if not conn:
            return stats

        try:
            files = self.get_file_list(conn)
            stats['total'] = len(files)

            if not files:
                logger.info("Нет файлов для загрузки")
                return stats

            # Фильтрация уже существующих файлов
            existing_files = {f.name.lower() for f in self.download_dir.glob('*') if f.is_file()}
            files_to_download = [
                f for f in files 
                if f['name'].lower() not in existing_files
            ]
            stats['skipped'] = stats['total'] - len(files_to_download)

            if not files_to_download:
                logger.info("Все файлы уже загружены")
                return stats

            logger.info(f"Начало загрузки {len(files_to_download)} файлов")

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(self.download_file, file): file 
                    for file in files_to_download
                }

                for future in concurrent.futures.as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        result = future.result()
                        if result['success']:
                            stats['success'] += 1
                            logger.debug(f"Успешно: {file['name']}")
                        else:
                            stats['errors'] += 1
                            stats['error_list'].append({
                                'file': file['name'],
                                'error': result['error']
                            })
                            logger.warning(f"Ошибка: {file['name']} - {result['error']}")
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = str(e)
                        stats['error_list'].append({
                            'file': file['name'],
                            'error': error_msg
                        })
                        logger.error(f"Критическая ошибка: {file['name']} - {error_msg}")

        finally:
            conn.close()
            logger.info("Соединение с БД закрыто")

        return stats

    def save_stats(self, stats: Dict[str, Any]) -> None:
        """Сохранение статистики загрузки"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stats_file = self.log_dir / "download_stats.log"

        try:
            with open(stats_file, 'a', encoding='utf-8') as f:
                f.write(f"\n=== {timestamp} ===\n")
                f.write(f"Всего файлов в БД: {stats['total']}\n")
                f.write(f"Успешно загружено: {stats['success']}\n")
                f.write(f"Пропущено (уже существует): {stats['skipped']}\n")
                f.write(f"Ошибок загрузки: {stats['errors']}\n")
                f.write("=" * 30 + "\n")
            logger.info(f"Статистика сохранена в {stats_file}")
        except IOError as e:
            logger.error(f"Ошибка сохранения статистики: {e}")

def load_config() -> Dict[str, str]:
    """Загрузка конфигурации из переменных окружения"""
    config = {
        'base_url': os.getenv('BASE_DOWNLOAD_URL', 'https://hackaton.hb.ru-msk.vkcloud-storage.ru/media'),
        'pg_user': os.getenv('POSTGRES_USER'),
        'pg_password': os.getenv('POSTGRES_PASSWORD'),
        'pg_host': os.getenv('PG_HOST', 'db'),
        'pg_port': os.getenv('POSTGRES_PORT', '5432'),
        'db_name': 'filestorage',
        'download_dir': os.getenv('DOWNLOAD_DIR', 'data/downloaded_files'),
        'log_dir': os.getenv('LOG_DIR', 'logs'),
        'max_workers': os.getenv('DOWNLOAD_WORKERS', '10')
    }
    
    if not all([config['pg_user'], config['pg_password']]):
        logger.error("Необходимо установить POSTGRES_USER и POSTGRES_PASSWORD")
        sys.exit(1)
        
    return config

def main():
    """Точка входа скрипта"""
    config = load_config()
    downloader = FileDownloader(config)
    
    logger.info("Начало процесса загрузки файлов")
    stats = downloader.process_files()
    
    logger.info("\nИтоговая статистика:")
    logger.info(f"Всего файлов в БД: {stats['total']}")
    logger.info(f"Успешно загружено: {stats['success']}")
    logger.info(f"Пропущено (уже существует): {stats['skipped']}")
    logger.info(f"Ошибок загрузки: {stats['errors']}")
    
    downloader.save_stats(stats)
    
    if stats['errors'] > 0:
        logger.warning(f"Были ошибки при загрузке {stats['errors']} файлов")
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class FileDownloader:
    """Класс для загрузки файлов из базы данных"""
    
    def __init__(self, config: dict):
        """
        Инициализация загрузчика
        
        :param config: Конфигурация подключения к БД и параметров загрузки
        """
        self.config = config
        self.download_dir = Path(config.get('download_dir', 'data/downloaded_files'))
        self.log_dir = Path(config.get('log_dir', 'logs'))
        self.max_workers = int(config.get('max_workers', 10))
        self.allowed_extensions = (
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
            '.txt', '.csv', '.json'
        )
        
        # Создаем необходимые директории
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_db_connection(self) -> Optional[psycopg2.extensions.connection]:
        """Установка соединения с PostgreSQL"""
        try:
            conn = psycopg2.connect(
                dbname=self.config['db_name'],
                user=self.config['pg_user'],
                password=self.config['pg_password'],
                host=self.config['pg_host'],
                port=self.config['pg_port']
            )
            logger.info(f"Успешное подключение к БД '{self.config['db_name']}'")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            return None

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

    def download_file(self, file_info: Dict[str, str]) -> Dict[str, Any]:
        """Загрузка одного файла"""
        file_name = file_info['name']
        file_link = file_info['link']
        full_url = f"{self.config['base_url']}/{file_link.lstrip('/')}"
        local_path = self.download_dir / file_name
        
        result = {
            'name': file_name,
            'success': False,
            'path': str(local_path),
            'error': ''
        }

        # Проверка существующего файла
        if local_path.exists() and local_path.stat().st_size > 0:
            result['success'] = True
            result['message'] = 'Файл уже существует'
            return result

        try:
            response = requests.get(full_url, stream=True, timeout=60)
            response.raise_for_status()

            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            result['success'] = True
            result['message'] = 'Успешно загружен'
            return result

        except requests.exceptions.RequestException as e:
            result['error'] = f"Ошибка загрузки: {str(e)}"
            return result
        except Exception as e:
            result['error'] = f"Неизвестная ошибка: {str(e)}"
            return result

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
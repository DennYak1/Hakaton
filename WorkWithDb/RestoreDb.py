#!/usr/bin/env python3
"""
Утилита восстановления PostgreSQL баз данных из дампов
Автоматизирует процесс восстановления данных в Docker-окружении
"""
import os
import subprocess
from pathlib import Path
from typing import List, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class DatabaseRestorer:
    def __init__(self):
        self.config = {
            'db_user': os.getenv('POSTGRES_USER', 'admin'),
            'db_password': os.getenv('POSTGRES_PASSWORD', 'secret'),
            'db_host': os.getenv('PG_HOST', 'db'),
            'db_port': '5432',
            'db_name': os.getenv('POSTGRES_DB', 'documents')
        }

    def _construct_connection_string(self):
        return f"postgresql://{self.config['db_user']}:{self.config['db_password']}@{self.config['db_host']}:{self.config['db_port']}/{self.config['db_name']}"

    def restore(self, dump_path: Path):
        logger.info(f"Начало восстановления дампа: {dump_path}")
        command = [
            "pg_restore",
            "--dbname", self._construct_connection_string(),
            "--no-owner",
            "--no-privileges",
            "--verbose",
            str(dump_path)
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"Успешно восстановлен дамп: {dump_path}")
            logger.debug(f"Вывод pg_restore: {result.stdout}")
            if result.stderr:
                logger.warning(f"Предупреждения pg_restore: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка восстановления {dump_path}: {e.stderr}")
            raise


@dataclass
class DatabaseConfig:
    """Контейнер для параметров подключения к БД"""
    user: str          # Имя пользователя PostgreSQL
    password: str      # Пароль пользователя
    host: str = "db"   # Хост (по умолчанию 'db' - имя сервиса в Docker)
    port: str = "5432" # Порт (стандартный для PostgreSQL)
    initial_db: str = "postgres"  # База для подключения

class DatabaseRestorer:
    """Класс для выполнения операций восстановления БД"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._validate_environment()

    def _validate_environment(self) -> None:
        """Проверка наличия необходимых утилит PostgreSQL"""
        try:
            # Проверяем доступность pg_restore
            subprocess.run(
                ["pg_restore", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "Утилиты PostgreSQL не найдены. Убедитесь, что postgresql-client установлен "
                "в Docker-образе (apt-get install postgresql-client)"
            )
            
        try:   
            subprocess.run(["psql", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "psql не найден"
            )

    def _construct_connection_string(self, mask_password: bool = False) -> str:
        """Формирование строки подключения с маскировкой пароля при необходимости"""
        password = "******" if mask_password else self.config.password
        return f"postgresql://{self.config.user}:{password}@{self.config.host}:{self.config.port}/{self.config.initial_db}"

    def restore_database(self, dump_path: Path) -> bool:
        """Восстановление БД из указанного дампа"""
        if not dump_path.exists():
            logger.error(f"Файл дампа не найден: {dump_path}")
            return False

        # Проверка валидности дампа
        try:
            result = subprocess.run(
                ["pg_restore", "--list", str(dump_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.debug(f"Содержимое дампа {dump_path.name}: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Невалидный файл дампа {dump_path.name}: {e.stderr}")
            return False

        # Формируем команду восстановления
        command = [
            "pg_restore",
            "--create",
            "--dbname", self._construct_connection_string(),
            "--no-owner",
            "--format", "c",
            "--no-privileges",
            "--verbose",
            str(dump_path)
        ]

        logger.info(f"Начато восстановление из {dump_path.name}")
        logger.debug(f"Команда: {' '.join(self._mask_sensitive_data(command))}")

        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.password
            
            result = subprocess.run(
                command,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=3600
            )
            
            if result.stdout:
                logger.debug(f"Вывод pg_restore: {result.stdout}")
            if result.stderr:
                logger.debug(f"Ошибки pg_restore: {result.stderr}")
                
            logger.info(f"Успешно восстановлено из {dump_path.name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка восстановления из {dump_path.name}: {e.stderr}")
            logger.debug(f"Код возврата: {e.returncode}")
            logger.debug(f"Вывод: {e.stdout}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при восстановлении {dump_path.name}: {str(e)}")
            return False

    def _mask_sensitive_data(self, command: List[str]) -> List[str]:
        """Маскировка чувствительных данных в команде для логирования"""
        masked = command.copy()
        for i, part in enumerate(masked):
            if part.startswith("postgresql://"):
                masked[i] = self._construct_connection_string(mask_password=True)
        return masked
    
    
    

def load_configuration(env_path: Optional[Path] = None) -> DatabaseConfig:
    """Загрузка конфигурации из переменных окружения"""
    if env_path:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    
    # Обязательные переменные окружения
    required_vars = {
        'user': os.getenv("POSTGRES_USER"),
        'password': os.getenv("POSTGRES_PASSWORD")
    }
    
    if not all(required_vars.values()):
        missing = [k for k, v in required_vars.items() if not v]
        raise ValueError(
            f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}"
        )

    return DatabaseConfig(
        user=required_vars['user'],
        password=required_vars['password'],
        host=os.getenv("PG_HOST", "db"),  # По умолчанию 'db' для Docker
        port=os.getenv("POSTGRES_PORT", "5432"),
        initial_db=os.getenv("PG_DB_INITIAL", "postgres")
    )

def locate_dump_files(dump_dir: Path, expected_files: List[str]) -> List[Path]:
    """Поиск файлов дампов в указанной директории"""
    if not dump_dir.is_dir():
        raise FileNotFoundError(f"Директория с дампами не найдена: {dump_dir}")

    found_files = []
    for filename in expected_files:
        file_path = dump_dir / filename
        if file_path.is_file():
            found_files.append(file_path)
        else:
            logger.warning(f"Ожидаемый файл дампа не найден: {file_path}")

    if not found_files:
        raise FileNotFoundError("Не найдено ни одного валидного файла дампа")
        
    return found_files

def execute_restoration_sequence(dumps: List[Path], restorer: DatabaseRestorer) -> bool:
    """Последовательное выполнение восстановления из всех дампов"""
    success = True
    for dump in dumps:
        if not restorer.restore_database(dump):
            success = False
            logger.error(f"Прерывание из-за ошибки с {dump.name}")
            break
    return success




def main() -> int:
    """Точка входа скрипта"""
    try:
        # Определяем корневую директорию проекта
        project_root = Path(__file__).parent
        
        # Загружаем конфигурацию из .env файла
        config = load_configuration(project_root / '.env')
        
        # Инициализируем восстановитель БД
        restorer = DatabaseRestorer(config)
        
        # Находим файлы дампов
        dump_files = locate_dump_files(
            project_root / "DumpFiles", 
            ["cms.dump", "lists.dump", "filestorage.dump"]
        )
      
        # Выполняем восстановление
        if execute_restoration_sequence(dump_files, restorer):
            logger.info("Все базы данных успешно восстановлены")
            return 0
        return 1
            
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())

# Hackathon

## Цель проекта:
Разработать прототип (MVP) поисковой системы на базе LLM  для интеграции 
его в VK HR Tek.  

## Структура проекта

```text
Hakaton/
├── WorkWithDb/
│   ├── RestoreDb.py
│   ├── FileDownloader.py
│   ├── lists.dump
│   ├── filestorage.dump
│   └── cms.dump
├── data/                  
│   └── downloaded_files   # Скачанные файлы
├── logs/                  # Логи
├── output/ 
│   └── data.json          # Обработанные данные
├── Data2.py               # Обработка данных
├── requirements.txt
├── .env                   # Файл с переменными окружения
├── .gitignore             # Файл для исключения файлов из Git
├── .dockerignore          # Файл для исключения файлов из Docker
├── docker-compose.yml     # Конфигурация Docker
├── Dockerfile             # Конфигурация Docker образа
└── 
```
## Развертывание проекта

### Требуется скачать:

- [Docker](https://www.docker.com/)


### Этапы запуска

1.  **Клонирование репозитория**

2. **Выполнение команд**
 ```bash
    docker-compose build
    docker-compose up

 ```
3. **После того, как файлы обработаются, выйдет сообщение об успешной обработке. После этого следует запустить контейнер в интерактивном режиме:**
 ```bash
    docker-compose run --service-ports document-processor /bin/bash
 ```
4. **После входа в контейнер выполните:**
 ```bash
    python3 /app/DS2plusTG.py
 ```



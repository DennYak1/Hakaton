
# Hackathon

## Цель проекта:
Разработать прототип (MVP) поисковой системы на базе LLM  для интеграции 
его в VK HR Tek.  

## Структура проекта

```text
Hakaton/
├── app/
│   └── main.py
├── WorkWithDb/
│   ├── RestoreDb.py
│   ├── FileDownloader.py
│   └── DumpFiles/
│       ├── cms.dump
│       ├── lists.dump
│       └── filestorage.dump
├── Data2.py
├── DS1.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env
├── .dockerignore
├── data/
├── output/
└── logs/
```
## Развертывание проекта

### Требуется скачать:

- [Docker](https://www.docker.com/)
- [Docker Compose standalone](https://docs.docker.com/compose/install/standalone/)

### Этапы запуска

1.  **Клонирование репозитория**

2. **Выполнение команд**
 ```bash
    docker-compose down
    docker-compose up -d --build
 ```



# URL Shortener API

![Tests](https://github.com/AVALON4231/url-shortener/actions/workflows/tests.yml/badge.svg)

Сервис сокращения ссылок с JWT-аутентификацией, персональной статистикой переходов и автоматическими тестами. Создан в учебных целях с использованием AI-ассистента.

## Функционал
- Регистрация и вход пользователей (JWT-токены)
- Создание коротких ссылок (принадлежат конкретному пользователю)
- Редирект на оригинальный URL с подсчётом кликов
- Статистика по своим ссылкам (количество кликов, дата создания)
- Возврат JSON для API-клиентов (Swagger) и редирект для браузеров
- Автоматическая документация Swagger с поддержкой авторизации

## Технологии
- Python 3.14.5
- FastAPI
- PostgreSQL (production), SQLite (разработка)
- Passlib (sha256_crypt)
- python-jose (JWT)
- pytest + mocks, dependency overrides
- GitHub Actions (CI)

## Установка и запуск

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/AVALON4231/url-shortener.git
   cd url-shortener

2. Создайте и активируйте виртуальное окружение:

   python -m venv venv

   source venv/bin/activate  

   Windows: venv\Scripts\activate

3. Установите зависимости:   
   pip install -r requirements.txt

4. Задайте переменные окружения:
   - SECRET_KEY — случайная строка для подписи JWT
   - DATABASE_URL — строка подключения к PostgreSQL (или SQLite для разработки) 

5. Запустите сервер:
   uvicorn main:app --reload

Приложение доступно на http://127.0.0.1:8000, документация — http://127.0.0.1:8000/docs.

## Тестирование

- pytest

Тесты автоматически запускаются при каждом пуше через GitHub Actions.

## Деплой

- Сервис развёрнут на Render с автоматическим деплоем из ветки main.

## Лицензия

- Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE.txt).
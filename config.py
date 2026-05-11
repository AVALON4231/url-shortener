import os

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # для локальной разработки без переменной окружения используется ключ-заглушка
    SECRET_KEY = "dev-secret-key-change-in-production"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
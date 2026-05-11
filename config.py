import os

SECRET_KEY = os.getenv("SECRET_KEY")
# При импорте не падаем, даже если ключ не задан.
# Ошибка возникнет только при попытке создать или проверить JWT.

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
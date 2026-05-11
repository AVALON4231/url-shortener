# Секретный ключ для подписи JWT (сгенерируйте случайную строку, можно в терминале: openssl rand -hex 32)
SECRET_KEY = "мояоченьдлиннаястроказаменилёмаё"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # время жизни токена
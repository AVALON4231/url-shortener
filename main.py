from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
from urllib.parse import urlparse  # ДОБАВЛЕНО: для валидации URL
import aiohttp

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel                              # ДОБАВЛЕНО
from slowapi import Limiter, _rate_limit_exceeded_handler  # ДОБАВЛЕНО: rate limiting
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import database
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


# ---------------------------------------------------------------
# ПУНКТ 1: Pydantic-модель — email/password приходят в теле
# запроса (JSON), а не в строке URL.
# Раньше: POST /register?email=vasya&password=12345
# Теперь: POST /register  +  body: {"email":..., "password":...}
# ---------------------------------------------------------------
class UserCreate(BaseModel):
    email: str
    password: str


# ---------------------------------------------------------------
# ПУНКТ 2: Валидация URL.
# Разрешаем только http:// и https://.
# Блокируем: javascript:, file://, просто текст, пустые строки.
# ---------------------------------------------------------------
def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


# ---------------------------------------------------------------
# ПУНКТ 3: Rate Limiting через slowapi.
# Ограничивает число запросов с одного IP — защита от спама.
# ---------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="URL Shortener", version="0.5.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    async def read_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = database.get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user


# --- Эндпоинты ---

# ПУНКТ 1 + ПУНКТ 3: тело запроса + макс. 5 регистраций/мин с одного IP
@app.post("/register")
@limiter.limit("5/minute")
def register(request: Request, data: UserCreate):
    if not data.email or not data.password:
        raise HTTPException(status_code=400, detail="Email and password required")
    success = database.create_user(data.email, data.password)
    if not success:
        raise HTTPException(status_code=400, detail="Email already registered")
    return {"message": "User created successfully"}


# ПУНКТ 3: макс. 10 попыток входа/мин — защита от перебора паролей
@app.post("/login")
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = database.get_user_by_email(form_data.username)
    if not user or not database.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ПУНКТ 2 + ПУНКТ 3: валидация URL + макс. 10 сокращений/мин
@app.get("/shorten")
@limiter.limit("10/minute")
async def shorten_url(url: str, request: Request, current_user: dict = Depends(get_current_user)):
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    # ПУНКТ 2: блокируем всё, кроме http/https
    if not is_valid_url(url):
        raise HTTPException(
            status_code=400,
            detail="Недопустимый URL. Разрешены только ссылки, начинающиеся с http:// или https://"
        )

    user_id = current_user["id"]
    short_code = database.create_short_link(url, user_id)

    title = url
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "ShortURL Bot/1.0"}
            async with session.get(url, timeout=2, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    start = html.lower().find('<title>')
                    end = html.lower().find('</title>', start)
                    if start != -1 and end != -1:
                        title = html[start+7:end].strip()[:200]
    except Exception:
        pass
    database.update_link_title(short_code, title)

    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))
    base = base.split("?")[0].split("#")[0]
    short_url = f"{base}/{short_code}"

    return {
        "original_url": url,
        "short_url": short_url,
        "short_code": short_code,
        "title": title
    }


# ПУНКТ 5: теперь включает clicks и created_at (см. database.py)
@app.get("/my-links")
async def my_links(request: Request, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    links = database.get_user_links(user_id)

    base = request.headers.get("x-forwarded-proto", "http") + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))
    base = base.split("?")[0].split("#")[0]

    for link in links:
        link["short_url"] = f"{base}/{link['short_code']}"
    return links


# ПУНКТ 7: удаление своей ссылки
@app.delete("/my-links/{short_code}")
def delete_link(short_code: str, current_user: dict = Depends(get_current_user)):
    deleted = database.delete_link(short_code, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Short link not found or not yours")
    return {"message": "Link deleted successfully"}


@app.get("/stats/{short_code}")
def get_link_stats(short_code: str, current_user: dict = Depends(get_current_user)):
    stats = database.get_stats(short_code, current_user["id"])
    if stats is None:
        raise HTTPException(status_code=404, detail="Short link not found or not yours")
    return stats


# Динамический сегмент — строго в конце
@app.get("/{short_code}")
def redirect_to_original(short_code: str, request: Request):
    original = database.get_original_url(short_code)
    if original is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    database.increment_clicks(short_code)
    if "application/json" in request.headers.get("accept", ""):
        return {"location": original}
    return RedirectResponse(url=original, status_code=302)

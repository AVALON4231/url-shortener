from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
import socket
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import database
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from services import link_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserCreate(BaseModel):
    email: str
    password: str


class ShortenRequest(BaseModel):
    url: str


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_safe_host(hostname: str) -> bool:
    """Блокирует SSRF: запрещает редиректы на внутренние адреса."""
    try:
        ip = socket.gethostbyname(hostname)
        return not ip.startswith(("127.", "10.", "192.168.", "172."))
    except Exception:
        return False


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="URL Shortener", version="0.6.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = database.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# --- Эндпоинты ---

@app.post("/register")
@limiter.limit("5/minute")
def register(request: Request, data: UserCreate):
    if not data.email or not data.password:
        raise HTTPException(400, "Email and password required")
    if not database.create_user(data.email, data.password):
        raise HTTPException(400, "Email already exists")
    return {"message": "User created"}


@app.post("/login")
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = database.get_user_by_email(form_data.username)
    if not user or not database.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token(
        {"sub": user["email"]},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token}


@app.post("/shorten")
@limiter.limit("10/minute")
async def shorten_url(
    data: ShortenRequest,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    url = data.url

    if not url or len(url) > 2048:
        raise HTTPException(400, "Invalid URL length")
    if not is_valid_url(url):
        raise HTTPException(400, "Invalid URL. Only http:// and https:// are allowed")

    parsed = urlparse(url)
    if not is_safe_host(parsed.hostname):
        raise HTTPException(400, "Unsafe host")

    # ИСПРАВЛЕНО: был пропущен await — без него вызов возвращал корутину, а не short_code
    short_code = await link_service.create_short_link(url, current_user["id"])

    logger.info(f"User {current_user['id']} shortened {url} → {short_code}")

    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))

    return {
        "short_url": f"{base}/{short_code}",
        "short_code": short_code
    }


# ВОССТАНОВЛЕНО: было удалено, но app.js вызывает GET /my-links
@app.get("/my-links")
async def my_links(request: Request, current_user: dict = Depends(get_current_user)):
    links = database.get_user_links(current_user["id"])

    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))

    for link in links:
        link["short_url"] = f"{base}/{link['short_code']}"
    return links


# ВОССТАНОВЛЕНО: удаление своей ссылки
@app.delete("/my-links/{short_code}")
def delete_link(short_code: str, current_user: dict = Depends(get_current_user)):
    deleted = database.delete_link(short_code, current_user["id"])
    if not deleted:
        raise HTTPException(404, "Link not found or not yours")
    return {"message": "Deleted"}


# ВОССТАНОВЛЕНО: статистика по ссылке
@app.get("/stats/{short_code}")
def get_stats(short_code: str, current_user: dict = Depends(get_current_user)):
    stats = database.get_stats(short_code, current_user["id"])
    if not stats:
        raise HTTPException(404, "Not found")
    return stats


# Динамический сегмент — строго последним
@app.get("/{short_code}")
def redirect(short_code: str):
    url = database.get_original_url(short_code)
    if not url:
        raise HTTPException(404, "Not found")
    database.increment_clicks(short_code)
    return RedirectResponse(url)

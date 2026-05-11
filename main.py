from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt

import database
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="URL Shortener", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статика и корневой маршрут (до всех остальных эндпоинтов)
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

@app.post("/register")
def register(email: str, password: str):
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    success = database.create_user(email, password)
    if not success:
        raise HTTPException(status_code=400, detail="Email already registered")
    return {"message": "User created successfully"}


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
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


@app.get("/shorten")
def shorten_url(url: str, request: Request, current_user: dict = Depends(get_current_user)):
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    user_id = current_user["id"]
    short_code = database.create_short_link(url, user_id)

    # Формируем базовый URL из заголовков запроса
    base = request.headers.get("x-forwarded-proto", request.url.scheme) + "://"
    base += request.headers.get("x-forwarded-host", request.headers.get("host", "127.0.0.1:8000"))
    if "?" in base:
        base = base.split("?")[0]
    if "#" in base:
        base = base.split("#")[0]
    short_url = f"{base}/{short_code}"
    return {
        "original_url": url,
        "short_url": short_url,
        "short_code": short_code
    }


@app.get("/{short_code}")
def redirect_to_original(short_code: str, request: Request):
    original = database.get_original_url(short_code)
    if original is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    database.increment_clicks(short_code)
    if "application/json" in request.headers.get("accept", ""):
        return {"location": original}
    return RedirectResponse(url=original, status_code=302)

import aiohttp

@app.get("/fetch-title")
async def fetch_title(url: str):
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    return {"title": url}
                text = await resp.text()
                # Простой поиск <title> (без регулярных выражений)
                start = text.lower().find('<title>')
                end = text.lower().find('</title>', start)
                if start != -1 and end != -1:
                    title = text[start+7:end].strip()
                    return {"title": title[:200]}  # обрезаем
                return {"title": url}
    except Exception:
        return {"title": url}

@app.get("/stats/{short_code}")
def get_link_stats(short_code: str, current_user: dict = Depends(get_current_user)):
    stats = database.get_stats(short_code, current_user["id"])
    if stats is None:
        raise HTTPException(status_code=404, detail="Short link not found or not yours")
    return stats
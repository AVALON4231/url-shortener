from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from datetime import datetime, timedelta
import database
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

app = FastAPI(title="URL Shortener", version="0.4.0")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Инициализация базы при старте
@app.on_event("startup")
def startup():
    database.init_db()

# Вспомогательная функция для создания JWT
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Зависимость: получаем текущего пользователя из токена
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
    return user  # возвращаем sqlite3.Row с полями id, email и т.д.

# --- Эндпоинты для пользователей ---

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
    user = database.get_user_by_email(form_data.username)  # username = email
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

# --- Эндпоинты для ссылок (требуют авторизацию) ---

@app.get("/shorten")
def shorten_url(url: str, current_user: dict = Depends(get_current_user)):
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    user_id = current_user["id"]
    short_code = database.create_short_link(url, user_id)
    return {
        "original_url": url,
        "short_url": f"http://127.0.0.1:8000/{short_code}",
        "short_code": short_code
    }

@app.get("/{short_code}")
def redirect_to_original(short_code: str):
    original = database.get_original_url(short_code)
    if original is None:
        raise HTTPException(status_code=404, detail="Short link not found")
    database.increment_clicks(short_code)
    return RedirectResponse(url=original, status_code=302)

@app.get("/stats/{short_code}")
def get_link_stats(short_code: str, current_user: dict = Depends(get_current_user)):
    stats = database.get_stats(short_code, current_user["id"])
    if stats is None:
        raise HTTPException(status_code=404, detail="Short link not found or not yours")
    return stats
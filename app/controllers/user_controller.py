from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.services.user_service import UserService
from app.dependencies import create_access_token
from datetime import timedelta
from config import ACCESS_TOKEN_EXPIRE_MINUTES

user_service = UserService()


def register_controller(email: str, password: str):
    success = user_service.register(email, password)
    if not success:
        raise HTTPException(status_code=400, detail="Email already exists")
    return {"message": "User created"}


async def login_controller(form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token}
from fastapi import APIRouter, Depends, Request
from app.controllers.user_controller import register_controller, login_controller
from app.dependencies import limiter, UserCreate

router = APIRouter()


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, data: UserCreate):
    return register_controller(data.email, data.password)


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, form_data=Depends(login_controller)):
    return form_data
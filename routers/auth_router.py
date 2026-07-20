from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User
from auth import hash_password, verify_password, create_access_token

router = APIRouter()

@router.post("/auth/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        return RedirectResponse("/?error=email_taken#signup", status_code=302)

    user = User(email=email, name=name, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id), "email": user.email})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key="session", value=token, httponly=True, secure=False, samesite="lax")
    return response

@router.post("/auth/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return HTMLResponse("<h1>Неверный email или пароль</h1><a href='/login'>Назад</a>", status_code=401)
    token = create_access_token({"sub": str(user.id), "email": user.email})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key="session", value=token, httponly=True, secure=False, samesite="lax")
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("session")
    return response
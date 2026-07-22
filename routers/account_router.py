from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Page
from .deps import get_current_user
from pathlib import Path

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/account", response_class=HTMLResponse)
async def account(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.user_id == user.id).order_by(Page.created_at.desc()))
    pages = result.scalars().all()
    error = request.query_params.get("error", "")
    return templates.TemplateResponse(
        request,
        name="account.html",
        context={"request": request, "user": user, "pages": pages, "error": error}
    )

@router.post("/account/delete/{page_id}")
async def delete_page(page_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.id == page_id, Page.user_id == user.id))
    page = result.scalar_one_or_none()
    if page:
        (Path("static") / f"{page.username}.html").unlink(missing_ok=True)
        for ext in ["png", "jpg", "jpeg", "webp"]:
            (Path("static/avatars") / f"{page.username}.{ext}").unlink(missing_ok=True)
        await db.delete(page)
        await db.commit()
    return RedirectResponse("/account", status_code=302)
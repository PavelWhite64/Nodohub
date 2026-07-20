from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Page
from .deps import get_current_user
from pathlib import Path

router = APIRouter()

@router.get("/account", response_class=HTMLResponse)
async def account(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.user_id == user.id).order_by(Page.created_at.desc()))
    pages = result.scalars().all()

    pages_html = ""
    for page in pages:
        pages_html += f"""
        <div class="page-card">
            <h3>{page.username}</h3>
            <p>{page.role or 'Нет роли'} — {page.bio[:60] if page.bio else ''}</p>
            <div class="actions">
                <a href="/dashboard/{page.id}" class="btn">Редактировать</a>
                <a href="/{page.username}.html" class="btn" target="_blank">Посмотреть</a>
                <form action="/account/delete/{page.id}" method="post" style="display:inline">
                    <button type="submit" class="btn btn-danger">Удалить</button>
                </form>
            </div>
        </div>"""

    limit_message = ""
    if request.query_params.get("error") == "limit":
        limit_message = """<div style="color:#c7512e;text-align:center;margin-bottom:20px">Достигнут лимит визиток (максимум 3)</div>"""

    create_button = ""
    if len(pages) < 3:
        create_button = '<div class="create-btn"><a href="/dashboard/new" class="btn">Создать новую визитку</a></div>'

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Личный кабинет — Nodohub</title>
    <style>
        :root{{ --bg:#faf9f6;--text:#2b2b2b;--accent:#c7512e;--border:#e0ded8;--muted:#6b6b6b; }}
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
            background:var(--bg);color:var(--text);
            font-size:17px;font-weight:300;line-height:1.6;
            padding:40px;max-width:720px;margin:0 auto;
        }}
        h1{{font-weight:400;font-size:32px;letter-spacing:-0.5px;margin-bottom:8px}}
        .logout{{float:right;font-size:14px;color:var(--accent);text-decoration:none}}
        .page-card{{
            background:#fff;border:1px solid var(--border);border-radius:12px;
            padding:24px;margin-bottom:16px;
        }}
        .actions{{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;}}
        .btn{{
            display:inline-block;padding:8px 20px;
            border:1px solid var(--accent);color:var(--accent);
            text-decoration:none;font-size:14px;background:transparent;
            cursor:pointer;transition:background .2s,color .2s;
        }}
        .btn:hover{{background:var(--accent);color:#fff}}
        .btn-danger{{border-color:#a12b2b;color:#a12b2b}}
        .btn-danger:hover{{background:#a12b2b;color:#fff}}
        .create-btn{{margin-bottom:24px;}}
    </style>
</head>
<body>
    <a href="/logout" class="logout">Выйти</a>
    <h1>Мои визитки</h1>
    {limit_message}
    {create_button}
    {pages_html}
    {f'<p style="color:var(--muted);text-align:center;margin-top:40px">Создано {len(pages)} из 3 возможных</p>' if pages else ''}
</body>
</html>"""
    return HTMLResponse(html)

@router.post("/account/delete/{page_id}")
async def delete_page(page_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.id == page_id, Page.user_id == user.id))
    page = result.scalar_one_or_none()
    if page:
        static_path = Path("static") / f"{page.username}.html"
        if static_path.exists():
            static_path.unlink()
        await db.delete(page)
        await db.commit()
    return RedirectResponse("/account", status_code=302)
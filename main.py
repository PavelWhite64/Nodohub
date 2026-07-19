import json, argparse, sys
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from jose import jwt, JWTError
import uvicorn
from typing import Optional

from database import engine, Base, get_db
from models import User, Page
from auth import hash_password, verify_password, create_access_token, SECRET_KEY, ALGORITHM
from generator.renderer import render_page
from generator.models import PageConfig, Link

app = FastAPI(title="Nodohub")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ---------- Зависимость: текущий пользователь ----------
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id).options(selectinload(User.page)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------- Статические страницы (главная, вход, сгенерированные) ----------
@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("static/index.html")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return FileResponse("static/login.html")

@app.get("/{username}.html", response_class=HTMLResponse)
async def serve_page(username: str):
    path = Path("static") / f"{username}.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Page not found")

# ---------- API генерации (опционально) ----------
@app.post("/api/generate")
def generate_page(config: PageConfig):
    from generator.renderer import save_page
    path = save_page(config)
    return {"url": f"/{config.username}.html"}

# ---------- Регистрация ----------
@app.post("/auth/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        return HTMLResponse("<h1>Этот email уже зарегистрирован</h1><a href='/'>Назад</a>", status_code=400)
    user = User(email=email, name=name, hashed_password=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token({"sub": str(user.id), "email": user.email})
    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(key="session", value=token, httponly=True, secure=False, samesite="lax")
    return response

# ---------- Вход ----------
@app.post("/auth/login")
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

# ---------- Выход ----------
@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("session")
    return response

# ---------- Дашборд (GET) ----------
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not user.page:
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 0
        while True:
            result = await db.execute(select(Page).where(Page.username == username))
            if not result.scalar_one_or_none():
                break
            counter += 1
            username = f"{base_username}{counter}"
        page = Page(user_id=user.id, username=username, links="[]")
        db.add(page)
        await db.commit()
        await db.refresh(page)
    else:
        page = user.page

    links = json.loads(page.links) if page.links else []
    while len(links) < 5:
        links.append({"title": "", "url": "", "featured": False})

    # Генерируем поля ссылок
    link_fields = ""
    for i in range(5):
        link_fields += f"""
    <div class="field">
      <label>Ссылка {i+1}</label>
      <input type="text" name="link_title_{i}" placeholder="Название" value="{links[i]['title']}">
      <input type="url" name="link_url_{i}" placeholder="https://..." value="{links[i]['url']}" style="margin-top:8px">
      <div class="featured-check">
        <input type="checkbox" name="link_featured_{i}" {'checked' if links[i]['featured'] else ''}>
        <label>Главная ссылка</label>
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Личный кабинет — Nodohub</title>
  <style>
    :root{{ --bg:#faf9f6;--text:#2b2b2b;--muted:#6b6b6b;--accent:#c7512e;--border:#e0ded8; }}
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--text);
      font-size:17px;font-weight:300;line-height:1.6;
      -webkit-font-smoothing:antialiased;
      padding:40px 24px;max-width:720px;margin:0 auto;
    }}
    h1{{font-weight:400;font-size:32px;letter-spacing:-0.5px;margin-bottom:8px}}
    .logout{{float:right;font-size:14px;color:var(--accent);text-decoration:none;margin-top:8px}}
    .card{{
      background:#fff;border:1px solid var(--border);border-radius:12px;
      padding:32px;margin-top:32px;
    }}
    .field{{margin-bottom:20px}}
    .field label{{
      display:block;font-size:13px;color:var(--muted);
      margin-bottom:8px;letter-spacing:0.2px;
    }}
    .field input, .field textarea{{
      width:100%;padding:12px 16px;
      background:transparent;border:1px solid var(--border);
      font-family:inherit;font-size:16px;color:var(--text);
      transition:border-color .2s;outline:none;
    }}
    .field input:focus, .field textarea:focus{{border-color:var(--accent)}}
    .field textarea{{min-height:80px;resize:vertical}}
    .field .featured-check{{display:flex;align-items:center;gap:8px;margin-top:8px}}
    .btn{{
      display:inline-block;padding:12px 28px;
      border:1px solid var(--accent);color:var(--accent);
      font-size:15px;font-weight:400;background:transparent;
      cursor:pointer;transition:background .2s,color .2s;
      text-align:center;width:100%;
    }}
    .btn:hover{{background:var(--accent);color:#fff}}
    .success{{background:#e6f7e6;color:#2b2b2b;padding:12px 16px;border-radius:8px;margin-top:20px}}
    .error{{background:#fde8e8;color:#a12b2b;padding:12px 16px;border-radius:8px;margin-top:20px}}
    .preview-link{{display:block;margin-top:16px;font-size:14px;color:var(--accent)}}
  </style>
</head>
<body>
  <a href="/logout" class="logout">Выйти</a>
  <h1>{user.name}</h1>
  <form method="post" class="card">
    <div class="field">
      <label>Username (адрес вашей страницы)</label>
      <input type="text" name="username" value="{page.username}" required placeholder="anna">
    </div>
    <div class="field">
      <label>Имя</label>
      <input type="text" name="name" value="{user.name}" required placeholder="Анна Соколова">
    </div>
    <div class="field">
      <label>Роль</label>
      <input type="text" name="role" value="{page.role or ''}" placeholder="Продуктовый дизайнер">
    </div>
    <div class="field">
      <label>О себе</label>
      <textarea name="bio" placeholder="Создаю интерфейсы...">{page.bio or ''}</textarea>
    </div>
    {link_fields}
    <button type="submit" class="btn">Сохранить страницу</button>
  </form>
</body>
</html>"""
    return HTMLResponse(html)

# ---------- Дашборд (POST) ----------
@app.post("/dashboard", response_class=HTMLResponse)
async def dashboard_save(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    name: str = Form(...),
    role: Optional[str] = Form(""),
    bio: Optional[str] = Form(""),
    link_title_0: Optional[str] = Form(""),
    link_url_0: Optional[str] = Form(""),
    link_featured_0: Optional[bool] = Form(False),
    link_title_1: Optional[str] = Form(""),
    link_url_1: Optional[str] = Form(""),
    link_featured_1: Optional[bool] = Form(False),
    link_title_2: Optional[str] = Form(""),
    link_url_2: Optional[str] = Form(""),
    link_featured_2: Optional[bool] = Form(False),
    link_title_3: Optional[str] = Form(""),
    link_url_3: Optional[str] = Form(""),
    link_featured_3: Optional[bool] = Form(False),
    link_title_4: Optional[str] = Form(""),
    link_url_4: Optional[str] = Form(""),
    link_featured_4: Optional[bool] = Form(False),
):
    if not user.page:
        page = Page(user_id=user.id, username=username)
        db.add(page)
    else:
        page = user.page

    old_username = page.username
    page.username = username
    page.role = role
    page.bio = bio

    links = []
    for i in range(5):
        title = locals()[f"link_title_{i}"]
        url = locals()[f"link_url_{i}"]
        featured = locals()[f"link_featured_{i}"]
        if title and url:
            links.append({"title": title, "url": url, "featured": featured})
    page.links = json.dumps(links)
    await db.commit()
    await db.refresh(page)

    initials = ''.join([w[0].upper() for w in name.strip().split()[:2]]) if name else "N"

    try:
        page_config = PageConfig(
            username=page.username,
            name=name,
            role=page.role or "",
            bio=page.bio or "",
            avatar_initial=initials,
            theme=page.theme or "minimal",
            links=[Link(title=l["title"], url=l["url"], featured=l["featured"]) for l in links]
        )
    except Exception:
        return HTMLResponse("<h1>Ошибка в URL ссылок</h1><a href='/dashboard'>Назад</a>", status_code=400)

    html = render_page(page_config)
    output_dir = Path("static")
    output_dir.mkdir(exist_ok=True)
    if old_username != page.username:
        old_path = output_dir / f"{old_username}.html"
        if old_path.exists():
            old_path.unlink()
    (output_dir / f"{page.username}.html").write_text(html, encoding="utf-8")

    return HTMLResponse(f"""<h1>Страница обновлена!</h1>
    <p><a href="/{page.username}.html">Посмотреть</a></p>
    <p><a href="/dashboard">Редактировать</a></p>""")

# ---------- CLI ----------
def cli():
    parser = argparse.ArgumentParser(description="Nodohub static page generator")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()
    data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config = PageConfig(**data)
    from generator.renderer import save_page
    path = save_page(config)
    print(f"✅ Page generated: {path}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        sys.argv.pop(1)
        cli()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
import json, io
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from PIL import Image, ImageOps

from database import get_db
from models import User, Page
from generator.renderer import render_page
from generator.models import PageConfig, Link
from .deps import get_current_user

router = APIRouter()

AVATAR_DIR = Path("static/avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2 МБ

def get_avatar_url(username: str) -> Optional[str]:
    """Ищем аватар в любом из поддерживаемых форматов, приоритет — обработанный jpg."""
    for ext in ["jpg", "jpeg", "png", "webp"]:
        path = AVATAR_DIR / f"{username}.{ext}"
        if path.exists():
            return f"/avatars/{username}.{ext}"
    return None

def delete_avatars(username: str):
    for ext in ALLOWED_EXTENSIONS:
        path = AVATAR_DIR / f"{username}.{ext}"
        if path.exists():
            path.unlink()

def process_avatar(image_data: bytes) -> bytes:
    """Обрезает квадрат по центру и изменяет размер до 500×500."""
    img = Image.open(io.BytesIO(image_data))
    # Конвертируем RGBA в RGB, если нужно
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    width, height = img.size
    min_side = min(width, height)
    left = (width - min_side) // 2
    top = (height - min_side) // 2
    img = img.crop((left, top, left + min_side, top + min_side))
    img = img.resize((500, 500), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    buf.seek(0)
    return buf.read()

def render_dashboard_html(user: User, page: Page, links: list, saved: bool = False, error: Optional[str] = None) -> str:
    avatar_url = get_avatar_url(page.username)
    avatar_preview = ""
    if avatar_url:
        avatar_preview = f'<div class="avatar-preview"><img src="{avatar_url}" alt="Текущий аватар"></div>'
    else:
        initials = ''.join([w[0].upper() for w in user.name.split()[:2]]) if user.name else "N"
        avatar_preview = f"""<div class="avatar-preview">
            <svg width="140" height="140" viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg">
                <rect width="140" height="140" fill="#e8e5df"/>
                <text x="50%" y="54%" dominant-baseline="middle" text-anchor="middle" font-family="-apple-system,sans-serif" font-size="42" font-weight="300" fill="#2b2b2b">{initials}</text>
            </svg>
        </div>"""

    # Генерация полей ссылок (без изменений)
    link_fields = f"""
    <div class="field">
      <label>Ссылка 1</label>
      <input type="text" name="link_title_0" placeholder="Название" value="{links[0].get('title', '')}">
      <input type="url" name="link_url_0" placeholder="https://..." value="{links[0].get('url', '')}" style="margin-top:8px">
      <div class="featured-radio">
        <input type="radio" name="featured_link" value="0" id="featured_0" {'checked' if links[0].get('featured') else ''}>
        <label for="featured_0">Главная ссылка</label>
      </div>
    </div>
    """

    group_4 = f"""
          <div class="field" id="link-field-4">
            <label>Ссылка 5</label>
            <input type="text" name="link_title_4" placeholder="Название" value="{links[4].get('title', '')}">
            <input type="url" name="link_url_4" placeholder="https://..." value="{links[4].get('url', '')}" style="margin-top:8px">
            <div class="featured-radio">
              <input type="radio" name="featured_link" value="4" id="featured_4" {'checked' if links[4].get('featured') else ''}>
              <label for="featured_4">Главная ссылка</label>
            </div>
          </div>
"""
    has_data_4 = bool(links[4].get('title') or links[4].get('url'))
    group_3 = f"""
          <div class="field" id="link-field-3">
            <label>Ссылка 4</label>
            <input type="text" name="link_title_3" placeholder="Название" value="{links[3].get('title', '')}">
            <input type="url" name="link_url_3" placeholder="https://..." value="{links[3].get('url', '')}" style="margin-top:8px">
            <div class="featured-radio">
              <input type="radio" name="featured_link" value="3" id="featured_3" {'checked' if links[3].get('featured') else ''}>
              <label for="featured_3">Главная ссылка</label>
            </div>
            <input type="checkbox" id="toggle-link-4" class="toggle-link" {'' if has_data_4 else ''}>
            <label for="toggle-link-4" class="add-link-btn">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </label>
            <div id="group-4" class="link-group">
              {group_4}
            </div>
          </div>
"""
    has_data_3 = bool(links[3].get('title') or links[3].get('url'))
    group_2 = f"""
          <div class="field" id="link-field-2">
            <label>Ссылка 3</label>
            <input type="text" name="link_title_2" placeholder="Название" value="{links[2].get('title', '')}">
            <input type="url" name="link_url_2" placeholder="https://..." value="{links[2].get('url', '')}" style="margin-top:8px">
            <div class="featured-radio">
              <input type="radio" name="featured_link" value="2" id="featured_2" {'checked' if links[2].get('featured') else ''}>
              <label for="featured_2">Главная ссылка</label>
            </div>
            <input type="checkbox" id="toggle-link-3" class="toggle-link" {'' if has_data_3 else ''}>
            <label for="toggle-link-3" class="add-link-btn">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </label>
            <div id="group-3" class="link-group">
              {group_3}
            </div>
          </div>
"""
    has_data_2 = bool(links[2].get('title') or links[2].get('url'))
    group_1 = f"""
    <div class="field" id="link-field-1">
      <label>Ссылка 2</label>
      <input type="text" name="link_title_1" placeholder="Название" value="{links[1].get('title', '')}">
      <input type="url" name="link_url_1" placeholder="https://..." value="{links[1].get('url', '')}" style="margin-top:8px">
      <div class="featured-radio">
        <input type="radio" name="featured_link" value="1" id="featured_1" {'checked' if links[1].get('featured') else ''}>
        <label for="featured_1">Главная ссылка</label>
      </div>
      <input type="checkbox" id="toggle-link-2" class="toggle-link" {'' if has_data_2 else ''}>
      <label for="toggle-link-2" class="add-link-btn">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      </label>
      <div id="group-2" class="link-group">
        {group_2}
      </div>
    </div>
"""

    has_data_1 = bool(links[1].get('title') or links[1].get('url'))
    checked_1 = "checked" if has_data_1 else ""
    link_fields += f"""
    <input type="checkbox" id="toggle-link-1" class="toggle-link" {checked_1}>
    <label for="toggle-link-1" class="add-link-btn">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
    </label>
    <div id="group-1" class="link-group">
      {group_1}
    </div>
"""

    toggle_css = """
    .toggle-link { display: none; }
    label.add-link-btn {
        width: 48px;
        height: 48px;
        margin: 20px auto;
        border: 2px dashed var(--accent);
        border-radius: 50%;
        color: var(--accent);
        cursor: pointer;
        transition: all .2s ease;
        background: transparent;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0;
        line-height: 0;
        padding: 0;
    }
    label.add-link-btn:hover {
        background: var(--accent);
        color: #fff;
    }
    label.add-link-btn svg {
        width: 28px;
        height: 28px;
        display: block;
        color: inherit;
    }
    .link-group { display: none; }
    #toggle-link-1:checked ~ #group-1 { display: block; }
    #toggle-link-2:checked ~ #group-2 { display: block; }
    #toggle-link-3:checked ~ #group-3 { display: block; }
    #toggle-link-4:checked ~ #group-4 { display: block; }
    #toggle-link-1:checked + label[for="toggle-link-1"] { display: none; }
    #toggle-link-2:checked + label[for="toggle-link-2"] { display: none; }
    #toggle-link-3:checked + label[for="toggle-link-3"] { display: none; }
    #toggle-link-4:checked + label[for="toggle-link-4"] { display: none; }
    .field input[type="checkbox"],
    .field input[type="radio"] {
      width: auto;
    }
    .featured-radio {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 12px;
    }
    .featured-radio input[type="radio"] {
        appearance: none;
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border: 2px solid var(--border);
        border-radius: 50%;
        margin: 0;
        cursor: pointer;
        transition: all .2s;
        background: transparent;
    }
    .featured-radio input[type="radio"]:checked {
        border-color: var(--accent);
        background: var(--accent);
    }
    .featured-radio label {
        color: var(--muted);
        cursor: pointer;
        font-size: 14px;
        font-weight: 400;
    }
    """

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Редактор визитки — Nodohub</title>
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
    .back-link{{float:right;font-size:14px;color:var(--accent);text-decoration:none;margin-top:8px}}
    .card{{
      background:#fff;border:1px solid var(--border);border-radius:12px;
      padding:40px;margin-top:32px;
    }}
    .field{{margin-bottom:28px}}
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
    .btn{{
      display:inline-block;padding:14px 32px;
      border:1px solid var(--accent);color:var(--accent);
      font-size:15px;font-weight:400;background:transparent;
      cursor:pointer;transition:background .2s,color .2s;
      text-align:center;width:auto;margin:0 auto;
    }}
    .btn-wrapper{{text-align:center;margin-top:8px;}}
    .btn:hover{{background:var(--accent);color:#fff}}
    .success{{background:#e6f7e6;color:#2b2b2b;padding:12px 16px;border-radius:8px;margin-top:20px}}
    .error{{background:#fde8e8;color:#a12b2b;padding:12px 16px;border-radius:8px;margin-top:20px}}
    .preview-link{{display:block;margin-top:16px;font-size:14px;color:var(--accent)}}
    hr.divider{{border:0;height:1px;background:var(--border);margin:24px 0 32px 0;}}

    .avatar-section {{
        display: flex;
        align-items: center;
        gap: 24px;
        margin-bottom: 28px;
        padding: 16px;
        border: 2px dashed var(--border);
        border-radius: 12px;
        transition: border-color .2s;
    }}
    .avatar-section:hover {{
        border-color: var(--accent);
    }}
    .avatar-preview {{
        width: 140px;
        height: 140px;
        border-radius: 50%;
        border: 2px solid var(--border);
        overflow: hidden;
        flex-shrink: 0;
        background: #f5f5f5;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .avatar-preview img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
    }}
    .avatar-preview svg {{
        width: 100%;
        height: 100%;
    }}
    .avatar-upload {{
        flex: 1;
    }}
    .avatar-upload label.upload-btn {{
        display: inline-block;
        padding: 10px 20px;
        border: 1px solid var(--accent);
        color: var(--accent);
        font-size: 14px;
        cursor: pointer;
        transition: background .2s, color .2s;
        margin-bottom: 8px;
        border-radius: 4px;
    }}
    .avatar-upload label.upload-btn:hover {{
        background: var(--accent);
        color: #fff;
    }}
    .avatar-upload input[type="file"] {{
        display: none;
    }}
    .avatar-hint {{
        font-size: 13px;
        color: var(--muted);
        margin-top: 6px;
        line-height: 1.4;
    }}

    {toggle_css}
  </style>
</head>
<body>
  <a href="/account" class="back-link">← В кабинет</a>
  <h1>{user.name}</h1>
  <hr class="divider">
  {"<div class='error'>" + error + "</div>" if error else ""}
  {f"<div class='success'>Страница обновлена! <a class='preview-link' href='/{page.username}.html'>Посмотреть</a></div>" if saved else ""}
  <form method="post" enctype="multipart/form-data" class="card">
    <div class="field">
      <label>Аватар</label>
      <div class="avatar-section">
        {avatar_preview}
        <div class="avatar-upload">
          <label class="upload-btn" for="avatar-input">Выбрать фото</label>
          <input id="avatar-input" type="file" name="avatar" accept="image/png, image/jpeg, image/webp">
          <div class="avatar-hint">Рекомендуется 300×300 px<br>PNG, JPG или WebP, до 2 МБ</div>
        </div>
      </div>
    </div>
    <div class="field">
      <label>Адрес вашей страницы</label>
      <div style="padding:12px 16px;background:#f5f5f5;border-radius:4px;">{page.username}</div>
      <input type="hidden" name="username" value="{page.username}">
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
    <div class="btn-wrapper">
      <button type="submit" class="btn">Сохранить страницу</button>
    </div>
  </form>
</body>
</html>"""

@router.get("/dashboard/new")
async def new_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.user_id == user.id))
    count = len(result.scalars().all())
    if count >= 3:
        return RedirectResponse("/account?error=limit", status_code=302)
    base = user.email.split('@')[0]
    username = base
    counter = 0
    while True:
        result = await db.execute(select(Page).where(Page.username == username))
        if not result.scalar_one_or_none():
            break
        counter += 1
        username = f"{base}{counter}"
    page = Page(user_id=user.id, username=username, links="[]")
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return RedirectResponse(f"/dashboard/{page.id}", status_code=302)

@router.get("/dashboard/{page_id}", response_class=HTMLResponse)
async def dashboard_edit(page_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.id == page_id, Page.user_id == user.id))
    page = result.scalar_one_or_none()
    if not page:
        return RedirectResponse("/account", status_code=302)
    links = json.loads(page.links) if page.links else []
    if not isinstance(links, list):
        links = []
    while len(links) < 5:
        links.append({"title": "", "url": "", "featured": False})
    html = render_dashboard_html(user, page, links)
    return HTMLResponse(html)

@router.post("/dashboard/{page_id}", response_class=HTMLResponse)
async def dashboard_save(
    page_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    username: str = Form(...),
    name: str = Form(...),
    role: Optional[str] = Form(""),
    bio: Optional[str] = Form(""),
    featured_link: Optional[str] = Form(None),
    link_title_0: Optional[str] = Form(""),
    link_url_0: Optional[str] = Form(""),
    link_title_1: Optional[str] = Form(""),
    link_url_1: Optional[str] = Form(""),
    link_title_2: Optional[str] = Form(""),
    link_url_2: Optional[str] = Form(""),
    link_title_3: Optional[str] = Form(""),
    link_url_3: Optional[str] = Form(""),
    link_title_4: Optional[str] = Form(""),
    link_url_4: Optional[str] = Form(""),
    avatar: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.id == page_id, Page.user_id == user.id))
    page = result.scalar_one_or_none()
    if not page:
        return RedirectResponse("/account", status_code=302)

    old_username = page.username
    page.username = username
    page.role = role
    page.bio = bio

    featured_index = int(featured_link) if featured_link and featured_link.isdigit() else None
    links = []
    for i in range(5):
        title = locals()[f"link_title_{i}"]
        url = locals()[f"link_url_{i}"]
        if title and url:
            is_featured = (featured_index == i)
            links.append({"title": title, "url": url, "featured": is_featured})
    page.links = json.dumps(links)
    await db.commit()
    await db.refresh(page)

    # Обработка аватара
    AVATAR_DIR.mkdir(exist_ok=True)
    if avatar and avatar.filename:
        ext = avatar.filename.rsplit('.', 1)[-1].lower() if '.' in avatar.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            html = render_dashboard_html(user, page, links, error="Допустимы только PNG, JPG или WebP.")
            return HTMLResponse(html)
        contents = await avatar.read()
        if len(contents) > MAX_AVATAR_SIZE:
            html = render_dashboard_html(user, page, links, error="Файл слишком большой (макс. 2 МБ).")
            return HTMLResponse(html)

        # Обработка и сохранение аватара как JPEG
        try:
            processed = process_avatar(contents)
        except Exception:
            html = render_dashboard_html(user, page, links, error="Не удалось обработать изображение.")
            return HTMLResponse(html)

        # Удаляем все старые аватары
        delete_avatars(page.username)
        # Сохраняем как username.jpg
        (AVATAR_DIR / f"{page.username}.jpg").write_bytes(processed)

    initials = ''.join([w[0].upper() for w in name.split()[:2]]) if name else "N"

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
        html = render_dashboard_html(user, page, links, error="Одна из ссылок содержит некорректный URL.")
        return HTMLResponse(html)

    html = render_page(page_config)
    output_dir = Path("static")
    output_dir.mkdir(exist_ok=True)
    if old_username != page.username:
        (output_dir / f"{old_username}.html").unlink(missing_ok=True)
    (output_dir / f"{page.username}.html").write_text(html, encoding="utf-8")

    success_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="5;url=/{page.username}.html">
  <title>Страница создана — Nodohub</title>
  <style>
    :root{{ --bg:#faf9f6;--text:#2b2b2b;--muted:#6b6b6b;--accent:#c7512e;--border:#e0ded8; }}
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      background:var(--bg);color:var(--text);
      font-size:17px;font-weight:300;line-height:1.6;
      -webkit-font-smoothing:antialiased;
      display:flex;align-items:center;justify-content:center;
      min-height:100vh;padding:40px 24px;
    }}
    .card{{
      background:#fff;border:1px solid var(--border);border-radius:12px;
      padding:48px 40px;max-width:480px;width:100%;
      text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.03);
    }}
    .checkmark{{
      width:64px;height:64px;border-radius:50%;
      background:#e6f7e6;display:flex;align-items:center;justify-content:center;
      margin:0 auto 24px;
    }}
    .checkmark svg{{width:32px;height:32px;stroke:#2b7a2b;stroke-width:2}}
    h1{{font-weight:400;font-size:28px;letter-spacing:-0.3px;margin-bottom:12px}}
    p{{color:var(--muted);margin-bottom:8px;font-size:16px}}
    .username{{font-weight:500;color:var(--text)}}
    .actions{{margin-top:32px;display:flex;flex-direction:column;gap:12px}}
    .btn{{
      display:inline-block;padding:14px 24px;
      border:1px solid var(--accent);color:var(--accent);
      font-size:15px;font-weight:400;background:transparent;
      text-decoration:none;transition:background .2s,color .2s;
    }}
    .btn:hover{{background:var(--accent);color:#fff}}
    .btn-secondary{{border-color:var(--border);color:var(--muted)}}
    .btn-secondary:hover{{background:#f5f5f5;color:var(--text)}}
    .note{{margin-top:24px;font-size:13px;color:var(--muted)}}
  </style>
</head>
<body>
  <div class="card">
    <div class="checkmark">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <h1>Страница создана!</h1>
    <p>Ваша визитка теперь доступна по адресу:</p>
    <p class="username">nodohub.ru/{page.username}</p>
    <div class="actions">
      <a href="/{page.username}.html" class="btn">Посмотреть</a>
      <a href="/account" class="btn btn-secondary">В кабинет</a>
    </div>
    <p class="note">Вы будете перенаправлены на свою страницу через 5 секунд</p>
  </div>
</body>
</html>"""
    return HTMLResponse(success_html)
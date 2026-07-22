import json, io
from pathlib import Path
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from PIL import Image

from database import get_db
from models import User, Page
from generator.renderer import render_page
from generator.models import PageConfig, Link
from .deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

AVATAR_DIR = Path("static/avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024
MAX_LINKS = 10                     # можно изменить на любое число (5, 10, 15)

def get_avatar_url(username: str) -> Optional[str]:
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
    img = Image.open(io.BytesIO(image_data))
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    width, height = img.size
    min_side = min(width, height)
    left = (width - min_side) // 2
    top = (height - min_side) // 2
    img = img.crop((left, top, left + min_side, top + min_side))
    img = img.resize((500, 500), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    buf.seek(0)
    return buf.read()

def build_link_fields(links: list) -> str:
    """Генерирует HTML для каскадных полей ссылок (1..MAX_LINKS)."""
    while len(links) < MAX_LINKS:
        links.append({"title": "", "url": "", "featured": False})

    # ---------- первая ссылка всегда видна ----------
    html = f"""
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

    # ---------- рекурсивная вложенность для ссылок 2..MAX_LINKS ----------
    def _group(i: int) -> str:
        """Строит группу для i-й ссылки (i от 1 до MAX_LINKS-1)."""
        # последняя ссылка – просто поле без кнопки
        if i == MAX_LINKS - 1:
            return f"""
          <div class="field" id="link-field-{i}">
            <label>Ссылка {i+1}</label>
            <input type="text" name="link_title_{i}" placeholder="Название" value="{links[i].get('title', '')}">
            <input type="url" name="link_url_{i}" placeholder="https://..." value="{links[i].get('url', '')}" style="margin-top:8px">
            <div class="featured-radio">
              <input type="radio" name="featured_link" value="{i}" id="featured_{i}" {'checked' if links[i].get('featured') else ''}>
              <label for="featured_{i}">Главная ссылка</label>
            </div>
          </div>
"""
        # остальные: поле + кнопка + вложенная группа
        has_next = bool(links[i+1].get('title') or links[i+1].get('url'))
        inner = _group(i+1)
        return f"""
          <div class="field" id="link-field-{i}">
            <label>Ссылка {i+1}</label>
            <input type="text" name="link_title_{i}" placeholder="Название" value="{links[i].get('title', '')}">
            <input type="url" name="link_url_{i}" placeholder="https://..." value="{links[i].get('url', '')}" style="margin-top:8px">
            <div class="featured-radio">
              <input type="radio" name="featured_link" value="{i}" id="featured_{i}" {'checked' if links[i].get('featured') else ''}>
              <label for="featured_{i}">Главная ссылка</label>
            </div>
            <input type="checkbox" id="toggle-link-{i+1}" class="toggle-link" {'' if has_next else ''}>
            <label for="toggle-link-{i+1}" class="add-link-btn" aria-label="Добавить ссылку {i+2}">
              <span class="sr-only">Добавить ссылку {i+2}</span>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </label>
            <div id="group-{i+1}" class="link-group">
              {inner}
            </div>
          </div>
"""

    # внешняя кнопка для 2-й ссылки
    has_1 = bool(links[1].get('title') or links[1].get('url'))
    checked_1 = "checked" if has_1 else ""
    html += f"""
    <input type="checkbox" id="toggle-link-1" class="toggle-link" {checked_1}>
    <label for="toggle-link-1" class="add-link-btn" aria-label="Добавить ссылку 2">
      <span class="sr-only">Добавить ссылку 2</span>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <line x1="12" y1="5" x2="12" y2="19"></line>
        <line x1="5" y1="12" x2="19" y2="12"></line>
      </svg>
    </label>
    <div id="group-1" class="link-group">
      {_group(1)}
    </div>
"""
    return html

def generate_toggle_css() -> str:
    """CSS-правила для каскадного добавления ссылок."""
    rules = ["""
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
    .toggle-link { display: none; }
    label.add-link-btn {
        width: 48px; height: 48px; margin: 20px auto; border: 2px dashed var(--accent);
        border-radius: 50%; color: var(--accent); cursor: pointer; transition: all .2s ease;
        background: transparent; display: flex; align-items: center; justify-content: center;
    }
    label.add-link-btn:hover { background: var(--accent); color: #fff; }
    label.add-link-btn svg { width: 28px; height: 28px; display: block; }
    .link-group { display: none; }
    """]
    for i in range(1, MAX_LINKS):
        rules.append(f"#toggle-link-{i}:checked ~ #group-{i} {{ display: block; }}")
        rules.append(f"#toggle-link-{i}:checked + label[for=\"toggle-link-{i}\"] {{ display: none; }}")
    rules.append("""
    .field input[type="checkbox"], .field input[type="radio"] { width: auto; }
    .featured-radio { display: flex; align-items: center; gap: 10px; margin-top: 12px; }
    .featured-radio input[type="radio"] {
        appearance: none; -webkit-appearance: none; width: 18px; height: 18px;
        border: 2px solid var(--border); border-radius: 50%; margin: 0; cursor: pointer;
        transition: all .2s; background: transparent;
    }
    .featured-radio input[type="radio"]:checked { border-color: var(--accent); background: var(--accent); }
    .featured-radio label { color: var(--muted); cursor: pointer; font-size: 14px; font-weight: 400; }
    """)
    return "\n".join(rules)

# ---------- эндпоинты ----------
@router.get("/dashboard/new")
async def new_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    result = await db.execute(select(Page).where(Page.user_id == user.id))
    if len(result.scalars().all()) >= 3:
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

    return templates.TemplateResponse(
        request,
        name="dashboard.html",
        context={
            "request": request,
            "user": user,
            "page": page,
            "links": links,
            "avatar_url": get_avatar_url(page.username),
            "avatar_initial": ''.join([w[0].upper() for w in user.name.split()[:2]]) if user.name else "N",
            "link_fields": build_link_fields(links),
            "toggle_css": generate_toggle_css(),
            "saved": False,
            "error": None
        }
    )

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
    for i in range(MAX_LINKS):
        title = locals().get(f"link_title_{i}", "")
        url = locals().get(f"link_url_{i}", "")
        if title and url:
            links.append({"title": title, "url": url, "featured": (featured_index == i)})
    page.links = json.dumps(links)
    await db.commit()
    await db.refresh(page)

    if old_username != page.username:
        delete_avatars(old_username)
        (Path("static") / f"{old_username}.html").unlink(missing_ok=True)

    AVATAR_DIR.mkdir(exist_ok=True)
    if avatar and avatar.filename:
        ext = avatar.filename.rsplit('.', 1)[-1].lower() if '.' in avatar.filename else ''
        err_ctx = {
            "request": request, "user": user, "page": page, "links": links,
            "avatar_url": get_avatar_url(page.username),
            "avatar_initial": name[0].upper() if name else "N",
            "link_fields": build_link_fields(links),
            "toggle_css": generate_toggle_css(),
            "saved": False
        }
        if ext not in ALLOWED_EXTENSIONS:
            err_ctx["error"] = "Допустимы только PNG, JPG или WebP."
            return templates.TemplateResponse(request, name="dashboard.html", context=err_ctx)
        contents = await avatar.read()
        if len(contents) > MAX_AVATAR_SIZE:
            err_ctx["error"] = "Файл слишком большой (макс. 2 МБ)."
            return templates.TemplateResponse(request, name="dashboard.html", context=err_ctx)
        try:
            processed = process_avatar(contents)
        except Exception:
            err_ctx["error"] = "Не удалось обработать изображение."
            return templates.TemplateResponse(request, name="dashboard.html", context=err_ctx)
        delete_avatars(page.username)
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
        err_ctx = {
            "request": request, "user": user, "page": page, "links": links,
            "avatar_url": get_avatar_url(page.username),
            "avatar_initial": initials,
            "link_fields": build_link_fields(links),
            "toggle_css": generate_toggle_css(),
            "saved": False,
            "error": "Одна из ссылок содержит некорректный URL."
        }
        return templates.TemplateResponse(request, name="dashboard.html", context=err_ctx)

    html = render_page(page_config)
    output_dir = Path("static")
    output_dir.mkdir(exist_ok=True)
    (output_dir / f"{page.username}.html").write_text(html, encoding="utf-8")

    return templates.TemplateResponse(
        request,
        name="success.html",
        context={"request": request, "page": page}
    )
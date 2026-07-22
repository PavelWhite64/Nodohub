from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

router = APIRouter()

# Сообщения об ошибках вынесены отдельно, чтобы не загромождать код
ERROR_MESSAGES = {
    "email_taken": '<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">Этот email уже зарегистрирован.</div>',
    "username_format": '<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">Формат username: @nickname (латиница, цифры, _ или -).</div>',
    "username_taken": '<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">Этот username уже занят.</div>',
    "invalid_credentials": '<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">Неверный email или пароль.</div>',
}

@router.get("/", response_class=HTMLResponse)
async def root(error: Optional[str] = None):
    index_path = Path("static/index.html")
    html_content = index_path.read_text(encoding="utf-8")
    if error and error in ERROR_MESSAGES:
        html_content = html_content.replace("<!-- ERROR_MESSAGE -->", ERROR_MESSAGES[error])
    return HTMLResponse(html_content)

@router.get("/login", response_class=HTMLResponse)
async def login_page(error: Optional[str] = None):
    login_path = Path("static/login.html")
    html_content = login_path.read_text(encoding="utf-8")
    if error and error in ERROR_MESSAGES:
        html_content = html_content.replace("<!-- ERROR_MESSAGE -->", ERROR_MESSAGES[error])
    return HTMLResponse(html_content)

@router.get("/{username}.html", response_class=HTMLResponse)
async def serve_page(username: str):
    path = Path("static") / f"{username}.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Page not found")
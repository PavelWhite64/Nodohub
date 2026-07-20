from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from typing import Optional

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def root(error: Optional[str] = None):
    index_path = Path("static/index.html")
    html_content = index_path.read_text(encoding="utf-8")
    if error == "email_taken":
        error_html = '''<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">
            Этот email уже зарегистрирован.
        </div>'''
        html_content = html_content.replace("<!-- ERROR_MESSAGE -->", error_html)
    return HTMLResponse(html_content)

@router.get("/login", response_class=HTMLResponse)
async def login_page(error: Optional[str] = None):
    login_path = Path("static/login.html")
    html_content = login_path.read_text(encoding="utf-8")
    if error == "invalid_credentials":
        error_html = '''<div style="color:#c7512e;font-size:14px;margin-top:16px;text-align:center">
            Неверный email или пароль.
        </div>'''
        html_content = html_content.replace("<!-- ERROR_MESSAGE -->", error_html)
    return HTMLResponse(html_content)

@router.get("/{username}.html", response_class=HTMLResponse)
async def serve_page(username: str):
    path = Path("static") / f"{username}.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Page not found")
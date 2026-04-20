from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.database import get_db
from app.models.user import User
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/auth")
templates = Jinja2Templates(directory="app/templates")

config = Config(environ={
    "GOOGLE_CLIENT_ID": settings.google_client_id,
    "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
})

oauth = OAuth(config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(request, "login.html", {
            "error": "Email atau password salah."
        })

    token = create_access_token(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, current_user: User = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "register.html", {"error": None})


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse(request, "register.html", {
            "error": "Email sudah terdaftar."
        })

    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse(request, "register.html", {
            "error": "Username sudah dipakai."
        })

    if len(password) < 8:
        return templates.TemplateResponse(request, "register.html", {
            "error": "Password minimal 8 karakter."
        })

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/google")
async def google_login(request: Request):
    redirect_uri = str(request.url_for("google_callback")) 
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse("/auth/login", status_code=302)

    user_info = token.get("userinfo")
    if not user_info:
        return RedirectResponse("/auth/login", status_code=302)

    email = user_info["email"]
    name = user_info.get("name", email.split("@")[0])

    user = db.query(User).filter(User.email == email).first()

    if not user:
        username = name.replace(" ", "").lower()
        base = username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base}{counter}"
            counter += 1

        user = User(
            username=username,
            email=email,
            hashed_password=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token_str = create_access_token(user.id)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("access_token", token_str, httponly=True, max_age=60 * 60 * 24 * 7)
    return response
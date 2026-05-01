from fastapi import FastAPI, Request, Depends, Query, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import asc, desc, or_
from starlette.middleware.sessions import SessionMiddleware

from app.database import get_db, engine, Base
from app.models.listing import Listing
from app.models.order import Order
from app.models.user import User
from app.models.card import Card
from app.models.pokemon import Pokemon
from app.core.dependencies import get_current_user
from app.core.cloudinary import upload_image
from app.routers import auth as auth_router
from app.routers import listings as listings_router
from app.routers import payments as payments_router
from app.routers import disputes as disputes_router
from app.config import settings

import app.models

app = FastAPI(title="GottaBuyEmAll")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router.router)
app.include_router(listings_router.router)
app.include_router(payments_router.router)
app.include_router(disputes_router.router)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def homepage(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    condition: str = Query(default=""),
    rarity: str = Query(default=""),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    q: str = Query(default=""),
):
    per_page = 20
    query = (
        db.query(Listing)
        .join(Listing.card)
        .join(Card.pokemon)
        .join(Listing.seller)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.seller),
            joinedload(Listing.grading),
        )
        .filter(Listing.status == "active")
    )

    if condition:
        query = query.filter(Listing.condition == condition)

    if rarity:
        query = query.filter(Card.rarity == rarity)

    if q:
        terms = q.strip().split()
        for term in terms:
            pattern = f"%{term}%"
            query = query.filter(
                or_(
                    Pokemon.name.ilike(pattern),
                    Card.set_name.ilike(pattern),
                    Card.card_name.ilike(pattern),
                    Card.card_variant.ilike(pattern),
                    User.username.ilike(pattern),
                )
            )

    if sort == "price_asc":
        query = query.order_by(asc(Listing.price))
    elif sort == "price_desc":
        query = query.order_by(desc(Listing.price))
    else:
        query = query.order_by(desc(Listing.created_at))

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    listings = query.offset((page - 1) * per_page).limit(per_page).all()

    hero_listings = (
        db.query(Listing)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.grading),
        )
        .filter(Listing.status == "active", Listing.image_urls.isnot(None))
        .order_by(desc(Listing.created_at))
        .limit(3)
        .all()
    )

    all_active = db.query(Listing).filter(Listing.status == "active")
    total_listings = all_active.count()
    active_sellers = db.query(User).filter(User.total_sales > 0).count()
    prices = [float(l.price) for l in all_active.limit(100).all() if l.price]

    def fmt_price(p):
        if p >= 1_000_000:
            val = f"{p/1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{val}jt"
        return f"{int(p)//1_000}rb"

    price_range = (
        f"Rp {fmt_price(min(prices))} – {fmt_price(max(prices))}"
        if prices else "–"
    )

    return templates.TemplateResponse(request, "storefront.html", {
        "listings": listings,
        "hero_listings": hero_listings,
        "stats": {
            "total_listings": total_listings,
            "active_sellers": active_sellers,
            "price_range": price_range,
        },
        "current_user": current_user,
        "messages": [],
        "filters": {"condition": condition, "rarity": rarity, "sort": sort},
        "page": page,
        "total_pages": total_pages,
        "q": q,
    })


@app.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    listings = (
        db.query(Listing)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.grading),
        )
        .filter(Listing.seller_id == current_user.id)
        .order_by(desc(Listing.created_at))
        .all()
    )

    orders_as_buyer = (
        db.query(Order)
        .options(
            joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Order.listing).joinedload(Listing.seller),
            joinedload(Order.dispute),
        )
        .filter(Order.buyer_id == current_user.id)
        .order_by(desc(Order.created_at))
        .all()
    )

    # Orders where the current user is the seller — paid or shipped (active fulfillment)
    orders_as_seller = (
        db.query(Order)
        .join(Order.listing)
        .options(
            joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Order.buyer),
        )
        .filter(
            Listing.seller_id == current_user.id,
            Order.status.in_(["paid", "shipped", "disputed"]),
        )
        .order_by(asc(Order.created_at))
        .all()
    )

    return templates.TemplateResponse(request, "profile.html", {
        "current_user": current_user,
        "profile_user": current_user,
        "listings": listings,
        "orders_as_buyer": orders_as_buyer,
        "orders_as_seller": orders_as_seller,
    })


@app.post("/profile/update")
async def update_profile(
    request: Request,
    bio: str = Form(default=""),
    favorite_pokemon: str = Form(default=""),
    whatsapp: str = Form(default=""),
    avatar: UploadFile = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    current_user.bio = bio.strip() or None
    current_user.favorite_pokemon = favorite_pokemon.strip() or None
    current_user.whatsapp = whatsapp.strip() or None

    if avatar and avatar.filename:
        file_bytes = await avatar.read()
        if file_bytes:
            url = upload_image(file_bytes, folder="gottabuyemall/avatars")
            if url:
                current_user.avatar_url = url

    db.commit()
    return RedirectResponse("/profile", status_code=302)


@app.get("/how-it-works", response_class=HTMLResponse)
async def how_it_works(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(request, "cara_kerja.html", {
        "current_user": current_user,
    })


@app.get("/faq", response_class=HTMLResponse)
async def faq(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    return RedirectResponse("/how-it-works", status_code=302)
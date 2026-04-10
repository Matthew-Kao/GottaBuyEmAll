from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, engine, Base
from app.models.listing import Listing
from app.models.user import User
from app.models.card import Card
from app.models.pokemon import Pokemon

import app.models 

app = FastAPI(title="GottaBuyEmAll")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: Session = Depends(get_db)):
    listings = (
        db.query(Listing)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.seller),
            joinedload(Listing.grading),
        )
        .filter(Listing.status == "active")
        .order_by(Listing.created_at.desc())
        .limit(20)
        .all()
    )

    total_listings = db.query(Listing).filter(Listing.status == "active").count()
    active_sellers = db.query(User).filter(User.total_sales > 0).count()

    prices = [float(l.price) for l in listings if l.price]

    def fmt_price(p):
        if p >= 1_000_000:
            val = f"{p/1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{val}jt"
        return f"{int(p)//1_000}rb"

    price_range = (
        f"Rp {fmt_price(min(prices))} – {fmt_price(max(prices))}"
        if prices else "–"
    )

    stats = {
        "total_listings": total_listings,
        "active_sellers": active_sellers,
        "price_range": price_range,
    }

    return templates.TemplateResponse(request, "storefront.html", {
        "listings": listings,
        "stats": stats,
        "current_user": None,
        "messages": [],
        "filters": {},
        "page": 1,
        "total_pages": 1,
    })
from decimal import Decimal

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import requests

from app.database import get_db
from app.models.card import Card
from app.models.pokemon import Pokemon
from app.models.listing import Listing
from app.models.user import User
from app.core.dependencies import get_current_user
from app.core.cloudinary import upload_image

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/sell", response_class=HTMLResponse)
async def sell_page(request: Request, current_user: User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)
    return templates.TemplateResponse(request, "sell.html", {
        "current_user": current_user,
    })


@router.get("/api/cards/search")
async def search_cards(q: str = "", page: int = 1):
    if not q or len(q) < 2:
        return JSONResponse([])
    try:
        resp = requests.get(
            "https://api.pokemontcg.io/v2/cards",
            params={"q": f"name:{q}*", "pageSize": 12, "page": page},
            timeout=8,
        )
        if resp.status_code != 200:
            return JSONResponse([])
        data = resp.json().get("data", [])
        results = []
        for card in data:
            results.append({
                "id": card["id"],
                "name": card["name"],
                "set": card.get("set", {}).get("name", ""),
                "number": card.get("number", ""),
                "rarity": card.get("rarity", ""),
                "image": card.get("images", {}).get("small", ""),
                "image_large": card.get("images", {}).get("large", ""),
                "types": card.get("types", []),
                "supertype": card.get("supertype", ""),
            })
        return JSONResponse(results)
    except Exception:
        return JSONResponse([])


@router.post("/sell")
async def create_listing(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    card_api_id: str = Form(default=""),
    card_name: str = Form(default=""),
    card_full_name: str = Form(default=""),
    card_set: str = Form(default=""),
    card_number: str = Form(default=""),
    card_rarity: str = Form(default="rare"),
    card_variant: str = Form(default="normal"),
    card_image_large: str = Form(default=""),
    pokemon_name: str = Form(default=""),
    condition: str = Form(default="near_mint"),
    price: str = Form(...),
    description: str = Form(default=""),
    is_negotiable: bool = Form(default=False),
    grading_service: str = Form(default=""),
    grade: str = Form(default=""),
    cert_number: str = Form(default=""),
    photo1: UploadFile = File(default=None),
    photo2: UploadFile = File(default=None),
    photo3: UploadFile = File(default=None),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    rarity_map = {
        "Common": "common",
        "Uncommon": "uncommon",
        "Rare": "rare",
        "Rare Holo": "rare",
        "Rare Ultra": "ultra_rare",
        "Rare Secret": "secret_rare",
        "Rare Rainbow": "secret_rare",
        "Rare Shiny": "ultra_rare",
        "Amazing Rare": "ultra_rare",
        "LEGEND": "ultra_rare",
    }
    rarity_clean = rarity_map.get(
        card_rarity,
        card_rarity if card_rarity in ["common", "uncommon", "rare", "ultra_rare", "secret_rare"] else "rare"
    )

    pokemon = db.query(Pokemon).filter(Pokemon.name.ilike(pokemon_name)).first()

    if not pokemon:
        pokemon = Pokemon(
            pokedex_number=-(hash(pokemon_name) % 1000000),
            name=pokemon_name.title() if pokemon_name else "Unknown",
            primary_type="Unknown",
            fun_fact="",
        )
        db.add(pokemon)
        db.flush()

    card = db.query(Card).filter(Card.set_code == card_api_id).first()

    if not card:
        card = Card(
            pokemon_id=pokemon.id,
            card_name=card_full_name or card_name or None,
            set_name=card_set or "Unknown Set",
            set_code=card_api_id or f"manual-{pokemon.id}",
            card_number=card_number,
            rarity=rarity_clean,
            card_variant=card_variant,
        )
        db.add(card)
        db.flush()
    else:
        if not card.card_name and (card_full_name or card_name):
            card.card_name = card_full_name or card_name

    image_urls = []
    for photo in [photo1, photo2, photo3]:
        if photo and photo.filename:
            file_bytes = await photo.read()
            if file_bytes:
                url = upload_image(file_bytes, folder="gottabuyemall/listings")
                if url:
                    image_urls.append(url)

    if not image_urls and card_image_large:
        image_urls.append(card_image_large)

    from app.models.card import Grading
    grading_id = None
    if grading_service and grade and cert_number:
        existing = db.query(Grading).filter(Grading.cert_number == cert_number).first()
        if not existing:
            grading = Grading(
                grading_service=grading_service,
                grade=Decimal(grade),
                cert_number=cert_number,
            )
            db.add(grading)
            db.flush()
            grading_id = grading.id

    listing = Listing(
        seller_id=current_user.id,
        card_id=card.id,
        grading_id=grading_id,
        price=Decimal(price.replace(",", "").replace(".", "")),
        condition=condition if not grading_id else None,
        description=description.strip() or None,
        image_urls=",".join(image_urls) if image_urls else None,
        is_negotiable=is_negotiable,
        status="active",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return RedirectResponse(f"/listings/{listing.id}", status_code=302)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
async def listing_detail(
    listing_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    listing = (
        db.query(Listing)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.seller),
            joinedload(Listing.grading),
        )
        .filter(Listing.id == listing_id)
        .first()
    )
    if not listing:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(request, "listing_detail.html", {
        "current_user": current_user,
        "listing": listing,
        "images": listing.image_urls.split(",") if listing.image_urls else [],
    })


@router.post("/listings/{listing_id}/delete")
async def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    listing = db.query(Listing).filter(Listing.id == listing_id).first()

    if not listing or listing.seller_id != current_user.id:
        return RedirectResponse("/", status_code=302)

    listing.status = "removed"
    db.commit()

    return RedirectResponse("/profile", status_code=302)
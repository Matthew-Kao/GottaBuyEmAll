import hashlib
import hmac
import json
from datetime import datetime
from decimal import Decimal

import requests
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.card import Card
from app.models.listing import Listing
from app.models.order import Order
from app.models.user import User

router = APIRouter(prefix="/payments")
templates = Jinja2Templates(directory="app/templates")

XENDIT_BASE = "https://api.xendit.co"


def xendit_headers():
    import base64
    token = base64.b64encode(f"{settings.xendit_secret_key}:".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


@router.post("/checkout/{listing_id}")
async def checkout(
    listing_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    listing = (
        db.query(Listing)
        .options(
            joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Listing.seller),
        )
        .filter(Listing.id == listing_id, Listing.status == "active")
        .first()
    )

    if not listing:
        return RedirectResponse("/", status_code=302)

    if listing.seller_id == current_user.id:
        return RedirectResponse(f"/listings/{listing_id}", status_code=302)

    # Create order in DB
    order = Order(
        buyer_id=current_user.id,
        listing_id=listing.id,
        total_price=listing.price,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Create Xendit invoice
    card_name = listing.card.card_name or listing.card.pokemon.name
    invoice_data = {
        "external_id": f"order-{order.id}",
        "amount": float(listing.price),
        "description": f"GottaBuyEmAll — {card_name} ({listing.card.set_name})",
        "payer_email": current_user.email,
        "customer": {
            "given_names": current_user.username,
            "email": current_user.email,
        },
        "success_redirect_url": str(request.base_url) + f"payments/success/{order.id}",
        "failure_redirect_url": str(request.base_url) + f"payments/failed/{order.id}",
        "currency": "IDR",
        "items": [
            {
                "name": card_name,
                "quantity": 1,
                "price": float(listing.price),
                "category": "Pokemon Card",
            }
        ],
    }

    try:
        resp = requests.post(
            f"{XENDIT_BASE}/v2/invoices",
            headers=xendit_headers(),
            json=invoice_data,
            timeout=10,
        )
        resp.raise_for_status()
        invoice = resp.json()

        order.xendit_invoice_id = invoice["id"]
        order.xendit_invoice_url = invoice["invoice_url"]
        order.payment_ref = invoice["external_id"]
        db.commit()

        return RedirectResponse(invoice["invoice_url"], status_code=302)

    except Exception as e:
        db.delete(order)
        db.commit()
        return RedirectResponse(f"/listings/{listing_id}", status_code=302)


@router.get("/success/{order_id}", response_class=HTMLResponse)
async def payment_success(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Order.listing).joinedload(Listing.seller),
        )
        .filter(Order.id == order_id)
        .first()
    )

    if not order:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(request, "payment_success.html", {
        "current_user": current_user,
        "order": order,
    })


@router.get("/failed/{order_id}", response_class=HTMLResponse)
async def payment_failed(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order and order.status == "pending":
        db.delete(order)
        db.commit()

    return RedirectResponse("/", status_code=302)


@router.post("/webhook/xendit")
async def xendit_webhook(request: Request, db: Session = Depends(get_db)):
    # Verify webhook token
    token = request.headers.get("x-callback-token", "")
    if token != settings.xendit_webhook_token:
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    body = await request.json()
    event = body.get("status")
    external_id = body.get("external_id", "")

    if not external_id.startswith("order-"):
        return JSONResponse({"status": "ignored"})

    order_id = int(external_id.replace("order-", ""))
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        return JSONResponse({"status": "order not found"})

    if event == "PAID" and order.status == "pending":
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        order.listing.status = "sold"
        db.commit()

    return JSONResponse({"status": "ok"})


@router.post("/confirm/{order_id}")
async def confirm_receipt(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.buyer_id == current_user.id,
        Order.status == "shipped",
    ).first()

    if not order:
        return RedirectResponse("/profile", status_code=302)

    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    db.commit()

    return RedirectResponse("/profile", status_code=302)
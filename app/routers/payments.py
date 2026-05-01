import hashlib
import hmac
import json
import time
from datetime import datetime
from decimal import Decimal

import requests
from fastapi import APIRouter, Request, Depends, HTTPException, Form
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

TRIPAY_BASE = "https://tripay.co.id/api-sandbox"


def tripay_headers():
    return {
        "Authorization": f"Bearer {settings.tripay_api_key}",
        "Content-Type": "application/json",
    }


def make_signature(merchant_ref: str, amount: int) -> str:
    key = settings.tripay_private_key
    msg = f"{settings.tripay_merchant_code}{merchant_ref}{amount}"
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


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

    order = Order(
        buyer_id=current_user.id,
        listing_id=listing.id,
        total_price=listing.price,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    card_name = listing.card.card_name or listing.card.pokemon.name
    merchant_ref = f"order-{order.id}"
    amount = int(listing.price)
    expired_time = int(time.time()) + (24 * 60 * 60)

    payload = {
        "method": "QRIS",
        "merchant_ref": merchant_ref,
        "amount": amount,
        "customer_name": current_user.username,
        "customer_email": current_user.email,
        "customer_phone": "08000000000",
        "order_items": [
            {
                "sku": f"CARD-{listing.card_id}",
                "name": card_name,
                "price": amount,
                "quantity": 1,
            }
        ],
        "return_url": str(request.base_url) + f"payments/success/{order.id}",
        "expired_time": expired_time,
        "signature": make_signature(merchant_ref, amount),
    }

    try:
        resp = requests.post(
            f"{TRIPAY_BASE}/transaction/create",
            headers=tripay_headers(),
            json=payload,
            timeout=10,
        )
        data = resp.json()

        if not data.get("success"):
            print(f"TRIPAY FAILED: {data}")
            db.delete(order)
            db.commit()
            return RedirectResponse(f"/listings/{listing_id}", status_code=302)

        result = data["data"]
        order.tripay_reference = result["reference"]
        order.tripay_payment_url = result["checkout_url"]
        order.payment_ref = merchant_ref
        db.commit()

        return RedirectResponse(result["checkout_url"], status_code=302)

    except Exception as e:
        print(f"TRIPAY ERROR: {e}")
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


@router.post("/webhook/tripay")
async def tripay_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()

    signature = request.headers.get("X-Callback-Signature", "")
    expected = hmac.new(
        settings.tripay_private_key.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    body = json.loads(raw_body)
    merchant_ref = body.get("merchant_ref", "")
    event = body.get("status")

    if not merchant_ref.startswith("order-"):
        return JSONResponse({"success": True, "message": "OK"})

    order_id = int(merchant_ref.replace("order-", ""))
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        return JSONResponse({"success": True, "message": "OK"})

    if event == "PAID" and order.status == "pending":
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        order.listing.status = "sold"
        db.commit()

    return JSONResponse({"success": True, "message": "OK"})


@router.post("/ship/{order_id}")
async def ship_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    shipping_courier: str = Form(...),
    tracking_number: str = Form(...),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    order = (
        db.query(Order)
        .options(joinedload(Order.listing))
        .filter(Order.id == order_id, Order.status == "paid")
        .first()
    )

    if not order or order.listing.seller_id != current_user.id:
        return RedirectResponse("/profile", status_code=302)

    order.status = "shipped"
    order.shipping_courier = shipping_courier.strip()
    order.tracking_number = tracking_number.strip()
    order.shipped_at = datetime.utcnow()
    db.commit()

    return RedirectResponse("/profile", status_code=302)


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

    return RedirectResponse(f"/payments/rate/{order_id}", status_code=302)


@router.get("/rate/{order_id}", response_class=HTMLResponse)
async def rate_seller_page(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    order = (
        db.query(Order)
        .options(
            joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Order.listing).joinedload(Listing.seller),
        )
        .filter(
            Order.id == order_id,
            Order.buyer_id == current_user.id,
            Order.status == "confirmed",
        )
        .first()
    )

    if not order:
        return RedirectResponse("/profile", status_code=302)

    return templates.TemplateResponse(request, "rate_seller.html", {
        "current_user": current_user,
        "order": order,
    })


@router.post("/rate/{order_id}")
async def submit_rating(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    rating: int = Form(...),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    order = (
        db.query(Order)
        .options(joinedload(Order.listing).joinedload(Listing.seller))
        .filter(
            Order.id == order_id,
            Order.buyer_id == current_user.id,
            Order.status == "confirmed",
        )
        .first()
    )

    if not order:
        return RedirectResponse("/profile", status_code=302)

    rating = max(1, min(5, rating))

    seller = order.listing.seller
    total = seller.seller_rating * seller.total_sales
    seller.total_sales += 1
    seller.seller_rating = round((total + rating) / seller.total_sales, 1)

    order.status = "done"
    order.completed_at = datetime.utcnow()

    db.commit()

    return RedirectResponse("/profile", status_code=302)
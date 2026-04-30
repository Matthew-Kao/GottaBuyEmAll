from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.card import Card
from app.models.listing import Listing
from app.models.order import Order
from app.models.order import Dispute
from app.models.user import User

router = APIRouter(prefix="/disputes")
templates = Jinja2Templates(directory="app/templates")


@router.get("/new/{order_id}", response_class=HTMLResponse)
async def dispute_form(
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
        )
        .first()
    )

    if not order:
        return RedirectResponse("/profile", status_code=302)

    if order.status not in ["paid", "shipped"]:
        return RedirectResponse("/profile", status_code=302)

    if order.dispute:
        return RedirectResponse("/profile", status_code=302)

    return templates.TemplateResponse(request, "dispute_form.html", {
        "current_user": current_user,
        "order": order,
    })


@router.post("/new/{order_id}")
async def create_dispute(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    reason: str = Form(...),
):
    if not current_user:
        return RedirectResponse("/auth/login", status_code=302)

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.buyer_id == current_user.id,
    ).first()

    if not order:
        return RedirectResponse("/profile", status_code=302)

    if order.status not in ["paid", "shipped"]:
        return RedirectResponse("/profile", status_code=302)

    if order.dispute:
        return RedirectResponse("/profile", status_code=302)

    dispute = Dispute(
        order_id=order.id,
        reason=reason.strip(),
        status="open",
    )
    db.add(dispute)
    order.status = "disputed"
    db.commit()

    return RedirectResponse("/profile", status_code=302)
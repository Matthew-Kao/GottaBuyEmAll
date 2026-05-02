from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.card import Card
from app.models.listing import Listing
from app.models.order import Order, Dispute
from app.models.user import User

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user or not current_user.is_admin:
        return None
    return current_user


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse("/", status_code=302)

    disputes = (
        db.query(Dispute)
        .options(
            joinedload(Dispute.order).joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Dispute.order).joinedload(Order.listing).joinedload(Listing.seller),
            joinedload(Dispute.order).joinedload(Order.buyer),
        )
        .filter(Dispute.status == "open")
        .order_by(desc(Dispute.created_at))
        .all()
    )

    all_orders = (
        db.query(Order)
        .options(
            joinedload(Order.listing).joinedload(Listing.card).joinedload(Card.pokemon),
            joinedload(Order.listing).joinedload(Listing.seller),
            joinedload(Order.buyer),
            joinedload(Order.dispute),
        )
        .order_by(desc(Order.created_at))
        .limit(50)
        .all()
    )

    all_users = (
        db.query(User)
        .order_by(desc(User.created_at))
        .all()
    )

    return templates.TemplateResponse(request, "admin/dashboard.html", {
        "current_user": current_user,
        "disputes": disputes,
        "all_orders": all_orders,
        "all_users": all_users,
    })


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    resolution: str = Form(...),
    resolution_notes: str = Form(default=""),
):
    if not current_user or not current_user.is_admin:
        return RedirectResponse("/", status_code=302)

    dispute = (
        db.query(Dispute)
        .options(joinedload(Dispute.order).joinedload(Order.listing))
        .filter(Dispute.id == dispute_id)
        .first()
    )

    if not dispute:
        return RedirectResponse("/admin", status_code=302)

    dispute.status = "resolved"
    dispute.resolution = resolution
    dispute.resolution_notes = resolution_notes.strip() or None
    dispute.resolved_at = datetime.utcnow()

    if resolution == "refund_buyer":
        dispute.order.status = "refunded"
    elif resolution == "release_to_seller":
        dispute.order.status = "done"
        dispute.order.completed_at = datetime.utcnow()
        # Update seller total_sales
        seller = dispute.order.listing.seller
        seller.total_sales += 1

    db.commit()

    return RedirectResponse("/admin", status_code=302)
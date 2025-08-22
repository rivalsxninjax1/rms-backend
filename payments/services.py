import stripe
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

stripe.api_key = settings.STRIPE_SECRET_KEY


def _order_to_line_items(order):
    currency = getattr(settings, "STRIPE_CURRENCY", "usd")
    line_items = []
    for it in order.items.select_related("menu_item"):
        name = it.menu_item.name if it.menu_item else "Item"
        unit_amount = int(Decimal(it.unit_price) * 100)
        qty = int(it.quantity or 1)
        line_items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": unit_amount,
                "product_data": {"name": name},
            },
            "quantity": qty,
        })
    return line_items


def create_checkout_session(order):
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=_order_to_line_items(order),
        mode="payment",
        success_url=f"{settings.DOMAIN}/payments/success/?order_id={order.id}",
        cancel_url=f"{settings.DOMAIN}/payments/cancel/",
        metadata={"order_id": order.id},
    )
    return session


def generate_order_invoice_pdf(order):
    items = list(order.items.select_related("menu_item").all())

    # Build PDF
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(20 * mm, y, f"Invoice – Order #{order.id}")
    y -= 10 * mm

    # Date
    p.setFont("Helvetica", 10)
    p.drawString(20 * mm, y, f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 12 * mm

    # Table header
    p.setFont("Helvetica-Bold", 11)
    p.drawString(20 * mm, y, "Item")
    p.drawString(110 * mm, y, "Qty")
    p.drawString(130 * mm, y, "Price")
    p.drawString(160 * mm, y, "Line Total")
    y -= 7 * mm
    p.line(20 * mm, y, 190 * mm, y)
    y -= 5 * mm
    p.setFont("Helvetica", 10)

    total = Decimal("0")
    for it in items:
        name = it.menu_item.name if it.menu_item else "Item"
        qty = int(it.quantity or 1)
        price = Decimal(it.unit_price or 0)
        line_total = price * qty
        total += line_total

        p.drawString(20 * mm, y, name[:45])
        p.drawRightString(120 * mm, y, str(qty))
        p.drawRightString(150 * mm, y, f"{price:.2f}")
        p.drawRightString(190 * mm, y, f"{line_total:.2f}")
        y -= 6 * mm

    y -= 6 * mm
    p.line(20 * mm, y, 190 * mm, y)
    y -= 8 * mm
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(150 * mm, y, "Total")
    p.drawRightString(190 * mm, y, f"{total:.2f}")
    p.showPage()
    p.save()

    rel_dir = "orders"
    rel_path = f"{rel_dir}/order-{order.id}.pdf"
    out_dir = Path(settings.MEDIA_ROOT) / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (Path(settings.MEDIA_ROOT) / rel_path).write_bytes(buf.getvalue())

    order.invoice_pdf.name = rel_path
    order.save(update_fields=["invoice_pdf"])
    return rel_path

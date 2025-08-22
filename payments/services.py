# payments/services.py
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _safe_name(order):
    return order.customer_name or (getattr(order, "user", None) and order.user.get_full_name()) or ""


def _safe_email(order):
    return order.customer_email or (getattr(order, "user", None) and order.user.email) or ""


def generate_order_invoice_pdf(order) -> str:
    """
    Create a PDF invoice for this order, save to MEDIA_ROOT/orders/, and
    return the relative path (e.g. 'orders/order-123.pdf').
    """
    # Compute totals + estimated wait (longest prep_minutes)
    total = Decimal("0.00")
    longest_prep = 0
    items = list(order.items.select_related("product"))

    for it in items:
        total += it.unit_price * it.quantity
        if it.product and it.product.prep_minutes:
            longest_prep = max(longest_prep, it.product.prep_minutes)

    # Render PDF to memory
    buf = BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 20 * mm

    # Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(20 * mm, y, f"Invoice – Order #{order.id}")
    y -= 10 * mm

    # Customer details
    p.setFont("Helvetica", 10)
    p.drawString(20 * mm, y, f"Customer: {_safe_name(order)}")
    y -= 6 * mm
    p.drawString(20 * mm, y, f"Email: {_safe_email(order)}")
    y -= 6 * mm
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

    # Items
    for it in items:
        name = it.product.name if it.product else "Item"
        line_total = it.unit_price * it.quantity
        p.drawString(20 * mm, y, name[:42])
        p.drawRightString(120 * mm, y, str(it.quantity))
        p.drawRightString(150 * mm, y, f"{it.unit_price:.2f}")
        p.drawRightString(190 * mm, y, f"{line_total:.2f}")
        y -= 6 * mm
        if y < 30 * mm:
            p.showPage()
            y = height - 20 * mm
            p.setFont("Helvetica", 10)

    # Summary
    y -= 5 * mm
    p.setFont("Helvetica-Bold", 11)
    p.drawRightString(190 * mm, y, f"Total: {total:.2f}")
    y -= 10 * mm
    p.setFont("Helvetica", 10)
    p.drawString(20 * mm, y, f"Estimated waiting time: {longest_prep} minutes")
    p.showPage()
    p.save()

    # Save file
    rel_dir = "orders"
    rel_path = f"{rel_dir}/order-{order.id}.pdf"
    out_dir = Path(settings.MEDIA_ROOT) / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (Path(settings.MEDIA_ROOT) / rel_path).write_bytes(buf.getvalue())

    # Persist on model
    order.invoice_pdf.name = rel_path
    order.save(update_fields=["invoice_pdf"])
    return rel_path

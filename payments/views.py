from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse

import stripe

from orders.models import Order
from payments.services import generate_order_invoice_pdf

stripe.api_key = settings.STRIPE_SECRET_KEY


def _order_to_line_items(order):
    currency = getattr(settings, "STRIPE_CURRENCY", "usd")
    line_items = []
    for it in order.items.select_related("product"):
        name = it.product.name if it.product else "Item"
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


def create_checkout_session(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if order.is_paid:
        return redirect(reverse("payments:checkout_success") + f"?order_id={order.id}")

    success_url = request.build_absolute_uri(
        reverse("payments:checkout_success")
    ) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri(
        reverse("payments:checkout_cancel")
    )

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],  # Visa/MasterCard etc.
        # Encourage 3-D Secure when Stripe deems necessary
        payment_method_options={
            "card": {"request_three_d_secure": "automatic"}
        },
        # Stripe will choose the right methods; this helps future-proof
        automatic_payment_methods={"enabled": True},

        line_items=_order_to_line_items(order),
        success_url=success_url,
        cancel_url=cancel_url,

        client_reference_id=str(order.id),
        metadata={"order_id": str(order.id), "user_id": str(getattr(order.user, "id", ""))},
    )

    order.stripe_session_id = session.id
    order.save(update_fields=["stripe_session_id"])
    return redirect(session.url, permanent=False)


def checkout_success(request):
    session_id = request.GET.get("session_id", "")
    order = None
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            order_id = session.get("client_reference_id") or (session.get("metadata", {}) or {}).get("order_id")
            order = Order.objects.filter(pk=order_id).first()
            if order and session.get("payment_status") == "paid" and not order.is_paid:
                order.is_paid = True
                order.stripe_payment_intent_id = session.get("payment_intent", "") or ""
                order.save(update_fields=["is_paid", "stripe_payment_intent_id"])
        except Exception:
            pass

    if not order:
        oid = request.GET.get("order_id")
        if oid:
            order = Order.objects.filter(pk=oid).first()

    if order and order.is_paid and not order.invoice_pdf:
        try:
            generate_order_invoice_pdf(order)
        except Exception:
            pass

    return render(request, "payments/checkout_success.html", {"order": order})


def checkout_cancel(request):
    return render(request, "payments/checkout_cancel.html")


@csrf_exempt
def stripe_webhook(request):
    sig = request.headers.get("Stripe-Signature", "")
    payload = request.body
    try:
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=sig, secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("client_reference_id") or (session.get("metadata", {}) or {}).get("order_id")
        if order_id:
            order = Order.objects.filter(pk=order_id).first()
            if order:
                if not order.is_paid:
                    order.is_paid = True
                order.stripe_session_id = session.get("id", "") or order.stripe_session_id
                order.stripe_payment_intent_id = session.get("payment_intent", "") or order.stripe_payment_intent_id
                order.save(update_fields=["is_paid", "stripe_session_id", "stripe_payment_intent_id"])
                try:
                    generate_order_invoice_pdf(order)
                except Exception:
                    pass

    return HttpResponse(status=200)

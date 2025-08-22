import json
from typing import List, Dict, Any, Optional

from django.utils.encoding import force_str
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication

from menu.models import MenuItem
from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderReadSerializer
from payments.services import create_checkout_session, generate_order_invoice_pdf
from core.authentication import LenientJWTAuthentication


# ------------------------ Normalization helpers ------------------------

def _extract_int(v, default=0) -> int:
    try:
        if isinstance(v, bool):   # avoid True -> 1
            return default
        return int(v)
    except Exception:
        return default


def _normalize_one_item(raw: Any) -> Optional[Dict[str, int]]:
    """
    Return {"menu_item": <id>, "quantity": <int>} or None.

    Accepts dicts like:
      {menu_item|menu|menu_id|menuId|product|product_id|id: <int>, quantity|qty|q: <int>}
    Accepts plain ints (treat as ID, qty=1).
    """
    # Plain integer => treat as ID
    if isinstance(raw, int):
        mid = _extract_int(raw)
        if mid > 0:
            return {"menu_item": mid, "quantity": 1}
        return None

    # String that is an int
    if isinstance(raw, str) and raw.isdigit():
        mid = int(raw)
        return {"menu_item": mid, "quantity": 1} if mid > 0 else None

    # Dicts with various shapes
    if isinstance(raw, dict):
        mid = 0
        for k in ("menu_item", "menuId", "menu", "id", "product", "product_id", "menu_id"):
            if k in raw:
                mid = _extract_int(raw.get(k))
                if mid > 0:
                    break
        if mid <= 0:
            return None

        qty = 1
        for qk in ("quantity", "qty", "q"):
            if qk in raw:
                qty = max(1, _extract_int(raw.get(qk), 1))
                break

        return {"menu_item": mid, "quantity": qty}

    return None


def _json_load_maybe(value: Any) -> Any:
    """If value is bytes/str JSON, decode it; otherwise return as-is."""
    if isinstance(value, (bytes, str)):
        try:
            return json.loads(force_str(value))
        except Exception:
            return value
    return value


def _normalize_items(raw_items: Any) -> List[Dict[str, int]]:
    """
    Returns a clean list of {"menu_item": int, "quantity": int}.
    Accepts:
      - list[dict|int|str]
      - dict with "items": [...]
      - single dict item
      - stringified JSON of any of the above
    """
    if raw_items is None:
        return []

    raw_items = _json_load_maybe(raw_items)

    if isinstance(raw_items, dict) and "items" in raw_items:
        raw_items = raw_items.get("items")

    out: List[Dict[str, int]] = []
    if isinstance(raw_items, list):
        for it in raw_items:
            ni = _normalize_one_item(_json_load_maybe(it))
            if ni:
                out.append(ni)
    elif isinstance(raw_items, dict) or isinstance(raw_items, (int, str)):
        ni = _normalize_one_item(raw_items)
        if ni:
            out.append(ni)

    # Deduplicate same menu_item by summing qty
    merged: Dict[int, int] = {}
    for it in out:
        mid, q = it["menu_item"], it["quantity"]
        merged[mid] = merged.get(mid, 0) + q

    return [{"menu_item": mid, "quantity": q} for mid, q in merged.items()]


def _force_session(request):
    if not request.session.session_key:
        request.session.save()


def _get_items_from_anywhere(request) -> (List[Dict[str, int]], Dict[str, Any]):
    """
    Try hard to find cart items in multiple locations. Also return a small debug dict.
    Priority:
      1) request.data: items / cart / cart_json
      2) request.data as list/dict
      3) request.POST string fields (items/cart/cart_json)
      4) header: X-Cart (JSON string)
      5) raw body (if JSON list/dict)
      6) session["cart"]
      7) cookie "cart" (JSON string)
    """
    debug = {"sources_checked": [], "raw_echo": {}}

    # 1) request.data explicit keys
    data = request.data
    if isinstance(data, dict):
        for key in ("items", "cart", "cart_json"):
            if key in data:
                debug["sources_checked"].append(f"data[{key}]")
                debug["raw_echo"][key] = data.get(key)
                norm = _normalize_items(data.get(key))
                if norm:
                    return norm, debug

    # 2) request.data direct
    if isinstance(data, (list, dict)):
        debug["sources_checked"].append("data")
        debug["raw_echo"]["data"] = data
        norm = _normalize_items(data)
        if norm:
            return norm, debug

    # 3) POST string fields
    if hasattr(request, "POST"):
        for key in ("items", "cart", "cart_json"):
            if key in request.POST:
                raw = request.POST.get(key)
                debug["sources_checked"].append(f"POST[{key}]")
                debug["raw_echo"][f"POST[{key}]"] = raw
                norm = _normalize_items(raw)
                if norm:
                    return norm, debug

    # 4) header X-Cart
    hdr = request.META.get("HTTP_X_CART")
    if hdr:
        debug["sources_checked"].append("HTTP_X_CART")
        debug["raw_echo"]["HTTP_X_CART"] = hdr
        norm = _normalize_items(hdr)
        if norm:
            return norm, debug

    # 5) raw body (JSON)
    if request.body:
        body = force_str(request.body)
        debug["sources_checked"].append("raw_body")
        if body:
            debug["raw_echo"]["raw_body"] = (body[:1000] + "...") if len(body) > 1000 else body
            norm = _normalize_items(body)
            if norm:
                return norm, debug

    # 6) session
    _force_session(request)
    sess = request.session.get("cart", [])
    debug["sources_checked"].append("session[cart]")
    debug["raw_echo"]["session_cart"] = sess
    norm = _normalize_items(sess)
    if norm:
        return norm, debug

    # 7) cookie
    cookie_cart = request.COOKIES.get("cart")
    if cookie_cart:
        debug["sources_checked"].append("cookie[cart]")
        debug["raw_echo"]["cookie_cart"] = (cookie_cart[:1000] + "...") if len(cookie_cart) > 1000 else cookie_cart
        norm = _normalize_items(cookie_cart)
        if norm:
            return norm, debug

    return [], debug


# ------------------------ Cart (Session) ------------------------

@method_decorator(csrf_exempt, name="dispatch")  # allow JS sync without CSRF hassles
class SessionCartViewSet(viewsets.ViewSet):
    """
    Session cart API:
      GET    /api/cart/               -> { "items": [{ "menu_item": <id>, "quantity": <int> }, ...] }
      POST   /api/cart/sync/          -> body { "items": [...] }  (replaces whole cart; many shapes allowed)
      POST   /api/cart/reset_session/ -> clears session + cart
      GET    /api/cart/debug/         -> diagnostic; shows what server sees (remove in prod)
    """
    authentication_classes = (LenientJWTAuthentication, SessionAuthentication)
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        _force_session(request)
        items = request.session.get("cart", [])
        safe = _normalize_items(items)
        request.session["cart"] = safe
        request.session.modified = True
        return Response({"items": safe})

    @action(detail=False, methods=["post"], url_path="sync")
    def sync(self, request):
        _force_session(request)
        # Accept from multiple shapes:
        incoming = request.data if request.data else {}
        normalized = []
        # prefer explicit keys first
        for key in ("items", "cart", "cart_json"):
            if key in incoming:
                normalized = _normalize_items(incoming.get(key))
                break
        if not normalized:
            normalized = _normalize_items(incoming)
        request.session["cart"] = normalized
        request.session.modified = True
        return Response({"items": normalized})

    @action(detail=False, methods=["post"], url_path="reset_session")
    def reset_session(self, request):
        try:
            request.session.flush()
        except Exception:
            pass
        return Response({"ok": True})

    @action(detail=False, methods=["get"], url_path="debug")
    def debug_cart(self, request):
        """Temporary diagnostic endpoint."""
        _force_session(request)
        return Response({
            "session_key": request.session.session_key,
            "session_cart": request.session.get("cart", []),
        })


# ------------------------ Orders ------------------------

class OrderViewSet(viewsets.ModelViewSet):
    """
    POST /api/orders/  -> creates an Order from cart (robust cart detection)
    """
    queryset = Order.objects.all().select_related("created_by").prefetch_related("items__menu_item")
    authentication_classes = (LenientJWTAuthentication, SessionAuthentication)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return OrderReadSerializer
        return OrderCreateSerializer

    def get_permissions(self):
        if self.action in ["create", "quick_checkout"]:
            return [permissions.AllowAny()]
        if self.action in ["list", "retrieve", "invoice"]:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.action in ["list", "retrieve"] and user.is_authenticated and not user.is_staff:
            qs = qs.filter(created_by=user)
        return qs

    def _resolve_existing_menu_items(self, items: List[Dict[str, int]]) -> List[Dict[str, int]]:
        """
        Convert normalized items (with ids) into only those that exist in DB.
        If some IDs are missing in DB, skip them.
        """
        ids = [it["menu_item"] for it in items]
        existing = set(MenuItem.objects.filter(id__in=ids).values_list("id", flat=True))
        return [it for it in items if it["menu_item"] in existing]

    def create(self, request, *args, **kwargs):
        normalized, debug = _get_items_from_anywhere(request)

        # If we saw something but couldn't normalize, return a helpful 422 with echo
        saw_something = any(debug["raw_echo"].values())
        if not normalized:
            if saw_something:
                return Response(
                    {"detail": "Invalid item format received.",
                     "debug": debug},
                    status=422,
                )
            # truly nothing found
            return Response(
                {"detail": "Cart is empty.",
                 "debug": debug},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Drop IDs not present in DB (prevents FK errors)
        normalized = self._resolve_existing_menu_items(normalized)
        if not normalized:
            return Response(
                {"detail": "Cart items refer to unknown menu IDs.",
                 "debug": debug},
                status=422,
            )

        payload = request.data.copy() if isinstance(request.data, dict) else {}
        payload["items"] = normalized

        serializer = self.get_serializer(data=payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        session = create_checkout_session(order)
        return Response(
            {"order_id": order.id, "checkout_url": session.url},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="quick-checkout")
    def quick_checkout(self, request):
        """
        Alternate entrypoint that prefers the 'X-Cart' header or JSON body list.
        Useful if your frontend wants a dedicated URL.
        """
        normalized, debug = _get_items_from_anywhere(request)
        if not normalized:
            return Response({"detail": "Cart is empty.", "debug": debug}, status=400)

        normalized = self._resolve_existing_menu_items(normalized)
        if not normalized:
            return Response({"detail": "Unknown menu IDs.", "debug": debug}, status=422)

        payload = request.data.copy() if isinstance(request.data, dict) else {}
        payload["items"] = normalized

        serializer = self.get_serializer(data=payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        session = create_checkout_session(order)
        return Response({"order_id": order.id, "checkout_url": session.url}, status=201)

    @action(detail=True, methods=["get"], url_path="invoice")
    def invoice(self, request, pk=None):
        order = self.get_object()
        if order.is_paid and not order.invoice_pdf:
            try:
                generate_order_invoice_pdf(order)
            except Exception:
                pass
        data = {
            "id": order.id,
            "is_paid": order.is_paid,
            "invoice": order.invoice_pdf.url if order.invoice_pdf else None,
        }
        return Response(data)

// === Auth helpers (JWT + refresh) ===
const auth = {
  access() {
    return localStorage.getItem("jwt_access") || "";
  },
  refresh() {
    return localStorage.getItem("jwt_refresh") || "";
  },
  setTokens(a, r) {
    if (a) localStorage.setItem("jwt_access", a);
    if (r) localStorage.setItem("jwt_refresh", r);
  },
  clear() {
    localStorage.removeItem("jwt_access");
    localStorage.removeItem("jwt_refresh");
  },
};

// === Org/Loc defaults ===
function getOrg() {
  return (
    localStorage.getItem("org_uuid") || "00000000-0000-0000-0000-000000000001"
  );
}
function getLoc() {
  return (
    localStorage.getItem("loc_uuid") || "00000000-0000-0000-0000-000000000002"
  );
}
function qsOrgLoc() {
  return `?organization=${encodeURIComponent(
    getOrg()
  )}&location=${encodeURIComponent(getLoc())}`;
}

// === Cart ===
function cartGet() {
  return JSON.parse(localStorage.getItem("cart") || "[]");
}
function cartSet(items) {
  localStorage.setItem("cart", JSON.stringify(items));
  cartCount();
}
function cartCount() {
  const c = cartGet().reduce((s, i) => s + Number(i.qty || 0), 0);
  const el = document.getElementById("cart-count");
  if (el) el.textContent = c;
}
function money(n) {
  return Number(n || 0).toFixed(2);
}

// === API with auto-refresh ===
async function _fetch(path, opts) {
  const res = await fetch(path, opts);
  let data = {};
  try {
    data = await res.json();
  } catch {}
  return { res, data };
}
async function api(path, opts = {}, retry = true) {
  opts.headers = Object.assign(
    { "Content-Type": "application/json" },
    opts.headers || {}
  );
  const t = auth.access();
  if (t) opts.headers["Authorization"] = "Bearer " + t;
  let { res, data } = await _fetch(path, opts);
  if (res.status !== 401) {
    if (!res.ok) throw { status: res.status, data };
    return data;
  }
  if (!retry || !auth.refresh()) throw { status: res.status, data };
  const rr = await fetch("/api/auth/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: auth.refresh() }),
  });
  const jd = await rr.json().catch(() => ({}));
  if (rr.ok && jd.access) {
    auth.setTokens(jd.access, jd.refresh);
    opts.headers["Authorization"] = "Bearer " + jd.access;
    const second = await _fetch(path, opts);
    if (!second.res.ok) throw { status: second.res.status, data: second.data };
    return second.data;
  } else {
    auth.clear();
    throw { status: res.status, data };
  }
}

// === Modal ===
const modalEl = () => document.getElementById("auth-modal");
function showStep(name) {
  ["choose", "login", "signup"].forEach((s) => {
    const el = document.getElementById("auth-step-" + s);
    if (el) el.classList.toggle("hidden", s !== name);
  });
}
function openAuthModal(step = "choose") {
  const m = modalEl();
  if (!m) return;
  m.classList.remove("hidden");
  m.setAttribute("aria-hidden", "false");
  showStep(step);
}
function closeAuthModal() {
  const m = modalEl();
  if (!m) return;
  m.classList.add("hidden");
  m.setAttribute("aria-hidden", "true");
}

function bindAuthModal() {
  const m = modalEl();
  if (!m) return;
  m.addEventListener("click", (e) => {
    if (e.target.dataset.close) closeAuthModal();
  });
  (document.getElementById("btn-go-login") || {}).onclick = () =>
    showStep("login");
  (document.getElementById("btn-go-signup") || {}).onclick = () =>
    showStep("signup");
  (document.getElementById("btn-continue-guest") || {}).onclick = () =>
    closeAuthModal();
  (document.getElementById("link-to-signup") || {}).onclick = (e) => {
    e.preventDefault();
    showStep("signup");
  };
  (document.getElementById("link-to-login") || {}).onclick = (e) => {
    e.preventDefault();
    showStep("login");
  };

  const loginForm = document.getElementById("modal-login-form");
  if (loginForm)
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(loginForm);
      const r = await fetch("/api/auth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: fd.get("username"),
          password: fd.get("password"),
        }),
      });
      const data = await r.json().catch(() => ({}));
      const st = document.getElementById("modal-login-status");
      if (r.ok && data.access) {
        auth.setTokens(data.access, data.refresh);
        st.textContent = "Logged in.";
        closeAuthModal();
        refreshHeaderAuth();
      } else {
        st.textContent = data && data.detail ? data.detail : "Login failed.";
      }
    });

  const signupForm = document.getElementById("modal-signup-form");
  if (signupForm)
    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(signupForm);
      const payload = {
        username: fd.get("username"),
        email: fd.get("email"),
        first_name: fd.get("first_name"),
        last_name: fd.get("last_name"),
        password: fd.get("password"),
      };
      const r = await fetch("/api/auth/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
      const st = document.getElementById("modal-signup-status");
      if (r.ok && data.access) {
        auth.setTokens(data.access, data.refresh);
        st.textContent = "Account created & logged in.";
        closeAuthModal();
        refreshHeaderAuth();
      } else {
        st.textContent =
          typeof data === "object" ? JSON.stringify(data) : "Signup failed.";
      }
    });
}

// === Header auth link ===
function refreshHeaderAuth() {
  const link = document.getElementById("auth-link");
  if (!link) return;
  if (auth.access()) {
    link.textContent = "Logout";
    link.onclick = (e) => {
      e.preventDefault();
      auth.clear();
      location.reload();
    };
  } else {
    link.textContent = "Login";
    link.onclick = (e) => {
      e.preventDefault();
      openAuthModal("choose");
    };
  }
}

// === Menu ===
async function loadMenu() {
  const wrap = document.getElementById("menu-grid");
  if (!wrap) return;
  try {
    const data = await api("/api/menu/items/" + qsOrgLoc());
    const items = Array.isArray(data) ? data : data.results || [];
    if (!items.length) {
      wrap.innerHTML = `<div class="card">No items available. Check Admin → Menu → Items (active & priced).</div>`;
      return;
    }
    wrap.innerHTML = items
      .map(
        (i) => `
      <div class="card">
        <h3>${i.name || i.title || "Item"}</h3>
        <p>${i.description || ""}</p>
        <strong>${money(i.price || i.unit_price || i.amount)}</strong><br/>
        <a href="/menu/${i.id}/"><button>View</button></a>
        <button data-id="${i.id}" data-name="${i.name || "Item"}" data-price="${
          i.price || i.unit_price || 0
        }">Add</button>
      </div>
    `
      )
      .join("");
    wrap.querySelectorAll("button[data-id]").forEach((b) => {
      b.onclick = () =>
        addToCart(
          Number(b.dataset.id),
          b.dataset.name,
          Number(b.dataset.price)
        );
    });
  } catch (e) {
    wrap.innerHTML = `<div class="card">Failed to load menu.</div>`;
    console.error("Menu fetch error", e);
  }
}

async function loadMenuItem(id) {
  const data = await api("/api/menu/items/" + qsOrgLoc());
  const items = Array.isArray(data) ? data : data.results || [];
  const itm = items.find((x) => x.id === id);
  if (!itm) {
    document.getElementById("mi-name").textContent = "Item not found";
    return;
  }
  document.getElementById("mi-name").textContent = itm.name || "Item";
  document.getElementById("mi-desc").textContent = itm.description || "";
  document.getElementById("mi-price").textContent = money(
    itm.price || itm.unit_price || 0
  );
  const btn = document.getElementById("add-to-cart");
  if (btn)
    btn.onclick = () =>
      addToCart(itm.id, itm.name, itm.price || itm.unit_price || 0);
}

// === Cart / Coupon ===
function addToCart(id, name, unit_price) {
  const cur = cartGet();
  const ex = cur.find((x) => x.menu_item === id);
  if (ex) {
    ex.qty += 1;
    ex.total = money(ex.qty * unit_price);
  } else {
    cur.push({
      menu_item: id,
      name,
      qty: 1,
      unit_price: money(unit_price),
      total: money(unit_price),
    });
  }
  cartSet(cur);
}
function renderCart() {
  const el = document.getElementById("cart");
  if (!el) return;
  const items = cartGet();
  if (!items.length) {
    el.innerHTML = "<p>Your cart is empty.</p>";
    return;
  }
  const total = items.reduce((s, i) => s + Number(i.total || 0), 0);
  el.innerHTML = `
    <div class="card">
      <ul>${items
        .map((i) => `<li>${i.name} × ${i.qty} = ${money(i.total)}</li>`)
        .join("")}</ul>
      <strong>Subtotal: <span id="subtotal">${money(total)}</span></strong>
      <div id="discount-line" style="display:none">Discount: -<span id="discount">0.00</span></div>
      <div>Payable: <strong id="payable">${money(total)}</strong></div>
    </div>`;
}
async function applyCoupon() {
  const code = (document.getElementById("coupon").value || "")
    .trim()
    .toUpperCase();
  if (!code) return;
  const res = await api("/api/promotions/validate/", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
  const st = document.getElementById("coupon-status");
  const subtotal = Number(document.getElementById("subtotal").textContent);
  if (res.valid) {
    const disc = subtotal * (res.discount_percent / 100);
    document.getElementById("discount").textContent = money(disc);
    document.getElementById("discount-line").style.display = "";
    document.getElementById("payable").textContent = money(subtotal - disc);
    st.textContent = `Applied ${res.discount_percent}%`;
    localStorage.setItem("coupon_code", code);
    localStorage.setItem("coupon_discount", String(res.discount_percent));
  } else {
    st.textContent = "Invalid/expired coupon";
    localStorage.removeItem("coupon_code");
    localStorage.removeItem("coupon_discount");
  }
}

// === Checkout (guest OK) + mock pay + better error messages ===
async function placeOrder(evt) {
  evt.preventDefault();
  const items = cartGet();
  if (!items.length) return alert("Cart empty");

  const fd = new FormData(evt.target);
  let org = (fd.get("organization") || "").trim();
  let loc = (fd.get("location") || "").trim();

  // Coerce numeric PKs; otherwise omit (backend allows null)
  const isInt = (s) => /^\d+$/.test(s);
  const organization = isInt(org) ? Number(org) : undefined;
  const location = isInt(loc) ? Number(loc) : undefined;

  // Extract id from multiple possible keys
  const getId = (o) => {
    if (o == null || typeof o !== "object") return null;
    // direct numeric or string
    if (o.menu_item != null) return parseInt(o.menu_item, 10) || null;
    if (o.id != null) return parseInt(o.id, 10) || null;
    if (o.item != null) return parseInt(o.item, 10) || null;
    if (o.product != null) return parseInt(o.product, 10) || null;
    if (o.menuitem != null) return parseInt(o.menuitem, 10) || null;
    // nested { menu_item: { id: 12 } }
    if (
      o.menu_item &&
      typeof o.menu_item === "object" &&
      o.menu_item.id != null
    ) {
      return parseInt(o.menu_item.id, 10) || null;
    }
    return null;
  };

  const orderItems = items
    .map((i) => {
      const id =
        getId(i) ?? (typeof i === "object" ? getId({ menu_item: i }) : null);
      const q = Number(i.qty || i.quantity || 1);
      return id ? { menu_item: id, quantity: q > 0 ? q : 1 } : null;
    })
    .filter(Boolean);

  const payload = {
    service_type: fd.get("service_type") || "DINE_IN",
    items: orderItems,
  };
  if (organization !== undefined) payload.organization = organization;
  if (location !== undefined) payload.location = location;

  const statusEl = document.getElementById("order-status");

  try {
    const order = await api("/api/orders/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    try {
      await api(`/api/orders/${order.id}/place/`, { method: "POST" });
    } catch {}

    const btn = document.getElementById("pay-now");
    const acct = document.getElementById("create-account");
    const payable = Number(document.getElementById("payable").textContent);

    if (btn) {
      btn.style.display = "";
      btn.onclick = async () => {
        try {
          const res = await api("/api/payments/mock/pay/", {
            method: "POST",
            body: JSON.stringify({
              order_id: order.id,
              amount: money(payable),
              currency: "NPR",
            }),
          });
          statusEl.textContent =
            res.status === "captured" ? "Payment success" : "Payment failed";
          if (res.status === "captured") localStorage.removeItem("cart");
          if (acct && !auth.access()) {
            acct.style.display = "";
            acct.onclick = () => openAuthModal("signup");
          }
        } catch (err) {
          statusEl.textContent = `Payment error: ${JSON.stringify(
            err.data || err
          )}`;
        }
      };
    }
  } catch (err) {
    statusEl.textContent = `Order error (${
      err.status || "400"
    }): ${JSON.stringify(err.data || err)}`;
  }
}

// === Orders (prompt login) ===
async function loadOrders() {
  const el = document.getElementById("orders");
  if (!el) return;
  try {
    const data = await api("/api/orders/");
    const items = Array.isArray(data) ? data : data.results || [];
    el.innerHTML = items
      .map(
        (o) =>
          `<div class="card"><div><strong>Order #${o.id}</strong> — ${
            o.status || "PENDING"
          }</div><div>${(o.items || [])
            .map((i) => `${i.name || i.menu_item}×${i.quantity || i.qty}`)
            .join(", ")}</div></div>`
      )
      .join("");
  } catch {
    el.innerHTML = "<p>Login to view orders.</p>";
    openAuthModal("login");
  }
}

// === Boot ===
function refreshHeaderAuth() {
  const link = document.getElementById("auth-link");
  if (!link) return;
  if (auth.access()) {
    link.textContent = "Logout";
    link.onclick = (e) => {
      e.preventDefault();
      auth.clear();
      location.reload();
    };
  } else {
    link.textContent = "Login";
    link.onclick = (e) => {
      e.preventDefault();
      openAuthModal("choose");
    };
  }
}

document.addEventListener("DOMContentLoaded", () => {
  bindAuthModal();
  refreshHeaderAuth();
  cartCount();
  if (window.page === "menu") loadMenu();
  if (window.page === "menu_item") loadMenuItem(window.item_id);
  if (window.page === "cart") {
    renderCart();
    const btn = document.getElementById("apply-coupon");
    if (btn) btn.onclick = applyCoupon;
  }
  if (window.page === "checkout") {
    renderCart();
    const f = document.getElementById("order-form");
    if (f) f.addEventListener("submit", placeOrder);
    if (!auth.access()) openAuthModal("choose");
  }
  if (window.page === "orders") loadOrders();
});

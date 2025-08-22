// === Auth helpers (JWT + refresh) ===
const auth = {
  access() { return localStorage.getItem("jwt_access") || ""; },
  refresh() { return localStorage.getItem("jwt_refresh") || ""; },
  setTokens(a, r) { if (a) localStorage.setItem("jwt_access", a); if (r) localStorage.setItem("jwt_refresh", r); },
  clear() { localStorage.removeItem("jwt_access"); localStorage.removeItem("jwt_refresh"); }
};

// === Cart (local) ===
function cartGet(){ return JSON.parse(localStorage.getItem("cart") || "[]"); }
function cartSet(items){ localStorage.setItem("cart", JSON.stringify(items)); cartCount(); }
function cartCount(){
  const c = (cartGet()||[]).reduce((s,i)=>s + Number(i.qty||0), 0);
  const el = document.getElementById("cart-count");
  if (el) el.textContent = c;
}
function money(n){ return Number(n||0).toFixed(2); }

// === API with auto-refresh ===
async function _fetch(path, opts){
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch {}
  return {res, data};
}
async function api(path, opts={}, retry=true){
  opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers||{});
  const t = auth.access(); if (t) opts.headers["Authorization"]="Bearer "+t;

  const first = await _fetch(path, opts);
  if (first.res.status !== 401){
    if(!first.res.ok) throw {status:first.res.status, data:first.data};
    return first.data;
  }
  if (!retry || !auth.refresh()) throw {status:first.res.status, data:first.data};

  const rr = await fetch("/api/auth/token/refresh/", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ refresh: auth.refresh() })
  });
  const jd = await rr.json().catch(()=>({}));
  if (rr.ok && jd.access){
    auth.setTokens(jd.access, jd.refresh);
    opts.headers["Authorization"]="Bearer "+jd.access;
    const second = await _fetch(path, opts);
    if(!second.res.ok) throw {status:second.res.status, data:second.data};
    return second.data;
  } else {
    auth.clear();
    throw {status:first.res.status, data:first.data};
  }
}

// === Small utils ===
function fmtDT(iso){
  try{ return new Date(iso).toLocaleString(); }catch{ return iso || ""; }
}

// === Auth modal ===
const modalEl = ()=>document.getElementById("auth-modal");
function showStep(name){
  ["choose","login","signup"].forEach(s=>{
    const el = document.getElementById("auth-step-"+s);
    if (el) el.classList.toggle("hidden", s!==name);
  });
}
function openAuthModal(step="choose"){
  const m = modalEl(); if(!m) return;
  m.classList.remove("hidden"); m.setAttribute("aria-hidden","false");
  showStep(step);
}
function closeAuthModal(){
  const m = modalEl(); if(!m) return;
  m.classList.add("hidden"); m.setAttribute("aria-hidden","true");
}

function refreshHeaderAuth(){
  const link = document.getElementById("auth-link"); if(!link) return;

  // Hide/Show "My Orders" link based on login (works with id or href fallback)
  const ordersLink = document.getElementById("nav-orders") || document.querySelector('a[href="/orders/"]');
  if (ordersLink) ordersLink.style.display = auth.access() ? "inline-block" : "none";

  if (auth.access()){
    link.textContent="Logout";
    link.onclick = async (e)=>{
      e.preventDefault();
      // Clear auth + cart and reset session (start as a fresh guest)
      auth.clear();
      cartSet([]);
      try { await api("/api/cart/reset_session/", { method:"POST", body:"{}" }); } catch {}
      location.reload();
    };
  } else {
    link.textContent="Login";
    link.onclick = (e)=>{ e.preventDefault(); openAuthModal("login"); };
  }
}

function bindAuthModal(){
  const m = modalEl(); if(!m) return;
  m.addEventListener("click", (e)=>{ if (e.target.dataset.close) closeAuthModal(); });

  // REMOVE / DISABLE "Continue as guest"
  const guestBtn = document.getElementById("btn-continue-guest");
  if (guestBtn) { guestBtn.style.display = "none"; guestBtn.disabled = true; }

  (document.getElementById("btn-go-login")||{}).onclick = ()=>showStep("login");
  (document.getElementById("btn-go-signup")||{}).onclick = ()=>showStep("signup");
  (document.getElementById("link-to-signup")||{}).onclick = (e)=>{ e.preventDefault(); showStep("signup"); };
  (document.getElementById("link-to-login")||{}).onclick = (e)=>{ e.preventDefault(); showStep("login"); };

  const loginForm = document.getElementById("modal-login-form");
  if (loginForm) loginForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd = new FormData(loginForm);
    const payload = { username: fd.get("username"), password: fd.get("password") };
    const r = await fetch("/api/auth/token/", {
      method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)
    });
    const data = await r.json().catch(()=>({}));
    const st = document.getElementById("modal-login-status");
    if (r.ok) {
      // Fresh cart for new user login
      cartSet([]);
      try { await api("/api/cart/reset_session/", { method:"POST", body:"{}" }); } catch {}
      auth.setTokens(data.access, data.refresh);
      refreshHeaderAuth();
      st.textContent="";
      closeAuthModal();
    } else {
      st.textContent = "Login failed.";
    }
  });

  const signupForm = document.getElementById("modal-signup-form");
  if (signupForm) signupForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd = new FormData(signupForm);
    const payload = {
      username: fd.get("username"),
      email: fd.get("email"),
      first_name: fd.get("first_name"),
      last_name: fd.get("last_name"),
      password: fd.get("password"),
    };
    const res = await fetch("/api/auth/register/", {
      method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)
    });
    const st = document.getElementById("modal-signup-status");
    if (res.ok) {
      // Auto-login after signup
      const r = await fetch("/api/auth/token/", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ username: payload.username, password: payload.password })
      });
      const data = await r.json().catch(()=>({}));
      if (r.ok) {
        // Fresh cart for new user
        cartSet([]);
        try { await api("/api/cart/reset_session/", { method:"POST", body:"{}" }); } catch {}
        auth.setTokens(data.access, data.refresh);
        refreshHeaderAuth();
        st.textContent = "";
        closeAuthModal();
      } else {
        st.textContent = "Signup ok, login failed.";
      }
    } else {
      st.textContent = "Signup failed.";
    }
  });
}

// === Menu ===
async function loadMenu(){
  const wrap = document.getElementById("menu-grid"); if(!wrap) return;
  try{
    const data = await api("/api/menu/items/");
    const items = Array.isArray(data) ? data : (data.results||[]);
    if (!items.length){ wrap.innerHTML = `<div class="card">No items available.</div>`; return; }
    wrap.innerHTML = items.map(i=>`
      <div class="card">
        <h3>${i.name || "Item"}</h3>
        <p>${i.description || ""}</p>
        <strong>NPR ${money(i.price || 0)}</strong><br/>
        <a href="/menu/${i.id}/"><button>View</button></a>
        <button data-id="${i.id}" data-name="${i.name || "Item"}" data-price="${i.price || 0}">Add</button>
      </div>
    `).join("");
    wrap.querySelectorAll("button[data-id]").forEach(b=>{
      b.onclick = ()=>addToCart(Number(b.dataset.id), b.dataset.name, Number(b.dataset.price));
    });
  }catch(e){
    wrap.innerHTML=`<div class="card">Failed to load menu.</div>`;
    console.error("Menu fetch error", e);
  }
}

async function loadMenuItem(id){
  const wrap = document.getElementById("menu-item"); if(!wrap) return;
  try{
    const i = await api(`/api/menu/items/${id}/`);
    wrap.innerHTML = `
      <div class="card">
        <h2>${i.name || "Item"}</h2>
        <p>${i.description || ""}</p>
        <strong>NPR ${money(i.price || 0)}</strong><br/>
        <div class="row"><button id="btn-add">Add to Cart</button></div>
      </div>
    `;
    const btn = document.getElementById("btn-add");
    if (btn) btn.onclick = ()=>addToCart(Number(i.id), i.name, Number(i.price||0));
  }catch(e){
    wrap.innerHTML=`<div class="card">Failed to load item.</div>`;
  }
}

// === Cart actions ===
function addToCart(id, name, unit_price){
  const cur = cartGet();
  const ex = cur.find(x => (x.menu_item===id) || (x.id===id));
  if(ex){
    ex.qty = Number(ex.qty||0) + 1;
    ex.total = money(ex.qty * unit_price);
  } else {
    cur.push({ menu_item:id, name, qty:1, unit_price:money(unit_price), total:money(unit_price) });
  }
  cartSet(cur);
  syncCartToServer();
}

function changeQty(menu_item, delta){
  const cur = cartGet();
  const it = cur.find(x => (x.menu_item===menu_item) || (x.id===menu_item));
  if (!it) return;
  const price = Number(it.unit_price);
  it.qty = Math.max(0, Number(it.qty||0) + delta);
  if (it.qty === 0){
    const idx = cur.indexOf(it);
    if (idx >= 0) cur.splice(idx,1);
  } else {
    it.total = money(it.qty * price);
  }
  cartSet(cur);
  renderCart();
  syncCartToServer();
}

function renderCart(){
  const el = document.getElementById("cart"); if(!el) return;
  const items = cartGet();
  if (!items.length){ el.innerHTML="<p>Your cart is empty.</p>"; return; }

  const total = items.reduce((s,i)=>s+Number(i.total||0),0);
  el.innerHTML = `
    <div class="card">
      <ul>
        ${items.map(i=>`
          <li class="row" style="justify-content:space-between; align-items:center;">
            <span>${i.name}</span>
            <div class="row" style="gap:6px;">
              <button data-minus="${i.menu_item}">−</button>
              <strong>${i.qty}</strong>
              <button data-plus="${i.menu_item}">+</button>
              <span>NPR ${money(i.total)}</span>
              <button data-remove="${i.menu_item}">x</button>
            </div>
          </li>
        `).join("")}
      </ul>
      <div class="space"></div>
      <strong>Subtotal: <span id="subtotal">${money(total)}</span></strong>
      <div>Payable: <strong id="payable">${money(total)}</strong></div>
    </div>`;

  el.querySelectorAll("button[data-plus]").forEach(b=>{
    b.onclick = ()=>changeQty(Number(b.dataset.plus), +1);
  });
  el.querySelectorAll("button[data-minus]").forEach(b=>{
    b.onclick = ()=>changeQty(Number(b.dataset.minus), -1);
  });
  el.querySelectorAll("button[data-remove]").forEach(b=>{
    b.onclick = ()=>{
      const id = Number(b.dataset.remove);
      const cur = cartGet().filter(x => x.menu_item !== id);
      cartSet(cur); renderCart(); syncCartToServer();
    };
  });
}

// === Server cart sync ===
async function syncCartToServer(){
  try{
    const items = (cartGet()||[]).map(i=>({ menu_item: i.menu_item || i.id, quantity: Number(i.qty||1) }));
    await api("/api/cart/sync/", { method:"POST", body: JSON.stringify({items}) });
  }catch(e){ console.warn("cart sync failed", e); }
}

async function loadServerCartAndAdopt(){
  // Only adopt from server if local cart is empty
  const local = cartGet();
  if (Array.isArray(local) && local.length) return;
  try{
    const server = await api("/api/cart/");
    const sitems = (server.items||[]).map(i=>({ menu_item:i.menu_item, qty:i.quantity, name:"Item", unit_price:0, total:0 }));
    if (sitems.length) {
      cartSet(sitems);
      cartCount();
      if (window.page==='cart' || window.page==='checkout') { try{ renderCart(); }catch(e){} }
    }
  }catch(e){ /* no server cart yet */ }
}

// === Checkout: place order -> immediately open payment (mock) ===
async function placeOrder(evt){
  evt.preventDefault();

  // Require login so orders appear in "My Orders"
  if (!auth.access()) {
    openAuthModal("login");
    const statusEl = document.getElementById("order-status");
    if (statusEl) statusEl.textContent = "Please log in to place your order.";
    return;
  }

  let items = cartGet() || [];
  // Filter out bad entries and coerce to numbers
  items = items
    .map(i => ({ menu_item: Number(i.menu_item || i.id), quantity: Number(i.qty || i.quantity || 1) }))
    .filter(i =>
      Number.isFinite(i.menu_item) && i.menu_item > 0 &&
      Number.isFinite(i.quantity) && i.quantity > 0
    );

  // Fallback: if local cart empty, try server cart
  if (!items.length) {
    try {
      const server = await api("/api/cart/");
      const sitems = (server.items||[])
        .map(i => ({ menu_item: Number(i.menu_item || i.id), quantity: Number(i.quantity || i.qty || 1) }))
        .filter(i =>
          Number.isFinite(i.menu_item) && i.menu_item > 0 &&
          Number.isFinite(i.quantity) && i.quantity > 0
        );
      if (sitems.length) {
        items = sitems;
        // also adopt to local for UI
        const slocal = (server.items||[]).map(i=>({ menu_item:i.menu_item, qty:i.quantity, name:"Item", unit_price:0, total:0 }));
        cartSet(slocal);
      }
    } catch {}
  }

  if (!items.length) { alert("Cart empty"); return; }

  const fd = new FormData(evt.target);
  const payload = { service_type: fd.get("service_type") || "DINE_IN", items };

  const statusEl = document.getElementById("order-status");
  const payBtn = document.getElementById("pay-now");
  const acctBtn = document.getElementById("create-account");

  try {
    const order = await api("/api/orders/", { method:"POST", body:JSON.stringify(payload) });
    await api(`/api/orders/${order.id}/place/`, { method:"POST" });

    // Immediately "open" payment (mock capture)
    const payable = Number((document.getElementById("payable") && document.getElementById("payable").textContent) || "0");
    await api("/api/payments/mock/pay/", { method:"POST", body: JSON.stringify({ order_id: order.id, amount: payable }) });

    statusEl.textContent = "Payment successful.";
    payBtn.style.display="none"; if (acctBtn) acctBtn.style.display="inline-block";
  } catch(e) {
    const err = (e && e.data && (e.data.detail || JSON.stringify(e.data))) || (e && e.message) || "Unknown";
    statusEl.textContent = "Order error: " + err;
  }
}

// === Orders (for My Orders page; requires auth) ===
async function loadOrders(){
  const el = document.getElementById("orders-list"); if(!el) return;

  // Hard gate: require login before loading
  if (!auth.access()) {
    el.innerHTML = "<p>Please log in to view your orders.</p>";
    openAuthModal("login");
    return;
  }

  try {
    const data = await api("/api/orders/");
    const list = Array.isArray(data) ? data : (data.results||[]);

    if (!list.length){
      el.innerHTML = `<div class="card">You have no orders yet.</div>`;
      return;
    }

    el.innerHTML = list.map(o=>{
      const when = fmtDT(o.created_at);
      const items = (o.items||[]).map(it=>`
        <li class="row" style="justify-content:space-between;">
          <span>${it.menu_item_name}</span>
          <span>Qty: ${it.quantity}</span>
          <span>NPR ${money(it.unit_price)}</span>
          <strong>NPR ${money(it.line_total)}</strong>
        </li>
      `).join("");
      const total = money(o.total || 0);
      return `
        <div class="card">
          <div class="row" style="justify-content:space-between;align-items:center;">
            <h3 style="margin:0;">Order #${o.id}</h3>
            <span class="muted">${when}</span>
          </div>
          <p>Status: <strong>${o.status}</strong> &nbsp;·&nbsp; Service: ${o.service_type}</p>
          <ul>${items}</ul>
          <div class="space"></div>
          <p><strong>Total: NPR ${total}</strong></p>
        </div>
      `;
    }).join("");
  } catch {
    el.innerHTML = "<p>Could not load orders.</p>";
  }
}

// === Boot ===
document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal();
  refreshHeaderAuth();
  cartCount();

  await loadServerCartAndAdopt();

  if(window.page==='menu') loadMenu();
  if(window.page==='menu_item') loadMenuItem(window.item_id);
  if(window.page==='cart'){ renderCart(); }
  if(window.page==='checkout'){
    renderCart();
    const f = document.getElementById("order-form");
    if (f) f.addEventListener("submit", placeOrder);
    if(!auth.access()) openAuthModal("login");  // force login on checkout
  }
  if(window.page==='orders'){
    if (!auth.access()) { openAuthModal("login"); return; }
    loadOrders();
  }
});

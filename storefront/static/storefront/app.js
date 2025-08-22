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
function cartCount(){ const c = cartGet().reduce((s,i)=>s+Number(i.qty||0),0); const el=document.getElementById("cart-count"); if(el) el.textContent=c; }
function money(n){ return Number(n||0).toFixed(2); }

// === API with auto-refresh ===
async function _fetch(path, opts){ const res = await fetch(path, opts); let data={}; try{ data=await res.json(); }catch{} return {res,data}; }
async function api(path, opts={}, retry=true){
  opts.headers = Object.assign({ "Content-Type": "application/json" }, opts.headers||{});
  const t = auth.access(); if (t) opts.headers["Authorization"]="Bearer "+t;
  let {res,data} = await _fetch(path, opts);
  if (res.status !== 401){ if(!res.ok) throw {status:res.status, data}; return data; }
  if (!retry || !auth.refresh()) throw {status:res.status, data};
  const rr = await fetch("/api/auth/token/refresh/", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({refresh:auth.refresh()}) });
  const jd = await rr.json().catch(()=>({}));
  if (rr.ok && jd.access){
    auth.setTokens(jd.access, jd.refresh);
    opts.headers["Authorization"]="Bearer "+jd.access;
    const second = await _fetch(path, opts);
    if(!second.res.ok) throw {status:second.res.status, data:second.data};
    return second.data;
  } else { auth.clear(); throw {status:res.status, data}; }
}

// === Auth modal (same as before, trimmed for brevity) ===
const modalEl = ()=>document.getElementById("auth-modal");
function showStep(name){ ["choose","login","signup"].forEach(s=>{ const el=document.getElementById("auth-step-"+s); if(el) el.classList.toggle("hidden", s!==name); }); }
function openAuthModal(step="choose"){ const m=modalEl(); if(!m) return; m.classList.remove("hidden"); m.setAttribute("aria-hidden","false"); showStep(step); }
function closeAuthModal(){ const m=modalEl(); if(!m) return; m.classList.add("hidden"); m.setAttribute("aria-hidden","true"); }

function bindAuthModal(){
  const m=modalEl(); if(!m) return;
  m.addEventListener("click",(e)=>{ if(e.target.dataset.close) closeAuthModal(); });
  (document.getElementById("btn-go-login")||{}).onclick = ()=>showStep("login");
  (document.getElementById("btn-go-signup")||{}).onclick = ()=>showStep("signup");
  (document.getElementById("btn-continue-guest")||{}).onclick = ()=>closeAuthModal();
  (document.getElementById("link-to-signup")||{}).onclick = (e)=>{e.preventDefault();showStep("signup");};
  (document.getElementById("link-to-login")||{}).onclick = (e)=>{e.preventDefault();showStep("login");};

  const loginForm = document.getElementById("modal-login-form");
  if (loginForm) loginForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd = new FormData(loginForm);
    const r = await fetch("/api/auth/token/", { method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ username: fd.get("username"), password: fd.get("password") }) });
    const data = await r.json().catch(()=>({}));
    const st = document.getElementById("modal-login-status");
    if (r.ok && data.access){
      auth.setTokens(data.access, data.refresh);
      st.textContent="Logged in.";
      try{
        await api("/api/cart/claim/", { method:"POST", body:"{}" });
        const server = await api("/api/cart/", { method:"GET" });
        const sitems = (server.items||[]).map(i=>({ menu_item:i.menu_item, qty:i.quantity, name:"Item", unit_price:0, total:0 }));
        cartSet(sitems);
      }catch(e){ console.warn("claim failed", e); }
      closeAuthModal(); refreshHeaderAuth();
    } else {
      st.textContent = (data && data.detail) ? data.detail : "Login failed.";
    }
  });

  const signupForm = document.getElementById("modal-signup-form");
  if (signupForm) signupForm.addEventListener("submit", async (e)=>{
    e.preventDefault();
    const fd = new FormData(signupForm);
    const payload = { username:fd.get("username"), email:fd.get("email"),
                      first_name:fd.get("first_name"), last_name:fd.get("last_name"),
                      password:fd.get("password") };
    const r = await fetch("/api/auth/register/", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload) });
    const data = await r.json().catch(()=>({}));
    const st = document.getElementById("modal-signup-status");
    if (r.ok && data.access){
      auth.setTokens(data.access, data.refresh);
      st.textContent="Account created & logged in.";
      try{
        await api("/api/cart/claim/", { method:"POST", body:"{}" });
        const server = await api("/api/cart/", { method:"GET" });
        const sitems = (server.items||[]).map(i=>({ menu_item:i.menu_item, qty:i.quantity, name:"Item", unit_price:0, total:0 }));
        cartSet(sitems);
      }catch(e){ console.warn("claim failed", e); }
      closeAuthModal(); refreshHeaderAuth();
    } else {
      st.textContent = typeof data === "object" ? JSON.stringify(data) : "Signup failed.";
    }
  });
}

function refreshHeaderAuth(){
  const link = document.getElementById("auth-link"); if(!link) return;
  if (auth.access()){
    link.textContent="Logout";
    link.onclick = async (e)=>{
      e.preventDefault();
      auth.clear();
      cartSet([]);
      try{ await api("/api/cart/reset_session/", { method:"POST", body:"{}" }); }catch(e){}
      location.reload();
    };
  } else {
    link.textContent="Login";
    link.onclick=(e)=>{e.preventDefault();openAuthModal("choose");};
  }
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
  }catch(e){ wrap.innerHTML=`<div class="card">Failed to load menu.</div>`; console.error("Menu fetch error",e); }
}

async function loadMenuItem(id){
  try{
    const data = await api("/api/menu/items/");
    const items = Array.isArray(data) ? data : (data.results||[]);
    const itm = items.find(x=>x.id===id);
    if(!itm){ document.getElementById("mi-name").textContent="Item not found"; return; }
    document.getElementById("mi-name").textContent = itm.name || "Item";
    document.getElementById("mi-desc").textContent = itm.description || "";
    document.getElementById("mi-price").textContent = money(itm.price || 0);
    const btn = document.getElementById("add-to-cart");
    if (btn) btn.onclick = ()=>addToCart(itm.id, itm.name, (itm.price || 0));
  }catch(e){ console.error(e); }
}

// === Cart ===
function addToCart(id,name,unit_price){
  const cur=cartGet(); const ex=cur.find(x=> (x.menu_item===id) || (x.id===id));
  if(ex){ ex.qty=(Number(ex.qty||0)+1); ex.total=money(ex.qty*unit_price); }
  else { cur.push({ menu_item:id, name, qty:1, unit_price:money(unit_price), total:money(unit_price) }); }
  cartSet(cur);
  syncCartToServer();
}
function renderCart(){
  const el=document.getElementById("cart"); if(!el) return;
  const items=cartGet(); if(!items.length){ el.innerHTML="<p>Your cart is empty.</p>"; return; }
  const total = items.reduce((s,i)=>s+Number(i.total||0),0);
  el.innerHTML = `
    <div class="card">
      <ul>${items.map(i=>`<li>${i.name} × ${i.qty} = NPR ${money(i.total)}</li>`).join("")}</ul>
      <strong>Subtotal: <span id="subtotal">${money(total)}</span></strong>
      <div>Payable: <strong id="payable">${money(total)}</strong></div>
    </div>`;
}

// === Server cart sync ===
async function syncCartToServer(){
  try{
    const items = cartGet().map(i=>({ menu_item: i.menu_item || i.id, quantity: Number(i.qty||1) }));
    await api("/api/cart/sync/", { method:"POST", body: JSON.stringify({items}) });
  }catch(e){ console.warn("cart sync failed", e); }
}
async function loadServerCartAndAdopt(){
  try{
    const server = await api("/api/cart/");
    const sitems = (server.items||[]).map(i=>({ menu_item:i.menu_item, qty:i.quantity, name:"Item", unit_price:0, total:0 }));
    cartSet(sitems);
  }catch(e){ /* no server cart yet */ }
}

// === Checkout: place order -> immediately open payment (mock) ===
async function placeOrder(evt){
  evt.preventDefault();
  const items=cartGet(); if(!items.length) return alert("Cart empty");

  const fd=new FormData(evt.target);
  const payload = {
    service_type: fd.get("service_type") || "DINE_IN",
    items: items.map(i=>({ menu_item: Number(i.menu_item || i.id), quantity: Number(i.qty || 1) }))
  };

  const statusEl = document.getElementById("order-status");
  const payBtn = document.getElementById("pay-now");
  const acctBtn = document.getElementById("create-account");

  try{
    const order = await api("/api/orders/", { method:"POST", body:JSON.stringify(payload) });
    await api(`/api/orders/${order.id}/place/`, { method:"POST" });

    // Immediately "open" payment (mock capture)
    const payable = Number(document.getElementById("payable").textContent || "0");
    const res = await api("/api/payments/mock/pay/", {
      method:"POST",
      body:JSON.stringify({ order_id:order.id, amount:money(payable), currency:"NPR" })
    });

    if(res.status==="captured"){
      statusEl.textContent = "Payment success";
      cartSet([]);
      await syncCartToServer();
    } else {
      statusEl.textContent = "Payment failed. Try Pay Now.";
      if (payBtn){
        payBtn.style.display="";
        payBtn.onclick = async ()=>{
          const again = await api("/api/payments/mock/pay/", {
            method:"POST",
            body:JSON.stringify({ order_id:order.id, amount:money(payable), currency:"NPR" })
          });
          statusEl.textContent = again.status==="captured" ? "Payment success" : "Payment failed";
          if(again.status==="captured"){ cartSet([]); await syncCartToServer(); }
        };
      }
    }

    // Offer to create account if still guest
    if(acctBtn && !auth.access()){
      acctBtn.style.display="";
      acctBtn.onclick=()=>openAuthModal("signup");
    }
  }catch(err){
    statusEl.textContent = `Order error (${err.status||"400"}): ${JSON.stringify(err.data || err)}`;
  }
}

// === Orders list (with invoice links) ===
async function loadOrders(){
  const el=document.getElementById("orders"); if(!el) return;
  try{
    const data = await api("/api/orders/");
    const items = Array.isArray(data)?data:(data.results||[]);
    el.innerHTML = items.map(o=>`
      <div class="card">
        <div><strong>Order #${o.id}</strong> — ${o.status||"PENDING"}</div>
        <div><a href="/api/orders/${o.id}/invoice/" target="_blank">Invoice</a></div>
      </div>`).join("");
  }catch{ el.innerHTML="<p>Login to view orders.</p>"; openAuthModal("login"); }
}

// === Boot ===
document.addEventListener("DOMContentLoaded", async ()=>{
  bindAuthModal(); refreshHeaderAuth(); cartCount();
  await loadServerCartAndAdopt();
  if(window.page==='menu') loadMenu();
  if(window.page==='menu_item') loadMenuItem(window.item_id);
  if(window.page==='cart'){ renderCart(); }
  if(window.page==='checkout'){ renderCart(); const f=document.getElementById("order-form"); if(f) f.addEventListener("submit",placeOrder); if(!auth.access()) openAuthModal("choose"); }
  if(window.page==='orders') loadOrders();
});

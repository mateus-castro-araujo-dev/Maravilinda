/* ── CSRF Helper ─────────────────────────────────────────────────────────────── */
function getCsrf() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

async function apiPost(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
    body: JSON.stringify(data),
  });
  return res.json();
}

/* ── Flash Messages ──────────────────────────────────────────────────────────── */
function showFlash(msg, type = 'success') {
  const container = document.getElementById('flash-container') || createFlashContainer();
  const el = document.createElement('div');
  el.className = `flash flash-${type}`;
  el.innerHTML = `<span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function createFlashContainer() {
  const div = document.createElement('div');
  div.id = 'flash-container';
  div.className = 'flash-container';
  document.body.appendChild(div);
  return div;
}

/* ── Cart State ──────────────────────────────────────────────────────────────── */
let cartData = { cart: [], count: 0, total: 0 };

async function refreshCart() {
  try {
    const data = await fetch('/api/cart/').then(r => r.json());
    cartData = data;
    updateCartUI();
  } catch (e) {}
}

function updateCartUI() {
  // Badge
  document.querySelectorAll('.cart-count').forEach(el => {
    el.textContent = cartData.count;
    el.style.display = cartData.count > 0 ? 'flex' : 'none';
  });

  // Sidebar items
  const sidebar = document.getElementById('cart-items-list');
  if (!sidebar) return;

  if (cartData.cart.length === 0) {
    sidebar.innerHTML = `
      <div class="cart-empty">
        <div class="icon">🛍️</div>
        <p>Seu carrinho está vazio</p>
        <a href="/produtos" class="btn btn-primary btn-sm">Explorar Produtos</a>
      </div>`;
  } else {
    sidebar.innerHTML = cartData.cart.map(item => `
      <div class="cart-item" data-key="${item.key}">
        <div class="cart-item-img">
          <img src="${item.image}" alt="${item.name}" loading="lazy">
        </div>
        <div class="cart-item-info">
          <div class="cart-item-name">${item.name}</div>
          <div class="cart-item-variant">${[item.color, item.size].filter(Boolean).join(' · ')}</div>
          <div class="cart-item-price">${fmtPrice(item.price)}</div>
          <div class="cart-item-controls">
            <button class="qty-btn-sm" onclick="updateCartItem('${item.key}', ${item.qty - 1})">−</button>
            <span>${item.qty}</span>
            <button class="qty-btn-sm" onclick="updateCartItem('${item.key}', ${item.qty + 1})">+</button>
            <button class="cart-item-remove" onclick="removeCartItem('${item.key}')" title="Remover">✕</button>
          </div>
        </div>
      </div>`).join('');
  }

  const totalEl = document.getElementById('cart-total');
  if (totalEl) totalEl.textContent = fmtPrice(cartData.total);
  const checkoutBtn = document.getElementById('cart-checkout-btn');
  if (checkoutBtn) checkoutBtn.style.display = cartData.count > 0 ? 'flex' : 'none';
}

function fmtPrice(v) {
  return 'R$ ' + v.toFixed(2).replace('.', ',');
}

/* ── Add to Cart ─────────────────────────────────────────────────────────────── */
async function addToCart(productId, color, size, qty = 1) {
  const btn = document.getElementById('btn-comprar');
  const originalHTML = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>'; }

  try {
    const res = await apiPost('/api/cart/add/', { product_id: productId, color, size, qty });
    if (res.success) {
      await refreshCart();   // busca itens reais do servidor antes de abrir
      openCart();
      showFlash('Produto adicionado ao carrinho!', 'success');
    } else {
      showFlash(res.error || 'Erro ao adicionar produto.', 'error');
    }
  } catch (e) {
    showFlash('Erro de conexão.', 'error');
  }

  if (btn) { btn.disabled = false; btn.innerHTML = originalHTML; }
}

async function updateCartItem(key, qty) {
  const res = await apiPost('/api/cart/update/', { key, qty });
  if (res.success) {
    cartData.count = res.count;
    cartData.total = res.total;
    await refreshCart();
  }
}

async function removeCartItem(key) {
  const res = await apiPost('/api/cart/remove/', { key });
  if (res.success) {
    cartData.count = res.count;
    cartData.total = res.total;
    await refreshCart();
    showFlash('Item removido do carrinho.', 'info');
  }
}

/* ── Cart Sidebar ────────────────────────────────────────────────────────────── */
function openCart() {
  document.getElementById('cart-sidebar')?.classList.add('open');
  document.getElementById('overlay')?.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeCart() {
  document.getElementById('cart-sidebar')?.classList.remove('open');
  closeOverlay();
}

function closeOverlay() {
  document.getElementById('overlay')?.classList.remove('open');
  document.getElementById('nav-drawer')?.classList.remove('open');
  document.body.style.overflow = '';
}

/* ── Mobile Nav ──────────────────────────────────────────────────────────────── */
function toggleMenu() {
  const drawer = document.getElementById('nav-drawer');
  const overlay = document.getElementById('overlay');
  const isOpen = drawer?.classList.toggle('open');
  overlay?.classList.toggle('open', isOpen);
  document.body.style.overflow = isOpen ? 'hidden' : '';
}

/* ── Search ──────────────────────────────────────────────────────────────────── */
function toggleSearch() {
  const bar = document.getElementById('search-bar');
  const isOpen = bar?.classList.toggle('open');
  if (isOpen) bar?.querySelector('input')?.focus();
}

/* ── Sticky Header ───────────────────────────────────────────────────────────── */
function initStickyHeader() {
  const header = document.querySelector('.header');
  if (!header) return;
  const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 20);
  window.addEventListener('scroll', onScroll, { passive: true });
}

/* ── Product Gallery ─────────────────────────────────────────────────────────── */
function initGallery() {
  const mainImg = document.getElementById('gallery-main-img');
  if (!mainImg) return;

  document.querySelectorAll('.gallery-thumb').forEach(thumb => {
    thumb.addEventListener('click', () => {
      mainImg.src = thumb.dataset.src;
      document.querySelectorAll('.gallery-thumb').forEach(t => t.classList.remove('active'));
      thumb.classList.add('active');
    });
  });
}

/* ── Size & Color Selectors ──────────────────────────────────────────────────── */
function selectSize(el) {
  document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('selected-size').value = el.dataset.size;
}

function selectColor(el) {
  document.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  document.getElementById('selected-color').value = el.dataset.color;
}

/* ── Quantity Control ────────────────────────────────────────────────────────── */
function changeQty(delta) {
  const input = document.getElementById('qty-input');
  if (!input) return;
  const newVal = Math.max(1, Math.min(99, parseInt(input.value || 1) + delta));
  input.value = newVal;
}

/* ── Freight Calculator ──────────────────────────────────────────────────────── */
async function calcFrete(inputId, resultId) {
  const cep = document.getElementById(inputId)?.value.replace(/\D/g, '');
  if (cep?.length !== 8) { showFlash('Digite um CEP válido.', 'error'); return; }

  const resultEl = document.getElementById(resultId);
  if (resultEl) resultEl.innerHTML = '<div style="text-align:center;padding:12px;color:#999">Calculando...</div>';

  try {
    const res = await apiPost('/api/frete/', { cep });
    if (res.pac) {
      if (resultEl) {
        resultEl.innerHTML = `
          <div class="frete-option">
            <div><strong>PAC</strong><br><small>${res.pac.days}</small></div>
            <strong>R$ ${res.pac.price.toFixed(2).replace('.', ',')}</strong>
          </div>
          <div class="frete-option">
            <div><strong>SEDEX</strong><br><small>${res.sedex.days}</small></div>
            <strong>R$ ${res.sedex.price.toFixed(2).replace('.', ',')}</strong>
          </div>`;
      }
    } else {
      showFlash('Não foi possível calcular o frete.', 'error');
    }
  } catch (e) {
    showFlash('Erro ao calcular frete.', 'error');
  }
}

/* ── Checkout: CEP Autocomplete ──────────────────────────────────────────────── */
async function lookupCep(cep) {
  cep = cep.replace(/\D/g, '');
  if (cep.length !== 8) return;
  try {
    const res = await fetch(`/api/cep/${cep}/`).then(r => r.json());
    if (res.logradouro) {
      setField('street', res.logradouro);
      setField('neighborhood', res.bairro);
      setField('city', res.localidade);
      setField('state', res.uf);
      document.getElementById('number')?.focus();
    }
  } catch (e) {}
}

function setField(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

/* ── Checkout: Payment Selection ─────────────────────────────────────────────── */
function selectPayment(method) {
  document.querySelectorAll('.payment-option').forEach(el => {
    el.classList.toggle('selected', el.dataset.method === method);
  });
  document.getElementById('payment-input').value = method;
}

/* ── Checkout: Freight Selection ─────────────────────────────────────────────── */

// Taxas Mercado Pago por parcelas
const MP_FEES = {
  1:  0.0499,
  2:  0.0699,
  3:  0.0699,
  4:  0.0899,
  5:  0.0899,
  6:  0.0899,
  7:  0.0999,
  8:  0.0999,
  9:  0.0999,
  10: 0.0999,
  11: 0.0999,
  12: 0.0999,
};

let currentInstallments = 1;

function getMpFeeRate(installments) {
  return MP_FEES[installments] || MP_FEES[1];
}

function updateCheckoutTotal() {
  const subtotal = parseFloat(document.getElementById('subtotal-val')?.dataset.value || 0);
  const freight  = parseFloat(document.getElementById('freight_price')?.value || 0);
  const method   = document.getElementById('payment-input')?.value || 'pix';

  let total = subtotal + freight;

  const feeRow = document.getElementById('mp-fee-row');
  const feeVal = document.getElementById('mp-fee-val');

  if (method === 'credit') {
    const rate = getMpFeeRate(currentInstallments);
    const fee  = parseFloat((total * rate).toFixed(2));
    total += fee;
    if (feeRow) feeRow.style.display = '';
    if (feeVal) feeVal.textContent = `R$ ${fee.toFixed(2).replace('.', ',')}`;
  } else {
    if (feeRow) feeRow.style.display = 'none';
  }

  const totalEl = document.getElementById('checkout-total');
  if (totalEl) totalEl.textContent = fmtPrice(total);
}

async function calcCheckoutFrete() {
  const cep = document.getElementById('cep')?.value.replace(/\D/g, '');
  if (cep?.length !== 8) { showFlash('Digite um CEP válido primeiro.', 'error'); return; }

  const resultEl = document.getElementById('frete-options');
  if (resultEl) resultEl.innerHTML = '<div style="padding:12px;color:#999">Calculando frete...</div>';

  try {
    const res = await apiPost('/api/frete/', { cep });
    if (res.pac && resultEl) {
      resultEl.innerHTML = `
        <label class="frete-radio-option" onclick="selectFreight('PAC', ${res.pac.price})">
          <input type="radio" name="freight_radio" value="PAC">
          <div class="frete-radio-info">
            <strong>PAC</strong> — ${res.pac.days}
          </div>
          <strong>${res.pac.price === 0 ? 'Grátis' : 'R$ ' + res.pac.price.toFixed(2).replace('.', ',')}</strong>
        </label>
        <label class="frete-radio-option" onclick="selectFreight('SEDEX', ${res.sedex.price})">
          <input type="radio" name="freight_radio" value="SEDEX">
          <div class="frete-radio-info">
            <strong>SEDEX</strong> — ${res.sedex.days}
          </div>
          <strong>${res.sedex.price === 0 ? 'Grátis' : 'R$ ' + res.sedex.price.toFixed(2).replace('.', ',')}</strong>
        </label>`;
    }
  } catch (e) {}
}

function selectFreight(type, price) {
  document.getElementById('freight_type').value = type;
  document.getElementById('freight_price').value = price;
  const freightEl = document.getElementById('checkout-freight');
  if (freightEl) freightEl.textContent = price === 0 ? 'Grátis' : fmtPrice(price);
  updateCheckoutTotal();
}

// Auto-calcular frete ao preencher CEP
document.addEventListener('DOMContentLoaded', function () {
  const cepInput = document.getElementById('cep');
  if (!cepInput) return;
  cepInput.addEventListener('input', function () {
    const digits = this.value.replace(/\D/g, '');
    if (digits.length === 8) calcCheckoutFrete();
  });
});

/* ── Copy PIX ────────────────────────────────────────────────────────────────── */
function copyPix() {
  const code = document.getElementById('pix-code-text')?.textContent;
  if (code) {
    navigator.clipboard.writeText(code).then(() => showFlash('Código PIX copiado!', 'success'));
  }
}

/* ── Auto-dismiss Flashes ────────────────────────────────────────────────────── */
function initFlashes() {
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => el.style.opacity = '0', 3500);
    setTimeout(() => el.remove(), 4000);
  });
}

/* ── CEP Mask ────────────────────────────────────────────────────────────────── */
function maskCep(el) {
  let v = el.value.replace(/\D/g, '');
  if (v.length > 5) v = v.slice(0, 5) + '-' + v.slice(5, 8);
  el.value = v;
}

/* ── Admin: Upload múltiplo acumulativo ──────────────────────────────────────── */
let _allFiles = []; // arquivos acumulados entre múltiplos cliques

function acumularImagens(input) {
  const preview = document.getElementById('new-imgs-preview');
  if (!preview) return;

  Array.from(input.files).forEach(file => {
    const idx = _allFiles.length;
    _allFiles.push(file);

    const reader = new FileReader();
    reader.onload = e => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;display:inline-block';

      const img = document.createElement('img');
      img.src = e.target.result;
      img.style.cssText = 'width:90px;height:110px;object-fit:cover;border:1px solid #E5E7EB;display:block';

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = '<i class="ph-fill ph-x"></i>';
      btn.style.cssText = 'position:absolute;top:4px;right:4px;width:22px;height:22px;background:#DC2626;color:white;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:12px;line-height:1';
      btn.onclick = () => { _allFiles[idx] = null; wrap.remove(); };

      wrap.appendChild(img);
      wrap.appendChild(btn);
      preview.appendChild(wrap);
    };
    reader.readAsDataURL(file);
  });

  // Limpa o input para permitir selecionar os mesmos arquivos novamente
  input.value = '';
}

function removeSavedImg(btn) {
  const wrap = btn.closest('[data-saved-img]');
  if (wrap) wrap.remove();
}

function initProductForm() {
  const form = document.getElementById('produto-admin-form');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();

    const submitBtn = form.querySelector('[type="submit"]');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner"></span> Salvando...'; }

    const fd = new FormData(form);

    // Remove o input de trigger (vazio) e adiciona os arquivos reais acumulados
    fd.delete('images');
    _allFiles.forEach(f => { if (f) fd.append('images', f); });

    try {
      const res = await fetch(form.action, { method: 'POST', body: fd });
      // Flask redireciona após sucesso — seguir o redirect
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }
      // Se não redirecionou, recarregar para exibir flash messages
      window.location.reload();
    } catch (err) {
      showFlash('Erro ao salvar produto. Tente novamente.', 'error');
      if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = 'Salvar'; }
    }
  });
}

/* ── Admin: Image Preview (legado) ──────────────────────────────────────────── */
function previewImages(input) { acumularImagens(input); }

/* ── Admin: Confirm Delete ───────────────────────────────────────────────────── */
function confirmDelete(form) {
  if (confirm('Tem certeza? Esta ação não pode ser desfeita.')) {
    form.submit();
  }
}

/* ── Admin: Status Update ────────────────────────────────────────────────────── */
function updateOrderStatus(orderId) {
  const status = document.getElementById(`status-${orderId}`)?.value;
  const payStatus = document.getElementById(`pay-status-${orderId}`)?.value;
  if (!status) return;

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/admin/pedido/${orderId}/status/`;
  form.innerHTML = `
    <input type="hidden" name="csrf_token" value="${getCsrf()}">
    <input type="hidden" name="status" value="${status}">
    <input type="hidden" name="payment_status" value="${payStatus || ''}">`;
  document.body.appendChild(form);
  form.submit();
}

/* ── Wishlist ────────────────────────────────────────────────────────────────── */
function toggleWishlist(btn, pid, e) {
  if (e) { e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); }
  if (document.body.dataset.loggedIn !== 'true') {
    window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
    return;
  }
  fetch('/api/wishlist/toggle/', {
    method: 'POST',
    headers: { 'X-CSRFToken': getCsrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'product_id=' + pid,
  })
  .then(r => {
    if (!r.ok) throw new Error('status ' + r.status);
    return r.json();
  })
  .then(d => {
    if (d.saved) {
      btn.classList.add('active');
      btn.innerHTML = '<i class="ph-fill ph-heart"></i>';
    } else {
      btn.classList.remove('active');
      btn.innerHTML = '<i class="ph-light ph-heart"></i>';
    }
  })
  .catch(() => {
    window.location.href = '/login/?next=' + encodeURIComponent(window.location.pathname);
  });
}

document.addEventListener('DOMContentLoaded', function () {
  const isLoggedIn = document.body.dataset.loggedIn === 'true';
  if (!isLoggedIn) return;
  fetch('/api/wishlist/ids/')
    .then(r => r.json())
    .then(d => {
      (d.ids || []).forEach(pid => {
        document.querySelectorAll(`.product-card-wishlist[data-pid="${pid}"]`).forEach(btn => {
          btn.classList.add('active');
          btn.innerHTML = '<i class="ph-fill ph-heart"></i>';
        });
      });
    })
    .catch(() => {});
});

/* ── Mapa de cores em português ──────────────────────────────────────────────── */
const COR_MAP = {
  'preto':'#1A1A1A','branco':'#FFFFFF','off-white':'#F5F0EB','creme':'#FFF8DC',
  'bege':'#D4B896','nude':'#C8956C','areia':'#C2A882','caramelo':'#C47A2B',
  'marrom':'#7B4F2E','rosa':'#FFB6C1','rosa claro':'#FFD6E0','rosa escuro':'#C4637A',
  'rosa bebê':'#FFDDE1','pink':'#FF4FA3','magenta':'#D5006D',
  'vermelho':'#DC2626','vinho':'#7F1D1D','borgonha':'#800020',
  'coral':'#FF6B6B','salmão':'#FA8072','laranja':'#EA580C',
  'amarelo':'#EAB308','mostarda':'#B7791F','dourado':'#D4A017',
  'verde':'#16A34A','verde musgo':'#4A6741','verde militar':'#4B5320',
  'verde água':'#7FFFD4','menta':'#98D8C8','esmeralda':'#50C878',
  'azul':'#2563EB','azul claro':'#93C5FD','azul escuro':'#1E3A5F',
  'navy':'#001F5B','royal':'#4169E1','jeans':'#4A6FA5',
  'índigo':'#4F46E5','roxo':'#9333EA','lilás':'#C084FC',
  'lavanda':'#E6E6FA','violeta':'#7C3AED','ametista':'#9966CC',
  'cinza':'#9CA3AF','cinza claro':'#D1D5DB','cinza escuro':'#4B5563',
  'prata':'#C0C0C0','chumbo':'#36454F','terracota':'#C9684A',
  'turquesa':'#40E0D0','tiffany':'#81D8D0','petróleo':'#1B4F6A',
  'chocolate':'#7B3F00','ferrugem':'#8B4513','damasco':'#FBCEB1',
};

function corParaHex(nome) {
  const n = nome.trim().toLowerCase();
  if (COR_MAP[n]) return COR_MAP[n];
  if (/^#[0-9a-f]{3,6}$/i.test(nome.trim())) return nome.trim();
  return '#CCCCCC';
}

function initColorPreview() {
  const input = document.getElementById('colors-input');
  const preview = document.getElementById('colors-preview');
  if (!input || !preview) return;

  function renderPreview() {
    const nomes = input.value.split(',').map(s => s.trim()).filter(Boolean);
    preview.innerHTML = '';
    nomes.forEach(nome => {
      if (!nome) return;
      const hex = corParaHex(nome);
      const wrap = document.createElement('div');
      wrap.style.cssText = 'display:flex;align-items:center;gap:6px;background:#F9FAFB;padding:4px 10px 4px 6px;border:1px solid #E5E7EB';

      const dot = document.createElement('div');
      dot.style.cssText = `width:22px;height:22px;background:${hex};border:1px solid rgba(0,0,0,0.12);flex-shrink:0`;

      const label = document.createElement('span');
      label.textContent = nome;
      label.style.cssText = 'font-size:12px;color:#374151';

      wrap.appendChild(dot);
      wrap.appendChild(label);
      preview.appendChild(wrap);
    });
  }

  input.addEventListener('input', renderPreview);
  renderPreview(); // render ao carregar (edição de produto existente)
}

/* ── Canvas: partículas flutuantes do hero ───────────────────────────────────── */
function initHeroParticles() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const ctx = canvas.getContext('2d');
  let W, H, particles, raf;

  const COLORS = [
    'rgba(255,100,160,',   // rosa vibrante
    'rgba(255,180,210,',   // rosa claro
    'rgba(255,220,235,',   // rosa muito claro
    'rgba(255,255,255,',   // branco puro
    'rgba(255,140,185,',   // rosa médio
  ];

  function resize() {
    W = canvas.width  = canvas.offsetWidth;
    H = canvas.height = canvas.offsetHeight;
  }

  function makeParticle(fromBottom = false) {
    const r = Math.random() * 2.2 + 0.4;
    return {
      x:       Math.random() * W,
      y:       fromBottom ? H + r : Math.random() * H,
      r,
      color:   COLORS[Math.floor(Math.random() * COLORS.length)],
      opacity: Math.random() * 0.35 + 0.08,
      vy:      Math.random() * 0.45 + 0.12,   // velocidade vertical (sobe)
      vx:      (Math.random() - 0.5) * 0.22,  // leve deriva lateral
      pulse:   Math.random() * Math.PI * 2,    // fase do pulso
      pulseSpeed: Math.random() * 0.02 + 0.008,
    };
  }

  function init() {
    resize();
    const count = Math.min(Math.floor(W / 14), 90);
    particles = Array.from({ length: count }, () => makeParticle());
  }

  function drawGlow(p, alpha) {
    const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 4);
    grad.addColorStop(0,   p.color + alpha + ')');
    grad.addColorStop(0.4, p.color + (alpha * 0.5) + ')');
    grad.addColorStop(1,   p.color + '0)');
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r * 4, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    particles.forEach(p => {
      // Pulso suave de opacidade
      p.pulse += p.pulseSpeed;
      const alpha = p.opacity * (0.7 + 0.3 * Math.sin(p.pulse));

      // Halo difuso
      drawGlow(p, alpha * 0.6);

      // Núcleo
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color + alpha + ')';
      ctx.fill();

      // Mover
      p.y -= p.vy;
      p.x += p.vx;

      // Reciclar quando sair pelo topo ou pelas laterais
      if (p.y < -p.r * 5 || p.x < -20 || p.x > W + 20) {
        Object.assign(p, makeParticle(true));
        p.x = Math.random() * W;
      }
    });

    raf = requestAnimationFrame(draw);
  }

  init();
  draw();

  const ro = new ResizeObserver(() => { resize(); init(); });
  ro.observe(canvas.parentElement);
}

/* ── Bootstrap ───────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initStickyHeader();
  initGallery();
  initFlashes();
  initColorPreview();
  initHeroParticles();
  refreshCart();

  // Overlay click closes everything
  document.getElementById('overlay')?.addEventListener('click', () => {
    closeCart();
    closeOverlay();
  });

  // Search form submit
  document.getElementById('search-form')?.addEventListener('submit', e => {
    e.preventDefault();
    const q = document.getElementById('search-input')?.value.trim();
    if (q) window.location.href = `/produtos?q=${encodeURIComponent(q)}`;
  });

  // CEP field on checkout
  document.getElementById('cep')?.addEventListener('input', function () {
    maskCep(this);
    if (this.value.replace(/\D/g, '').length === 8) lookupCep(this.value);
  });
});

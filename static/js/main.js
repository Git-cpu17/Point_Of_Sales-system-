// Enhanced grocery store JavaScript with better UX

// API base URL - update this with your Azure deployment URL
const API_BASE = window.location.origin; // Use relative URLs for flexibility

// Favorites key (still global)
const FAVORITES_KEY = 'freshmart_favorites';

// -------------------- SAFETY: ensure CURRENT_USER exists --------------------
window.CURRENT_USER = window.CURRENT_USER ?? { id: null, role: '' };

// -------------------- Utility functions --------------------
function escapeHtml(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount);
}

function normalizeProduct(p) {
  return {
    product_id: p.product_id ?? p.ProductID,
    name: p.name ?? p.Name,
    price: Number(p.price ?? p.Price ?? 0),
    quantity_in_stock: p.quantity_in_stock ?? p.QuantityInStock ?? 0,
    department_id: p.department_id ?? p.DepartmentID ?? null,
    barcode: p.barcode ?? p.Barcode ?? ''
  };
}

// -------------------- Products management --------------------
async function ensureProducts() {
  if (window.PRODUCTS && Array.isArray(window.PRODUCTS)) {
    if (window.PRODUCTS.length && ('ProductID' in window.PRODUCTS[0] || 'Name' in window.PRODUCTS[0])) {
      window.PRODUCTS = window.PRODUCTS.map(normalizeProduct);
    }
    return window.PRODUCTS;
  }
  try {
    const res = await fetch(`${API_BASE}/products`);
    if (!res.ok) throw new Error('Failed to fetch products');
    const products = (await res.json()).map(normalizeProduct);
    window.PRODUCTS = products;
    return products;
  } catch (err) {
    console.error('Error loading products:', err);
    return [];
  }
}

function getProductById(id) {
  const products = window.PRODUCTS || [];
  return products.find(p => Number(p.product_id) === Number(id)) || null;
}

// -------------------- Cart operations (per-user) --------------------
function getCartKey() {
  const id = (window.CURRENT_USER && window.CURRENT_USER.id != null) ? String(window.CURRENT_USER.id) : 'guest';
  return `cart:${id}`;
}

function readCart() {
  try {
    const raw = localStorage.getItem(getCartKey());
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Error reading cart:', e);
    return [];
  }
}

function writeCart(cart) {
  try {
    localStorage.setItem(getCartKey(), JSON.stringify(cart));
    updateCartBadge();
    updateCartTotal();
    document.dispatchEvent(new CustomEvent('cart:updated', { detail: { cart } }));
  } catch (e) {
    console.error('Error writing cart:', e);
  }
}

function updateCartBadge() {
  const badges = document.querySelectorAll('#bagCount, .badge');
  const cart = readCart();
  const totalQty = cart.reduce((s, it) => s + (it.quantity || 0), 0);
  badges.forEach(badge => {
    if (badge) badge.textContent = totalQty;
  });
}

function updateCartTotal() {
  const cart = readCart();
  const total = cart.reduce((sum, item) => sum + ((item.price || 0) * (item.quantity || 0)), 0);
  const totalElements = document.querySelectorAll('.cart-total');
  totalElements.forEach(el => {
    if (el) el.textContent = formatCurrency(total);
  });
}

// -------------------- Cart manipulation --------------------
function addToCart(productId) {
  ensureProducts().then(() => {
    const product = getProductById(productId);
    if (!product) {
      showNotification('Product not found', 'error');
      return;
    }

    const cart = readCart();
    const idx = cart.findIndex(it => Number(it.product_id) === Number(productId));
    
    if (idx >= 0) {
      cart[idx].quantity = (cart[idx].quantity || 0) + 1;
    } else {
      cart.push({
        product_id: product.product_id,
        name: product.name,
        price: Number(product.price) || 0,
        quantity: 1
      });
    }
    
    writeCart(cart);

    // Animate button
    const btn = document.querySelector(`[data-product-id="${productId}"] .add-btn`);
    if (btn) {
      btn.style.transform = 'scale(0.95)';
      setTimeout(() => { btn.style.transform = ''; }, 200);
    }

    showNotification(`${product.name} added to cart!`, 'success');
  });
}

function removeFromCart(productId) {
  const cart = readCart().filter(it => Number(it.product_id) !== Number(productId));
  writeCart(cart);
  renderCartPage();
  showNotification('Item removed from cart', 'info');
}

function updateQuantity(productId, qty) {
  const cart = readCart();
  const idx = cart.findIndex(it => Number(it.product_id) === Number(productId));

  if (idx >= 0) {
    cart[idx].quantity = Math.max(0, Number(qty) || 0);
    if (cart[idx].quantity === 0) cart.splice(idx, 1);
    writeCart(cart);
    renderCartPage();
  }
}

function clearCart() {
  if (confirm('Are you sure you want to clear your entire cart?')) {
    writeCart([]);
    renderCartPage();
    showNotification('Cart cleared', 'info');
  }
}

async function checkout() {
  const cart = readCart();
  if (!cart.length) {
    showNotification('Your cart is empty', 'warning');
    return;
  }

  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  const message = `Order Summary:\n\n` +
    cart.map(item => `${item.name} x${item.quantity} - ${formatCurrency(item.price * item.quantity)}`).join('\n') +
    `\n\nTotal: ${formatCurrency(total)}\n\nProceed with checkout?`;

  if (confirm(message)) {
    showNotification('Processing your order...', 'success');
    setTimeout(() => {
      writeCart([]);
      renderCartPage();
      showNotification('Order placed successfully! 🎉', 'success');
    }, 2000);
  }
}

// -------------------- Render cart page --------------------
function renderCartPage() {
  const container = document.getElementById('cartContainer');
  if (!container) return;

  const cart = readCart();

  if (!cart.length) {
    container.innerHTML = `
      <div style="text-align: center; padding: 3rem;">
        <div style="font-size: 4rem; opacity: 0.5; margin-bottom: 1rem;">🛒</div>
        <h3 style="color: var(--text-light); margin-bottom: 1rem;">Your cart is empty</h3>
        <p style="color: var(--text-light); margin-bottom: 2rem;">Add some fresh groceries to get started!</p>
        <a href="/" class="btn primary" style="display: inline-flex;">Start Shopping</a>
      </div>
    `;
    updateCartBadge();
    return;
  }

  let html = `
    <table class="cart-table">
      <thead>
        <tr>
          <th>Product</th>
          <th>Price</th>
          <th>Quantity</th>
          <th>Subtotal</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
  `;

  let total = 0;
  cart.forEach(item => {
    const subtotal = (Number(item.price) || 0) * (Number(item.quantity) || 0);
    total += subtotal;
    html += `
      <tr>
        <td><div class="cart-item-name">${escapeHtml(item.name)}</div></td>
        <td>${formatCurrency(item.price)}</td>
        <td>
          <input class="qty-input" type="number" min="1" max="99" 
                 value="${escapeHtml(item.quantity)}" 
                 data-product-id="${escapeHtml(item.product_id)}">
        </td>
        <td><strong>${formatCurrency(subtotal)}</strong></td>
        <td>
          <button class="remove-btn" data-product-id="${escapeHtml(item.product_id)}">Remove</button>
        </td>
      </tr>
    `;
  });

  html += `
      </tbody>
    </table>
    
    <div class="cart-summary">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span>Subtotal:</span>
        <strong>${formatCurrency(total)}</strong>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--primary-green);">
        <span>Delivery:</span>
        <strong>${total >= 50 ? 'FREE' : formatCurrency(5.99)}</strong>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; font-size: 1.2rem;">
        <span>Total:</span>
        <strong class="cart-total">${formatCurrency(total >= 50 ? total : total + 5.99)}</strong>
      </div>
    </div>
  `;

  container.innerHTML = html;

  container.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      const pid = e.currentTarget.getAttribute('data-product-id');
      removeFromCart(pid);
    });
  });

  container.querySelectorAll('.qty-input').forEach(input => {
    input.addEventListener('change', e => {
      const pid = e.currentTarget.getAttribute('data-product-id');
      const qty = Number(e.currentTarget.value) || 0;
      updateQuantity(pid, qty);
    });
  });

  updateCartBadge();
}

// -------------------- Notifications --------------------
function showNotification(message, type = 'info') {
  const existing = document.querySelector('.notification');
  if (existing) existing.remove();

  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.5rem;">
      ${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}
      <span>${escapeHtml(message)}</span>
    </div>
  `;

  Object.assign(notification.style, {
    position: 'fixed',
    top: '20px',
    right: '20px',
    background: type === 'success' ? 'var(--primary-green)' : 
                type === 'error' ? '#dc3545' : 
                type === 'warning' ? 'var(--warm-yellow)' : 'var(--text-dark)',
    color: 'white',
    padding: '1rem 1.5rem',
    borderRadius: '10px',
    boxShadow: 'var(--shadow-lg)',
    zIndex: 1000,
    animation: 'slideIn 0.3s ease',
    maxWidth: '300px'
  });

  document.body.appendChild(notification);

  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// -------------------- Search --------------------
function setupSearchInput() {
  const input = document.getElementById('searchInput');
  if (!input) return;

  let debounceTimer;
  input.addEventListener('input', e => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const query = (e.target.value || '').trim().toLowerCase();
      filterProducts(query);
    }, 300);
  });
}

function filterProducts(query) {
  const grid = document.getElementById('productGrid');
  if (!grid) return;

  const cards = Array.from(grid.querySelectorAll('.product-card'));
  if (!query) {
    cards.forEach(c => { c.style.display = ''; c.style.animation = 'fadeIn 0.3s ease'; });
    return;
  }

  cards.forEach(card => {
    const name = (card.getAttribute('data-name') || '').toLowerCase();
    const desc = (card.getAttribute('data-description') || '').toLowerCase();
    const matches = name.includes(query) || desc.includes(query);
    if (matches) { card.style.display = ''; card.style.animation = 'fadeIn 0.3s ease'; }
    else { card.style.display = 'none'; }
  });

  const visibleCards = cards.filter(c => c.style.display !== 'none');
  let noResults = document.querySelector('.no-results-message');

  if (visibleCards.length === 0) {
    if (!noResults) {
      noResults = document.createElement('div');
      noResults.className = 'no-results-message';
      noResults.style.cssText = 'grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-light);';
      noResults.innerHTML = `
        <div style="font-size: 3rem; opacity: 0.5; margin-bottom: 1rem;">🔍</div>
        <h3>No products found</h3>
        <p>Try searching with different keywords</p>
      `;
      grid.appendChild(noResults);
    }
  } else if (noResults) {
    noResults.remove();
  }
}

// -------------------- Category filters --------------------
function setupCategoryFilters() {
  const categoryCards = document.querySelectorAll('.category-card');
  categoryCards.forEach(card => {
    card.addEventListener('click', e => {
      const category = e.currentTarget.getAttribute('data-category');
      categoryCards.forEach(c => c.classList.remove('active'));
      e.currentTarget.classList.add('active');
      showNotification(`Filtering by ${category}`, 'info');
    });
  });
}

// -------------------- Login --------------------
function setupLoginForm() {
  const form = document.getElementById('loginForm');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Signing in...';
    submitBtn.disabled = true;

    const user_id = document.getElementById('user_id').value;
    const password = document.getElementById('password').value;

    try {
      const response = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id, password })
      });

      const data = await response.json();
      if (data && data.success) {
        sessionStorage.setItem('role', data.role || '');
        showNotification('Login successful! Redirecting...', 'success');
        setTimeout(() => { window.location.href = data.redirectUrl || '/'; }, 1000);
      } else {
        showNotification(data.message || 'Invalid credentials', 'error');
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
      }
    } catch (err) {
      console.error('Login error:', err);
      showNotification('Connection error. Please try again.', 'error');
      submitBtn.textContent = originalText;
      submitBtn.disabled = false;
    }
  });
}

// -------------------- Animations --------------------
function addAnimationStyles() {
  if (document.getElementById('custom-animations')) return;
  const style = document.createElement('style');
  style.id = 'custom-animations';
  style.textContent = `
    @keyframes fadeIn { from {opacity:0; transform:translateY(10px);} to {opacity:1; transform:translateY(0);} }
    @keyframes slideOut { to { transform:translateX(400px); opacity:0; } }
    .category-card.active { background: var(--primary-green); color: white; }
    .notification { transition: all 0.3s ease; }
  `;
  document.head.appendChild(style);
}

// -------------------- Initialize --------------------
document.addEventListener('DOMContentLoaded', () => {
  addAnimationStyles();
  setupSearchInput();
  setupCategoryFilters();
  ensureProducts().catch(() => {});

  if (document.getElementById('cartContainer')) {
    renderCartPage();
    document.addEventListener('cart:updated', () => {
      if (document.getElementById('cartContainer')) renderCartPage();
    });
    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) checkoutBtn.addEventListener('click', checkout);
    const clearBtn = document.getElementById('clearCartBtn');
    if (clearBtn) clearBtn.addEventListener('click', clearCart);
  }

  if (document.getElementById('loginForm')) setupLoginForm();
  updateCartBadge();

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute('href'));
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
});

// -------------------- Global exports --------------------
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateQuantity = updateQuantity;
window.clearCart = clearCart;
window.checkout = checkout;

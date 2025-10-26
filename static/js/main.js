// Replace with your Azure Flask backend URL (no trailing slash)
const API_BASE = "https://posapp-fcghfrh4cfc5h0dh.centralus-01.azurewebsites.net";

// Client-side search + bag (cart) implementation.
// This script augments server-rendered pages and also supports fetching products via API if needed.

// Name of the localStorage key for cart
const CART_KEY = 'pos_cart';

// Basic HTML-escape helper
function escapeHtml(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// --- PRODUCTS source helper ---
// Prefer server-provided window.PRODUCTS (set by index.html). Fallback to API fetch.
async function ensureProducts() {
  if (window.PRODUCTS && Array.isArray(window.PRODUCTS)) return window.PRODUCTS;
  try {
    const res = await fetch(`${API_BASE}/products`);
    if (!res.ok) throw new Error('Failed to fetch products');
    const products = await res.json();
    window.PRODUCTS = products;
    return products;
  } catch (err) {
    console.error('Could not ensure products:', err);
    return [];
  }
}

function getProductById(id) {
  const products = window.PRODUCTS || [];
  return products.find(p => Number(p.product_id) === Number(id)) || null;
}

// --------------------
// Cart helpers
// --------------------
function readCart() {
  try {
    const raw = localStorage.getItem(CART_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.error('Error reading cart:', e);
    return [];
  }
}

function writeCart(cart) {
  try {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartBadge();
  } catch (e) {
    console.error('Error writing cart:', e);
  }
}

function updateCartBadge() {
  const badge = document.getElementById('bagCount');
  if (!badge) return;
  const cart = readCart();
  const totalQty = cart.reduce((s, it) => s + (it.quantity || 0), 0);
  badge.textContent = totalQty;
}

// Add product to cart (by product_id)
function addToCart(productId) {
  ensureProducts().then(() => {
    const product = getProductById(productId);
    if (!product) {
      alert('Product not found.');
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
    // small confirmation
    flashAddedToCart(product.name);
  });
}

function flashAddedToCart(name) {
  // lightweight UX feedback
  const el = document.createElement('div');
  el.className = 'cart-toast';
  el.textContent = `${name} added to bag`;
  Object.assign(el.style, {
    position: 'fixed',
    right: '18px',
    bottom: '18px',
    background: '#2b7a3a',
    color: '#fff',
    padding: '10px 14px',
    borderRadius: '8px',
    zIndex: 120
  });
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1800);
}

function removeFromCart(productId) {
  const cart = readCart().filter(it => Number(it.product_id) !== Number(productId));
  writeCart(cart);
  renderCartPage();
}

function updateQuantity(productId, qty) {
  const cart = readCart();
  const idx = cart.findIndex(it => Number(it.product_id) === Number(productId));
  if (idx >= 0) {
    cart[idx].quantity = Math.max(0, Number(qty) || 0);
    if (cart[idx].quantity === 0) {
      cart.splice(idx, 1);
    }
    writeCart(cart);
    renderCartPage();
  }
}

function clearCart() {
  writeCart([]);
  renderCartPage();
}

function checkout() {
  const cart = readCart();
  if (!cart.length) {
    alert('Your bag is empty.');
    return;
  }
  // Placeholder: in a real app you'd POST to /checkout or similar
  alert('Checkout placeholder — implement backend route to complete purchase.');
  // For demo, clear cart after checkout
  writeCart([]);
  renderCartPage();
}

// --------------------
// Render cart page
// --------------------
function renderCartPage() {
  const container = document.getElementById('cartContainer');
  if (!container) return;
  const cart = readCart();

  if (!cart.length) {
    container.innerHTML = `<div class="cart-container"><p>Your bag is empty. <a href="/">Continue shopping</a></p></div>`;
    updateCartBadge();
    return;
  }

  let html = `<table class="cart-table"><thead><tr><th>Product</th><th>Price</th><th>Qty</th><th>Subtotal</th><th></th></tr></thead><tbody>`;
  let total = 0;

  cart.forEach(item => {
    const subtotal = (Number(item.price) || 0) * (Number(item.quantity) || 0);
    total += subtotal;
    html += `<tr data-product-id="${escapeHtml(item.product_id)}">
      <td class="cart-item-name">${escapeHtml(item.name)}</td>
      <td>$${(Number(item.price) || 0).toFixed(2)}</td>
      <td><input class="qty-input" type="number" min="0" value="${escapeHtml(item.quantity)}" data-product-id="${escapeHtml(item.product_id)}"></td>
      <td>$${subtotal.toFixed(2)}</td>
      <td><button class="btn secondary remove-btn" data-product-id="${escapeHtml(item.product_id)}">Remove</button></td>
    </tr>`;
  });

  html += `</tbody></table>`;
  html += `<div class="cart-summary"><strong>Total: $${total.toFixed(2)}</strong></div>`;
  container.innerHTML = html;

  // attach event handlers
  container.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const pid = e.currentTarget.getAttribute('data-product-id');
      removeFromCart(pid);
    });
  });
  container.querySelectorAll('.qty-input').forEach(input => {
    input.addEventListener('change', (e) => {
      const pid = e.currentTarget.getAttribute('data-product-id');
      const qty = Number(e.currentTarget.value) || 0;
      updateQuantity(pid, qty);
    });
  });

  updateCartBadge();
}

// --------------------
// Search implementation
// --------------------
function setupSearchInput() {
  const input = document.getElementById('searchInput');
  if (!input) return;

  input.addEventListener('input', (e) => {
    const q = (e.target.value || '').trim().toLowerCase();
    filterProductGrid(q);
  });
}

function filterProductGrid(query) {
  const grid = document.getElementById('productGrid');
  if (!grid) return;

  const cards = Array.from(grid.querySelectorAll('.product-card'));
  if (!query) {
    cards.forEach(c => c.style.display = '');
    return;
  }
  cards.forEach(c => {
    const name = (c.getAttribute('data-name') || '').toLowerCase();
    const desc = (c.getAttribute('data-description') || '').toLowerCase();
    const matches = name.includes(query) || desc.includes(query);
    c.style.display = matches ? '' : 'none';
  });
}

// --------------------
// Initialization
// --------------------
document.addEventListener('DOMContentLoaded', () => {
  // Search input setup
  setupSearchInput();

  // Ensure PRODUCTS is ready (in case we need to look up for addToCart)
  ensureProducts().catch(() => { /* ignore */ });

  // If on the bag page, render cart
  if (document.getElementById('cartContainer')) {
    renderCartPage();

    // wire up checkout/clear buttons
    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) checkoutBtn.addEventListener('click', checkout);
    const clearBtn = document.getElementById('clearCartBtn');
    if (clearBtn) clearBtn.addEventListener('click', () => {
      if (confirm('Clear all items from bag?')) clearCart();
    });
  }

  // update bag count shown in header
  updateCartBadge();
});
let data;

// --- Login form setup ---
function setupLoginForm() {
  const form = document.getElementById('loginForm');
  if (!form) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    const user_id_elem = document.getElementById('user_id');
    const password_elem = document.getElementById('password');
    if (!user_id_elem || !password_elem) return;

    const user_id = user_id_elem.value;
    const password = password_elem.value;

    fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, password })
    })
    .then(res => res.json())
    .then(resData => {
        data = resData;
        if (data && data.success) {
          sessionStorage.setItem('role', data.role || '');
          // redirectUrl should be an absolute or relative path returned by the backend
          if (data.redirectUrl) {
            window.location.href = data.redirectUrl;
          } else {
            // fallback
            window.location.href = '/';
          }
        } else {
          alert((data && data.message) ? data.message : 'Login failed');
        }
      })
    .catch(err => {
          console.error('Login error:', err);
          alert('Login failed. Please try again.');
    });
  });
}

// --- Products: fetch and render ---
function fetchProducts() {
  fetch(`${API_BASE}/products`)
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.json();
    })
    .then(products => {
      const container = document.getElementById('productGrid');
      if (!container) return;
      container.innerHTML = '';
      products.forEach(p => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
          <h3>${escapeHtml(p.name)}</h3>
          <p>${escapeHtml(p.description || '')}</p>
          <strong>$${p.price}</strong>
          <p>Stock: ${p.quantity_in_stock}</p>
          ${renderRoleButtons(p)}
        `;
        container.appendChild(card);
      });
    })
    .catch(err => {
      console.error('Error loading products:', err);
    });
}

// small helper to avoid simple XSS when injecting text
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderRoleButtons(product) {
  const role = sessionStorage.getItem('role');
  if (role === 'admin') {
    return `
      <button onclick="editProduct(${product.product_id})">Edit</button>
      <button onclick="hideProduct(${product.product_id})">Hide</button>
      <button onclick="removeProduct(${product.product_id})">Remove</button>
    `;
  } else if (role === 'employee') {
    return `
      <button onclick="editProduct(${product.product_id})">Edit</button>
      <button onclick="hideProduct(${product.product_id})">Hide</button>
    `;
  } else {
    return `<button onclick="addToCart(${product.product_id})">Add to Cart</button>`;
  }
}

// --- Transactions ---
function loadTransactions(filters = {}) {
  const params = new URLSearchParams(filters).toString();
  fetch(`${API_BASE}/transactions?${params}`)
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.json();
    })
    .then(renderTransactions)
    .catch(err => {
      console.error('Error loading transactions:', err);
    });
}

function renderTransactions(data) {
  const table = document.getElementById('transactionTable');
  if (!table) return;
  table.innerHTML = '';
  data.forEach(tx => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${escapeHtml(tx.transaction_id)}</td>
      <td>${escapeHtml(tx.transaction_date)}</td>
      <td>${escapeHtml(tx.total_amount)}</td>
      <td>${escapeHtml(tx.employee_name)}</td>
      <td>${escapeHtml(tx.customer_name)}</td>
      <td>${escapeHtml(tx.payment_method)}</td>
    `;
    table.appendChild(row);
  });
}

// attach filter form if present
function setupTransactionFilters() {
  const filterForm = document.getElementById('filterForm');
  if (!filterForm) return;
  filterForm.addEventListener('submit', e => {
    e.preventDefault();
    const filters = {
      employee: (document.getElementById('employeeFilter') || {}).value || '',
      payment_method: (document.getElementById('paymentFilter') || {}).value || '',
      sort_by: (document.getElementById('sortBy') || {}).value || ''
    };
    loadTransactions(filters);
  });
}

// --- Product actions ---
function editProduct(id) {
  const newQty = prompt("Enter new quantity:");
  if (newQty === null) return;
  fetch(`${API_BASE}/product/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id, quantity: newQty })
  }).then(() => fetchProducts())
    .catch(err => console.error('Edit product error:', err));
}

function hideProduct(id) {
  fetch(`${API_BASE}/product/hide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id })
  }).then(() => fetchProducts())
    .catch(err => console.error('Hide product error:', err));
}

function removeProduct(id) {
  fetch(`${API_BASE}/product/remove`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id })
  }).then(() => fetchProducts())
    .catch(err => console.error('Remove product error:', err));
}

function addToCart(id) {
  // Implement addToCart according to your backend/cart logic
  console.log('addToCart', id);
}

// --- Page specific initialization ---
document.addEventListener('DOMContentLoaded', () => {
  // If login form is present on the page, initialize login handling
  if (document.getElementById('loginForm')) {
    setupLoginForm();
  }
  // If products page elements exist, init product loading
  if (document.getElementById('productGrid')) {
    fetchProducts();
  }
  // If transaction filter form exists, setup filters
  if (document.getElementById('filterForm')) {
    setupTransactionFilters();
    // Optionally load transactions initially
    loadTransactions();
  }
});

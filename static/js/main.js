// Replace with your Azure Flask backend URL (no trailing slash)
const API_BASE = "https://posapp-fcghfrh4cfc5h0dh.centralus-01.azurewebsites.net";

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

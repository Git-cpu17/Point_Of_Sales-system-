// Replace with your Azure Flask backend URL
const API_BASE = "https://posapp-fcghfrh4cfc5h0dh.centralus-01.azurewebsites.net/";

async function loadProducts() {
  try {
    const response = await fetch(`${API_BASE}/products`);
    const data = await response.json();

    const list = document.getElementById("product-list");
    if (list) {
      list.innerHTML = "";
      data.forEach(item => {
        const li = document.createElement("li");
        li.textContent = `${item.name} - $${item.price}`;
        list.appendChild(li);
      });
    }
  } catch (error) {
    console.error("Error loading products:", error);
  }
}

document.addEventListener("DOMContentLoaded", loadProducts);
function setupLoginForm() {
  const form = document.getElementById('loginForm');
  if (!form) return;

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    const user_id = document.getElementById('user_id').value;
    const password = document.getElementById('password').value;

    fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, password })
    })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        window.location.href = data.redirectUrl;
      } else {
        alert(data.message);
      }
    })
    .catch(err => {
      console.error('Login error:', err);
      alert('Login failed. Please try again.');
    });
  });
}

// 📦 Load Product 
function loadProducts() {
  fetch(`${API_BASE}/products`)
    .then(res => res.json())
    .then(products => {
      const container = document.getElementById('productGrid');
      container.innerHTML = '';
      products.forEach(p => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
          <h3>${p.name}</h3>
          <p>${p.description}</p>
          <strong>$${p.price}</strong>
          <p>Stock: ${p.quantity_in_stock}</p>
          ${renderRoleButtons(p)}
        `;
        container.appendChild(card);
      });
    });
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


// 🚀 Page-Specific Initialization
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  if (path.includes('login.html')) setupLoginForm();
  if (path.includes('products.html')) fetchProducts();
});

function loadTransactions(filters = {}) {
  const params = new URLSearchParams(filters).toString();
  fetch(`${API_BASE}/transactions?${params}`)
    .then(res => res.json())
    .then(renderTransactions);
}

function renderTransactions(data) {
  const table = document.getElementById('transactionTable');
  table.innerHTML = '';
  data.forEach(tx => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${tx.transaction_id}</td>
      <td>${tx.transaction_date}</td>
      <td>${tx.total_amount}</td>
      <td>${tx.employee_name}</td>
      <td>${tx.customer_name}</td>
      <td>${tx.payment_method}</td>
    `;
    table.appendChild(row);
  });
}

const filterForm = document.getElementById('filterForm');
if (filterForm) {
  filterForm.addEventListener('submit', e => {
    e.preventDefault();
    const filters = {
      employee: document.getElementById('employeeFilter').value,
      payment_method: document.getElementById('paymentFilter').value,
      sort_by: document.getElementById('sortBy').value
    };
    loadTransactions(filters);
  });
}

function editProduct(id) {
  const newQty = prompt("Enter new quantity:");
  fetch(`${API_BASE}/product/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id, quantity: newQty })
  }).then(loadProducts);
}

function hideProduct(id) {
  fetch(`${API_BASE}/product/hide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id })
  }).then(loadProducts);
}

function removeProduct(id) {
  fetch(`${API_BASE}/product/remove`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: id })
  }).then(loadProducts);
}
sessionStorage.setItem('role', data.role);

document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  if (path.includes('login.html')) setupLoginForm();
  if (path.includes('transactions.html')) setupTransactionFilters();
});




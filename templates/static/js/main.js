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

// 📦 Product Fetcher
function fetchProducts() {
  const productContainer = document.getElementById('productList');
  if (!productContainer) return;

  fetch(`${API_BASE}/products`)
    .then(res => {
      if (!res.ok) throw new Error('Network response was not ok');
      return res.json();
    })
    .then(products => {
      productContainer.innerHTML = products.map(p => `
        <div class="product">
          <h3>${p.name}</h3>
          <p>${p.description}</p>
          <strong>$${p.price}</strong>
        </div>
      `).join('');
    })
    .catch(err => {
      console.error('Product fetch error:', err);
      productContainer.innerHTML = '<p>Failed to load products.</p>';
    });
}

// 🚀 Page-Specific Initialization
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  if (path.includes('login.html')) setupLoginForm();
  if (path.includes('products.html')) fetchProducts();
});

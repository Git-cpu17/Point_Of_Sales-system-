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

  function formToParams(form) {
    return new URLSearchParams(new FormData(form));
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
    return Array.isArray(window.CACHED_BAG) ? window.CACHED_BAG : [];
  }

  function writeCart(cart) {
    try {
      window.CACHED_BAG = Array.isArray(cart) ? cart : [];
      updateCartBadge();
      updateCartTotal();
      document.dispatchEvent(new CustomEvent('cart:updated', { detail: { cart: window.CACHED_BAG } }));
    } catch (e) {
      console.error('Error writing cart (server cache):', e);
    }
  }

  function updateCartBadge() {
    const badges = document.querySelectorAll('#bagCount');
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

  async function refreshBag() {
    const r = await fetch('/api/bag', { credentials: 'same-origin' });
    if (!r.ok) throw new Error('Failed to load bag');
    const rows = await r.json();
    const cart = rows.map(row => ({
      bag_id: row.BagID,
      product_id: Number(row.ProductID),
      name: row.Name,
      price: Number(row.Price) || 0,
      quantity: Number(row.Quantity) || 0,
      added_at: row.AddedAt
    }));
    writeCart(cart);
  }
  
  function findBagItemByProduct(productId) {
    const cart = readCart();
    return cart.find(it => Number(it.product_id) === Number(productId)) || null;
  }

 // -------------------- Cart manipulation --------------------
  async function addToCart(productId) {
    await ensureProducts().catch(() => {});
    const product = getProductById(productId);
    if (!product) {
      showNotification('Product not found', 'error');
      return;
    }
  
    // Upsert on server
    const res = await fetch('/api/bag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ product_id: Number(productId), quantity: 1 })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showNotification(data?.message || 'Failed to add to bag', 'error');
      return;
    }
  
    await refreshBag();
  
    // Animate button
    const btn = document.querySelector(`[data-product-id="${productId}"] .add-btn`);
    if (btn) {
      btn.style.transform = 'scale(0.95)';
      setTimeout(() => { btn.style.transform = ''; }, 200);
    }
  
    showNotification(`${product.name} added to bag!`, 'success');
  }

  async function removeFromCart(productId) {
    const item = findBagItemByProduct(productId);
    if (!item) { showNotification('Item not in bag', 'warning'); return; }
  
    const res = await fetch(`/api/bag/${item.bag_id}`, { method: 'DELETE', credentials: 'same-origin' });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showNotification(data?.message || 'Failed to remove item', 'error');
      return;
    }
    await refreshBag();
    renderCartPage();
    showNotification('Item removed from bag', 'info');
  }

  async function updateQuantity(productId, qty) {
    const item = findBagItemByProduct(productId);
    if (!item) return;
  
    const quantity = Math.max(0, Number(qty) || 0);
    if (quantity === 0) {
      return removeFromCart(productId);
    }
  
    const res = await fetch(`/api/bag/${item.bag_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ quantity })
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showNotification(data?.message || 'Failed to update quantity', 'error');
      return;
    }
    await refreshBag();
    renderCartPage();
  }

  async function clearCart() {
    if (!confirm('Are you sure you want to clear your entire bag?')) return;
    const res = await fetch('/api/bag', { method: 'DELETE', credentials: 'same-origin' });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showNotification(data?.message || 'Failed to clear bag', 'error');
      return;
    }
    await refreshBag();
    renderCartPage();
    showNotification('Bag cleared', 'info');
  }

  async function checkout() {
    const cart = readCart();
    if (!cart.length) {
      showNotification('Your cart is empty', 'warning');
      return;
    }

    const items = cart
      .filter(it => it && Number.isInteger(Number(it.product_id)) && Number(it.quantity) > 0)
      .map(it => ({ product_id: Number(it.product_id), quantity: Number(it.quantity) }));

    if (!items.length) {
      showNotification('Your cart has no valid items', 'error');
      return;
    }

    const summary =
      'Order Summary:\n\n' +
      cart.map(it => `${it.name} x${it.quantity} - ${formatCurrency((Number(it.price)||0)*(Number(it.quantity)||0))}`).join('\n') +
      `\n\n(Actual total will be computed server-side)\nProceed with checkout?`;

    if (!confirm(summary)) return;

    try {
      showNotification('Processing your order...', 'success');

      const res = await fetch('/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        showNotification(data?.message || `Checkout failed (HTTP ${res.status})`, 'error');
        return;
      }

      await refreshBag();
      renderCartPage();
      showNotification(`Order placed! Transaction ID: ${data.transaction_id} — Total: ${formatCurrency(Number(data.total_amount)||0)}`, 'success');

    } catch (err) {
      console.error('Checkout error:', err);
      showNotification('Network error during checkout.', 'error');
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
    refreshBag().catch(() => { updateCartBadge(); });

    if (document.getElementById('cartContainer')) {
      refreshBag().then(() => {
        renderCartPage();
      }).catch(() => {
        renderCartPage();
      });
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
    const reportForm=document.getElementById('reportForm');
    if(reportForm){
      const runBtn=document.getElementById('runBtn');
      if(runBtn){
        runBtn.addEventListener('click',async()=>{
          const params=formToParams(reportForm);
          const res=await fetch('/reports/query',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:params});
          const html=await res.text();
          if(typeof renderResults==='function'){renderResults(html);}else{const box=document.getElementById('reportResults');if(box){box.innerHTML=html;box.style.display='block';}}
        });
      }
      const csvBtn=document.getElementById('csvBtn');
      if(csvBtn){
        csvBtn.addEventListener('click',()=>{
          const params=formToParams(reportForm);
          window.location='/reports/csv?'+params.toString();
        });
      }
    }
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    (function () {
      const form = document.getElementById('reportForm');
      const runBtn = document.getElementById('runBtn');
      const results = document.getElementById('reportResults');
      if (!form || !runBtn || !results) return;
    
      function val(id) {
        const el = document.getElementById(id);
        return el ? (el.value || '').trim() : '';
      }
    
      async function runReport() {
        const payload = {
          date_from: val('date_from'),
          date_to: val('date_to'),
          department_id: val('department_id'),
          employee_id: val('employee_id'),
          group_by: val('group_by') || 'product',
          min_qty: val('min_qty') || 0
        };
    
        results.innerHTML = '<div class="loading">Loading…</div>';
    
        try {
          const res = await fetch('/reports/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const html = await res.text();
          results.innerHTML = html;
        } catch (err) {
          console.error(err);
          results.innerHTML = '<div class="error">Could not load report. Please try again.</div>';
        }
      }
    
      runBtn.addEventListener('click', runReport);
    })();
  });

  // -------------------- Employee Report Filters & Sorting --------------------
  document.addEventListener('DOMContentLoaded', () => {
      const tableBody = document.getElementById('employeeTableBody');
      const filterBtn = document.getElementById('filterBtn');

      // --- Department dropdown ---
      const deptDropdown = document.getElementById('employeeDepartmentDropdown');
      const deptCheckboxes = document.querySelectorAll('.employee-dept-option');
      const deptHiddenInput = document.getElementById('employeeDepartment');
      const deptToggleBtn = deptDropdown ? deptDropdown.querySelector('.dropdown-toggle') : null;

      function updateDeptLabel() {
          const selected = Array.from(deptCheckboxes)
              .filter(ch => ch.checked)
              .map(ch => ch.value);
          deptHiddenInput.value = selected.join(',');

          if (!deptToggleBtn) return;
          if (selected.length === 0) {
              deptToggleBtn.textContent = 'Select Department ▼';
          } else if (selected.length <= 2) {
              deptToggleBtn.textContent = selected.join(', ');
          } else {
              deptToggleBtn.textContent = `${selected.length} selected`;
          }
      }

      deptCheckboxes.forEach(ch => ch.addEventListener('change', updateDeptLabel));

      document.getElementById('employeeSelectAllDepts').addEventListener('click', () => {
          deptCheckboxes.forEach(ch => ch.checked = true);
          updateDeptLabel();
      });

      document.getElementById('employeeClearAllDepts').addEventListener('click', () => {
          deptCheckboxes.forEach(ch => ch.checked = false);
          updateDeptLabel();
      });

      if (deptToggleBtn) {
          deptToggleBtn.addEventListener('click', (e) => {
              e.stopPropagation();
              deptDropdown.classList.toggle('open');
          });
      }

      document.addEventListener('click', (e) => {
          if (deptDropdown && !deptDropdown.contains(e.target)) {
              deptDropdown.classList.remove('open');
          }
      });

      updateDeptLabel();

      // --- Sorting ---
      let sortColumn = '';
      let sortOrder = '';

      async function fetchEmployees() {
          const payload = {
              department: deptHiddenInput.value.split(',').filter(Boolean),
              name: document.getElementById("name").value,
              job_title: document.getElementById("job_title").value,
              hire_date_from: document.getElementById("hire_date_from").value,
              hire_date_to: document.getElementById("hire_date_to").value,
              revenue_min: document.getElementById("revenue_min").value,
              revenue_max: document.getElementById("revenue_max").value,
              sort_column: sortColumn,
              sort_order: sortOrder
          };

          tableBody.innerHTML = '<tr><td colspan="8">Loading…</td></tr>';

          try {
              const res = await fetch("/api/employee_report", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify(payload)
              });
              if (!res.ok) throw new Error(`HTTP ${res.status}`);
              const data = await res.json();
              tableBody.innerHTML = data.html || '<tr><td colspan="8">No results found</td></tr>';
          } catch (err) {
              console.error(err);
              tableBody.innerHTML = '<tr><td colspan="8">Error loading report</td></tr>';
          }
      }

      filterBtn.addEventListener('click', fetchEmployees);

      // --- Sorting by table headers ---
      const sortableHeaders = document.querySelectorAll('.report-table th.sortable');
      sortableHeaders.forEach(th => {
          th.addEventListener('click', () => {
              const column = th.dataset.column;
              if (sortColumn === column) {
                  sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
              } else {
                  sortColumn = column;
                  sortOrder = 'asc';
              }
              sortableHeaders.forEach(h => h.classList.remove('asc', 'desc'));
              th.classList.add(sortOrder);
              fetchEmployees();
          });
      });
  });

  // -------------------- Product Overview Report Filters --------------------
  document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('productTableBody');
    const filterBtn = document.getElementById('productFilterBtn');
    const exportBtn = document.getElementById('productExportBtn');
    const printBtn = document.getElementById('productPrintBtn');
    const sortableHeaders = document.querySelectorAll('.report-table th.sortable'); // clickable headers

    const deptDropdown = document.getElementById('departmentDropdown');
    const deptCheckboxes = document.querySelectorAll('.dept-option');
    const deptHiddenInput = document.getElementById('department');
    const deptToggleBtn = deptDropdown ? deptDropdown.querySelector('.dropdown-toggle') : null;

    // --- Helper to update dropdown button label ---
    function updateDeptLabel() {
      const selected = Array.from(deptCheckboxes)
        .filter(ch => ch.checked)
        .map(ch => ch.value);

      deptHiddenInput.value = selected.join(',');

      if (!deptToggleBtn) return;
      if (selected.length === 0) {
        deptToggleBtn.textContent = 'Select Department ▼';
      } else if (selected.length <= 2) {
        deptToggleBtn.textContent = selected.join(', ');
      } else {
        deptToggleBtn.textContent = `${selected.length} selected`;
      }
    }

    // --- Department checkbox logic ---
    deptCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', updateDeptLabel);
    });

    // --- Select All / Clear All functionality ---
    const selectAllBtn = document.getElementById('selectAllDepts');
    const clearAllBtn = document.getElementById('clearAllDepts');

    if (selectAllBtn && clearAllBtn) {
      selectAllBtn.addEventListener('click', () => {
        deptCheckboxes.forEach(ch => ch.checked = true);
        updateDeptLabel();
      });

      clearAllBtn.addEventListener('click', () => {
        deptCheckboxes.forEach(ch => ch.checked = false);
        updateDeptLabel();
      });
    }

    // --- Dropdown open/close behavior ---
    if (deptToggleBtn) {
      deptToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation(); // prevent immediate close
        deptDropdown.classList.toggle('open');
      });
    }

    document.addEventListener('click', (e) => {
      if (deptDropdown && !deptDropdown.contains(e.target)) {
        deptDropdown.classList.remove('open');
      }
    });

    if (!tableBody) return;

    let sortColumn = '';
    let sortDirection = 'ASC';

    async function filterProductsServerSide() {
      const payload = {
        department: deptHiddenInput.value.split(',').filter(Boolean),
        product_name: document.getElementById("product_name").value,
        stock_status: document.getElementById("stock_status").value,
        on_sale: document.getElementById("on_sale").checked ? "Yes" : "All",
        min_price: document.getElementById("price_min").value,
        max_price: document.getElementById("price_max").value,
        qty_min: document.getElementById("qty_min").value,
        qty_max: document.getElementById("qty_max").value,
        restock_from: document.getElementById("restock_from").value,
        restock_to: document.getElementById("restock_to").value,
        sort_column: sortColumn,
        sort_direction: sortDirection
      };

      tableBody.innerHTML = '<tr><td colspan="12">Loading…</td></tr>';

      try {
        const res = await fetch("/api/product_report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        tableBody.innerHTML = data.html || '<tr><td colspan="12">No results found</td></tr>';
      } catch (err) {
        console.error(err);
        tableBody.innerHTML = '<tr><td colspan="12">Error loading report</td></tr>';
      }
    }

    // --- Button handlers ---
    filterBtn.addEventListener('click', filterProductsServerSide);
    exportBtn.addEventListener('click', () => {
      const params = new URLSearchParams({
        department: deptHiddenInput.value,
        product_name: document.getElementById("product_name").value,
        stock_status: document.getElementById("stock_status").value,
        on_sale: document.getElementById("on_sale").checked ? "Yes" : "All",
        min_price: document.getElementById("price_min").value,
        max_price: document.getElementById("price_max").value,
        qty_min: document.getElementById("qty_min").value,
        qty_max: document.getElementById("qty_max").value,
        restock_from: document.getElementById("restock_from").value,
        restock_to: document.getElementById("restock_to").value
      });
      window.location.href = `/reports/csv?${params.toString()}`;
    });
    printBtn.addEventListener('click', () => window.print());

    // --- Sortable header click logic ---
    sortableHeaders.forEach(header => {
      header.addEventListener('click', () => {
        const column = header.dataset.column;
        if (sortColumn === column) {
          sortDirection = sortDirection === 'ASC' ? 'DESC' : 'ASC';
        } else {
          sortColumn = column;
          sortDirection = 'ASC';
        }

        // Visual feedback (↑ / ↓ arrows)
        sortableHeaders.forEach(h => {
          h.textContent = h.textContent.replace(/ ↑| ↓/, '');
        });
        header.textContent += sortDirection === 'ASC' ? ' ↑' : ' ↓';

        filterProductsServerSide();
      });
    });

    // Initialize label text when page loads
    updateDeptLabel();
  });

  // -------------------- Customer Report Filters --------------------
  document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.getElementById("customerTableBody");
    const filterBtn = document.getElementById("customerFilterBtn");
    const exportBtn = document.getElementById("customerExportBtn");
    const printBtn = document.getElementById("customerPrintBtn");

    if (!tableBody) return;

    let sortColumn = "";
    let sortDirection = "asc";

    async function loadCustomerReport() {
      const payload = {
        customer_name: document.getElementById("customer_name").value.trim(),
        email: document.getElementById("email").value.trim(),
        date_from: document.getElementById("date_from").value,
        date_to: document.getElementById("date_to").value,
        total_spent_min: document.getElementById("total_spent_min").value,
        total_spent_max: document.getElementById("total_spent_max").value,
        sort_column: sortColumn,
        sort_direction: sortDirection
      };

      tableBody.innerHTML = '<tr><td colspan="8">Loading…</td></tr>';

      try {
        const res = await fetch("/api/customer_report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        tableBody.innerHTML = data.html || '<tr><td colspan="8">No results found</td></tr>';
      } catch (err) {
        console.error(err);
        tableBody.innerHTML = '<tr><td colspan="8">Error loading report</td></tr>';
      }
    }

    // Filter button
    filterBtn.addEventListener("click", loadCustomerReport);

    // Header sorting
    const headers = document.querySelectorAll(".sortable");
    headers.forEach(th => {
      th.addEventListener("click", () => {
        const column = th.dataset.column;
        if (sortColumn === column) {
          sortDirection = sortDirection === "asc" ? "desc" : "asc";
        } else {
          sortColumn = column;
          sortDirection = "asc";
        }

        headers.forEach(h => h.classList.remove("asc", "desc"));
        th.classList.add(sortDirection);

        loadCustomerReport();
      });
    });

    // Export CSV
    exportBtn.addEventListener("click", () => {
      const params = new URLSearchParams({
        customer_name: document.getElementById("customer_name").value,
        email: document.getElementById("email").value,
        date_from: document.getElementById("date_from").value,
        date_to: document.getElementById("date_to").value,
        total_spent_min: document.getElementById("total_spent_min").value,
        total_spent_max: document.getElementById("total_spent_max").value
      });
      window.location.href = `/reports/csv?${params.toString()}`;
    });

    // Print
    printBtn.addEventListener("click", () => window.print());
  });

  // -------------------- Global exports --------------------
  window.addToCart = addToCart;
  window.removeFromCart = removeFromCart;
  window.updateQuantity = updateQuantity;
  window.clearCart = clearCart;
  window.checkout = checkout;

  // -------------------- Shopping Lists (page logic) --------------------
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('listContainer');
    if (!container) return;
  
    let currentListId = null;
    let currentLists = [];

    async function sl_refreshListsUI() {
      const select = document.getElementById('listSelect');
      const delBtn = document.getElementById('deleteListBtn');
    
      const r = await fetch('/api/lists', { credentials: 'same-origin' });
      if (r.status === 401) { window.location.href = '/login'; return; }
      if (!r.ok) { alert('Failed to load lists'); return; }
    
      currentLists = await r.json();
      if (!currentLists.length) { select.innerHTML = ''; delBtn.disabled = true; return; }
    
      if (!currentListId) {
        const def = currentLists.find(l => l.IsDefault) || currentLists[0];
        currentListId = def.ListID;
      } else if (!currentLists.some(l => l.ListID === currentListId)) {
        currentListId = (currentLists.find(l => l.IsDefault) || currentLists[0]).ListID;
      }
    
      select.innerHTML = currentLists.map(l =>
        `<option value="${l.ListID}" ${l.ListID === currentListId ? 'selected' : ''}>
           ${l.Name}${l.IsDefault ? ' (default)' : ''}
         </option>`).join('');
    
      const selected = currentLists.find(l => l.ListID === currentListId);
      delBtn.disabled = !selected || !!selected.IsDefault;
    }
    
    function sl_selectedIsDefault() {
      const selected = currentLists.find(l => l.ListID === currentListId);
      return !!(selected && selected.IsDefault);
    }
  
    async function sl_getDefaultListId() {
      const r = await fetch('/api/lists', { credentials: 'same-origin' });
      if (r.status === 401) { window.location.href = '/login'; return null; }
      if (!r.ok) return null;
      const lists = await r.json();
      if (!lists.length) return null;
      const def = lists.find(l => l.IsDefault) || lists[0];
      return def.ListID;
    }
  
    async function sl_loadItems() {
      if (!currentListId) return;
      const r = await fetch(`/api/lists/${currentListId}/items`, { credentials: 'same-origin' });
      if (!r.ok) return;
      const items = await r.json();
      sl_render(items);
    }
  
    function sl_render(items) {
      const wrap = document.getElementById('listTableWrap');
      const empty = document.getElementById('emptyListText');
      if (!items.length) {
        empty.style.display = '';
        wrap.innerHTML = '';
        return;
      }
      empty.style.display = 'none';
      const rows = items.map(it => `
        <tr data-product-id="${it.ProductID}">
          <td>${it.Name}</td>
          <td>$${(Number(it.Price)||0).toFixed(2)}</td>
          <td class="qtycell">
            <button class="qty-dec" aria-label="decrease">−</button>
            <span class="qty">${it.Quantity}</span>
            <button class="qty-inc" aria-label="increase">+</button>
          </td>
          <td><button class="remove">Remove</button></td>
        </tr>
      `).join('');
      wrap.innerHTML = `
        <table class="table">
          <thead><tr><th>Item</th><th>Price</th><th>Qty</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }
  
    // Event delegation for + / − / remove
    document.getElementById('listTableWrap').addEventListener('click', async (e) => {
      const row = e.target.closest('tr[data-product-id]');
      if (!row) return;
      const pid = row.getAttribute('data-product-id');
  
      if (e.target.classList.contains('qty-inc')) {
        const newQty = Number(row.querySelector('.qty').textContent) + 1;
        await fetch(`/api/lists/${currentListId}/items/${pid}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ quantity: newQty })
        });
        sl_loadItems();
  
      } else if (e.target.classList.contains('qty-dec')) {
        const newQty = Math.max(0, Number(row.querySelector('.qty').textContent) - 1);
        if (newQty === 0) {
          await fetch(`/api/lists/${currentListId}/items/${pid}`, { method: 'DELETE', credentials: 'same-origin' });
        } else {
          await fetch(`/api/lists/${currentListId}/items/${pid}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ quantity: newQty })
          });
        }
        
        sl_loadItems();
  
      } else if (e.target.classList.contains('remove')) {
        await fetch(`/api/lists/${currentListId}/items/${pid}`, { method: 'DELETE', credentials: 'same-origin' });
        sl_loadItems();
      }
    });

    document.getElementById('listSelect').addEventListener('change', async (e) => {
      currentListId = Number(e.target.value);
      await sl_refreshListsUI(); // updates delete button state
      await sl_loadItems();
    });
    
    document.getElementById('createListBtn').addEventListener('click', async () => {
      const name = prompt('Name for the new list:');
      if (!name || !name.trim()) return;
      const r = await fetch('/api/lists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ name: name.trim() })
      });
      if (!r.ok) {
        const data = await r.json().catch(() => ({}));
        alert(data.message || 'Could not create list.');
        return;
      }
      await sl_refreshListsUI();
      await sl_loadItems();
    });
    
    document.getElementById('deleteListBtn').addEventListener('click', async () => {
      if (sl_selectedIsDefault()) { alert('Cannot delete the default list.'); return; }
      if (!confirm('Delete this list?')) return;
    
      const r = await fetch(`/api/lists/${currentListId}`, {
        method: 'DELETE',
        credentials: 'same-origin'
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) { alert(data.message || 'Could not delete list.'); return; }
    
      await sl_refreshListsUI();
      await sl_loadItems();
    });
  
    document.getElementById('addListToCartBtn').addEventListener('click', async () => {
      await fetch(`/api/lists/${currentListId}/add-to-bag`, { method: 'POST', credentials: 'same-origin' });
      if (typeof refreshBag === 'function') {
        await refreshBag();
        if (typeof updateCartBadge === 'function') updateCartBadge();
      }
    });
  
    document.getElementById('clearListBtn').addEventListener('click', async () => {
      if (!confirm('Clear your list?')) return;
      await fetch(`/api/lists/${currentListId}/items`, { method: 'DELETE', credentials: 'same-origin' });
      sl_loadItems();
    });
  
    (async () => {
      await sl_refreshListsUI();
      await sl_loadItems();
    })();
  });
  
  async function addToList(productId, qty = 1) {
    const r = await fetch('/api/lists', { credentials: 'same-origin' });
    if (r.status === 401) { window.location.href = '/login'; return; }
    if (!r.ok) { alert('Failed to load lists'); return; }
  
    const lists = await r.json();
    if (!lists.length) { alert('No shopping lists found.'); return; }
  
    const menu = lists.map((l, i) => `${i + 1}. ${l.Name}${l.IsDefault ? ' (default)' : ''}`).join('\n');
    const choice = prompt(`Add to which list?\n${menu}`);
    if (choice == null) return;
    const idx = parseInt(choice, 10) - 1;
  
    const target = lists[idx];
    if (!target) { alert('Invalid selection.'); return; }
  
    const res = await fetch(`/api/lists/${target.ListID}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ product_id: productId, quantity: qty })
    });
  
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.message || 'Failed to save to list');
      return;
    }
    alert('Saved to list!');
  }

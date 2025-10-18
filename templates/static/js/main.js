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

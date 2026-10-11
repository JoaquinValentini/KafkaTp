const form = document.querySelector("#order-form");
const output = document.querySelector("#orders");
const feedback = document.querySelector("#feedback");

function render(orders) {
  if (!orders.length) {
    output.innerHTML = '<p class="muted">Todavía no hay pedidos.</p>';
    return;
  }
  output.innerHTML = orders.map(order => `
    <article class="order">
      <div class="order-head"><strong>${order.id}</strong><span class="status status-${order.status}">${order.status}</span></div>
      <p>${order.product} × ${order.quantity} · ${order.customer} · $ ${Number(order.price).toLocaleString("es-AR")}</p>
      <div class="timeline">${order.status_history.map(step => `<span class="step"><b>${step.status}</b><small>${new Date(step.at).toLocaleTimeString()}</small></span>`).join("")}</div>
    </article>`).join("");
}

async function refresh() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("API no disponible");
    render((await response.json()).orders);
    document.querySelector("#connection").textContent = "● conectado";
  } catch (error) {
    document.querySelector("#connection").textContent = "● desconectado";
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const payload = {
    customer: document.querySelector("#customer").value.trim(),
    product: document.querySelector("#product").value.trim(),
    quantity: Number(document.querySelector("#quantity").value),
    price: Number(document.querySelector("#price").value),
    payment_decision: document.querySelector("#payment-decision").value
  };
  try {
    const response = await fetch("/orders", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "No se pudo publicar");
    feedback.textContent = `✓ ${data.order_id} publicado en orders`;
    await refresh();
  } catch (error) {
    feedback.textContent = `Error: ${error.message}`;
  }
});

refresh();
setInterval(refresh, 1000);

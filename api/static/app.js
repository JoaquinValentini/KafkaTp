const form = document.querySelector("#order-form");
const output = document.querySelector("#orders");
const feedback = document.querySelector("#feedback");
const connection = document.querySelector("#connection").parentElement;
const app = document.querySelector("#app");
const detail = document.querySelector("#order-detail");
const detailTitle = document.querySelector("#detail-title");
const activityLog = document.querySelector("#activity-log");
let lastOrdersSnapshot = "";
let currentOrders = [];
let selectedOrderId = null;
let paymentsPaused = false;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[character]));
}

function updateMetrics(orders) {
  document.querySelector("#metric-total").textContent = orders.length;
  document.querySelector("#metric-approved").textContent = orders.filter(order => order.status_history.some(step => step.status === "PAYMENT_APPROVED")).length;
  document.querySelector("#metric-rejected").textContent = orders.filter(order => order.status_history.some(step => step.status === "PAYMENT_REJECTED")).length;
  document.querySelector("#metric-notifications").textContent = orders.filter(order => order.status === "NOTIFICATION_SENT").length;
}

function renderDetail(order) {
  if (!order) {
    detailTitle.textContent = "Seleccioná un pedido";
    detail.innerHTML = '<p class="detail-empty">Hacé clic en una tarjeta para ver sus datos.</p>';
    return;
  }
  detailTitle.textContent = order.id;
  detail.innerHTML = `<div class="detail-grid">
    <div class="detail-item"><small>CLIENTE</small><b>${escapeHtml(order.customer)}</b></div>
    <div class="detail-item"><small>PRODUCTO</small><b>${escapeHtml(order.product)}</b></div>
    <div class="detail-item"><small>CANTIDAD</small><b>${order.quantity}</b></div>
    <div class="detail-item"><small>TOTAL</small><b>$ ${(order.price * order.quantity).toLocaleString("es-AR")}</b></div>
    <div class="detail-item"><small>DECISIÓN DE PAGO</small><b>${order.payment_decision === "APPROVED" ? "Aprobado" : "Rechazado"}</b></div>
    <div class="detail-item"><small>ESTADO ACTUAL</small><b>${escapeHtml(order.status)}</b></div>
  </div>`;
}

function renderActivity(orders) {
  const entries = orders.flatMap(order => order.status_history.map(step => ({...step, id: order.id})))
    .sort((a, b) => new Date(b.at) - new Date(a.at)).slice(0, 12);
  activityLog.innerHTML = entries.length ? entries.map(entry => `<div class="log-entry"><b>${escapeHtml(entry.status)}</b> · ${escapeHtml(entry.id)}<small>${new Date(entry.at).toLocaleTimeString()}</small></div>`).join("") : '<p class="muted">Todavía no hay actividad.</p>';
}

function render(orders) {
  updateMetrics(orders);
  renderActivity(orders);
  const filter = document.querySelector("#status-filter").value;
  const visibleOrders = filter === "ALL" ? orders : orders.filter(order => order.status === filter || order.status_history.some(step => step.status === filter));
  if (!visibleOrders.length) {
    output.innerHTML = '<p class="empty-state"><span>⚡</span><b>No hay pedidos con este filtro</b><small>Probá crear otro evento o seleccioná “Todos”.</small></p>';
    return;
  }
  output.innerHTML = visibleOrders.map(order => `
    <article class="order${order.id === selectedOrderId ? " selected" : ""}" data-order-id="${escapeHtml(order.id)}">
      <div class="order-head"><strong>${escapeHtml(order.id)}</strong><span class="status status-${escapeHtml(order.status)}">${escapeHtml(order.status)}</span></div>
      <p>${escapeHtml(order.product)} × ${order.quantity} · ${escapeHtml(order.customer)} · $ ${(order.price * order.quantity).toLocaleString("es-AR")}</p>
      <div class="timeline">${order.status_history.map(step => `<span class="step"><b>${escapeHtml(step.status)}</b><small>${new Date(step.at).toLocaleTimeString()}</small></span>`).join("")}</div>
    </article>`).join("");
  output.querySelectorAll("[data-order-id]").forEach(card => card.addEventListener("click", () => {
    selectedOrderId = card.dataset.orderId;
    render(currentOrders);
    renderDetail(currentOrders.find(order => order.id === selectedOrderId));
  }));
}

async function refresh() {
  try {
    const response = await fetch("/api/status", {cache: "no-store"});
    if (!response.ok) throw new Error("API no disponible");
    const data = await response.json();
    currentOrders = data.orders;
    paymentsPaused = data.payments_paused;
    updatePaymentsControl();
    const snapshot = JSON.stringify(currentOrders);
    updateMetrics(currentOrders);
    renderActivity(currentOrders);
    if (snapshot !== lastOrdersSnapshot) {
      render(currentOrders);
      lastOrdersSnapshot = snapshot;
    }
    if (selectedOrderId) renderDetail(currentOrders.find(order => order.id === selectedOrderId));
    connection.className = "connection-card online";
    document.querySelector("#connection").textContent = "Conectado";
  } catch (error) {
    connection.className = "connection-card offline";
    document.querySelector("#connection").textContent = "Desconectado";
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const submitButton = form.querySelector("button");
  submitButton.disabled = true;
  submitButton.querySelector("span").textContent = "Publicando...";
  feedback.className = "feedback";
  const payload = {customer: document.querySelector("#customer").value.trim(), product: document.querySelector("#product").value.trim(), quantity: Number(document.querySelector("#quantity").value), price: Number(document.querySelector("#price").value), payment_decision: document.querySelector("#payment-decision").value};
  try {
    const response = await fetch("/orders", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "No se pudo publicar");
    feedback.textContent = `✓ ${data.order_id} publicado en orders`;
    await refresh();
  } catch (error) {
    feedback.className = "feedback error";
    feedback.textContent = `Error: ${error.message}`;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector("span").textContent = "Publicar evento";
  }
});

function updatePaymentsControl() {
  const button = document.querySelector("#payments-toggle");
  const help = document.querySelector("#payments-control-help");
  button.textContent = paymentsPaused ? "Reanudar payments" : "Pausar payments";
  button.classList.toggle("resume-button", paymentsPaused);
  help.textContent = paymentsPaused
    ? "Payments está pausado. Los pedidos nuevos quedan en orders hasta que lo reanudes."
    : "Pausá el consumidor, publicá un pedido y reanudalo para ver cómo Kafka conserva el mensaje.";
}

document.querySelector("#payments-toggle").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const action = paymentsPaused ? "resume" : "pause";
    const response = await fetch(`/api/services/payments/${action}`, {method: "POST"});
    if (!response.ok) throw new Error("No se pudo cambiar el estado de payments");
    await refresh();
    feedback.className = "feedback";
    feedback.textContent = paymentsPaused ? "✓ Payments reanudado; Kafka procesará los pendientes" : "✓ Payments pausado; los mensajes quedan en Kafka";
  } catch (error) {
    feedback.className = "feedback error";
    feedback.textContent = `Error: ${error.message}`;
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#status-filter").addEventListener("change", () => render(currentOrders));
document.querySelector("#refresh").addEventListener("click", refresh);
document.querySelector("#presentation-toggle").addEventListener("click", event => {
  app.classList.toggle("presentation-mode");
  event.target.textContent = app.classList.contains("presentation-mode") ? "Salir del modo presentación" : "Activar modo presentación";
});
document.querySelector("#clear-demo").addEventListener("click", async () => {
  if (!confirm("¿Querés borrar todos los pedidos de esta demo?")) return;
  const response = await fetch("/api/orders", {method: "DELETE"});
  if (!response.ok) {
    feedback.className = "feedback error";
    feedback.textContent = "No se pudo limpiar la demo";
    return;
  }
  selectedOrderId = null;
  lastOrdersSnapshot = "";
  feedback.className = "feedback";
  feedback.textContent = "✓ Demo reiniciada";
  await refresh();
});

refresh();
setInterval(refresh, 1000);

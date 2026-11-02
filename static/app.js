let appState = null;
let pendingVetoContext = null;

function esc(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const icon = type === "error" ? "⚠️" : type === "success" ? "✅" : "🍽️";
  el.innerHTML = `<span>${icon}</span><span>${esc(message)}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.25s ease";
    setTimeout(() => el.remove(), 260);
  }, 3600);
}

async function apiCall(url, options = {}) {
  const defaultHeaders = { "Content-Type": "application/json" };
  const res = await fetch(url, {
    ...options,
    headers: { ...defaultHeaders, ...(options.headers || {}) }
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || "Error en la operación");
  }
  return data;
}

function isOverrideEnabled() {
  const c1 = document.getElementById("chk-override-window");
  const c2 = document.getElementById("chk-override-window-mobile");
  return Boolean((c1 && c1.checked) || (c2 && c2.checked));
}

function syncOverrideCheckboxes(source) {
  const c1 = document.getElementById("chk-override-window");
  const c2 = document.getElementById("chk-override-window-mobile");
  if (source === c1 && c2) c2.checked = c1.checked;
  if (source === c2 && c1) c1.checked = c2.checked;
}

function renderAll(state) {
  appState = state;

  // 1. Cabecera y KPIs
  document.getElementById("hero-cycle-desc").textContent = `Aplicación privada para Álvaro & Ana • ${state.cycle_desc}`;
  const m = state.metrics;
  document.getElementById("kpi-alvaro-vetos").textContent = `${m.alvaro_vetos_left} / ${m.veto_limit}`;
  document.getElementById("kpi-ana-vetos").textContent = `${m.ana_vetos_left} / ${m.veto_limit}`;
  document.getElementById("kpi-manual-regen").textContent = `${m.manual_regens_left} / 1`;
  document.getElementById("kpi-freezer").textContent = `${m.frozen_available} / ${m.frozen_total}`;
  document.getElementById("kpi-coupons").textContent = `${m.pending_coupons}`;

  const kpiCouponsSub = document.getElementById("kpi-coupons-sub");
  if (m.expiring_coupons > 0) {
    kpiCouponsSub.textContent = `${m.expiring_coupons} por caducar`;
    kpiCouponsSub.style.color = "var(--danger)";
  } else {
    kpiCouponsSub.textContent = "Pendientes";
    kpiCouponsSub.style.color = "var(--text-muted)";
  }

  // Pills de navegación
  const pendingShopCount = state.shopping.ingredients.length - state.shopping.checked.length;
  document.getElementById("nav-pill-shopping").textContent = pendingShopCount;
  document.getElementById("nav-pill-freezer").textContent = m.frozen_available;
  document.getElementById("nav-pill-coupons").textContent = m.pending_coupons;
  document.getElementById("nav-pill-dishes").textContent = state.dishes.length;

  // Botón regenerar
  const btnRegen = document.getElementById("btn-hero-regen");
  if (m.manual_regens_left > 0) {
    btnRegen.disabled = false;
    btnRegen.textContent = "🎲 Regenerar Menú (1 disp.)";
  } else {
    btnRegen.disabled = true;
    btnRegen.textContent = "🔒 Regen. Agotada (0/1)";
  }

  // Alerta de cupones próximos a vencer
  const expBanner = document.getElementById("expiring-alert-banner");
  if (m.expiring_coupons > 0) {
    expBanner.style.display = "block";
    expBanner.innerHTML = `⚠️ <strong>Atención:</strong> Tienes <strong>${m.expiring_coupons} cupón(es)</strong> a punto de caducar o caducados. Revisa la pestaña de Cupones.`;
  } else {
    expBanner.style.display = "none";
  }

  // Ventana de vetos
  const vw = state.veto_window;
  const sideCard = document.getElementById("sidebar-window-card");
  const menuWinBanner = document.getElementById("menu-window-banner");
  if (vw.is_open) {
    sideCard.className = "window-status-card open";
    sideCard.innerHTML = `🟢 <strong>Plazo ABIERTO</strong><br/>${esc(vw.message)}`;
    menuWinBanner.innerHTML = `🟢 <span style="color:#047857;">Plazo de cambios ABIERTO:</span> ${esc(vw.message)}`;
  } else {
    sideCard.className = "window-status-card closed";
    sideCard.innerHTML = `🔒 <strong>Plazo CERRADO</strong><br/>Finalizó el domingo a las 16:00.`;
    menuWinBanner.innerHTML = `🔒 <span style="color:#B45309;">Menú Confirmado (Plazo cerrado):</span> Finalizó el domingo a las 16:00.`;
  }

  renderMenuTab(state);
  renderShoppingTab(state);
  renderFreezerTab(state);
  renderVetosTab(state);
  renderCouponsTab(state);
  renderDishesTab(state);
  renderSettingsTab(state);
}

function renderMenuTab(state) {
  const container = document.getElementById("menu-days-container");
  container.innerHTML = state.menu.map((d) => {
    const banners = [];
    if (d.is_holiday) {
      banners.push(`
        <div class="holiday-banner">
          🎉 <strong>¡DÍA FESTIVO!</strong> ${esc(d.holiday_name || "Festivo oficial")} • <em>Comida elaborada / especial recomendada</em>
        </div>
      `);
    }
    if (d.events && d.events.length > 0) {
      d.events.forEach((ev) => {
        const timeTag = ev.time ? ` (${esc(ev.time)})` : "";
        banners.push(`
          <div class="event-banner">
            🗓️ <strong>Evento AyA:</strong> ${esc(ev.summary)}${timeTag}
          </div>
        `);
      });
    }

    const elaborateBadge = d.is_festive ? `<span class="badge badge-elaborate">🍲 Elaborada</span>` : "";
    const comidaFreezerBadge = d.comida.in_freezer ? `<span class="badge badge-freezer">🧊 En congelador</span>` : "";
    const cenaFreezerBadge = d.cena.in_freezer ? `<span class="badge badge-freezer">🧊 En congelador</span>` : "";

    return `
      <article class="day-block ${d.is_holiday ? "holiday-border" : ""}">
        <div class="day-header">
          <div class="day-title">
            <span>📍 ${esc(d.day)}</span>
            ${d.date_str ? `<span class="day-date-pill">${esc(d.date_str)}</span>` : ""}
          </div>
        </div>
        ${banners.length ? `<div class="banners-stack">${banners.join("")}</div>` : ""}
        <div class="meals-grid">
          <!-- Comida -->
          <div class="meal-card">
            <div>
              <div class="meal-badges">
                <span class="badge badge-lunch">☀️ ALMUERZO</span>
                ${elaborateBadge}
                ${comidaFreezerBadge}
              </div>
              <div class="meal-name">${esc(d.comida.name || "No asignado")}</div>
              <div class="meal-ingredients"><strong>Ingredientes:</strong> ${esc(d.comida.ingredients || "Sin ingredientes")}</div>
            </div>
            <div class="meal-footer">
              <button class="btn btn-outline btn-sm" onclick="openVetoModal('${esc(d.day)}', 'comida', '${esc(d.comida.name || "")}')">
                🚫 Vetar comida
              </button>
              ${d.comida.gcal_url ? `<a href="${esc(d.comida.gcal_url)}" target="_blank" rel="noopener" style="font-size:0.78rem; color:var(--primary); text-decoration:none; font-weight:600;">📅 +Google Cal</a>` : ""}
            </div>
          </div>

          <!-- Cena -->
          <div class="meal-card">
            <div>
              <div class="meal-badges">
                <span class="badge badge-dinner">🌙 CENA</span>
                ${cenaFreezerBadge}
              </div>
              <div class="meal-name">${esc(d.cena.name || "No asignado")}</div>
              <div class="meal-ingredients"><strong>Ingredientes:</strong> ${esc(d.cena.ingredients || "Sin ingredientes")}</div>
            </div>
            <div class="meal-footer">
              <button class="btn btn-outline btn-sm" onclick="openVetoModal('${esc(d.day)}', 'cena', '${esc(d.cena.name || "")}')">
                🚫 Vetar cena
              </button>
              ${d.cena.gcal_url ? `<a href="${esc(d.cena.gcal_url)}" target="_blank" rel="noopener" style="font-size:0.78rem; color:var(--primary); text-decoration:none; font-weight:600;">📅 +Google Cal</a>` : ""}
            </div>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function renderShoppingTab(state) {
  const { ingredients, checked, breakdown } = state.shopping;
  const checkedSet = new Set(checked);

  document.getElementById("shopping-summary-text").innerHTML =
    `Total ingredientes distintos: <strong>${ingredients.length}</strong> • Comprados / En carrito: <strong>${checked.length} / ${ingredients.length}</strong>`;

  const grid = document.getElementById("shopping-items-grid");
  if (!ingredients.length) {
    grid.innerHTML = `<p style="color:var(--text-muted);">No hay ingredientes registrados en el menú actual.</p>`;
  } else {
    grid.innerHTML = ingredients.map((ing) => {
      const isChecked = checkedSet.has(ing);
      return `
        <label class="shop-item ${isChecked ? "checked" : ""}">
          <input type="checkbox" ${isChecked ? "checked" : ""} onchange="toggleShoppingItem('${esc(ing)}', this.checked)" />
          <span>${esc(ing)}</span>
        </label>
      `;
    }).join("");
  }

  const tbody = document.getElementById("shopping-breakdown-tbody");
  tbody.innerHTML = breakdown.map((b) => `
    <tr>
      <td><strong>${esc(b.day)}</strong></td>
      <td>${esc(b.dish)}</td>
      <td style="color:var(--text-secondary);">${esc(b.ingredients)}</td>
    </tr>
  `).join("");
}

function renderFreezerTab(state) {
  const grid = document.getElementById("freezer-items-grid");
  const items = state.freezer.items;
  if (!items.length) {
    grid.innerHTML = `<p style="color:var(--text-muted);">No hay alimentos registrados en la hoja congelador.</p>`;
    return;
  }

  grid.innerHTML = items.map((it) => {
    const matchedText = it.matched_dishes.length ? it.matched_dishes.join(", ") : "Sin platos directos vinculados";
    const statusBadge = it.available
      ? `<span class="badge" style="background:var(--success-soft); color:#047857;">🟢 DISPONIBLE (Sí)</span>`
      : `<span class="badge" style="background:var(--danger-soft); color:#B91C1C;">🔴 AGOTADO (No)</span>`;
    const btnClass = it.available ? "btn-outline" : "btn-primary";
    const btnLabel = it.available ? "Marcar NO" : "Marcar SÍ";

    return `
      <div class="freezer-item-card">
        <div>
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <strong style="font-size:0.98rem;">🍲 ${esc(it.name)}</strong>
            ${statusBadge}
          </div>
          <div style="font-size:0.78rem; color:var(--text-muted); margin-top:6px;">
            <em>Habilita:</em> ${esc(matchedText)}
          </div>
        </div>
        <button class="btn ${btnClass} btn-sm" onclick="toggleFreezerItem('${esc(it.name)}')">
          ${btnLabel}
        </button>
      </div>
    `;
  }).join("");
}

function renderVetosTab(state) {
  const tbody = document.getElementById("vetos-history-tbody");
  const history = state.veto_window.history || [];
  if (!history.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">Aún no se ha aplicado ningún veto.</td></tr>`;
    return;
  }

  tbody.innerHTML = history.map((h) => `
    <tr>
      <td>${esc(h.timestamp)}</td>
      <td><span class="badge ${h.user === "Álvaro" ? "badge-alvaro" : "badge-ana"}">${esc(h.user)}</span></td>
      <td><strong>${esc(h.day)}</strong></td>
      <td>${esc(h.meal_type)}</td>
      <td style="text-decoration:line-through; color:var(--text-muted);">${esc(h.old_dish)}</td>
      <td style="font-weight:700; color:var(--success);">${esc(h.new_dish)}</td>
    </tr>
  `).join("");
}

function renderCouponsTab(state) {
  const userFilter = document.getElementById("filter-coupon-user").value;
  const statusFilter = document.getElementById("filter-coupon-status").value;

  let list = state.coupons || [];
  if (userFilter !== "Todos") {
    list = list.filter((c) => c.user === userFilter);
  }
  if (statusFilter !== "Todos") {
    list = list.filter((c) => c.status === statusFilter);
  }

  const grid = document.getElementById("coupons-list-grid");
  if (!list.length) {
    grid.innerHTML = `<p style="color:var(--text-muted);">No hay cupones que coincidan con el filtro seleccionado.</p>`;
    return;
  }

  grid.innerHTML = list.map((c) => {
    const isUsed = c.status === "usado";
    const userBadge = c.user === "Álvaro" ? "badge-alvaro" : "badge-ana";
    return `
      <div class="coupon-card ${isUsed ? "used" : ""}">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
            <span class="badge ${userBadge}">👤 ${esc(c.user)}</span>
            <span style="font-size:0.78rem; font-weight:700; color:${esc(c.exp_color)};">⏳ ${esc(c.exp_msg)}</span>
          </div>
          <h4 style="margin-top:10px; font-size:1.05rem; ${isUsed ? "text-decoration:line-through;" : ""}">${esc(c.title)}</h4>
          <p style="font-size:0.85rem; font-weight:600; color:var(--text-secondary); margin-top:4px;">
            📍 ${esc(c.restaurant || "No especificado")}
          </p>
          ${c.notes ? `<p style="font-size:0.8rem; color:var(--text-muted); margin-top:6px;">📝 <em>${esc(c.notes)}</em></p>` : ""}
        </div>
        <div style="display:flex; justify-content:space-between; gap:8px; padding-top:10px; border-top:1px solid var(--border-color);">
          <button class="btn btn-outline btn-sm" onclick="toggleCoupon('${esc(c.id)}')">
            ${isUsed ? "↩️ Reactivar" : "✅ Marcar Canjeado"}
          </button>
          <button class="btn btn-danger-soft btn-sm" onclick="deleteCoupon('${esc(c.id)}')">
            🗑️ Eliminar
          </button>
        </div>
      </div>
    `;
  }).join("");
}

function renderDishesTab(state) {
  const query = (document.getElementById("search-dishes-input").value || "").toLowerCase().trim();
  const typeFilter = document.getElementById("filter-dishes-type").value;

  let list = state.dishes || [];
  document.getElementById("dishes-count-subtitle").textContent =
    `Actualmente hay ${list.length} platos registrados en el catálogo.`;

  if (typeFilter !== "Todos") {
    list = list.filter((d) => (d.type || "").toLowerCase() === typeFilter.toLowerCase());
  }
  if (query) {
    list = list.filter(
      (d) =>
        (d.name || "").toLowerCase().includes(query) ||
        (d.ingredients || "").toLowerCase().includes(query)
    );
  }

  const tbody = document.getElementById("dishes-catalog-tbody");
  if (!list.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No se encontraron recetas con ese criterio.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map((d) => {
    const t = (d.type || "ambas").toLowerCase();
    const badgeClass = t === "comida" ? "badge-lunch" : t === "cena" ? "badge-dinner" : "badge-freezer";
    return `
      <tr>
        <td><strong>${esc(d.name)}</strong></td>
        <td><span class="badge ${badgeClass}">${esc(t.toUpperCase())}</span></td>
        <td style="color:var(--text-secondary);">${esc(d.ingredients || "Sin ingredientes")}</td>
        <td>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-outline btn-sm" onclick="openEditDishModal('${esc(d.id)}')">✏️</button>
            <button class="btn btn-danger-soft btn-sm" onclick="deleteDish('${esc(d.id)}', '${esc(d.name)}')">🗑️</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function renderSettingsTab(state) {
  const s = state.settings.saved;
  const sec = state.settings.secrets_active;

  const sheetInput = document.getElementById("set-sheet-url");
  sheetInput.value = s.sheet_url || "";
  sheetInput.placeholder = sec.sheet_url ? "Activo vía secrets.toml / variables de entorno" : "https://docs.google.com/spreadsheets/d/...";

  document.getElementById("set-gid-dishes").value = s.sheet_gid_dishes || "83672031";
  document.getElementById("set-gid-freezer").value = s.sheet_gid_freezer || "797240193";
  document.getElementById("set-smtp-host").value = s.smtp_host || "smtp.gmail.com";
  document.getElementById("set-smtp-port").value = s.smtp_port || 587;

  const userInput = document.getElementById("set-smtp-user");
  userInput.value = s.smtp_user || "";
  userInput.placeholder = sec.smtp_user ? "Activo vía secrets.toml / entorno" : "tu_correo@gmail.com";

  const passInput = document.getElementById("set-smtp-pass");
  passInput.value = "";
  passInput.placeholder = sec.smtp_password || s.has_saved_password ? "•••••••• (Configurada de forma segura)" : "Contraseña de aplicación de 16 letras";

  const recInput = document.getElementById("set-recipients");
  recInput.value = s.recipients || "";
  recInput.placeholder = sec.recipients ? "Activos vía secrets.toml / entorno" : "correo1@gmail.com, correo2@gmail.com";

  const calInput = document.getElementById("set-calendar-ics");
  calInput.value = s.calendar_ics_url || "";
  calInput.placeholder = sec.calendar_ics_url ? "Activo vía secrets.toml / entorno" : "https://calendar.google.com/calendar/ical/.../basic.ics";
}

// --- Acciones Interactivas ---

window.openVetoModal = function (day, mealType, currentDishName) {
  pendingVetoContext = { day, meal_type: mealType };
  document.getElementById("modal-veto-title").textContent = `🚫 Vetar ${mealType} del ${day}`;
  document.getElementById("modal-veto-desc").innerHTML =
    `Se sustituirá <strong>${esc(currentDishName)}</strong> por una alternativa aleatoria válida respetando el congelador.`;
  document.getElementById("modal-veto").classList.add("open");
};

async function submitVeto(user) {
  if (!pendingVetoContext) return;
  try {
    const res = await apiCall("/api/menu/veto", {
      method: "POST",
      body: JSON.stringify({
        user,
        day: pendingVetoContext.day,
        meal_type: pendingVetoContext.meal_type,
        override_window: isOverrideEnabled()
      })
    });
    document.getElementById("modal-veto").classList.remove("open");
    renderAll(res.state);
    showToast(res.message, "success");
  } catch (err) {
    showToast(err.message, "error");
  }
}

window.toggleShoppingItem = async function (ingredient, isChecked) {
  if (!appState) return;
  const currentSet = new Set(appState.shopping.checked);
  if (isChecked) currentSet.add(ingredient);
  else currentSet.delete(ingredient);

  const updatedChecked = Array.from(currentSet);
  appState.shopping.checked = updatedChecked;
  renderShoppingTab(appState);

  try {
    const res = await apiCall("/api/shopping/checked", {
      method: "PUT",
      body: JSON.stringify({ checked: updatedChecked })
    });
    renderAll(res.state);
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.toggleFreezerItem = async function (itemName) {
  try {
    const res = await apiCall("/api/freezer/toggle", {
      method: "POST",
      body: JSON.stringify({ item_name: itemName })
    });
    renderAll(res.state);
    showToast(res.message, "success");
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.toggleCoupon = async function (couponId) {
  try {
    const res = await apiCall(`/api/coupons/${encodeURIComponent(couponId)}/toggle`, { method: "PATCH" });
    renderAll(res.state);
    showToast(res.message, "success");
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.deleteCoupon = async function (couponId) {
  try {
    const res = await apiCall(`/api/coupons/${encodeURIComponent(couponId)}`, { method: "DELETE" });
    renderAll(res.state);
    showToast(res.message, "info");
  } catch (err) {
    showToast(err.message, "error");
  }
};

window.openEditDishModal = function (dishId) {
  if (!appState) return;
  const dish = appState.dishes.find((d) => String(d.id) === String(dishId));
  if (!dish) return;
  document.getElementById("modal-dish-title").textContent = "✏️ Editar Plato";
  document.getElementById("dish-edit-id").value = dish.id;
  document.getElementById("dish-edit-name").value = dish.name || "";
  document.getElementById("dish-edit-type").value = (dish.type || "ambas").toLowerCase();
  document.getElementById("dish-edit-ingredients").value = dish.ingredients || "";
  document.getElementById("modal-dish").classList.add("open");
};

window.deleteDish = async function (dishId, dishName) {
  if (!confirm(`¿Seguro que deseas eliminar '${dishName}' del catálogo?`)) return;
  try {
    const res = await apiCall(`/api/dishes/${encodeURIComponent(dishId)}`, { method: "DELETE" });
    renderAll(res.state);
    showToast(res.message, "info");
  } catch (err) {
    showToast(err.message, "error");
  }
};

function switchTab(tabId) {
  document.querySelectorAll(".tab-view").forEach((el) => {
    el.style.display = el.id === `tab-${tabId}` ? "block" : "none";
  });
  document.querySelectorAll("#desktop-nav .nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  document.querySelectorAll("#mobile-nav .mobile-nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.addEventListener("DOMContentLoaded", async () => {
  // Registrar Service Worker para PWA
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }

  // Fecha por defecto en formulario de cupones (+30 días)
  const defaultDate = new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0];
  document.getElementById("cp-date").value = defaultDate;

  // Navegación por pestañas
  document.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Sincronización de checkboxes de override
  const c1 = document.getElementById("chk-override-window");
  const c2 = document.getElementById("chk-override-window-mobile");
  if (c1) c1.addEventListener("change", () => syncOverrideCheckboxes(c1));
  if (c2) c2.addEventListener("change", () => syncOverrideCheckboxes(c2));

  // Modal Veto
  document.getElementById("btn-close-veto-modal").addEventListener("click", () => {
    document.getElementById("modal-veto").classList.remove("open");
  });
  document.getElementById("btn-confirm-veto-alvaro").addEventListener("click", () => submitVeto("Álvaro"));
  document.getElementById("btn-confirm-veto-ana").addEventListener("click", () => submitVeto("Ana"));

  // Regeneración manual
  document.getElementById("btn-hero-regen").addEventListener("click", async () => {
    try {
      const res = await apiCall("/api/menu/regenerate", { method: "POST" });
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Sincronizar Google Sheets
  async function triggerSync() {
    showToast("Sincronizando Google Sheets y calendario...", "info");
    try {
      const res = await apiCall("/api/sync", { method: "POST" });
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  }
  document.getElementById("btn-sync-sheets").addEventListener("click", triggerSync);
  document.getElementById("btn-hero-sync").addEventListener("click", triggerSync);
  document.getElementById("btn-sync-freezer").addEventListener("click", triggerSync);

  // Enviar Email
  document.getElementById("btn-send-email").addEventListener("click", async () => {
    showToast("Enviando menú semanal por correo...", "info");
    try {
      const res = await apiCall("/api/email/send", {
        method: "POST",
        body: JSON.stringify({ is_test: false })
      });
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("btn-test-email").addEventListener("click", async () => {
    showToast("Enviando correo de prueba...", "info");
    try {
      const res = await apiCall("/api/email/send", {
        method: "POST",
        body: JSON.stringify({ is_test: true })
      });
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Lista de la compra: copiar y limpiar
  document.getElementById("btn-copy-whatsapp").addEventListener("click", async () => {
    if (!appState) return;
    const checkedSet = new Set(appState.shopping.checked);
    const pending = appState.shopping.ingredients.filter((i) => !checkedSet.has(i));
    const listToCopy = pending.length ? pending : appState.shopping.ingredients;
    const text = "🛒 *LISTA DE LA COMPRA SEMANAL:*\n" + listToCopy.map((i) => `• ${i}`).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      showToast("¡Lista copiada al portapapeles para WhatsApp!", "success");
    } catch (_) {
      showToast("No se pudo copiar automáticamente.", "error");
    }
  });

  document.getElementById("btn-clear-shopping").addEventListener("click", async () => {
    try {
      const res = await apiCall("/api/shopping/checked", {
        method: "PUT",
        body: JSON.stringify({ checked: [] })
      });
      renderAll(res.state);
      showToast("Lista de la compra desmarcada.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Reiniciar vetos
  document.getElementById("btn-reset-vetos").addEventListener("click", async () => {
    try {
      const res = await apiCall("/api/vetos/reset", { method: "POST" });
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Filtros cupones y creación
  document.getElementById("filter-coupon-user").addEventListener("change", () => appState && renderCouponsTab(appState));
  document.getElementById("filter-coupon-status").addEventListener("change", () => appState && renderCouponsTab(appState));

  document.getElementById("form-create-coupon").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const res = await apiCall("/api/coupons", {
        method: "POST",
        body: JSON.stringify({
          title: document.getElementById("cp-title").value,
          restaurant: document.getElementById("cp-restaurant").value,
          user: document.getElementById("cp-user").value,
          expiration_date: document.getElementById("cp-date").value,
          notes: document.getElementById("cp-notes").value
        })
      });
      document.getElementById("cp-title").value = "";
      document.getElementById("cp-restaurant").value = "";
      document.getElementById("cp-notes").value = "";
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Buscador y modal de recetas
  document.getElementById("search-dishes-input").addEventListener("input", () => appState && renderDishesTab(appState));
  document.getElementById("filter-dishes-type").addEventListener("change", () => appState && renderDishesTab(appState));

  document.getElementById("btn-open-new-dish").addEventListener("click", () => {
    document.getElementById("modal-dish-title").textContent = "➕ Añadir Nuevo Plato";
    document.getElementById("dish-edit-id").value = "";
    document.getElementById("dish-edit-name").value = "";
    document.getElementById("dish-edit-type").value = "ambas";
    document.getElementById("dish-edit-ingredients").value = "";
    document.getElementById("modal-dish").classList.add("open");
  });

  document.getElementById("btn-close-dish-modal").addEventListener("click", () => {
    document.getElementById("modal-dish").classList.remove("open");
  });

  document.getElementById("form-modal-dish").addEventListener("submit", async (e) => {
    e.preventDefault();
    const editId = document.getElementById("dish-edit-id").value;
    const payload = {
      name: document.getElementById("dish-edit-name").value,
      type: document.getElementById("dish-edit-type").value,
      ingredients: document.getElementById("dish-edit-ingredients").value
    };
    try {
      const res = editId
        ? await apiCall(`/api/dishes/${encodeURIComponent(editId)}`, { method: "PUT", body: JSON.stringify(payload) })
        : await apiCall("/api/dishes", { method: "POST", body: JSON.stringify(payload) });
      document.getElementById("modal-dish").classList.remove("open");
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Guardar Ajustes
  document.getElementById("form-settings").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const res = await apiCall("/api/settings", {
        method: "PUT",
        body: JSON.stringify({
          sheet_url: document.getElementById("set-sheet-url").value,
          sheet_gid_dishes: document.getElementById("set-gid-dishes").value,
          sheet_gid_freezer: document.getElementById("set-gid-freezer").value,
          calendar_ics_url: document.getElementById("set-calendar-ics").value,
          smtp_host: document.getElementById("set-smtp-host").value,
          smtp_port: Number(document.getElementById("set-smtp-port").value || 587),
          smtp_user: document.getElementById("set-smtp-user").value,
          smtp_password: document.getElementById("set-smtp-pass").value,
          smtp_use_tls: true,
          recipients: document.getElementById("set-recipients").value
        })
      });
      renderAll(res.state);
      showToast(res.message, "success");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Carga inicial
  try {
    const initialState = await apiCall("/api/state");
    renderAll(initialState);
    if (initialState.auto_generated_now) {
      showToast(`✨ ¡Menú generado automáticamente para ${initialState.cycle_desc}!`, "success");
    }
  } catch (err) {
    showToast("Error cargando el estado inicial: " + err.message, "error");
  }
});

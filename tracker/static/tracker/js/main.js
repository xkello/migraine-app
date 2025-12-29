/**
 * main.js - The glue between HTML and the human.
 */

document.addEventListener("DOMContentLoaded", function() {
    // 1. Initialize Migraine Toggle if on log page
    initMigraineToggle();

    // 2. Initialize Toast notifications from Django messages
    initToasts();

    // 3. Global Event Listeners (Toggles, Chart Navigation)
    initGlobalListeners();
});

/**
 * Toast Notifications
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    // Map Django levels to Bootstrap-like classes
    let toastClass = 'toast-info';
    if (type === 'success') toastClass = 'toast-success';
    if (type === 'error' || type === 'danger') toastClass = 'toast-error';
    if (type === 'warning') toastClass = 'toast-warning';

    toast.className = `toast-custom ${toastClass} fade show`;
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="d-flex align-items-center justify-content-between">
            <span>${message}</span>
            <button type="button" class="btn-close btn-close-white ms-2" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }
    }, 4000);
}

function initToasts() {
    const messageData = document.getElementById('django-messages');
    if (messageData) {
        try {
            const messages = JSON.parse(messageData.textContent);
            messages.forEach(msg => showToast(msg.message, msg.level_tag));
        } catch (e) {
            console.error("Error parsing Django messages", e);
        }
    }
}

/**
 * Migraine Toggle Logic
 */
function initMigraineToggle() {
    const checkbox = document.querySelector('[data-toggle-migraine]');
    if (!checkbox) return;

    const container = document.getElementById('migraine-fields-container');
    const fields = container ? container.querySelectorAll('input, select, textarea') : [];

    function updateFields() {
        const isChecked = checkbox.checked;
        fields.forEach(field => {
            field.disabled = !isChecked;
            if (!isChecked) field.required = false;
        });

        if (container) {
            container.style.opacity = isChecked ? "1" : "0.4";
            container.style.pointerEvents = isChecked ? "auto" : "none";
        }
    }

    checkbox.addEventListener("change", updateFields);
    updateFields();
}

/**
 * Global UI Listeners
 */
function initGlobalListeners() {
    // Graph collapsing/toggling
    document.addEventListener("click", function(e) {
        const toggleBtn = e.target.closest(".toggle-graph");
        if (toggleBtn) {
            const targetSelector = toggleBtn.getAttribute("data-target");
            const body = document.querySelector(targetSelector);
            if (!body) return;

            const icon = toggleBtn.querySelector("i");
            if (body.classList.contains("d-none")) {
                body.classList.remove("d-none");
                if (icon) icon.classList.replace("bi-chevron-down", "bi-chevron-up");
            } else {
                body.classList.add("d-none");
                if (icon) icon.classList.replace("bi-chevron-up", "bi-chevron-down");
            }
            return;
        }

        // Chart Navigation (Prev/Next)
        const navBtn = e.target.closest(".nav-prev, .nav-next");
        if (navBtn && window.series && window.charts) {
            const key = navBtn.dataset.chart;
            const cfg = window.series[key];
            if (!cfg || !window.charts[key]) return;

            if (navBtn.classList.contains("nav-prev")) {
                cfg.start -= cfg.size;
            } else {
                cfg.start += cfg.size;
            }
            updateSingleChart(window.charts[key], cfg);
            return;
        }

        // Weather Navigation
        const weatherBtn = e.target.closest(".weather-prev, .weather-next");
        if (weatherBtn && window.weatherGroup && window.updateWeatherCharts) {
            if (weatherBtn.classList.contains("weather-prev")) {
                window.weatherGroup.start -= window.weatherGroup.step;
            } else {
                window.weatherGroup.start += window.weatherGroup.step;
            }
            window.updateWeatherCharts();
        }
    });
}

/**
 * Chart Utility Functions
 */
function fmtLabel(isoDate) {
    if (!isoDate) return "";
    const parts = isoDate.split("-");
    if (parts.length < 3) return isoDate;
    return `${parts[2]}.${parts[1]}`;
}

function sliceWindow(arr, start, size) {
    if (!arr) return [];
    return arr.slice(start, start + size);
}

function clampStart(start, size, len) {
    if (len <= size) return 0;
    return Math.max(0, Math.min(start, len - size));
}

function getWindow(cfg) {
    const len = (cfg.labels || []).length;
    const start = clampStart(cfg.start || 0, cfg.size, len);
    return {
        labels: sliceWindow(cfg.labels, start, cfg.size),
        data: sliceWindow(cfg.data, start, cfg.size),
        start
    };
}

function updateSingleChart(chart, cfg) {
    if (!chart || !cfg) return;
    const win = getWindow(cfg);
    cfg.start = win.start;
    chart.data.labels = win.labels;
    chart.data.datasets[0].data = win.data;
    chart.update();
}

function hasAnyData(arr) {
    return arr && arr.length && arr.some(v => v !== null && v !== undefined);
}

function showNoDataMessage(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (parent.querySelector(".no-data-msg")) return;

    const msg = document.createElement("div");
    msg.className = "no-data-msg text-soft small text-center w-100 position-absolute start-0 top-50 translate-middle-y";
    msg.innerText = "No data yet";
    parent.style.position = "relative";
    parent.appendChild(msg);
    canvas.style.opacity = "0.2";
}

/**
 * Chart Creation Helpers
 */
function createLineChart(canvasId, label, color, cfg) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    if (!hasAnyData(cfg.data)) showNoDataMessage(canvasId);

    const win = getWindow(cfg);
    window.charts = window.charts || {};
    window.charts[canvasId] = new Chart(el, {
        type: "line",
        data: {
            labels: win.labels,
            datasets: [{
                label: label,
                data: win.data,
                borderColor: color,
                backgroundColor: "transparent",
                tension: 0.35,
                pointRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#BBE1FA" } } },
            scales: {
                x: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } },
                y: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } }
            }
        }
    });
}

function createBarChart(canvasId, label, color, cfg) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    if (!hasAnyData(cfg.data)) showNoDataMessage(canvasId);

    const win = getWindow(cfg);
    window.charts = window.charts || {};
    window.charts[canvasId] = new Chart(el, {
        type: "bar",
        data: {
            labels: win.labels,
            datasets: [{ label: label, data: win.data, backgroundColor: color }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#BBE1FA" } } },
            scales: {
                x: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } },
                y: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } }
            }
        }
    });
}

function createWeatherLine(canvasId, label, color, labelsArr, dataArr, fullData) {
    const el = document.getElementById(canvasId);
    if (!el) return;
    if (!hasAnyData(fullData)) showNoDataMessage(canvasId);

    window.charts = window.charts || {};
    window.charts[canvasId] = new Chart(el, {
        type: "line",
        data: {
            labels: labelsArr,
            datasets: [{
                label: label,
                data: dataArr,
                borderColor: color,
                backgroundColor: "transparent",
                tension: 0.35,
                pointRadius: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { labels: { color: "#BBE1FA" } } },
            scales: {
                x: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } },
                y: { ticks: { color: "#BBE1FA" }, grid: { color: "rgba(187,225,250,0.08)" } }
            }
        }
    });
}

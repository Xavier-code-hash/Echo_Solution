"use strict";

/* ============================================================
   Echo Solutions — main client script
   Covers: theme, sidebar, clock, charts (Chart.js), toasts,
   payment selector, AI chatbot, UX micro-interactions.
   ============================================================ */

document.addEventListener("DOMContentLoaded", function () {

  /* ── 1. DARK MODE ─────────────────────────────────────────── */
  var root  = document.documentElement;
  var saved = localStorage.getItem("theme") || "light";
  root.setAttribute("data-theme", saved);

  var dmBtn = document.getElementById("darkModeBtn");
  if (dmBtn) {
    var dmIc = dmBtn.querySelector("i");
    if (dmIc) dmIc.className = saved === "dark" ? "fas fa-sun" : "fas fa-moon";

    dmBtn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      var i = dmBtn.querySelector("i");
      if (i) i.className = next === "dark" ? "fas fa-sun" : "fas fa-moon";

      /* Re-theme all active charts when mode switches */
      updateChartsTheme();
    });
  }


  /* ── 2. SIDEBAR ───────────────────────────────────────────── */
  var sidebar   = document.getElementById("sidebar");
  var overlay   = document.getElementById("sbOverlay");
  var toggleBtn = document.getElementById("sidebarToggle");

  function isMobile() { return window.innerWidth <= 768; }

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("open");
    if (overlay) {
      overlay.style.display = "block";
      requestAnimationFrame(function () { overlay.classList.add("show"); });
    }
    if (isMobile()) document.body.style.overflow = "hidden";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "true");
      var i = toggleBtn.querySelector("i");
      if (i) i.className = "fas fa-times";
    }
    var first = sidebar.querySelector("a.sb-link");
    if (first) setTimeout(function () { first.focus(); }, 60);
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    if (overlay) {
      overlay.classList.remove("show");
      setTimeout(function () {
        if (!overlay.classList.contains("show")) overlay.style.display = "none";
      }, 320);
    }
    document.body.style.overflow = "";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "false");
      var i = toggleBtn.querySelector("i");
      if (i) i.className = "fas fa-bars";
    }
  }

  if (overlay) overlay.style.display = "none";

  if (toggleBtn) {
    toggleBtn.setAttribute("aria-expanded", "false");
    toggleBtn.addEventListener("click", function () {
      sidebar && sidebar.classList.contains("open") ? closeSidebar() : openSidebar();
    });
  }

  if (overlay) overlay.addEventListener("click", closeSidebar);

  if (sidebar) {
    sidebar.querySelectorAll("a.sb-link").forEach(function (a) {
      a.addEventListener("click", function () { if (isMobile()) closeSidebar(); });
    });
    /* Trap keyboard focus inside open mobile sidebar */
    sidebar.addEventListener("keydown", function (e) {
      if (e.key !== "Tab" || !isMobile() || !sidebar.classList.contains("open")) return;
      var nodes = Array.from(sidebar.querySelectorAll('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])'));
      if (nodes.length < 2) return;
      var first = nodes[0], last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sidebar && sidebar.classList.contains("open")) {
      closeSidebar();
      if (toggleBtn) toggleBtn.focus();
    }
  });

  /* Swipe gestures for mobile sidebar */
  (function () {
    var sx = 0, sy = 0;
    document.addEventListener("touchstart", function (e) {
      sx = e.touches[0].clientX; sy = e.touches[0].clientY;
    }, { passive: true });
    document.addEventListener("touchend", function (e) {
      var dx = e.changedTouches[0].clientX - sx;
      var dy = Math.abs(e.changedTouches[0].clientY - sy);
      if (sidebar && sidebar.classList.contains("open") && dx < -56 && dy < 80) closeSidebar();
      if (sidebar && !sidebar.classList.contains("open") && sx < 28 && dx > 56 && dy < 80) openSidebar();
    }, { passive: true });
  }());

  window.addEventListener("resize", function () {
    if (!isMobile() && sidebar && sidebar.classList.contains("open")) {
      sidebar.classList.remove("open");
      if (overlay) { overlay.classList.remove("show"); overlay.style.display = "none"; }
      document.body.style.overflow = "";
      if (toggleBtn) {
        toggleBtn.setAttribute("aria-expanded", "false");
        var i = toggleBtn.querySelector("i");
        if (i) i.className = "fas fa-bars";
      }
    }
  });

  /* Scroll-solidify landing nav */
  var navBar = document.querySelector(".nav");
  if (navBar) {
    var onScroll = function () { navBar.classList.toggle("solid", window.scrollY > 30); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }


  /* ── 3. LIVE CLOCK (user's local timezone) ────────────────── */
  var clockEl = document.querySelector(".tb-clock");
  if (clockEl) {
    /* Detect the user's IANA timezone automatically via the browser API */
    var userTZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

    function tickClock() {
      var now = new Date();
      /* Format using the browser's own locale + auto-detected timezone */
      var timeStr = now.toLocaleTimeString([], {
        hour:   "2-digit",
        minute: "2-digit",
        second: "2-digit",
        timeZone: userTZ,
      });
      var dateStr = now.toLocaleDateString([], {
        weekday: "short",
        month:   "short",
        day:     "numeric",
        timeZone: userTZ,
      });
      clockEl.innerHTML = '<i class="far fa-clock"></i> ' + timeStr +
                          ' <span style="opacity:.5;font-size:.72rem">' + dateStr + "</span>";
    }

    tickClock();
    /* Update every second for a live clock feel */
    setInterval(tickClock, 1000);
  }


  /* ── 4. TOAST SYSTEM ──────────────────────────────────────── */
  function showToast(msg, type) {
    type = type || "info";
    var icons = {
      success: "fa-check-circle",
      error:   "fa-exclamation-circle",
      warning: "fa-triangle-exclamation",
      info:    "fa-info-circle",
    };
    var wrap = document.querySelector(".toast-wrap");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.className = "toast-wrap";
      document.body.appendChild(wrap);
    }
    var t = document.createElement("div");
    t.className = "toast toast-" + type;
    t.innerHTML = '<i class="toast-ic fas ' + (icons[type] || icons.info) + '"></i>' +
                  '<span class="toast-msg">' + msg + '</span>' +
                  '<button class="toast-close" aria-label="Close">&times;</button>';
    wrap.appendChild(t);
    t.querySelector(".toast-close").addEventListener("click", function () { t.remove(); });
    /* Auto-dismiss after 5 s */
    setTimeout(function () {
      t.style.transition = "opacity .3s,transform .3s";
      t.style.opacity = "0";
      t.style.transform = "translateX(14px)";
      setTimeout(function () { t.remove(); }, 330);
    }, 5000);
  }

  /* Auto-init toasts declared in markup */
  document.querySelectorAll("[data-toast]").forEach(function (el) {
    showToast(el.dataset.toastMsg, el.dataset.toast);
  });


  /* ── 5. PASSWORD VISIBILITY TOGGLE ───────────────────────── */
  document.querySelectorAll("[data-pw-toggle]").forEach(function (btn) {
    var target = document.getElementById(btn.dataset.pwToggle);
    if (!target) return;
    btn.addEventListener("click", function () {
      var isText = target.type === "text";
      target.type = isText ? "password" : "text";
      var ic = btn.querySelector("i");
      if (ic) ic.className = isText ? "fas fa-eye" : "fas fa-eye-slash";
    });
  });


  /* ── 6. PAYMENT METHOD SELECTOR ───────────────────────────── */
  document.querySelectorAll(".pay-method").forEach(function (card) {
    card.addEventListener("click", function () {
      document.querySelectorAll(".pay-method").forEach(function (c) {
        c.classList.remove("sel", "pay-method--active");
      });
      card.classList.add("sel", "pay-method--active");
      var inp = document.getElementById("paymentGateway");
      if (inp) inp.value = card.dataset.gateway;
      document.querySelectorAll(".pay-section").forEach(function (s) { s.hidden = true; });
      var noMsg = document.getElementById("no-method-msg");
      if (noMsg) noMsg.hidden = true;
      var sec = document.getElementById("pay-" + card.dataset.gateway);
      if (sec) sec.hidden = false;
    });
  });


  /* ── 7. CONFIRM DIALOGS ───────────────────────────────────── */
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (!confirm(el.dataset.confirm || "Are you sure?")) e.preventDefault();
    });
  });


  /* ── 8. AUTO-DISMISS ALERTS ───────────────────────────────── */
  document.querySelectorAll(".auto-dismiss").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity .4s";
      el.style.opacity = "0";
    }, 4000);
  });


  /* ── 9. CHART.JS — lazy-load then initialise all charts ───── */

  /* Shared defaults applied to every chart */
  function applyChartDefaults(isDark) {
    if (typeof Chart === "undefined") return;

    var gridColor  = isDark ? "rgba(255,255,255,.06)"  : "rgba(0,0,0,.06)";
    var axisColor  = isDark ? "rgba(255,255,255,.35)"  : "rgba(0,0,0,.35)";
    var fontFamily = "'Plus Jakarta Sans',system-ui,sans-serif";

    Chart.defaults.font.family  = fontFamily;
    Chart.defaults.font.size    = 12;
    Chart.defaults.color        = axisColor;
    Chart.defaults.borderColor  = gridColor;

    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.enabled = false; /* we use custom tooltips */
    Chart.defaults.animation.duration = 600;
    Chart.defaults.animation.easing   = "easeOutQuart";
    Chart.defaults.responsive          = true;
    Chart.defaults.maintainAspectRatio = false;
  }

  /* External custom tooltip renderer */
  function buildTooltip(context) {
    var chart     = context.chart;
    var canvas    = chart.canvas;
    var tooltip   = context.tooltip;
    var tooltipEl = chart._customTooltip;

    if (!tooltipEl) {
      tooltipEl = document.createElement("div");
      tooltipEl.className = "chart-tooltip";
      canvas.parentNode.style.position = "relative";
      canvas.parentNode.appendChild(tooltipEl);
      chart._customTooltip = tooltipEl;
    }

    if (tooltip.opacity === 0) {
      tooltipEl.style.opacity = "0";
      return;
    }

    /* Build tooltip HTML */
    var title = tooltip.title && tooltip.title[0] ? tooltip.title[0] : "";
    var rows  = tooltip.dataPoints.map(function (dp) {
      var color = dp.dataset.borderColor || dp.dataset.backgroundColor || "#c8922a";
      var label = dp.dataset.label || "";
      var val   = dp.formattedValue;
      return '<div class="chart-tooltip-row">' +
             '<div class="chart-tooltip-swatch" style="background:' + color + '"></div>' +
             '<span class="chart-tooltip-label">' + label + '</span>' +
             '<span class="chart-tooltip-val">' + val + '</span>' +
             '</div>';
    }).join("");

    tooltipEl.innerHTML = (title ? '<div class="chart-tooltip-title">' + title + '</div>' : "") + rows;

    /* Position relative to canvas */
    var canvasRect = canvas.getBoundingClientRect();
    var parentRect = canvas.parentNode.getBoundingClientRect();
    var x = tooltip.caretX;
    var y = tooltip.caretY;
    tooltipEl.style.opacity  = "1";
    tooltipEl.style.left     = x + "px";
    tooltipEl.style.top      = y + "px";
    tooltipEl.style.transform = "translate(-50%, -110%)";
  }

  var CHART_REGISTRY = {}; /* track instances for theme updates */

  function updateChartsTheme() {
    if (typeof Chart === "undefined") return;
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    applyChartDefaults(isDark);
    Object.values(CHART_REGISTRY).forEach(function (ch) { ch.update(); });
  }

  /* Palette used across all chart series */
  var PALETTE = [
    "#c8922a", /* brass */
    "#2563eb", /* blue  */
    "#16a34a", /* green */
    "#d97706", /* amber */
    "#7c3aed", /* violet*/
    "#0891b2", /* cyan  */
    "#dc2626", /* red   */
    "#059669", /* emerald*/
  ];

  /* Generic Chart.js factory */
  function makeChart(ctx, config) {
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    applyChartDefaults(isDark);
    var ch = new Chart(ctx, config);
    var id = ctx.canvas ? ctx.canvas.id || Math.random().toString(36).slice(2) : "c" + Date.now();
    CHART_REGISTRY[id] = ch;
    return ch;
  }

  /* ── Period tab switcher ── */
  document.querySelectorAll(".chart-tabs").forEach(function (tabs) {
    var chartId = tabs.dataset.chartTarget;
    tabs.querySelectorAll(".chart-tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.querySelectorAll(".chart-tab").forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        var ch = CHART_REGISTRY[chartId];
        if (!ch) return;
        var period = tab.dataset.period;
        /* Dispatch a custom event so page-level scripts can refill data */
        tabs.dispatchEvent(new CustomEvent("periodchange", { detail: { period: period, chart: ch }, bubbles: true }));
      });
    });
  });

  /* ── Lazy-load Chart.js from CDN then init all declared charts ── */
  var chartCanvases = document.querySelectorAll("[data-chart]");
  if (chartCanvases.length > 0) {

    if (typeof Chart !== "undefined") {
      initAllCharts();
    } else {
      var script = document.createElement("script");
      script.src = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js";
      script.onload = initAllCharts;
      document.head.appendChild(script);
    }
  }

  function initAllCharts() {
    document.querySelectorAll("[data-chart]").forEach(function (canvas) {
      var type    = canvas.dataset.chart;            /* bar | line | pie | doughnut */
      var rawData = canvas.dataset.chartData;
      var labels  = canvas.dataset.chartLabels;

      if (!rawData) return;

      try {
        var data   = JSON.parse(rawData);
        var lblArr = labels ? JSON.parse(labels) : [];

        /* data can be a flat array or an array-of-arrays (multi-series) */
        var isMulti = Array.isArray(data[0]);

        var datasets;
        if (type === "pie" || type === "doughnut") {
          datasets = [{
            data:            data,
            backgroundColor: PALETTE.slice(0, data.length).map(function (c) { return c + "cc"; }),
            borderColor:     PALETTE.slice(0, data.length),
            borderWidth:     2,
            hoverOffset:     6,
          }];
        } else if (isMulti) {
          var seriesLabels = canvas.dataset.chartSeries
            ? JSON.parse(canvas.dataset.chartSeries)
            : data.map(function (_, i) { return "Series " + (i + 1); });

          datasets = data.map(function (series, i) {
            var col = PALETTE[i % PALETTE.length];
            return buildDataset(type, series, seriesLabels[i], col);
          });
        } else {
          datasets = [buildDataset(type, data, canvas.dataset.chartLabel || "", PALETTE[0])];
        }

        var config = buildConfig(type, lblArr, datasets, canvas);
        makeChart(canvas.getContext("2d"), config);

      } catch (e) {
        console.warn("Echo chart init error on #" + canvas.id + ":", e);
      }
    });
  }

  function buildDataset(type, data, label, color) {
    if (type === "line") {
      return {
        label:           label,
        data:            data,
        borderColor:     color,
        backgroundColor: color + "22",
        borderWidth:     2.5,
        pointRadius:     4,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        fill:            true,
        tension:         0.4,
      };
    }
    /* bar */
    return {
      label:            label,
      data:             data,
      backgroundColor:  color + "cc",
      borderColor:      color,
      borderWidth:      1.5,
      borderRadius:     6,
      borderSkipped:    false,
      hoverBackgroundColor: color,
    };
  }

  function buildConfig(type, labels, datasets, canvas) {
    var isDark = document.documentElement.getAttribute("data-theme") === "dark";
    var gridColor = isDark ? "rgba(255,255,255,.06)" : "rgba(0,0,0,.06)";
    var axisColor = isDark ? "rgba(255,255,255,.35)" : "rgba(0,0,0,.35)";

    /* KES currency formatter for y-axis */
    var isCurrency = canvas.dataset.chartCurrency === "true";

    var config = {
      type: type,
      data: { labels: labels, datasets: datasets },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        plugins: {
          legend:  { display: false },
          tooltip: {
            enabled:  false,
            external: buildTooltip,
          },
        },
        interaction: { mode: "index", intersect: false },
        animation:   { duration: 600, easing: "easeOutQuart" },
      },
    };

    /* Scales only for bar/line */
    if (type !== "pie" && type !== "doughnut") {
      config.options.scales = {
        x: {
          ticks:  { color: axisColor, font: { size: 11 } },
          grid:   { color: gridColor, drawTicks: false },
          border: { display: false },
        },
        y: {
          ticks: {
            color: axisColor,
            font:  { size: 11 },
            callback: function (v) {
              return isCurrency
                ? "KES " + (v >= 1000 ? (v / 1000).toFixed(0) + "k" : v)
                : v;
            },
          },
          grid:   { color: gridColor },
          border: { display: false },
          beginAtZero: true,
        },
      };
    }

    /* Pie / doughnut tweak */
    if (type === "doughnut") {
      config.options.cutout = "65%";
      config.options.plugins.centerText = canvas.dataset.chartCenter || "";
    }

    return config;
  }

  /* ── Custom legend builder (rendered outside canvas) ── */
  document.querySelectorAll("[data-chart-legend]").forEach(function (legendEl) {
    var targetId = legendEl.dataset.chartLegend;
    /* Wait for Chart.js to finish then build legend */
    setTimeout(function () {
      var ch = CHART_REGISTRY[targetId];
      if (!ch) return;
      legendEl.innerHTML = ch.data.datasets.map(function (ds, i) {
        var color = Array.isArray(ds.borderColor)
          ? ds.borderColor[0]
          : ds.borderColor || ds.backgroundColor || PALETTE[i];
        return '<span class="chart-legend-item" data-idx="' + i + '">' +
               '<span class="chart-legend-dot" style="background:' + color + '"></span>' +
               (ds.label || "") +
               '</span>';
      }).join("");

      /* Toggle dataset visibility on legend click */
      legendEl.querySelectorAll(".chart-legend-item").forEach(function (item) {
        item.addEventListener("click", function () {
          var idx = parseInt(item.dataset.idx, 10);
          var meta = ch.getDatasetMeta(idx);
          meta.hidden = !meta.hidden;
          item.classList.toggle("hidden", meta.hidden);
          ch.update();
        });
      });
    }, 100);
  });


  /* ── AI CHATBOT WIDGET ─────────────────────────────────── */
  var aiRoot = document.querySelector("[data-ai-chat]");
  if (!aiRoot) return;

  var aiPanel   = aiRoot.querySelector("[data-ai-panel]");
  var aiToggle  = aiRoot.querySelector("[data-ai-toggle]");
  var aiThread  = aiRoot.querySelector("[data-ai-thread]");
  var aiForm    = aiRoot.querySelector("[data-ai-form]");
  var aiInput   = aiRoot.querySelector("[data-ai-input]");
  var aiCounter = aiRoot.querySelector("[data-ai-counter]");

  function timeGreeting() {
    var h = new Date().getHours();
    return h < 12 ? "morning" : h < 17 ? "afternoon" : h < 22 ? "evening" : "night";
  }
  function fmt() {
    return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  var greet = "Hello, good " + timeGreeting() + "! I can help with pricing, vacancies, or setup.";
  document.querySelectorAll("[data-ai-greeting]").forEach(function (el) { el.textContent = greet; });

  function openChat() {
    if (!aiPanel) return;
    aiPanel.hidden = false;
    aiRoot.classList.add("open");
    if (aiToggle) aiToggle.setAttribute("aria-expanded", "true");
    setTimeout(function () { if (aiInput) aiInput.focus(); }, 80);
  }

  function closeChat() {
    if (!aiPanel) return;
    aiPanel.hidden = true;
    aiRoot.classList.remove("open");
    if (aiToggle) { aiToggle.setAttribute("aria-expanded", "false"); aiToggle.focus(); }
  }

  if (aiToggle) {
    aiToggle.setAttribute("aria-expanded", "false");
    aiToggle.addEventListener("click", function () {
      aiPanel && aiPanel.hidden ? openChat() : closeChat();
    });
  }

  var aiClose = aiRoot.querySelector("[data-ai-close]");
  if (aiClose) aiClose.addEventListener("click", closeChat);

  document.querySelectorAll("[data-ai-open]").forEach(function (btn) {
    btn.addEventListener("click", openChat);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && aiPanel && !aiPanel.hidden) closeChat();
  });

  /* Character counter */
  var MAX = 280;
  if (aiInput) {
    aiInput.setAttribute("maxlength", MAX);
    if (aiCounter) {
      aiInput.addEventListener("input", function () {
        var rem = MAX - aiInput.value.length;
        aiCounter.textContent = rem < 60 ? rem : "";
        aiCounter.style.color = rem < 20 ? "rgba(220,38,38,.85)" : "rgba(255,255,255,.3)";
      });
    }
  }

  function appendMsg(text, isUser) {
    if (!aiThread) return;
    var w = document.createElement("div");
    w.className = isUser ? "ai-msg ai-msg-user" : "ai-msg";
    var b = document.createElement("div");
    b.className = "ai-bubble";
    b.textContent = text;
    var m = document.createElement("div");
    m.className = "ai-meta";
    m.textContent = isUser ? "You · " + fmt() : "Echo AI · " + fmt();
    w.appendChild(b);
    w.appendChild(m);
    aiThread.appendChild(w);
    aiThread.scrollTo({ top: aiThread.scrollHeight, behavior: "smooth" });
  }

  function showTyping() {
    if (!aiThread) return null;
    var w = document.createElement("div");
    w.className = "ai-msg ai-typing-wrap";
    w.innerHTML = '<div class="ai-typing"><span></span><span></span><span></span></div>';
    aiThread.appendChild(w);
    aiThread.scrollTo({ top: aiThread.scrollHeight, behavior: "smooth" });
    return w;
  }

  /* Simple keyword-based replies for the chatbot */
  function reply(msg) {
    var t = msg.toLowerCase();
    if (/price|pricing|cost|plan|subscription/.test(t))
      return "Plans start free for up to 5 units. Professional is KES 2,500/month for unlimited units. Enterprise pricing is custom.";
    if (/vacan|empty|listing|unit/.test(t))
      return "You can list vacant units with photos and pricing, then share them publicly. I can walk you through posting your first listing.";
    if (/pay|mpesa|stripe|paypal|card/.test(t))
      return "Tenants can pay via M-Pesa STK push, card (Stripe), or PayPal. Payments post automatically with instant receipts.";
    if (/demo|contact|team|talk|sales/.test(t))
      return "Use the Contact page or request a demo from inside your dashboard once you sign up.";
    if (/maintenance|repair|ticket|request/.test(t))
      return "Tenants raise maintenance requests from their portal. You get instant notifications and can track progress from the Maintenance dashboard.";
    if (/report|analytic|revenue|income/.test(t))
      return "The Reports section gives you revenue, occupancy, and overdue breakdowns — complete with interactive bar, line, and pie charts.";
    if (/hello|hi|hey|good|morning|afternoon|evening/.test(t))
      return "Good " + timeGreeting() + "! What can I help you with?";
    return "I can help with pricing, vacancies, payments, maintenance, or reports. What would you like to know?";
  }

  function send(text) {
    var t = (text || "").trim();
    if (!t) return;
    appendMsg(t, true);
    var typing = showTyping();
    setTimeout(function () {
      if (typing) typing.remove();
      appendMsg(reply(t), false);
    }, 420 + Math.min(t.length * 9, 900));
  }

  if (aiForm && aiInput) {
    aiForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var t = aiInput.value.trim();
      if (!t) return;
      aiInput.value = "";
      if (aiCounter) aiCounter.textContent = "";
      if (aiPanel && aiPanel.hidden) openChat();
      send(t);
    });
    aiInput.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter")
        aiForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    });
  }

  aiRoot.querySelectorAll("[data-ai-prompt]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var p = btn.dataset.aiPrompt || btn.textContent.trim();
      if (!p) return;
      if (aiPanel && aiPanel.hidden) openChat();
      send(p);
    });
  });

});
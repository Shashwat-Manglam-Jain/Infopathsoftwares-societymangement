/**
 * Shared form-guard: double-submit protection + toast notifications.
 * Used by standalone pages (signup, login, public_login) that don't extend base.html.
 */
(function () {
  // --- Inject CSS ---
  var style = document.createElement("style");
  style.textContent =
    "@keyframes toast-in{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}" +
    "@keyframes toast-out{from{transform:translateX(0);opacity:1}to{transform:translateX(120%);opacity:0}}" +
    ".toast-enter{animation:toast-in .3s ease-out forwards}" +
    ".toast-exit{animation:toast-out .25s ease-in forwards}" +
    "@keyframes btn-spin{to{transform:rotate(360deg)}}" +
    ".btn-spinner{display:inline-block;width:1em;height:1em;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:btn-spin .6s linear infinite;vertical-align:middle;margin-right:.4em}" +
    "button[disabled]{opacity:.55;cursor:not-allowed!important}";
  document.head.appendChild(style);

  // --- Toast container ---
  var container = document.createElement("div");
  container.id = "toast-container";
  container.className =
    "fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none";
  container.style.maxWidth = "420px";
  document.body.appendChild(container);

  // --- Toast system ---
  var ICONS = {
    success:
      '<svg class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    error:
      '<svg class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
    warning:
      '<svg class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>',
    info: '<svg class="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
  };
  var STYLES = {
    success: "bg-green-50 text-green-800 border-green-200",
    error: "bg-red-50 text-red-800 border-red-200",
    warning: "bg-amber-50 text-amber-800 border-amber-200",
    info: "bg-blue-50 text-blue-800 border-blue-200",
  };
  var ICON_COLORS = {
    success: "text-green-500",
    error: "text-red-500",
    warning: "text-amber-500",
    info: "text-blue-500",
  };

  window.showToast = function (text, level) {
    level = level || "info";
    if (level === "debug") return;
    var c = document.getElementById("toast-container");
    if (!c) return;
    var toast = document.createElement("div");
    toast.className =
      "pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg text-sm toast-enter " +
      (STYLES[level] || STYLES.info);
    toast.innerHTML =
      '<span class="mt-0.5 ' +
      (ICON_COLORS[level] || ICON_COLORS.info) +
      '">' +
      (ICONS[level] || ICONS.info) +
      "</span>" +
      '<span class="flex-1 font-medium">' +
      text +
      "</span>" +
      '<button class="ml-2 flex-shrink-0 opacity-60 hover:opacity-100" onclick="this.parentElement.classList.replace(\'toast-enter\',\'toast-exit\');setTimeout(function(){this.remove()}.bind(this.parentElement),300)">' +
      '<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button>';
    c.appendChild(toast);
    var duration = level === "error" ? 6000 : 4000;
    setTimeout(function () {
      if (toast.parentElement) {
        toast.classList.replace("toast-enter", "toast-exit");
        setTimeout(function () {
          toast.remove();
        }, 300);
      }
    }, duration);
  };

  // --- Double-submit protection ---
  document.addEventListener(
    "submit",
    function (e) {
      var form = e.target;
      if (form.tagName !== "FORM") return;
      if (form.method && form.method.toLowerCase() === "get") return;
      if (form.dataset.noGuard) return;
      if (form.dataset.submitted === "true") {
        e.preventDefault();
        return;
      }
      form.dataset.submitted = "true";
      var btns = form.querySelectorAll(
        'button[type="submit"], input[type="submit"], button:not([type])'
      );
      btns.forEach(function (btn) {
        btn.disabled = true;
        if (btn.tagName === "BUTTON") {
          btn.dataset.originalText = btn.innerHTML;
          btn.innerHTML =
            '<span class="btn-spinner"></span> ' +
            (btn.dataset.loadingText || "Processing…");
        }
      });
      setTimeout(function () {
        form.dataset.submitted = "";
        btns.forEach(function (btn) {
          btn.disabled = false;
          if (btn.dataset.originalText) {
            btn.innerHTML = btn.dataset.originalText;
            delete btn.dataset.originalText;
          }
        });
      }, 15000);
    },
    true
  );
})();

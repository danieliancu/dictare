/* dictare.ro site behaviour: sticky header, mobile menu, testimonial carousel, htmx UX. */
(function () {
  "use strict";

  /* Sticky header shadow after scroll */
  const header = document.querySelector("[data-sticky-header]");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* Mobile menu */
  document.addEventListener("click", (e) => {
    const toggle = e.target.closest("[data-nav-toggle]");
    if (!toggle) return;
    const menu = document.getElementById(toggle.getAttribute("aria-controls"));
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    menu.classList.toggle("is-open", open);
    if (header) header.classList.toggle("is-scrolled", open || window.scrollY > 8);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const toggle = document.querySelector('[data-nav-toggle][aria-expanded="true"]');
    if (toggle) {
      toggle.click();
      toggle.focus();
    }
  });
  document.querySelectorAll(".mobile-menu a").forEach((a) =>
    a.addEventListener("click", () => {
      const toggle = document.querySelector('[data-nav-toggle][aria-expanded="true"]');
      if (toggle) toggle.click();
    })
  );

  /* Testimonial carousel (no autoplay) */
  document.querySelectorAll("[data-carousel]").forEach((root) => {
    const slides = Array.from(root.querySelectorAll("[data-slide]"));
    const dots = Array.from(root.querySelectorAll("[data-dot]"));
    if (slides.length < 2) return;
    let index = 0;
    const show = (i) => {
      index = (i + slides.length) % slides.length;
      slides.forEach((s, j) => {
        s.setAttribute("aria-hidden", String(j !== index));
        if (j === index) s.removeAttribute("inert");
        else s.setAttribute("inert", "");
      });
      dots.forEach((d, j) => d.setAttribute("aria-current", String(j === index)));
    };
    root.querySelector("[data-prev]")?.addEventListener("click", () => show(index - 1));
    root.querySelector("[data-next]")?.addEventListener("click", () => show(index + 1));
    dots.forEach((d, j) => d.addEventListener("click", () => show(j)));
    show(0);
  });

  /* Toasts */
  function toast(message) {
    const region = document.getElementById("toasts");
    if (!region) return;
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = message;
    region.replaceChildren(el);
    setTimeout(() => el.remove(), 5000);
  }
  window.dictareToast = toast;

  /* htmx: errors, focus management, busy state */
  document.addEventListener("htmx:sendError", () => {
    toast("Nu există conexiune la internet. Verifică rețeaua și încearcă din nou.");
  });
  document.addEventListener("htmx:responseError", (e) => {
    const status = e.detail.xhr.status;
    if (status === 429) toast("Prea multe cereri. Așteaptă un minut și încearcă din nou.");
    else if (status === 403) toast("Sesiunea a expirat. Reîncarcă pagina.");
    else if (status === 404) toast("Exercițiul nu mai este disponibil. Reîncarcă pagina.");
    else toast("Ceva n-a mers. Încearcă din nou în câteva secunde.");
  });
  document.addEventListener("htmx:beforeRequest", (e) => {
    const ex = e.detail.elt.closest("[data-exercise]");
    if (ex) ex.setAttribute("aria-busy", "true");
  });
  document.addEventListener("htmx:afterRequest", (e) => {
    const ex = e.detail.elt.closest && e.detail.elt.closest("[data-exercise]");
    if (ex) ex.setAttribute("aria-busy", "false");
  });
  document.addEventListener("htmx:afterSettle", (e) => {
    const scope = e.detail.elt.parentElement || document;
    const target = scope.querySelector("[data-autofocus]");
    if (target) {
      target.focus({ preventScroll: true });
      const rect = target.getBoundingClientRect();
      if (rect.top < 60 || rect.bottom > window.innerHeight) {
        target.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    } else {
      const play = scope.querySelector("[data-exercise] [data-play]");
      if (play && e.detail.requestConfig && e.detail.requestConfig.verb === "get") {
        play.focus({ preventScroll: true });
        scope.querySelector("[data-exercise]").scrollIntoView({ block: "start", behavior: "smooth" });
      }
    }
  });
})();

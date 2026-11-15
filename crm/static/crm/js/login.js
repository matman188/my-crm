(() => {
    "use strict";
    const toggle = document.querySelector("[data-password-toggle]");
    const password = document.getElementById("id_password");
    if (!toggle || !password) return;
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
        const show = password.type === "password";
        password.type = show ? "text" : "password";
        toggle.textContent = show ? "Hide" : "Show";
        toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
        toggle.setAttribute("aria-pressed", String(show));
    });
})();

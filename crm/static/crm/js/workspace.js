(() => {
    "use strict";
    const dialog = document.querySelector("[data-workspace-confirm]");
    const cancel = dialog.querySelector("[data-workspace-cancel]");
    const accept = dialog.querySelector("[data-workspace-accept]");
    let resolveDialog = null;
    let navigating = false;
    let toastTimer;
    const tracked = new Map();
    const approved = new WeakMap();
    const buttonLabels = new Map();

    function confirmAction({ title, message, label = "Confirm", danger = false }) {
        if (dialog.open) return Promise.resolve(false);
        dialog.querySelector("[data-workspace-confirm-title]").textContent = title;
        dialog.querySelector("[data-workspace-confirm-message]").textContent = message;
        accept.textContent = label;
        accept.classList.toggle("danger", danger);
        dialog.showModal();
        cancel.focus();
        return new Promise(resolve => { resolveDialog = resolve; });
    }
    function finishDialog(value) {
        const resolve = resolveDialog;
        resolveDialog = null;
        dialog.close();
        resolve?.(value);
    }
    cancel.addEventListener("click", () => finishDialog(false));
    accept.addEventListener("click", () => finishDialog(true));
    dialog.addEventListener("cancel", event => { event.preventDefault(); finishDialog(false); });
    dialog.addEventListener("close", () => {
        if (!dialog.open && resolveDialog) { const resolve = resolveDialog; resolveDialog = null; resolve(false); }
    });

    function signature(form) {
        const mode = form.querySelector('[name="customer_mode"]')?.value;
        return JSON.stringify([...form.elements].filter(field =>
            field.name && !field.disabled && !["submit", "button", "reset"].includes(field.type) &&
            !["csrfmiddlewaretoken", "next", "revision"].includes(field.name) &&
            (!field.closest("[data-customer-dialog]") || mode === "new")
        ).map(field => [field.name, field.type === "checkbox" || field.type === "radio" ? field.checked :
            field.multiple ? [...field.selectedOptions].map(option => option.value) : field.value]));
    }
    function isDirty(form) {
        const state = tracked.get(form);
        return Boolean(state && (state.invalid || state.initial !== signature(form)));
    }
    function updateState(form) {
        const state = tracked.get(form);
        if (state) {
            const dirty = isDirty(form);
            if (state.rowSave) {
                state.rowSave.disabled = !dirty;
                return;
            }
            if (state.label) {
                state.label.textContent = dirty ? "Unsaved changes" : location.pathname.includes("/create/") ? "New record" : "Saved";
                state.label.classList.toggle("is-dirty", dirty);
            }
        }
    }
    function notify(message) {
        const toast = document.querySelector("[data-workspace-toast]");
        toast.textContent = message;
        toast.hidden = false;
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => { toast.hidden = true; }, 5000);
    }
    const hasUnsaved = () => [...tracked.keys()].some(isDirty) || Boolean(document.querySelector('[data-customer-dialog][data-unsaved-changes="true"]'));
    function rememberListScroll() {
        try { sessionStorage.setItem("crm-scroll:" + location.pathname + location.search, String(window.scrollY)); } catch { /* Storage is optional. */ }
    }
    window.crmUX = { confirm: confirmAction, notify, isDirty, allowNavigation() { navigating = true; } };
    window.addEventListener("beforeunload", event => {
        if (!navigating && hasUnsaved()) { event.preventDefault(); event.returnValue = ""; }
    });
    document.addEventListener("click", async event => {
        const link = event.target.closest("a[href]");
        if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute("download")) return;
        const destination = new URL(link.href, location.href);
        if (!["http:", "https:"].includes(destination.protocol) || destination.href === location.href || (destination.pathname === location.pathname && destination.search === location.search && destination.hash)) return;
        if (/^\/(orders|customers|products|services|product-categories|users)\/$/.test(location.pathname)) {
            rememberListScroll();
        }
        if (!hasUnsaved()) return;
        event.preventDefault();
        if (await confirmAction({ title: "Unsaved changes", message: "Leave this page and discard your unsaved changes?", label: "Leave page" })) {
            navigating = true;
            window.location.assign(link.href);
        }
    });

    document.addEventListener("submit", async event => {
        const form = event.target;
        if (event.defaultPrevented || form.method.toLowerCase() !== "post") return;
        if (form.dataset.submitting === "true") { event.preventDefault(); return; }
        const button = event.submitter;
        const leavingDirty = new URL(form.action, location.href).pathname === "/logout/" && hasUnsaved();
        const quickOrderSave = form.matches("[data-order-list-edit]");
        const otherRowsDirty = quickOrderSave && [...tracked.keys()].some(other => other !== form && isDirty(other));
        const refundForm = document.querySelector("[data-order-refund]");
        const orderEditor = document.querySelector("[data-order-editor]");
        let otherEditsMessage = "";
        if (form === refundForm && isDirty(orderEditor)) {
            otherEditsMessage = "Save the order first, or continue and discard the unsaved order changes.";
        } else if (form === orderEditor && isDirty(refundForm)) {
            otherEditsMessage = "Save the order and discard the unsaved refund?";
        }
        const message = button?.dataset.confirm || (leavingDirty ? "Log out and discard your unsaved changes?" : "") ||
            (otherRowsDirty ? "Save this order and discard unsaved changes on the other rows?" : otherEditsMessage);
        const ownConfirmation = button?.dataset.confirm && form.matches("[data-order-editor], #delete-draft-form");
        if (message && !ownConfirmation && approved.get(form) !== button) {
            event.preventDefault();
            const label = button?.textContent.trim() || "Log out";
            if (await confirmAction({ title: button?.dataset.confirmTitle || label, message, label, danger: button?.classList.contains("danger") })) {
                approved.set(form, button);
                try { if (button) form.requestSubmit(button); else form.requestSubmit(); } finally { approved.delete(form); }
            }
            return;
        }
        if (quickOrderSave) rememberListScroll();
        navigating = true;
        form.dataset.submitting = "true";
        form.setAttribute("aria-busy", "true");
        // Keep submitters enabled until the browser captures their name/value.
        // Dropping action=complete here would accidentally perform a normal Save.
        [...form.elements].filter(field => field.type === "submit").forEach(control => {
            buttonLabels.set(control, control.textContent);
            control.setAttribute("aria-disabled", "true");
        });
        if (button) button.textContent = "Saving…";
    });

    function markRequired(root) {
        root.querySelectorAll("input[required], select[required], textarea[required]").forEach(field => {
            const label = field.labels?.[0];
            if (!label || label.querySelector(".required-marker")) return;
            const marker = document.createElement("span");
            marker.className = "required-marker";
            marker.setAttribute("aria-hidden", "true");
            marker.textContent = " *";
            label.append(marker);
        });
    }
    function addNext(form, value) {
        if (!value || form.querySelector('[name="next"]')) return;
        const input = document.createElement("input");
        input.type = "hidden"; input.name = "next"; input.value = value; form.append(input);
    }
    document.addEventListener("DOMContentLoaded", () => {
        const list = /^\/(orders|customers|products|services|product-categories|users)\/$/.test(location.pathname);
        const next = new URL(location.href).searchParams.get("next");
        if (list) {
            document.querySelectorAll("a[href]").forEach(link => {
                const url = new URL(link.href, location.href);
                if (url.origin === location.origin && /\/(create|edit|change-password)\/$/.test(url.pathname) && !url.searchParams.has("next")) {
                    url.searchParams.set("next", location.pathname + location.search);
                    link.href = url.pathname + url.search;
                }
            });
        }
        document.querySelectorAll('form[method="post"]').forEach(form => {
            addNext(form, next || (list ? location.pathname + location.search : ""));
            const fields = Array.from(form.elements).filter(field => field.matches('input:not([type="hidden"]):not([type="submit"]), textarea, select'));
            if (form.matches("[data-directory-selection]") || form.closest("dialog") || !fields.length) return;
            const rowSave = form.querySelector("[data-order-row-save]");
            const refundForm = form.matches("[data-order-refund]");
            const label = rowSave || refundForm ? null : document.createElement("p");
            if (label) { label.className = "save-state"; label.setAttribute("role", "status"); form.prepend(label); }
            const invalid = fields.filter(field => field.matches('[aria-invalid="true"]:not(:disabled)') && !field.closest("dialog"));
            tracked.set(form, { initial: signature(form), invalid: invalid.length > 0 || Boolean(form.querySelector('.non-field-errors:not([hidden])')), label, rowSave });
            const eventTargets = [form, ...fields.filter(field => !form.contains(field))];
            const refreshForm = () => { updateState(form); markRequired(form); };
            for (const target of eventTargets) {
                for (const type of ["input", "change", "crm:changed"]) {
                    target.addEventListener(type, refreshForm);
                }
            }
            updateState(form);
            if (invalid.length) {
                if (refundForm) { invalid[0].focus(); return; }
                const summary = document.createElement("div"); summary.className = "non-field-errors error-summary"; summary.setAttribute("role", "alert");
                const title = document.createElement("strong"); title.textContent = "Please check these fields:"; summary.append(title);
                const links = document.createElement("ul");
                invalid.forEach(field => { const item = document.createElement("li"); const link = document.createElement("a"); link.href = "#" + field.id; link.textContent = field.labels?.[0]?.textContent || field.name; link.addEventListener("click", event => { event.preventDefault(); field.focus(); }); item.append(link); links.append(item); });
                summary.append(links); form.prepend(summary);
                if (!document.querySelector("dialog[open]")) invalid[0].focus();
            }
        });
        markRequired(document);
        document.querySelectorAll("table.data-table").forEach(table => {
            const headers = [...table.querySelectorAll("thead th")].map(cell => cell.textContent);
            table.querySelectorAll("tbody tr").forEach(row => [...row.children].forEach((cell, index) => { cell.dataset.label = headers[index] || ""; }));
        });
        try {
            const key = "crm-scroll:" + location.pathname + location.search;
            const scroll = sessionStorage.getItem(key);
            if (scroll !== null) { window.scrollTo(0, Number(scroll)); sessionStorage.removeItem(key); }
        } catch { /* Storage is optional. */ }
    });
    window.addEventListener("pageshow", () => {
        navigating = false;
        document.querySelectorAll('form[data-submitting="true"]').forEach(form => { delete form.dataset.submitting; form.removeAttribute("aria-busy"); });
        buttonLabels.forEach((label, button) => { button.textContent = label; button.removeAttribute("aria-disabled"); }); buttonLabels.clear();
        tracked.forEach((state, form) => updateState(form));
    });
})();

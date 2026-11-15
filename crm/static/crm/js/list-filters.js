(() => {
    "use strict";
    document.querySelectorAll("form[data-list-filters]").forEach(form => {
        form.addEventListener("change", event => {
            if (!event.target.matches("select") || event.target.disabled) return;
            // Older/dashboard Unpaid links must not prevent choosing another payment status.
            const view = form.elements.namedItem("view");
            if (view?.value === "unpaid" && event.target.name === "payment_status") view.value = "all";
            form.requestSubmit();
        });
    });
})();

(() => {
    "use strict";
    function bindConfirmation(buttonSelector, dialogSelector, cancelSelector) {
        const button = document.querySelector(buttonSelector);
        const dialog = document.querySelector(dialogSelector);
        if (!button || !dialog) return;
        const cancel = dialog.querySelector(cancelSelector);
        button.addEventListener("click", () => {
            dialog.showModal();
            cancel.focus();
        });
        cancel.addEventListener("click", () => dialog.close());
        dialog.addEventListener("close", () => button.focus());
    }
    bindConfirmation("[data-delete-customer]", "[data-customer-delete-dialog]", "[data-cancel-customer-delete]");
    bindConfirmation("[data-customer-status-action]", "[data-customer-status-dialog]", "[data-cancel-customer-status]");
})();

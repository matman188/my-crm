(() => {
    "use strict";
    const editor = document.querySelector("[data-order-editor]");
    const dialog = document.querySelector("[data-order-confirmation]");
    if (!editor || !dialog) return;
    const title = dialog.querySelector("[data-confirm-title]");
    const message = dialog.querySelector("[data-confirm-message]");
    const cancelButton = dialog.querySelector("[data-confirm-cancel]");
    const confirmButton = dialog.querySelector("[data-confirm-accept]");
    let pendingAction = null;
    let approvedSubmitter = null;

    function ask(trigger, form = null) {
        if (dialog.open) return;
        pendingAction = { trigger, form };
        const label = trigger.textContent.trim();
        title.textContent = label;
        message.textContent = trigger.dataset.confirm;
        if (form && window.crmUX?.isDirty(document.querySelector("[data-order-refund]"))) {
            message.textContent += " The unsaved refund will be discarded.";
        }
        confirmButton.textContent = label;
        confirmButton.classList.toggle("danger", trigger.classList.contains("danger"));
        confirmButton.disabled = false;
        dialog.showModal();
        cancelButton.focus();
    }

    function confirmSubmission(event) {
        if (event.defaultPrevented || event.submitter === approvedSubmitter) return;
        if (!event.submitter?.dataset.confirm) return;
        event.preventDefault();
        ask(event.submitter, event.currentTarget);
    }

    editor.addEventListener("submit", confirmSubmission);
    document.getElementById("delete-draft-form")?.addEventListener("submit", confirmSubmission);
    document.querySelectorAll("a[data-confirm]").forEach(link => {
        link.addEventListener("click", event => {
            if (event.defaultPrevented) return;
            event.preventDefault();
            ask(link);
        });
    });

    cancelButton.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        if (dialog.open) return;
        const trigger = pendingAction?.trigger;
        pendingAction = null;
        trigger?.focus();
    });
    confirmButton.addEventListener("click", () => {
        if (!pendingAction) return;
        const { trigger, form } = pendingAction;
        pendingAction = null;
        confirmButton.disabled = true;
        dialog.close();
        trigger.focus();
        if (form) {
            // Revalidate and keep the original button's action/form association.
            // Approval lasts only for this synchronous submission attempt.
            approvedSubmitter = trigger;
            try {
                form.requestSubmit(trigger);
            } finally {
                approvedSubmitter = null;
            }
        } else {
            window.crmUX?.allowNavigation();
            window.location.assign(trigger.href);
        }
    });
})();

(() => {
    "use strict";
    const editor = document.querySelector("[data-order-editor]");
    if (!editor) return;

    const customers = JSON.parse(document.getElementById("order-customer-catalog").textContent);
    const picker = editor.querySelector("[data-customer-picker]");
    const input = picker.querySelector("[data-customer-search]");
    const list = picker.querySelector("[data-customer-options]");
    const status = editor.querySelector("[data-customer-search-status]");
    const customerId = editor.querySelector('[name="customer"]');
    const mode = editor.querySelector('[name="customer_mode"]');
    const badge = editor.querySelector("[data-new-customer-badge]");
    const dialog = editor.querySelector("[data-customer-dialog]");
    const newFields = [...dialog.querySelectorAll("input, select, textarea")];
    const customerNotes = editor.querySelector("[data-customer-notes]");
    const newNotes = editor.querySelector('[name="customer-notes"]');
    const newEmail = editor.querySelector('[name="customer-email"]');
    const editButton = editor.querySelector("[data-edit-customer]");
    const dialogTitle = dialog.querySelector("[data-customer-dialog-title]");
    const useButton = dialog.querySelector("[data-use-customer]");
    const cancelButton = dialog.querySelector("[data-cancel-customer]");
    const dialogHelp = dialog.querySelector("[data-customer-dialog-help]");
    const saveErrors = dialog.querySelector("[data-customer-save-errors]");
    let matches = [];
    let activeIndex = -1;
    let snapshot = null;
    let editingCustomerId = mode.value === "edit" ? customerId.value : "";
    let savingCustomer = false;
    let dialogInitial = "";
    const dialogValues = () => JSON.stringify(newFields.map(field => field.value));
    ["input", "change"].forEach(type => dialog.addEventListener(type, () => {
        dialog.dataset.unsavedChanges = String(dialog.open && dialogValues() !== dialogInitial);
    }));

    function updateCustomerNotes() {
        const selected = customers.find(customer => String(customer.id) === customerId.value);
        const notes = mode.value === "new" || mode.value === "edit" ? newNotes.value : selected?.notes;
        customerNotes.textContent = notes || "No customer notes.";
        const contact = editor.querySelector("[data-customer-contact]");
        if (contact) {
            contact.replaceChildren();
            const details = selected?.details || {};
            if (mode.value !== "new" && details.email) {
                const link = document.createElement("a"); link.href = "mailto:" + details.email; link.textContent = details.email; contact.append(link);
            }
            if (mode.value !== "new" && details.primary_phone) {
                const link = document.createElement("a"); link.href = "tel:" + details.primary_phone.replace(/[^+\d]/g, ""); link.textContent = details.primary_phone; contact.append(link);
            }
        }
    }

    function validateNewEmail() {
        const email = newEmail.value.trim().toLowerCase();
        const duplicate = customers.some(customer => String(customer.id) !== editingCustomerId && customer.email.trim().toLowerCase() === email);
        newEmail.setCustomValidity(email && duplicate ? "A customer with this email already exists." : "");
    }
    newEmail.addEventListener("input", validateNewEmail);

    function enableNewFields(enabled) {
        newFields.forEach(field => { field.disabled = !enabled; });
        badge.hidden = mode.value !== "new" && mode.value !== "edit";
        badge.textContent = mode.value === "edit" ? "Customer changes" : "New customer";
        if (editButton) editButton.disabled = mode.value !== "new" && !customers.some(customer => String(customer.id) === customerId.value);
        updateCustomerNotes();
        editor.dispatchEvent(new Event("crm:changed", { bubbles: true }));
    }

    function closeList() {
        list.hidden = true;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        activeIndex = -1;
    }

    function showMatches(showAll = false) {
        const words = showAll ? [] : input.value.trim().toLocaleLowerCase().split(/\s+/);
        const filtered = customers.filter(customer => !customer.is_archived && words.every(word => customer.label.toLocaleLowerCase().includes(word)));
        matches = filtered.slice(0, 20);
        activeIndex = -1;
        input.removeAttribute("aria-activedescendant");
        list.replaceChildren();
        matches.forEach(customer => {
            const option = document.createElement("li");
            option.id = `customer-option-${customer.id}`;
            option.dataset.customerId = String(customer.id);
            option.setAttribute("role", "option");
            option.setAttribute("aria-selected", "false");
            option.textContent = customer.label;
            list.append(option);
        });
        if (!matches.length) {
            const empty = document.createElement("li");
            empty.className = "customer-empty";
            empty.setAttribute("role", "presentation");
            empty.textContent = "No customers found";
            list.append(empty);
        }
        status.textContent = `${filtered.length} customer${filtered.length === 1 ? "" : "s"} found${filtered.length > 20 ? "; type to narrow the list" : ""}.`;
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
    }

    function chooseCustomer(customer) {
        customerId.value = String(customer.id);
        mode.value = "existing";
        editingCustomerId = "";
        input.value = customer.label;
        input.setCustomValidity("");
        enableNewFields(false);
        closeList();
        status.textContent = `${customer.name} selected.`;
    }

    input.addEventListener("focus", () => showMatches(Boolean(customerId.value) || mode.value === "new"));
    input.addEventListener("click", () => {
        if (list.hidden) showMatches(Boolean(customerId.value) || mode.value === "new");
    });
    input.addEventListener("input", () => {
        customerId.value = "";
        mode.value = "existing";
        editingCustomerId = "";
        enableNewFields(false);
        input.setCustomValidity("Choose a customer from the list or create a new one.");
        showMatches();
    });
    input.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            if (!list.hidden) event.preventDefault();
            closeList();
        } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (list.hidden) showMatches(Boolean(customerId.value) || mode.value === "new");
            if (!matches.length) return;
            activeIndex = event.key === "ArrowDown" ? (activeIndex + 1) % matches.length : (activeIndex <= 0 ? matches.length - 1 : activeIndex - 1);
            [...list.children].forEach((option, index) => option.setAttribute("aria-selected", String(index === activeIndex)));
            const active = list.children[activeIndex];
            input.setAttribute("aria-activedescendant", active.id);
            active.scrollIntoView({ block: "nearest" });
        } else if (event.key === "Enter" && !list.hidden) {
            event.preventDefault();
            if (activeIndex >= 0) chooseCustomer(matches[activeIndex]);
            else if (matches.length === 1) chooseCustomer(matches[0]);
        } else if (event.key === "Tab") {
            closeList();
        }
    });
    list.addEventListener("pointerdown", event => event.preventDefault());
    list.addEventListener("click", event => {
        const option = event.target.closest("[data-customer-id]");
        if (option) chooseCustomer(customers.find(customer => String(customer.id) === option.dataset.customerId));
    });
    input.addEventListener("blur", closeList);
    document.addEventListener("pointerdown", event => {
        if (!picker.contains(event.target)) closeList();
    });

    function openDialog(edit = false) {
        snapshot = {
            values: newFields.map(field => field.value),
            mode: mode.value,
            customer: customerId.value,
            label: input.value,
            editingCustomerId,
        };
        const selected = customers.find(customer => String(customer.id) === customerId.value);
        const editingNew = edit && mode.value === "new";
        editingCustomerId = edit && !editingNew && selected ? String(selected.id) : "";
        if (editingCustomerId && mode.value !== "edit") {
            newFields.forEach(field => { field.value = selected.details[field.name.replace(/^customer-/, "")] || ""; });
        } else if (!editingCustomerId && mode.value !== "new") {
            newFields.forEach(field => { field.value = ""; });
        }
        dialogTitle.textContent = editingCustomerId ? "Edit Customer" : "New customer";
        useButton.textContent = editingCustomerId ? "Save customer" : "Use customer";
        dialogHelp.textContent = editingCustomerId ? "Saving updates this customer immediately." : "New customers are saved with the order.";
        saveErrors.hidden = true;
        closeList();
        enableNewFields(true);
        dialogInitial = dialogValues();
        dialog.dataset.unsavedChanges = "false";
        dialog.showModal();
        newFields.find(field => field.type !== "hidden")?.focus();
    }

    function cancelDialog() {
        if (savingCustomer) return;
        if (snapshot) {
            newFields.forEach((field, index) => { field.value = snapshot.values[index]; });
            mode.value = snapshot.mode;
            customerId.value = snapshot.customer;
            input.value = snapshot.label;
            editingCustomerId = snapshot.editingCustomerId;
        }
        validateNewEmail();
        if (mode.value === "new" && !newFields.every(field => field.checkValidity())) {
            mode.value = "existing";
            customerId.value = "";
            input.value = "";
        }
        if (mode.value === "edit" && !newFields.every(field => field.checkValidity())) {
            const selected = customers.find(customer => String(customer.id) === customerId.value);
            mode.value = "existing";
            editingCustomerId = "";
            input.value = selected?.label || "";
        }
        enableNewFields(mode.value === "new" || mode.value === "edit");
        dialog.dataset.unsavedChanges = "false";
        dialog.close();
        snapshot = null;
    }

    async function saveCustomer() {
        const selected = customers.find(customer => String(customer.id) === editingCustomerId);
        const body = new URLSearchParams();
        newFields.forEach(field => body.append(field.name, field.value));
        body.append("revision", editor.querySelector('[name="revision"]').value);
        savingCustomer = true;
        useButton.disabled = true;
        useButton.textContent = "Saving…";
        cancelButton.disabled = true;
        newFields.forEach(field => { field.disabled = true; });
        saveErrors.hidden = true;
        try {
            const response = await fetch(selected.save_url, {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-CSRFToken": editor.querySelector('[name="csrfmiddlewaretoken"]').value },
                body,
            });
            const result = await response.json();
            if (!response.ok) {
                const errors = Object.entries(result.errors || {}).flatMap(([name, errors]) =>
                    errors.map(error => `${name === "__all__" ? "" : name.replaceAll("_", " ") + ": "}${error.message}`));
                saveErrors.textContent = result.message || errors.join("\n") || "Could not save the customer. Please try again.";
                saveErrors.hidden = false;
                return;
            }
            Object.assign(selected, result.customer);
            chooseCustomer(selected);
            snapshot = null;
            dialog.dataset.unsavedChanges = "false";
            dialog.close();
            status.textContent = "Customer saved.";
            window.crmUX?.notify("Customer saved. Any unsaved order changes still need to be saved.");
        } catch {
            saveErrors.textContent = "Could not confirm the customer save. Please try again.";
            saveErrors.hidden = false;
        } finally {
            savingCustomer = false;
            useButton.disabled = false;
            useButton.textContent = "Save customer";
            cancelButton.disabled = false;
            if (dialog.open) newFields.forEach(field => { field.disabled = false; });
        }
    }

    async function useCustomer() {
        if (savingCustomer) return;
        validateNewEmail();
        const invalid = newFields.find(field => !field.checkValidity());
        if (invalid) {
            invalid.reportValidity();
            return;
        }
        if (editingCustomerId) {
            await saveCustomer();
            return;
        }
        const first = editor.querySelector('[name="customer-first_name"]').value.trim();
        const last = editor.querySelector('[name="customer-last_name"]').value.trim();
        mode.value = "new";
        customerId.value = "";
        input.value = `${first} ${last}`.trim();
        input.setCustomValidity("");
        enableNewFields(true);
        dialog.dataset.unsavedChanges = "false";
        dialog.close();
        snapshot = null;
        status.textContent = "New customer selected.";
    }

    editor.querySelector("[data-create-customer]")?.addEventListener("click", () => openDialog());
    editButton?.addEventListener("click", () => openDialog(true));
    dialog.querySelector("[data-cancel-customer]").addEventListener("click", cancelDialog);
    dialog.querySelector("[data-use-customer]").addEventListener("click", useCustomer);
    dialog.addEventListener("cancel", event => {
        event.preventDefault();
        cancelDialog();
    });
    dialog.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.target.matches("textarea, button")) {
            event.preventDefault();
            useCustomer();
        }
    });

    if (mode.value === "new" || mode.value === "edit") {
        const first = editor.querySelector('[name="customer-first_name"]').value;
        const last = editor.querySelector('[name="customer-last_name"]').value;
        input.value = `${first} ${last}`.trim();
    } else {
        const selected = customers.find(customer => String(customer.id) === customerId.value);
        if (selected) input.value = selected.label;
    }
    enableNewFields(mode.value === "new" || mode.value === "edit");
    if ((mode.value === "new" || mode.value === "edit") && dialog.dataset.hasErrors === "true") openDialog(mode.value === "edit");
})();

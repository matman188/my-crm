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
    let matches = [];
    let activeIndex = -1;
    let snapshot = null;

    function enableNewFields(enabled) {
        newFields.forEach(field => { field.disabled = !enabled; });
        badge.hidden = mode.value !== "new";
    }

    function closeList() {
        list.hidden = true;
        input.setAttribute("aria-expanded", "false");
        input.removeAttribute("aria-activedescendant");
        activeIndex = -1;
    }

    function showMatches(showAll = false) {
        const words = showAll ? [] : input.value.trim().toLocaleLowerCase().split(/\s+/);
        const filtered = customers.filter(customer => words.every(word => customer.label.toLocaleLowerCase().includes(word)));
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

    function openDialog() {
        snapshot = {
            values: newFields.map(field => field.value),
            mode: mode.value,
            customer: customerId.value,
            label: input.value,
        };
        closeList();
        enableNewFields(true);
        dialog.showModal();
        newFields.find(field => field.type !== "hidden")?.focus();
    }

    function cancelDialog() {
        if (snapshot) {
            newFields.forEach((field, index) => { field.value = snapshot.values[index]; });
            mode.value = snapshot.mode;
            customerId.value = snapshot.customer;
            input.value = snapshot.label;
        }
        if (mode.value === "new" && !newFields.every(field => field.checkValidity())) {
            mode.value = "existing";
            customerId.value = "";
            input.value = "";
        }
        enableNewFields(mode.value === "new");
        dialog.close();
        snapshot = null;
    }

    function useCustomer() {
        const invalid = newFields.find(field => !field.checkValidity());
        if (invalid) {
            invalid.reportValidity();
            return;
        }
        const first = editor.querySelector('[name="customer-first_name"]').value.trim();
        const last = editor.querySelector('[name="customer-last_name"]').value.trim();
        mode.value = "new";
        customerId.value = "";
        input.value = `${first} ${last}`.trim();
        input.setCustomValidity("");
        enableNewFields(true);
        dialog.close();
        snapshot = null;
        status.textContent = "New customer selected.";
    }

    editor.querySelector("[data-create-customer]")?.addEventListener("click", openDialog);
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

    if (mode.value === "new") {
        const first = editor.querySelector('[name="customer-first_name"]').value;
        const last = editor.querySelector('[name="customer-last_name"]').value;
        input.value = `${first} ${last}`.trim();
    } else {
        const selected = customers.find(customer => String(customer.id) === customerId.value);
        if (selected) input.value = selected.label;
    }
    enableNewFields(mode.value === "new");
    if (mode.value === "new" && dialog.dataset.hasErrors === "true") openDialog();
})();

(() => {
    "use strict";
    const editor = document.querySelector("[data-order-editor]");
    if (!editor) return;
    const catalog = JSON.parse(document.getElementById("order-service-catalog").textContent);
    const services = new Map(catalog.map(service => [String(service.id), service]));
    const currency = editor.dataset.currency;
    const locked = editor.dataset.orderLocked === "true";
    const money = cents => `${currency} ${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
    const cents = price => {
        const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(String(price));
        return match ? BigInt(match[1]) * 100n + BigInt((match[2] || "").padEnd(2, "0")) : 0n;
    };
    const quantity = input => {
        const value = input?.value || "";
        return /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= Number(input.max) ? BigInt(value) : 0n;
    };
    const field = (row, name) => row.querySelector(`[name="${row.dataset.formPrefix}-${name}"]`);
    const deleted = row => Boolean(field(row, "DELETE")?.checked);
    const removed = [];
    const disabledBeforeRemoval = new WeakMap();
    const changed = () => editor.dispatchEvent(new Event("crm:changed", { bubbles: true }));
    const notesSelector = "textarea[data-order-notes]";

    function sizeNotes(root) {
        const notes = root.matches(notesSelector) ? [root] : [...root.querySelectorAll(notesSelector)];
        // Reset to the two-row HTML size before measuring so notes can shrink too.
        notes.forEach(note => {
            note.style.height = "";
            note.style.overflowY = "hidden";
        });
        const heights = notes.map(note => note.scrollHeight > note.clientHeight
            ? note.scrollHeight + note.offsetHeight - note.clientHeight : 0);
        notes.forEach((note, index) => {
            if (heights[index] > 0) note.style.height = `${heights[index]}px`;
        });
    }

    function removalFeedback() {
        const feedback = editor.querySelector("[data-removal-feedback]");
        feedback.hidden = removed.length === 0;
        editor.querySelector("[data-removal-message]").textContent = `${removed.length} removed. Changes take effect when you save.`;
    }

    function hideDeleted(row) {
        if (!deleted(row)) return;
        row.hidden = true;
        disabledBeforeRemoval.set(row, [...row.querySelectorAll("input, select, textarea")].map(input => [input, input.disabled]));
        row.querySelectorAll("input, select, textarea").forEach(input => {
            if (input.type !== "hidden" && !input.name.endsWith("-DELETE")) input.disabled = true;
        });
    }

    function populateServices(root) {
        root.querySelectorAll("[data-charge]").forEach(row => {
            const select = field(row, "service");
            const value = select.value;
            const general = Boolean(row.closest("[data-general]"));
            const item = row.closest("[data-order-item]");
            const productId = item ? Number(field(item, "product").value) : null;
            select.replaceChildren(new Option("Choose a service", ""));
            catalog.filter(service => ((locked || general || String(productId) === item?.dataset.originalProduct) && String(service.id) === row.dataset.originalService) || (!service.is_archived && (general ? service.products.length === 0 : productId && (
                service.products.length === 0 || service.products.includes(productId)
            )))).forEach(service => {
                const captured = String(service.id) === row.dataset.originalService && row.dataset.originalPrice !== "";
                const label = `${service.name}${service.products.length === 0 ? " (Global service)" : ""} — ${currency} ${captured ? row.dataset.originalPrice : service.price}${captured ? " (captured)" : ""}${service.is_archived ? " (archived)" : ""}`;
                const option = new Option(label, String(service.id));
                option.disabled = String(service.price).startsWith("-");
                select.add(option);
            });
            select.value = value;
        });
    }

    function recalculate() {
        let total = 0n;
        let visibleIndex = 0;
        editor.querySelectorAll("[data-order-item]").forEach(item => {
            if (!deleted(item)) item.querySelector("[data-item-heading]").textContent = `Item ${++visibleIndex}`;
            item.dataset.subtotal = "0";
        });
        editor.querySelectorAll("[data-charge]").forEach(row => {
            const item = row.closest("[data-order-item]");
            const serviceId = field(row, "service").value;
            const service = services.get(serviceId);
            const captured = serviceId === row.dataset.originalService && row.dataset.originalPrice !== "";
            const unitPrice = cents(captured ? row.dataset.originalPrice : service?.price || "0");
            const amount = deleted(row) || (item && deleted(item)) ? 0n : unitPrice * quantity(field(row, "quantity"));
            row.querySelector("[data-unit-price]").textContent = service ? money(unitPrice) : "—";
            row.querySelector("[data-charge-total]").textContent = money(amount);
            if (item) item.dataset.subtotal = String(BigInt(item.dataset.subtotal) + amount);
            total += amount;
        });
        editor.querySelectorAll("[data-order-item]").forEach(item => {
            item.querySelector("[data-item-total]").textContent = money(BigInt(item.dataset.subtotal));
        });
        document.querySelectorAll("[data-order-total]").forEach(display => {
            display.textContent = money(total);
        });
    }

    function appendRow(container, template, placeholder, rows, rowSelector) {
        const count = container.querySelector('input[name$="-TOTAL_FORMS"]');
        const index = Number(count.value);
        const activeRows = [...rows.querySelectorAll(rowSelector)].filter(row => !deleted(row)).length;
        if (index >= 60 || activeRows >= 50) {
            const feedback = editor.querySelector("[data-editor-feedback]");
            feedback.textContent = "Up to 50 items or services per section are supported. Save your removals before adding more entries.";
            feedback.hidden = false;
            return;
        }
        rows.insertAdjacentHTML("beforeend", template.innerHTML.replaceAll(placeholder, String(index)));
        count.value = String(index + 1);
        populateServices(rows.lastElementChild);
        // A newly added charge is itself the root, rather than a descendant.
        if (rows.lastElementChild.matches("[data-charge]")) populateServices(container);
        sizeNotes(rows.lastElementChild);
        rows.lastElementChild.querySelector("select, input:not([type=hidden])")?.focus();
        recalculate();
        changed();
        return rows.lastElementChild;
    }

    editor.addEventListener("click", event => {
        const button = event.target.closest("button");
        if (!button) return;
        if (button.matches("[data-assign-to-me]")) {
            const assignedTo = editor.querySelector('[name="assigned_to"]');
            const currentUserId = button.dataset.assignToMe;
            if (assignedTo && !assignedTo.disabled && [...assignedTo.options].some(option => option.value === currentUserId && !option.disabled)) {
                assignedTo.value = currentUserId;
                assignedTo.dispatchEvent(new Event("change", { bubbles: true }));
                assignedTo.focus();
            }
        } else if (button.matches("[data-add-item]")) {
            appendRow(editor, editor.querySelector("[data-item-template]"), "__prefix__", editor.querySelector("[data-item-rows]"), "[data-order-item]");
        } else if (button.matches("[data-add-charge]")) {
            const container = button.closest("[data-services]");
            appendRow(container, container.querySelector("[data-charge-template]"), "__charge__", container.querySelector("[data-service-rows]"), "[data-charge]");
        } else if (button.matches("[data-duplicate-item]")) {
            if (locked) return;
            const original = button.closest("[data-order-item]");
            const clone = original.cloneNode(true);
            const oldPrefix = original.dataset.formPrefix;
            clone.querySelectorAll("input, select, textarea").forEach((control, i) => {
                const source = original.querySelectorAll("input, select, textarea")[i];
                control.value = source.value;
                if (control.type === "checkbox") control.checked = source.checked;
            });
            // Clone markup alone does not retain live select/textarea values.
            clone.querySelectorAll("select").forEach(select => [...select.options].forEach(option => option.selected ? option.setAttribute("selected", "") : option.removeAttribute("selected")));
            clone.querySelectorAll("textarea").forEach(control => { control.textContent = control.value; });
            clone.querySelectorAll("input").forEach(control => { control.setAttribute("value", control.value); });
            clone.querySelectorAll("[data-charge]").forEach(row => { row.dataset.originalService = ""; row.dataset.originalPrice = ""; });
            clone.dataset.originalProduct = "";
            if (original.dataset.productArchived === "true") {
                const product = field(clone, "product");
                product.value = "";
                [...product.options].forEach(option => option.selected = option.value === "");
                [...product.options].forEach(option => option.selected ? option.setAttribute("selected", "") : option.removeAttribute("selected"));
            }
            clone.querySelectorAll("input[name$='-id']").forEach(control => { control.value = ""; control.setAttribute("value", ""); });
            clone.querySelectorAll("input[name$='-INITIAL_FORMS']").forEach(control => { control.value = "0"; control.setAttribute("value", "0"); });
            clone.querySelectorAll("input[name$='-item']").forEach(control => { control.value = ""; control.setAttribute("value", ""); });
            clone.querySelectorAll("[data-charge]").forEach(row => {
                if (deleted(row)) row.remove();
            });
            // Keep management indexes intact; removed cloned rows become empty extras.
            const markup = clone.outerHTML.replaceAll(oldPrefix, "items-__copy_item__");
            const added = appendRow(editor, { innerHTML: markup }, "__copy_item__", editor.querySelector("[data-item-rows]"), "[data-order-item]");
            if (added) { populateServices(added); recalculate(); changed(); window.crmUX?.notify("Item duplicated using current service prices. Check the product, services and deadline before saving."); }
        } else if (button.matches("[data-apply-deadline]")) {
            const date = editor.querySelector("[data-bulk-date]");
            const time = editor.querySelector("[data-bulk-time]");
            if (!date.value || !date.checkValidity() || !time.checkValidity()) {
                date.setCustomValidity(date.value ? "" : "Choose a due date first."); date.reportValidity(); date.setCustomValidity(""); return;
            }
            editor.querySelectorAll("[data-order-item]").forEach(row => {
                if (deleted(row) || field(row, "due_date").disabled) return;
                field(row, "due_date").value = date.value;
                field(row, "due_time").value = time.value;
            });
            changed();
            window.crmUX?.notify("Deadline applied to all items. Save the order to keep it.");
        } else if (button.matches("[data-undo-removal]")) {
            const row = removed.pop();
            if (!row) return;
            field(row, "DELETE").checked = false;
            row.hidden = false;
            (disabledBeforeRemoval.get(row) || []).forEach(([input, disabled]) => { input.disabled = disabled; });
            sizeNotes(row);
            removalFeedback(); recalculate(); changed();
            row.querySelector("select:not(:disabled), input:not(:disabled):not([type=hidden]), textarea:not(:disabled)")?.focus();
        } else if (button.matches("[data-remove-charge], [data-remove-item]")) {
            const row = button.closest(button.matches("[data-remove-item]") ? "[data-order-item]" : "[data-charge]");
            field(row, "DELETE").checked = true;
            hideDeleted(row);
            removed.push(row);
            removalFeedback();
            recalculate();
            changed();
        }
    });

    editor.addEventListener("change", event => {
        if (event.target.name.endsWith("-product")) populateServices(event.target.closest("[data-order-item]"));
        recalculate();
    });
    editor.addEventListener("input", event => {
        if (event.target.matches(notesSelector)) sizeNotes(event.target);
        recalculate();
    });
    window.addEventListener("resize", () => sizeNotes(editor));

    editor.querySelectorAll("[data-order-item], [data-charge]").forEach(row => {
        if (deleted(row)) {
            hideDeleted(row);
            if (!row.parentElement.closest("[data-order-item][hidden]")) removed.push(row);
        }
    });
    removalFeedback();
    populateServices(editor);
    sizeNotes(editor);
    recalculate();
})();

(() => {
    "use strict";
    const editor = document.querySelector("[data-order-editor]");
    if (!editor) return;
    const catalog = JSON.parse(document.getElementById("order-service-catalog").textContent);
    const services = new Map(catalog.map(service => [String(service.id), service]));
    const currency = editor.dataset.currency;
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

    function hideDeleted(row) {
        if (!deleted(row)) return;
        row.hidden = true;
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
            catalog.filter(service => general ? service.products.length === 0 : productId && (
                service.products.length === 0 || service.products.includes(productId)
            )).forEach(service => {
                const label = `${service.name} — ${currency} ${service.price}`;
                const option = new Option(label, String(service.id));
                option.disabled = String(service.price).startsWith("-");
                select.add(option);
            });
            select.value = value;
        });
    }

    function recalculate() {
        let total = 0n;
        editor.querySelectorAll("[data-order-item]").forEach((item, index) => {
            item.querySelector("[data-item-heading]").textContent = `Item ${index + 1}`;
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
        editor.querySelector("[data-order-total]").textContent = money(total);
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
        rows.lastElementChild.querySelector("select, input:not([type=hidden])")?.focus();
        recalculate();
    }

    editor.addEventListener("click", event => {
        const button = event.target.closest("button");
        if (!button) return;
        if (button.matches("[data-add-item]")) {
            appendRow(editor, editor.querySelector("[data-item-template]"), "__prefix__", editor.querySelector("[data-item-rows]"), "[data-order-item]");
        } else if (button.matches("[data-add-charge]")) {
            const container = button.closest("[data-services]");
            appendRow(container, container.querySelector("[data-charge-template]"), "__charge__", container.querySelector("[data-service-rows]"), "[data-charge]");
        } else if (button.matches("[data-remove-charge], [data-remove-item]")) {
            const row = button.closest(button.matches("[data-remove-item]") ? "[data-order-item]" : "[data-charge]");
            field(row, "DELETE").checked = true;
            hideDeleted(row);
            recalculate();
        }
    });

    editor.addEventListener("change", event => {
        if (event.target.name.endsWith("-product")) populateServices(event.target.closest("[data-order-item]"));
        recalculate();
    });
    editor.addEventListener("input", recalculate);

    editor.querySelectorAll("[data-order-item], [data-charge]").forEach(hideDeleted);
    populateServices(editor);
    recalculate();
})();

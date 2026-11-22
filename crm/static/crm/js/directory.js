(() => {
    "use strict";
    const directory = document.querySelector("[data-directory]");
    if (!directory) return;

    directory.addEventListener("click", event => {
        if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        if (event.target.closest("a, button, input, label, select, form, details, .directory-selection-cell") || window.getSelection()?.toString()) return;
        event.target.closest("[data-directory-row]")?.querySelector("[data-directory-link]")?.click();
    });

    const form = directory.querySelector("[data-directory-selection]");
    if (!form) return;
    const records = [...directory.querySelectorAll('input[name="selected"]')];
    const selectPage = directory.querySelector("[data-directory-select-page]");
    const selectRemaining = form.querySelector("[data-directory-remaining]");
    const action = form.elements.namedItem("bulk_action");
    const scope = form.elements.namedItem("scope");
    const total = Number(form.elements.namedItem("total").value);
    const apply = form.querySelector("[data-directory-apply]");
    const status = form.querySelector("[data-directory-count]");

    function updateSelection() {
        const checked = records.filter(record => record.checked).length;
        const allMatching = scope.value === "all";
        const count = allMatching ? total : checked;
        const countLabel = count.toLocaleString();
        selectPage.checked = checked === records.length;
        selectPage.indeterminate = checked > 0 && !selectPage.checked;
        selectRemaining.hidden = allMatching || !selectPage.checked || total <= records.length;
        status.textContent = allMatching ? `All ${countLabel} matching entries selected` : `${countLabel} selected`;
        records.forEach(record => record.closest("tr").classList.toggle("is-selected", record.checked));

        const label = action.selectedOptions[0].textContent;
        const target = allMatching ? `all ${countLabel} matching entries` : `${countLabel} selected ${count === 1 ? "entry" : "entries"}`;
        apply.disabled = !action.value || !count;
        apply.classList.toggle("danger", action.value === "delete");
        apply.dataset.confirmTitle = `${label} entries`;
        apply.dataset.confirm = `${label} ${target}?${action.value === "delete" ? " Deletion is permanent. Entries linked to orders will be kept." : ""}`;
    }

    selectRemaining.textContent = `Select remaining ${(total - records.length).toLocaleString()}`;
    selectRemaining.addEventListener("click", () => {
        scope.value = "all";
        updateSelection();
        action.focus();
    });
    directory.addEventListener("change", event => {
        if (event.target === selectPage) {
            records.forEach(record => { record.checked = selectPage.checked; });
            scope.value = "page";
        } else if (event.target.matches('input[name="selected"]')) {
            scope.value = "page";
        } else if (event.target !== action) {
            return;
        }
        updateSelection();
    });
    window.addEventListener("pageshow", updateSelection);
    updateSelection();
})();

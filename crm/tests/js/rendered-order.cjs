// Exercises the actual Django-rendered forms; invoked by test_qol.py.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const { JSDOM } = require("jsdom");
const fixtures = JSON.parse(fs.readFileSync(0, "utf8"));
const directory = path.join(__dirname, "../../static/crm/js");
const checks = [];
const windows = [];

async function boot(html, url) {
    const dom = new JSDOM(html, { url: "http://localhost" + url, runScripts: "outside-only" });
    const w = dom.window;
    windows.push(w);
    await new Promise(resolve => w.document.readyState === "loading" ? w.document.addEventListener("DOMContentLoaded", resolve, { once: true }) : resolve());
    w.scrollTo = () => {};
    w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    w.HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new w.Event("close")); };
    w.HTMLFormElement.prototype.requestSubmit = function (submitter) {
        if (this.checkValidity()) this.dispatchEvent(new w.SubmitEvent("submit", { bubbles: true, cancelable: true, submitter }));
    };
    // jsdom has no layout. Model text rows and borders for the autosize check.
    Object.defineProperties(w.HTMLTextAreaElement.prototype, {
        clientHeight: { get() { return this.style.height ? parseFloat(this.style.height) - 2 : this.rows * 20 + 24; } },
        offsetHeight: { get() { return this.clientHeight + 2; } },
        scrollHeight: { get() { return Math.max(this.clientHeight, this.value.split("\n").length * 20 + 24); } },
    });
    for (const name of ["workspace", "list-filters", "directory", "order-customer", "order-confirmation", "order-form"]) w.eval(fs.readFileSync(path.join(directory, name + ".js"), "utf8"));
    w.document.dispatchEvent(new w.Event("DOMContentLoaded"));
    const editor = w.document.querySelector("[data-order-editor]");
    return { w, editor, q: selector => w.document.querySelector(selector), change(control, value) { control.value = value; control.dispatchEvent(new w.Event("change", { bubbles: true })); } };
}

(async () => {
    const ui = await boot(fixtures.draft, "/orders/1/edit/?next=%2Forders%2F%3Fview%3Dmine%26page%3D2");
    const { w, q, editor, change } = ui;
    assert.equal(w.crmUX.isDirty(editor), false);
    assert.match(q("[data-charge] select").selectedOptions[0].textContent, /12.35 \(captured\)/);
    checks.push("initial clean state and captured-price labels");

    const orderNotes = q('[name="notes"]');
    const itemNotes = q('[name="items-0-notes"]');
    const serviceNotes = q('[name="items-0-services-0-notes"]');
    const extraNotes = q('[name="general-0-notes"]');
    for (const note of [orderNotes, itemNotes, serviceNotes, extraNotes]) {
        assert.equal(note.rows, 2);
        assert.equal(note.style.height, "");
    }
    const originalNotes = orderNotes.value;
    orderNotes.value = "First line\nSecond line\nThird line";
    orderNotes.dispatchEvent(new w.Event("input", { bubbles: true }));
    assert.equal(orderNotes.style.height, "86px");
    orderNotes.value = originalNotes;
    orderNotes.dispatchEvent(new w.Event("input", { bubbles: true }));
    assert.equal(orderNotes.style.height, "");
    itemNotes.value = "First line\nSecond line\nThird line\nFourth line";
    itemNotes.dispatchEvent(new w.Event("input", { bubbles: true }));
    checks.push("order notes start with two rows and grow and shrink as edited");

    q("[data-duplicate-item]").click();
    const items = [...editor.querySelectorAll("[data-order-item]")];
    assert.equal(items.length, 2);
    assert.equal(editor.querySelector('[name="items-TOTAL_FORMS"]').value, "2");
    assert.equal(items[1].querySelector('[name="items-1-id"]').value, "");
    assert.equal(items[1].querySelector('[name="items-1-services-INITIAL_FORMS"]').value, "0");
    assert.equal(items[1].querySelector('[name="items-1-services-0-item"]').value, "");
    assert.equal(items[1].querySelector('[name="items-1-services-0-quantity"]').value, "2");
    assert.equal(items[1].querySelector('[name="items-1-notes"]').style.height, "106px");
    assert.match(items[1].querySelector("[data-unit-price]").textContent, /20.00/);
    assert.equal(w.crmUX.isDirty(editor), true);
    checks.push("duplicate item uses fresh IDs and current prices");

    change(q("[data-bulk-date]"), "2027-02-03");
    change(q("[data-bulk-time]"), "14:30");
    q("[data-apply-deadline]").click();
    for (const item of items) {
        assert.equal(item.querySelector('input[name$="-due_date"]').value, "2027-02-03");
        assert.equal(item.querySelector('input[name$="-due_time"]').value, "14:30");
    }
    checks.push("apply deadline and optional time to all items");
    const removedCharge = items[1].querySelector("[data-charge]");
    removedCharge.querySelector("[data-remove-charge]").click();
    assert.equal(removedCharge.hidden, true);
    assert.equal(removedCharge.querySelector('input[name$="-DELETE"]').checked, true);
    q("[data-undo-removal]").click();
    assert.equal(removedCharge.hidden, false);
    assert.equal(removedCharge.querySelector('input[name$="-DELETE"]').checked, false);
    items[1].querySelector("[data-remove-item]").click();
    assert.equal(items[1].hidden, true);
    q("[data-undo-removal]").click();
    assert.equal(items[1].hidden, false);
    assert.equal(items[1].querySelector("select").disabled, false);
    checks.push("undo item and service removals restores fields and totals");

    // Customer API saves must not reset the order's dirty state or revision.
    const customer = JSON.parse(q("#order-customer-catalog").textContent).find(c => String(c.id) === q('[name="customer"]').value);
    w.fetch = async () => ({ ok: true, json: async () => ({ customer: { ...customer, notes: "Updated customer notes" } }) });
    q("[data-edit-customer]").click();
    q("[data-use-customer]").click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(q("[data-customer-dialog]").open, false);
    assert.equal(w.crmUX.isDirty(editor), true);
    assert.match(q("[data-workspace-toast]").textContent, /Customer saved/);
    checks.push("independent customer save retains unsaved order changes");

    const leave = new w.Event("beforeunload", { cancelable: true });
    w.dispatchEvent(leave);
    assert.equal(leave.defaultPrevented, true);
    q(".order-back-link").click();
    assert.equal(q("[data-workspace-confirm]").open, true);
    q("[data-workspace-cancel]").click();
    assert.equal(w.crmUX.isDirty(editor), true);
    assert.equal(q("[data-workspace-confirm]").open, false);
    checks.push("unsaved navigation warning and cancellation preserve changes");
    const duplicated = Object.fromEntries(new w.FormData(editor));
    assert.equal(duplicated.next, "/orders/?view=mine&page=2");

    const progress = await boot(fixtures.progress, "/orders/2/edit/");
    const refundForm = progress.q("[data-order-refund]");
    const refundAmount = refundForm.elements.namedItem("amount");
    const refundSave = progress.q('button[form="order-refund-form"]');
    assert.equal(progress.editor.elements.namedItem("complaint-logged").type, "checkbox");
    assert.equal(new progress.w.FormData(progress.editor).has("amount"), false);
    assert.equal(new progress.w.FormData(refundForm).has("complaint-details"), false);
    progress.change(refundAmount, "15.00");
    assert.equal(progress.w.crmUX.isDirty(refundForm), true);
    assert.equal(progress.w.crmUX.isDirty(progress.editor), false);
    assert.equal(progress.q('[name="items-0-product"]').disabled, true);
    assert.equal(progress.q('[name="items-0-services-0-quantity"]').disabled, true);
    const progressRow = progress.q("[data-order-item]");
    const date = progressRow.querySelector('input[name$="-due_date"]');
    assert.equal(date.disabled, false);
    progress.change(progress.q("[data-bulk-date]"), "2028-01-02");
    progress.q("[data-apply-deadline]").click();
    assert.equal(date.value, "2028-01-02");
    assert.equal(progressRow.querySelector('input[name$="-due_time"]').value, "");
    checks.push("In Progress keeps commercial fields locked while updating deadlines");
    refundForm.requestSubmit(refundSave);
    assert.equal(progress.q("[data-workspace-confirm]").open, true);
    assert.match(progress.q("[data-workspace-confirm-message]").textContent, /unsaved order changes/);
    progress.q("[data-workspace-cancel]").click();
    assert.equal(date.value, "2028-01-02");
    progress.change(refundAmount, "");
    checks.push("complaints save with the order and refunds have their own inline submit");

    const complete = progress.q('button[name="action"][value="complete"]');
    assert.ok(complete);
    let submitted = null;
    progress.w.document.addEventListener("submit", event => {
        if (!event.defaultPrevented) submitted = event.submitter;
    });
    progress.editor.requestSubmit(complete);
    assert.equal(submitted, null);
    assert.equal(progress.q("[data-order-confirmation]").open, true);
    assert.equal(progress.q("[data-confirm-title]").textContent, complete.textContent.trim());
    progress.q("[data-confirm-accept]").click();
    assert.equal(submitted, complete);
    assert.equal(complete.disabled, false);
    assert.equal(complete.value, "complete");
    submitted = null;
    progress.editor.requestSubmit(complete);
    assert.equal(submitted, null);
    checks.push("confirmed workflow action retains submitter and blocks duplicate submission");

    const orders = await boot(fixtures.orders, "/orders/?status=in_progress");
    const orderRow = orders.q("[data-directory-row]");
    const orderLink = orderRow.querySelector("[data-directory-link]");
    assert.match(orderLink.textContent, /^SO-\d+$/);
    assert.equal(new URL(orderLink.href).searchParams.get("next"), "/orders/?status=in_progress");
    let openedOrder = false;
    orderLink.addEventListener("click", event => { event.preventDefault(); openedOrder = true; });
    orderRow.querySelector("summary").click();
    assert.equal(orderRow.querySelector("details").open, true);
    assert.equal(openedOrder, false);
    orderRow.querySelector(".money").click();
    assert.equal(openedOrder, true);
    checks.push("order rows open the form and leave the item preview operable");

    const [firstEdit, otherEdit] = orders.w.document.querySelectorAll("[data-order-list-edit]");
    const payment = firstEdit.elements.namedItem("payment_status");
    const otherPayment = otherEdit.elements.namedItem("payment_status");
    const rowSave = firstEdit.querySelector("[data-order-row-save]");
    assert.equal(rowSave.disabled, true);
    openedOrder = false;
    payment.click();
    assert.equal(openedOrder, false);
    orders.change(payment, "paid");
    assert.equal(rowSave.disabled, false);
    assert.equal(new orders.w.FormData(firstEdit).get("payment_status"), "paid");
    assert.equal(firstEdit.elements.namedItem("next").value, "/orders/?status=in_progress");
    orders.change(otherPayment, "paid");
    firstEdit.requestSubmit(rowSave);
    assert.equal(orders.q("[data-workspace-confirm]").open, true);
    orders.q("[data-workspace-cancel]").click();
    assert.equal(otherPayment.value, "paid");
    orders.change(otherPayment, "unpaid");
    let savedRow = null;
    orders.w.document.addEventListener("submit", event => {
        if (!event.defaultPrevented) savedRow = event.target;
    });
    firstEdit.requestSubmit(rowSave);
    assert.equal(savedRow, firstEdit);
    checks.push("inline order controls save the selected row and protect other unsaved rows");

    const directory = await boot(fixtures.customers, "/customers/?q=Alex&page=2");
    const recordLink = directory.q("[data-directory-link]");
    assert.equal(new URL(recordLink.href).searchParams.get("next"), "/customers/?q=Alex&page=2");
    let opened = false;
    recordLink.addEventListener("click", event => { event.preventDefault(); opened = true; });
    const recordRow = recordLink.closest("tr");
    recordRow.querySelector('input[name="selected"]').click();
    assert.equal(opened, false);
    assert.equal(directory.q("[data-directory-select-page]").indeterminate, true);
    recordRow.cells[1].click();
    assert.equal(opened, true);

    const form = directory.q("[data-directory-selection]");
    const page = directory.q("[data-directory-select-page]");
    const remaining = directory.q("[data-directory-remaining]");
    const apply = directory.q("[data-directory-apply]");
    assert.equal(remaining.hidden, true);
    page.click();
    assert.equal(directory.q("[data-directory-count]").textContent, "25 selected");
    assert.equal(new directory.w.FormData(form).getAll("selected").length, 25);
    assert.equal(form.elements.namedItem("scope").value, "page");
    assert.equal(remaining.textContent, "Select remaining 2");
    assert.equal(remaining.hidden, false);
    remaining.click();
    assert.equal(form.elements.namedItem("scope").value, "all");
    assert.equal(directory.q("[data-directory-count]").textContent, "All 27 matching entries selected");
    assert.equal(remaining.hidden, true);
    directory.change(form.elements.namedItem("bulk_action"), "delete");
    let deleted = false;
    directory.w.document.addEventListener("submit", event => { if (!event.defaultPrevented) deleted = true; });
    form.requestSubmit(apply);
    assert.equal(deleted, false);
    assert.equal(directory.q("[data-workspace-confirm]").open, true);
    assert.match(directory.q("[data-workspace-confirm-message]").textContent, /Delete all 27 matching entries/);
    directory.q("[data-workspace-cancel]").click();
    assert.equal(deleted, false);
    recordRow.querySelector('input[name="selected"]').click();
    assert.equal(form.elements.namedItem("scope").value, "page");
    assert.equal(directory.q("[data-directory-count]").textContent, "24 selected");
    checks.push("directory row navigation, paged selection, and bulk confirmation");

    const clean = await boot(fixtures.draft, "/orders/1/edit/");
    clean.q("[data-edit-customer]").click();
    clean.change(clean.q('[name="customer-notes"]'), "Unsaved modal note");
    assert.equal(clean.w.crmUX.isDirty(clean.editor), false);
    const modalLeave = new clean.w.Event("beforeunload", { cancelable: true });
    clean.w.dispatchEvent(modalLeave);
    assert.equal(modalLeave.defaultPrevented, true);
    clean.q("[data-cancel-customer]").click();
    const safeLeave = new clean.w.Event("beforeunload", { cancelable: true });
    clean.w.dispatchEvent(safeLeave);
    assert.equal(safeLeave.defaultPrevented, false);
    clean.change(clean.q('[name="notes"]'), "Unsaved order note");
    const logout = clean.q('form[action="/logout/"]');
    logout.requestSubmit(logout.querySelector("button"));
    assert.equal(clean.q("[data-workspace-confirm]").open, true);
    assert.match(clean.q("[data-workspace-confirm-message]").textContent, /Log out and discard/);
    clean.q("[data-workspace-cancel]").click();
    assert.equal(clean.w.crmUX.isDirty(clean.editor), true);
    checks.push("unsaved modal edits and logout are protected");

    console.log(JSON.stringify({ checks, duplicated }));
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => windows.forEach(w => w.close()));

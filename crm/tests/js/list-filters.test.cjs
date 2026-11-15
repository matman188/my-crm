const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const script = fs.readFileSync(path.join(__dirname, "../../static/crm/js/list-filters.js"), "utf8");

function setup() {
    const dom = new JSDOM(`<form method="get" data-list-filters>
        <input name="view" type="hidden" value="open"><input name="customer" type="hidden" value="7">
        <input type="search" name="q" value="Alex">
        <select name="status"><option value="">All statuses</option><option value="draft">Draft</option></select>
        <select name="payment_status"><option value="">All payments</option><option value="paid">Paid</option></select>
        <select name="sort"><option value="newest">Newest</option><option value="deadline">Deadline</option></select>
        <button type="submit">Search</button></form><form id="record"><select name="assigned_to"><option value="1">One</option></select></form>`,
        { url: "http://localhost/orders/?view=open&customer=7&page=3", runScripts: "outside-only" });
    const w = dom.window;
    const form = w.document.querySelector("[data-list-filters]");
    const requests = [];
    form.requestSubmit = () => requests.push(Object.fromEntries(new w.FormData(form)));
    w.eval(script);
    return { w, form, requests, change(name, value) { const field = form.elements.namedItem(name); field.value = value; field.dispatchEvent(new w.Event("change", { bubbles: true })); }, close: () => w.close() };
}

test("dropdowns immediately apply filters while retaining search, queue and customer scope", () => {
    const ui = setup();
    try {
        ui.change("status", "draft");
        assert.equal(ui.requests.length, 1);
        assert.deepEqual(ui.requests[0], { view: "open", customer: "7", q: "Alex", status: "draft", payment_status: "", sort: "newest" });
        assert.equal("page" in ui.requests[0], false);
        ui.change("sort", "deadline");
        assert.equal(ui.requests.length, 2);
        assert.equal(ui.requests[1].status, "draft");
        assert.equal(ui.requests[1].sort, "deadline");
    } finally { ui.close(); }
});

test("typing or blurring text waits for Search or Enter", () => {
    const ui = setup();
    try {
        const query = ui.form.elements.namedItem("q");
        query.value = "Sam";
        query.dispatchEvent(new ui.w.Event("input", { bubbles: true }));
        query.dispatchEvent(new ui.w.Event("change", { bubbles: true }));
        assert.equal(ui.requests.length, 0);
        // Native Search/Enter submits the same GET form and its current controls.
        ui.form.requestSubmit();
        assert.equal(ui.requests[0].q, "Sam");
    } finally { ui.close(); }
});

test("changing payment status exits a legacy Unpaid queue", () => {
    const ui = setup();
    try {
        ui.form.elements.namedItem("view").value = "unpaid";
        ui.change("payment_status", "paid");
        assert.equal(ui.requests[0].view, "all");
        assert.equal(ui.requests[0].payment_status, "paid");
    } finally { ui.close(); }
});

test("record forms and disabled dropdowns do not auto-submit", () => {
    const ui = setup();
    try {
        ui.form.elements.namedItem("status").disabled = true;
        ui.change("status", "draft");
        const other = ui.w.document.querySelector("#record");
        other.requestSubmit = () => assert.fail("A record form must not auto-submit");
        other.querySelector("select").dispatchEvent(new ui.w.Event("change", { bubbles: true }));
        assert.equal(ui.requests.length, 0);
    } finally { ui.close(); }
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const directory = path.join(__dirname, "../../static/crm/js");
const script = fs.readFileSync(path.join(directory, "invoice-settings.js"), "utf8");
const flush = () => new Promise(resolve => setImmediate(resolve));

async function setup() {
    const confirmation = fs.readFileSync(path.join(__dirname, "../../templates/crm/_workspace_dialog.html"), "utf8");
    const dom = new JSDOM(`<form method="post" data-invoice-settings data-preview-url="/system-settings/invoice-preview/">
        <input name="csrfmiddlewaretoken" value="csrf-token" type="hidden"><input name="section" value="invoicing" type="hidden">
        <label for="business-name">Business name</label><input id="business-name" name="company_name" value="Saved Business" required>
        <input name="invoice_logo" type="file"><textarea name="invoice_note">Saved note</textarea>
        <select data-invoice-sample><option value="short">Short</option><option value="long">Long</option></select>
        <button type="submit">Save settings</button><button type="button" data-preview-invoice>Preview sample invoice</button>
        <div data-preview-errors class="non-field-errors" hidden></div></form>
        <dialog data-invoice-preview><button type="button" data-close-invoice-preview>Close</button><p data-preview-status></p><iframe data-preview-frame hidden></iframe><a data-download-invoice-preview download="sample.pdf" hidden></a></dialog>${confirmation}`,
        { url: "http://localhost/system-settings/?tab=invoicing", runScripts: "outside-only" });
    const w = dom.window;
    await new Promise(resolve => w.document.readyState === "loading" ? w.document.addEventListener("DOMContentLoaded", resolve, { once: true }) : resolve());
    w.scrollTo = () => {};
    w.HTMLElement.prototype.scrollIntoView = () => {};
    w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    w.HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new w.Event("close")); };
    const revoked = [];
    w.URL.createObjectURL = () => "blob:http://localhost/sample-preview";
    w.URL.revokeObjectURL = url => revoked.push(url);
    const requests = [];
    let responder = async () => ({ ok: true, headers: { get: () => "application/pdf" }, blob: async () => new w.Blob(["%PDF-sample"], { type: "application/pdf" }) });
    w.fetch = (...args) => { requests.push(args); return responder(...args); };
    w.eval(fs.readFileSync(path.join(directory, "workspace.js"), "utf8"));
    w.eval(script);
    w.document.dispatchEvent(new w.Event("DOMContentLoaded"));
    const q = selector => w.document.querySelector(selector);
    return { w, q, form: q("form"), trigger: q("[data-preview-invoice]"), dialog: q("[data-invoice-preview]"), requests, revoked,
        respond: callback => { responder = callback; }, close: () => w.close(),
        change(selector, value) { const field = q(selector); field.value = value; field.dispatchEvent(new w.Event("input", { bubbles: true })); } };
}

test("preview posts unsaved settings and selected sample, keeps dirty state, and displays PDF", async () => {
    const ui = await setup();
    try {
        assert.equal(ui.w.crmUX.isDirty(ui.form), false);
        ui.change('[name="company_name"]', "Unsaved Business");
        ui.q("[data-invoice-sample]").value = "long";
        let saves = 0;
        ui.form.addEventListener("submit", event => { event.preventDefault(); saves++; });
        ui.trigger.click();
        await flush();
        assert.equal(ui.requests.length, 1);
        const [url, options] = ui.requests[0];
        assert.equal(url, "/system-settings/invoice-preview/");
        assert.equal(options.method, "POST");
        assert.equal(options.headers["X-CSRFToken"], "csrf-token");
        assert.equal(options.body.get("company_name"), "Unsaved Business");
        assert.equal(options.body.get("sample"), "long");
        assert.equal(saves, 0);
        assert.equal(ui.w.crmUX.isDirty(ui.form), true);
        assert.equal(ui.dialog.open, true);
        assert.equal(ui.q("[data-preview-frame]").hidden, false);
        assert.equal(ui.q("[data-download-invoice-preview]").href, "blob:http://localhost/sample-preview");
        assert.equal(ui.trigger.disabled, false);
        assert.match(ui.q("[data-preview-status]").textContent, /not been saved/);
    } finally { ui.close(); }
});

test("closing preview releases its file and returns focus without discarding input", async () => {
    const ui = await setup();
    try {
        ui.change('[name="invoice_note"]', "Unsaved customer note");
        ui.trigger.click(); await flush();
        ui.q("[data-close-invoice-preview]").click();
        assert.equal(ui.dialog.open, false);
        assert.deepEqual(ui.revoked, ["blob:http://localhost/sample-preview"]);
        assert.equal(ui.q("[data-preview-frame]").src, "about:blank");
        assert.equal(ui.q('[name="invoice_note"]').value, "Unsaved customer note");
        assert.equal(ui.w.document.activeElement, ui.trigger);
        assert.equal(ui.w.crmUX.isDirty(ui.form), true);
    } finally { ui.close(); }
});

test("an in-flight preview cannot be repeated and cancellation ignores a late response", async () => {
    const ui = await setup();
    try {
        let finish;
        ui.respond(() => new Promise(resolve => { finish = resolve; }));
        ui.trigger.click(); ui.trigger.click();
        assert.equal(ui.requests.length, 1);
        ui.q("[data-close-invoice-preview]").click();
        assert.equal(ui.requests[0][1].signal.aborted, true);
        finish({ ok: true, headers: { get: () => "application/pdf" }, blob: async () => new ui.w.Blob(["sample"]) });
        await flush();
        assert.equal(ui.dialog.open, false);
        assert.equal(ui.q("[data-preview-frame]").hidden, true);
        assert.equal(ui.trigger.disabled, false);
        assert.equal(ui.q("[data-preview-errors]").hidden, true);
    } finally { ui.close(); }
});

test("server validation and network failures preserve settings and allow retry", async () => {
    const ui = await setup();
    try {
        ui.change('[name="company_name"]', "Keep this name");
        ui.respond(async () => ({ ok: false, headers: { get: () => "application/json" }, json: async () => ({ errors: { company_name: [{ message: "Check this business name." }] } }) }));
        ui.trigger.click(); await flush();
        assert.equal(ui.dialog.open, false);
        assert.match(ui.q("[data-preview-errors]").textContent, /Business name: Check this business name/);
        assert.equal(ui.q('[name="company_name"]').value, "Keep this name");
        assert.equal(ui.w.crmUX.isDirty(ui.form), true);
        ui.respond(async () => { throw new Error("Network unavailable"); });
        ui.trigger.click(); await flush();
        assert.equal(ui.trigger.disabled, false);
        assert.match(ui.q("[data-preview-errors]").textContent, /Network unavailable/);
    } finally { ui.close(); }
});

test("invalid browser fields block preview and missing/expired PDF responses show errors", async () => {
    const ui = await setup();
    try {
        ui.change('[name="company_name"]', "");
        ui.trigger.click(); await flush();
        assert.equal(ui.requests.length, 0);
        ui.change('[name="company_name"]', "Business");
        ui.respond(async () => ({ ok: true, headers: { get: () => "text/html" } }));
        ui.trigger.click(); await flush();
        assert.equal(ui.dialog.open, false);
        assert.match(ui.q("[data-preview-errors]").textContent, /reload the page/);
    } finally { ui.close(); }
});

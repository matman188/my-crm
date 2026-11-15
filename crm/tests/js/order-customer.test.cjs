const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../../static/crm/js/order-customer.js"), "utf8");

function setup() {
    class Element {
        constructor(value = "") {
            this.value = value;
            this.dataset = {};
            this.handlers = {};
            this.children = [];
            this.validationMessage = "";
        }
        addEventListener(name, listener) { (this.handlers[name] ||= []).push(listener); }
        dispatchEvent(event) { return this.fire(event.type); }
        fire(name, extra = {}) {
            const event = { target: this, preventDefault() {}, ...extra };
            return Promise.all((this.handlers[name] || []).map(listener => listener(event)));
        }
        querySelector(selector) { return this.elements[selector]; }
        setCustomValidity(message) { this.validationMessage = message; }
        checkValidity() { return this.disabled || !this.validationMessage; }
        reportValidity() { this.reported = true; }
        setAttribute() {}
        removeAttribute() {}
        replaceChildren() { this.children = []; }
        append(element) { this.children.push(element); }
        focus() {}
    }
    const customers = [
        { id: 1, name: "Alex Smith", label: "Alex Smith", email: "Alex@example.com", notes: "Use side entrance.\n<strong>VIP</strong>" },
        { id: 2, name: "Sam Taylor", label: "Sam Taylor", email: "sam@example.com", notes: "" },
    ];
    customers.forEach(customer => {
        const [first_name, last_name] = customer.name.split(" ");
        customer.details = { first_name, last_name, email: customer.email, primary_phone: "0123456789", notes: customer.notes };
        customer.save_url = `/orders/10/customers/${customer.id}/save/`;
    });
    const editor = new Element();
    const picker = new Element();
    const input = new Element();
    const list = new Element();
    const customerId = new Element("1");
    const mode = new Element("existing");
    const notes = new Element();
    const dialog = new Element();
    dialog.open = false;
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; };
    const fields = Object.fromEntries(["first_name", "last_name", "email", "primary_phone", "notes"].map(name => [name, new Element()]));
    for (const [name, field] of Object.entries(fields)) field.name = `customer-${name}`;
    dialog.querySelectorAll = () => Object.values(fields);
    const open = new Element();
    const edit = new Element();
    const title = new Element();
    const help = new Element();
    const errors = new Element();
    const cancel = new Element();
    const use = new Element();
    picker.elements = { "[data-customer-search]": input, "[data-customer-options]": list };
    dialog.elements = { "[data-cancel-customer]": cancel, "[data-use-customer]": use, "[data-customer-dialog-title]": title, "[data-customer-dialog-help]": help, "[data-customer-save-errors]": errors };
    editor.elements = {
        "[data-customer-picker]": picker,
        "[data-customer-search-status]": new Element(),
        '[name="customer"]': customerId,
        '[name="customer_mode"]': mode,
        "[data-new-customer-badge]": new Element(),
        "[data-customer-dialog]": dialog,
        "[data-customer-notes]": notes,
        "[data-create-customer]": open,
        "[data-edit-customer]": edit,
        '[name="revision"]': new Element("1"),
        '[name="csrfmiddlewaretoken"]': new Element("csrf-token"),
        '[name="notes"]': new Element("Unsaved order note"),
    };
    for (const [name, field] of Object.entries(fields)) editor.elements[`[name="customer-${name}"]`] = field;
    const document = {
        querySelector: () => editor,
        getElementById: () => ({ textContent: JSON.stringify(customers) }),
        addEventListener() {},
        createElement: () => new Element(),
    };
    const requests = [];
    let responder = async (url, options) => {
        const original = customers.find(customer => url === customer.save_url);
        const details = Object.fromEntries([...options.body.entries()].filter(([key]) => key.startsWith("customer-")).map(([key, value]) => [key.slice(9), value]));
        const name = `${details.first_name} ${details.last_name}`;
        return { ok: true, json: async () => ({ customer: { ...original, name, label: name, details, email: details.email, notes: details.notes } }) };
    };
    const fetch = (url, options) => { requests.push({ url, options }); return responder(url, options); };
    const notifications = [];
    vm.runInNewContext(script, { document, fetch, URLSearchParams, Event, window: { crmUX: { notify: message => notifications.push(message) } } });
    const choose = id => list.fire("click", { target: { closest: () => ({ dataset: { customerId: String(id) } }) } });
    const fill = (changes = {}) => {
        const values = { first_name: "New", last_name: "Customer", email: "new@example.com", primary_phone: "0123456789", notes: "New customer instructions", ...changes };
        for (const [name, value] of Object.entries(values)) fields[name].value = value;
    };
    return { editor, customers, input, list, customerId, mode, notes, dialog, fields, open, edit, title, cancel, use, choose, fill, errors, requests, respond: handler => { responder = handler; } };
}

test("customer notes load, follow customer selection, and clear during a new search", () => {
    const ui = setup();
    assert.equal(ui.notes.textContent, ui.customers[0].notes);
    ui.choose(2);
    assert.equal(ui.notes.textContent, "No customer notes.");
    ui.choose(1);
    assert.equal(ui.notes.textContent, ui.customers[0].notes);
    ui.input.value = "Another person";
    ui.input.fire("input");
    assert.equal(ui.notes.textContent, "No customer notes.");
    assert.equal(ui.customerId.value, "");
});

test("an existing archived customer stays visible but is not offered in customer search", () => {
    const ui = setup();
    ui.customers[0].is_archived = true;
    // Use a fresh catalog through a save response to update the in-page entry.
    ui.respond(async () => ({ ok: true, json: async () => ({ customer: { ...ui.customers[0], is_archived: true } }) }));
    ui.edit.fire("click");
    return ui.use.fire("click").then(() => {
        assert.equal(ui.customerId.value, "1");
        assert.equal(ui.notes.textContent, ui.customers[0].notes);
        ui.input.fire("focus");
        assert.equal(ui.list.children.some(option => option.dataset.customerId === "1"), false);
        assert.equal(ui.list.children.some(option => option.dataset.customerId === "2"), true);
    });
});

test("accepted new customer notes are displayed and cancelling later changes restores them", () => {
    const ui = setup();
    ui.open.fire("click");
    ui.fill();
    ui.use.fire("click");
    assert.equal(ui.mode.value, "new");
    assert.equal(ui.notes.textContent, "New customer instructions");
    ui.open.fire("click");
    ui.fields.notes.value = "Do not keep";
    ui.fields.email.value = "ALEX@EXAMPLE.COM";
    ui.fields.email.fire("input");
    assert.notEqual(ui.fields.email.validationMessage, "");
    ui.dialog.fire("cancel");
    assert.equal(ui.mode.value, "new");
    assert.equal(ui.fields.email.value, "new@example.com");
    assert.equal(ui.fields.email.validationMessage, "");
    assert.equal(ui.notes.textContent, "New customer instructions");
});

test("duplicate emails are rejected in the modal regardless of case or whitespace", () => {
    const ui = setup();
    ui.open.fire("click");
    ui.fill({ email: " ALEX@EXAMPLE.COM " });
    ui.use.fire("click");
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.fields.email.validationMessage, "A customer with this email already exists.");
    assert.equal(ui.fields.email.reported, true);
    ui.fields.email.value = "different@example.com";
    ui.fields.email.fire("input");
    ui.use.fire("click");
    assert.equal(ui.fields.email.validationMessage, "");
    assert.equal(ui.dialog.open, false);
    assert.equal(ui.mode.value, "new");
});

test("cancelling new customer entry keeps the selected customer's notes", () => {
    const ui = setup();
    ui.open.fire("click");
    ui.fill();
    ui.cancel.fire("click");
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.customerId.value, "1");
    assert.equal(ui.notes.textContent, ui.customers[0].notes);
    assert.equal(ui.fields.notes.disabled, true);
});

test("Edit customer saves independently, permits its own email, and preserves unsaved order fields", async () => {
    const ui = setup();
    assert.equal(ui.edit.disabled, false);
    ui.edit.fire("click");
    assert.equal(ui.title.textContent, "Edit Customer");
    assert.equal(ui.use.textContent, "Save customer");
    assert.equal(ui.fields.first_name.value, "Alex");
    assert.equal(ui.fields.email.value, "Alex@example.com");
    ui.fields.email.value = " ALEX@EXAMPLE.COM ";
    ui.fields.notes.value = "Updated instructions";
    await ui.use.fire("click");
    assert.equal(ui.fields.email.validationMessage, "");
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.customerId.value, "1");
    assert.equal(ui.notes.textContent, "Updated instructions");
    assert.equal(ui.fields.notes.disabled, true);
    assert.equal(ui.dialog.open, false);
    assert.equal(ui.requests.length, 1);
    const { url, options } = ui.requests[0];
    assert.equal(url, "/orders/10/customers/1/save/");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["X-CSRFToken"], "csrf-token");
    assert.equal(options.body.get("revision"), "1");
    assert.equal(options.body.has("notes"), false);
    assert.equal(ui.editor.elements['[name="notes"]'].value, "Unsaved order note");
});

test("cancelling an existing customer edit restores the selected record and notes", () => {
    const ui = setup();
    ui.edit.fire("click");
    ui.fields.notes.value = "Do not keep";
    ui.cancel.fire("click");
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.customerId.value, "1");
    assert.equal(ui.notes.textContent, ui.customers[0].notes);
    assert.equal(ui.fields.notes.disabled, true);
});

test("reopening an edit uses saved changes and Escape restores the saved version", async () => {
    const ui = setup();
    ui.edit.fire("click");
    ui.fields.first_name.value = "Edited";
    ui.fields.notes.value = "Keep this version";
    await ui.use.fire("click");
    ui.edit.fire("click");
    assert.equal(ui.fields.first_name.value, "Edited");
    ui.fields.notes.value = "Do not keep this version";
    ui.dialog.fire("cancel");
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.notes.textContent, "Keep this version");
});

test("editing rejects another customer's email and selecting another customer uses current details", async () => {
    const ui = setup();
    ui.edit.fire("click");
    ui.fields.email.value = "SAM@example.com";
    await ui.use.fire("click");
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.fields.email.validationMessage, "A customer with this email already exists.");
    ui.fields.email.value = "alex@example.com";
    await ui.use.fire("click");
    ui.choose(2);
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.customerId.value, "2");
    assert.equal(ui.fields.email.disabled, true);
    assert.equal(ui.notes.textContent, "No customer notes.");
});

test("Create New starts blank after a save and cancelling restores the saved customer", async () => {
    const ui = setup();
    ui.edit.fire("click");
    ui.fields.notes.value = "Keep edit";
    await ui.use.fire("click");
    ui.open.fire("click");
    assert.equal(ui.title.textContent, "New customer");
    assert.equal(ui.fields.first_name.value, "");
    assert.equal(ui.fields.email.value, "");
    ui.cancel.fire("click");
    assert.equal(ui.mode.value, "existing");
    assert.equal(ui.fields.first_name.value, "Alex");
    assert.equal(ui.notes.textContent, "Keep edit");
    ui.input.fire("input");
    assert.equal(ui.edit.disabled, true);
});

test("server validation errors stay in the modal with entered fields and allow retry", async () => {
    const ui = setup();
    ui.edit.fire("click");
    ui.fields.notes.value = "Keep this unsaved customer edit";
    ui.respond(async () => ({ ok: false, json: async () => ({ errors: { email: [{ message: "Email already exists." }] } }) }));
    await ui.use.fire("click");
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.errors.hidden, false);
    assert.match(ui.errors.textContent, /Email already exists/);
    assert.equal(ui.fields.notes.value, "Keep this unsaved customer edit");
    assert.equal(ui.fields.notes.disabled, false);
    assert.equal(ui.use.disabled, false);
    assert.equal(ui.notes.textContent, ui.customers[0].notes);
    assert.equal(ui.editor.elements['[name="notes"]'].value, "Unsaved order note");
});

test("an in-flight save cannot be repeated or cancelled, and a network error leaves the modal editable", async () => {
    const ui = setup();
    let reject;
    ui.respond(() => new Promise((resolve, fail) => { reject = fail; }));
    ui.edit.fire("click");
    const save = ui.use.fire("click");
    ui.use.fire("click");
    ui.cancel.fire("click");
    ui.dialog.fire("cancel");
    assert.equal(ui.requests.length, 1);
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.cancel.disabled, true);
    reject(new Error("Offline"));
    await save;
    assert.match(ui.errors.textContent, /Could not confirm/);
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.use.disabled, false);
    assert.equal(ui.cancel.disabled, false);
    assert.equal(ui.fields.email.disabled, false);
});

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "../../static/crm/js/order-confirmation.js"), "utf8");

function setup() {
    let focused = null;
    class Element {
        constructor(textContent = "", dataset = {}, classes = []) {
            this.textContent = textContent;
            this.dataset = dataset;
            this.handlers = {};
            const values = new Set(classes);
            this.classList = {
                contains: name => values.has(name),
                toggle: (name, on) => on ? values.add(name) : values.delete(name),
            };
        }
        focus() { focused = this; }
        addEventListener(name, listener) { (this.handlers[name] ||= []).push(listener); }
        fire(name, fields = {}) {
            const event = {
                currentTarget: this, defaultPrevented: false,
                preventDefault() { this.defaultPrevented = true; }, ...fields,
            };
            for (const listener of this.handlers[name] || []) listener(event);
            return event;
        }
    }
    function form() {
        const element = new Element();
        element.submissions = [];
        element.valid = true;
        element.requestSubmit = button => {
            if (!element.valid) return;
            const event = element.fire("submit", { submitter: button });
            if (!event.defaultPrevented) element.submissions.push(button);
        };
        return element;
    }
    const editor = form();
    const deletion = form();
    const title = new Element();
    const message = new Element();
    const cancel = new Element("Cancel");
    const accept = new Element("Confirm");
    const dialog = new Element();
    dialog.open = false;
    dialog.querySelector = selector => ({
        "[data-confirm-title]": title,
        "[data-confirm-message]": message,
        "[data-confirm-cancel]": cancel,
        "[data-confirm-accept]": accept,
    })[selector];
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; dialog.fire("close"); };
    const discard = new Element("Discard", { confirm: "Discard this unsaved order?" });
    discard.href = "/orders/";
    const navigations = [];
    const document = {
        querySelector: selector => selector === "[data-order-editor]" ? editor : dialog,
        getElementById: () => deletion,
        querySelectorAll: () => [discard],
    };
    vm.runInNewContext(script, { document, window: { location: { assign: url => navigations.push(url) } } });
    const action = (label = "Mark complete", danger = false) => new Element(
        label, { confirm: `Are you sure you wish to ${label}?` }, danger ? ["danger"] : [],
    );
    return { editor, deletion, title, message, cancel, accept, dialog, discard, navigations, action, focused: () => focused };
}

test("Save and implicit Save submit immediately without opening the modal", () => {
    const ui = setup();
    const save = { dataset: {} };
    ui.editor.requestSubmit(save);
    ui.editor.requestSubmit();
    assert.deepEqual(ui.editor.submissions, [save, undefined]);
    assert.equal(ui.dialog.open, false);
});

test("top and bottom actions wait for confirmation and keep the original submitter", () => {
    for (const position of ["top", "bottom"]) {
        const ui = setup();
        const action = ui.action(`Mark complete (${position})`);
        ui.editor.requestSubmit(action);
        assert.equal(ui.dialog.open, true);
        assert.equal(ui.message.textContent, action.dataset.confirm);
        assert.equal(ui.title.textContent, action.textContent);
        assert.equal(ui.accept.textContent, action.textContent);
        assert.equal(ui.focused(), ui.cancel);
        assert.equal(ui.editor.submissions.length, 0);
        ui.accept.fire("click");
        assert.deepEqual(ui.editor.submissions, [action]);
        assert.equal(ui.dialog.open, false);
        ui.accept.fire("click");
        assert.equal(ui.editor.submissions.length, 1);
    }
});

test("Cancel and Escape dismiss the pending action and return focus", () => {
    for (const escape of [false, true]) {
        const ui = setup();
        const action = ui.action();
        ui.editor.requestSubmit(action);
        if (escape) {
            // Native dialog Escape behavior closes unless cancel is prevented.
            if (!ui.dialog.fire("cancel").defaultPrevented) ui.dialog.close();
        } else {
            ui.cancel.fire("click");
        }
        ui.accept.fire("click");
        assert.equal(ui.dialog.open, false);
        assert.equal(ui.editor.submissions.length, 0);
        assert.equal(ui.focused(), action);
    }
});

test("confirmation revalidates the form and does not approve a later attempt", () => {
    const ui = setup();
    const action = ui.action();
    ui.editor.requestSubmit(action);
    ui.editor.valid = false;
    ui.accept.fire("click");
    assert.equal(ui.editor.submissions.length, 0);
    ui.editor.valid = true;
    ui.editor.requestSubmit(action);
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.editor.submissions.length, 0);
});

test("Delete draft confirms its own form and destructive style is reset for other actions", () => {
    const ui = setup();
    const deletion = ui.action("Delete draft", true);
    ui.deletion.requestSubmit(deletion);
    assert.equal(ui.title.textContent, "Delete draft");
    assert.equal(ui.accept.classList.contains("danger"), true);
    ui.accept.fire("click");
    assert.deepEqual(ui.deletion.submissions, [deletion]);
    assert.equal(ui.editor.submissions.length, 0);
    ui.editor.requestSubmit(ui.action("Submit"));
    assert.equal(ui.title.textContent, "Submit");
    assert.equal(ui.accept.classList.contains("danger"), false);
});

test("Discard navigates only when confirmed", () => {
    const ui = setup();
    assert.equal(ui.discard.fire("click").defaultPrevented, true);
    assert.equal(ui.title.textContent, "Discard");
    ui.cancel.fire("click");
    assert.deepEqual(ui.navigations, []);
    ui.discard.fire("click");
    ui.accept.fire("click");
    assert.deepEqual(ui.navigations, ["/orders/"]);
});

test("an already-cancelled submission does not open a modal", () => {
    const ui = setup();
    ui.editor.fire("submit", { submitter: ui.action(), defaultPrevented: true });
    assert.equal(ui.dialog.open, false);
});

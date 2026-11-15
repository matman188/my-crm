const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../../static/crm/js/customer-delete.js"), "utf8");

function setup(statusAction = false) {
    let focused = null;
    function element() {
        return {
            handlers: {},
            addEventListener(type, callback) { this.handlers[type] = callback; },
            fire(type) { this.handlers[type]?.(); },
            focus() { focused = this; },
        };
    }
    const button = element();
    const cancel = element();
    const dialog = element();
    dialog.open = false;
    dialog.querySelector = () => cancel;
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; dialog.fire("close"); };
    const selectors = statusAction
        ? { "[data-customer-status-action]": button, "[data-customer-status-dialog]": dialog }
        : { "[data-delete-customer]": button, "[data-customer-delete-dialog]": dialog };
    vm.runInNewContext(script, { document: { querySelector: selector => selectors[selector] || null } });
    return { button, cancel, dialog, focused: () => focused };
}

test("Delete opens a modal with Cancel focused, without submitting a form", () => {
    const ui = setup();
    ui.button.fire("click");
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.focused(), ui.cancel);
});

test("Cancel or native Escape dismissal returns focus to Delete", () => {
    for (const escape of [false, true]) {
        const ui = setup();
        ui.button.fire("click");
        if (escape) ui.dialog.close();
        else ui.cancel.fire("click");
        assert.equal(ui.dialog.open, false);
        assert.equal(ui.focused(), ui.button);
    }
});

test("customer creation without a delete button needs no confirmation handler", () => {
    assert.doesNotThrow(() => vm.runInNewContext(script, { document: { querySelector: () => null } }));
});

test("Archive and Restore confirmations work when linked orders hide Delete", () => {
    const ui = setup(true);
    ui.button.fire("click");
    assert.equal(ui.dialog.open, true);
    assert.equal(ui.focused(), ui.cancel);
    ui.cancel.fire("click");
    assert.equal(ui.dialog.open, false);
    assert.equal(ui.focused(), ui.button);
});

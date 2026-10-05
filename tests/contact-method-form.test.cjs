const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/contact-method-form.js"), "utf8");

function formFixture(type, valueText, invalid = false) {
    const handlers = new Map();
    const method = {value: type, addEventListener: (event, handler) => handlers.set(event, handler)};
    const value = {
        value: valueText,
        parentElement: {querySelector: () => invalid ? {} : null},
    };
    const label = {textContent: "Contact information"};
    const help = {hidden: false};
    const form = {
        querySelector: (selector) => ({'[name="type"]': method, '[name="value"]': value,
            '[data-contact-method-value-label]': label, '[data-contact-method-help]': help})[selector],
    };
    const document = {
        addEventListener: (event, handler) => handlers.set(event, handler),
        querySelectorAll: () => [form],
    };
    vm.runInNewContext(source, {document});
    handlers.get("DOMContentLoaded")();
    return {method, value, label, help, change: () => handlers.get("change")()};
}

test("initial edit and bound invalid values remain until a user changes method", () => {
    const form = formFixture("email", "saved@example.com");
    assert.equal(form.value.value, "saved@example.com");
    assert.equal(form.label.textContent, "Email address");
    form.method.value = "telephone";
    form.change();
    assert.equal(form.value.value, "");
    assert.equal(form.value.type, "tel");
    assert.equal(form.help.hidden, false);

    const invalid = formFixture("email", "invalid", true);
    assert.equal(invalid.value.value, "invalid");
    invalid.method.value = "telephone";
    invalid.change();
    assert.equal(invalid.value.value, "");
    assert.equal(invalid.help.hidden, true);
});

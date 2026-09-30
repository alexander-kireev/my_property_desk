const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/task-form.js"), "utf8");

function fixture(initialType, {property = "", issue = ""} = {}) {
    const handlers = new Map();
    const choices = ["standalone", "property", "issue"].map((value) => ({
        value, checked: value === initialType, disabled: false,
        addEventListener(event, handler) { handlers.set(value + event, handler); },
    }));
    const propertySelect = {value: property, disabled: false};
    const issueSelect = {value: issue, disabled: false};
    const propertyPanel = {hidden: false, querySelector: () => propertySelect};
    const issuePanel = {hidden: false, querySelector: () => issueSelect};
    const relationship = {
        querySelectorAll: () => choices,
        querySelector(selector) {
            if (selector === 'select[name="relationship_type"]') return null;
            if (selector === 'input[name="relationship_type"]:checked') return choices.find((choice) => choice.checked);
            if (selector === 'input[name="relationship_type"][value="property"]') return choices[1];
            if (selector === 'input[name="relationship_type"][value="issue"]') return choices[2];
            if (selector === '[data-relationship-panel="property"]') return propertyPanel;
            if (selector === '[data-relationship-panel="issue"]') return issuePanel;
            return null;
        },
    };
    const form = {querySelector: (selector) => selector === "[data-task-relationship]" ? relationship : null};
    const document = {
        addEventListener(event, handler) { handlers.set(event, handler); },
        querySelectorAll: () => [form],
    };
    const refreshed = [];
    vm.runInNewContext(source, {document, window: {SearchableSelect: {refresh: (select) => refreshed.push(select)}}});
    handlers.get("DOMContentLoaded")();
    return {
        propertySelect, issueSelect, propertyPanel, issuePanel, refreshed,
        choose(type) {
            choices.forEach((choice) => { choice.checked = choice.value === type; });
            handlers.get(type + "change")();
        },
    };
}

test("Not linked keeps the prior issue picker visible and its value intact", () => {
    const view = fixture("issue", {issue: "42"});
    view.choose("standalone");
    assert.equal(view.issuePanel.hidden, false);
    assert.equal(view.issueSelect.disabled, true);
    assert.equal(view.issueSelect.value, "42");
    assert.equal(view.propertyPanel.hidden, true);
    view.choose("issue");
    assert.equal(view.issueSelect.disabled, false);
    assert.equal(view.issueSelect.value, "42");
});

test("switching relationship types retains each picker value without submitting the inactive one", () => {
    const view = fixture("property", {property: "7", issue: "42"});
    view.choose("issue");
    assert.equal(view.propertySelect.value, "7");
    assert.equal(view.propertySelect.disabled, true);
    assert.equal(view.issuePanel.hidden, false);
    view.choose("standalone");
    assert.equal(view.issuePanel.hidden, false);
    assert.equal(view.issueSelect.disabled, true);
    assert.equal(view.issueSelect.value, "42");
});

test("an initially unlinked task shows a disabled picker to keep the modal stable", () => {
    const view = fixture("standalone");
    assert.equal(view.propertyPanel.hidden, false);
    assert.equal(view.propertySelect.disabled, true);
    assert.equal(view.issuePanel.hidden, true);
    view.choose("property");
    assert.equal(view.propertySelect.disabled, false);
});

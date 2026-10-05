const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const dashboard = readFileSync(path.join(__dirname, "../static/js/dashboard.js"), "utf8");
const styles = readFileSync(path.join(__dirname, "../static/css/dashboard.css"), "utf8");
const taskTemplate = ["tasks.html", "includes/task_modals.html"]
    .map((file) => readFileSync(path.join(__dirname, "../task/templates/task", file), "utf8"))
    .join("\n");
const siteStyles = readFileSync(path.join(__dirname, "../static/css/components.css"), "utf8");

test("Dashboard Delete alone receives the red confirmation variant", () => {
    assert.match(dashboard, /classList\.toggle\("dashboard-danger-button", action === "delete"\)/);
    assert.match(styles, /\.dashboard-dialog \.dashboard-danger-button\s*\{[^}]*background: var\(--bs-danger\) !important/);
    assert.match(dashboard, /get\("confirmCancel"\)\.focus\(\)/);
});

test("Dashboard dialogs use Bootstrap modal lifecycle rather than native dialog methods", () => {
    assert.match(dashboard, /bootstrap\.Modal\.getOrCreateInstance\(get\("workDialog"\)\)\.show\(\)/);
    assert.match(dashboard, /bootstrap\.Modal\.getOrCreateInstance\(get\("confirmDialog"\)\)\.show\(\)/);
    assert.doesNotMatch(dashboard, /\.showModal\(\)/);
});

test("Task confirmations share a body footprint and paragraph rhythm", () => {
    for (const id of ["completeTaskModal", "dismissTaskModal", "deleteTaskModal"]) {
        assert.match(taskTemplate, new RegExp(`class="modal fade modal-resilient task-confirm-modal"[\\s\\S]*?id="${id}"`));
    }
    assert.match(siteStyles, /\.task-confirm-modal \.modal-body \{\s*min-height: 6rem;\s*\}/);
    assert.match(siteStyles, /\.task-confirm-modal \.modal-body p \{\s*margin: 0;\s*\}/);
    assert.match(siteStyles, /\.task-confirm-modal \.modal-body p \+ p \{\s*margin-top: 0?\.5rem;\s*\}/);
});

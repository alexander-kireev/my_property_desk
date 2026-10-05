const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/task-command-centre.js"), "utf8");

test("opening a selected Task reveals its row and panel together", () => {
    const calls = [];
    const frames = [];
    const panel = {hidden: true, classList: {contains: (name) => name === "work-mobile-expanded"}};
    const row = {
        nextElementSibling: panel,
        addEventListener: (_event, handler) => { row.click = handler; },
        setAttribute: (name, value) => calls.push([name, value]),
    };
    const document = {
        addEventListener: (_event, handler) => { document.ready = handler; },
        querySelector: (selector) => selector === ".task-command-centre" ? {} : null,
        querySelectorAll: (selector) => selector === ".task-command-row[aria-expanded]" ? [row] : [],
        getElementById: () => null,
    };
    const browser = {
        matchMedia: () => ({matches: true}),
        ExpandableText: {refresh: (element) => calls.push(["refresh", element])},
        WorkspaceReveal: {queueRange: (first, last, prepare) => frames.push(() => {
            prepare?.();
            calls.push(["revealRange", first, last]);
        })},
    };
    vm.runInNewContext(source, {
        document, window: browser,
        requestAnimationFrame: (callback) => frames.push(callback),
    });
    document.ready();
    row.click({button: 0, preventDefault: () => calls.push(["preventDefault"])});
    while (frames.length) frames.shift()();

    assert.equal(panel.hidden, false);
    assert.ok(calls.some(([name, first, last]) => name === "revealRange" && first === row && last === panel));
});

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/mobile-navbar.js"), "utf8");

function fixture({mobile = true, open = true, modal = false} = {}) {
    let keydown;
    let pointerdown;
    let hidden;
    let hides = 0;
    let focused = 0;
    const toggle = {focus: () => { focused += 1; }, contains: (target) => target === toggle, closest: () => null};
    const menu = {
        classList: {contains: (name) => name === "show" && open},
        addEventListener: (name, listener) => { if (name === "hidden.bs.collapse") hidden = listener; },
        contains: (target) => target === menu,
    };
    const navbar = {querySelector: (selector) => selector === "#siteNavbar" ? menu : toggle};
    const document = {
        querySelector: (selector) => selector === ".app-navbar" ? navbar : modal ? {} : null,
        addEventListener: (name, listener) => { if (name === "keydown") keydown = listener; if (name === "pointerdown") pointerdown = listener; },
    };
    vm.runInNewContext(source, {
        document,
        window: {matchMedia: () => ({matches: mobile})},
        bootstrap: {Collapse: {getOrCreateInstance: () => ({hide: () => { hides += 1; }})}},
    });
    return {
        pressEscape: () => {
            const event = {key: "Escape", defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }};
            keydown(event);
            return event;
        },
        pointerDown: (target) => pointerdown({target}),
        finishHide: () => hidden?.(),
        get hides() { return hides; },
        get focused() { return focused; },
    };
}

test("Escape hides the open mobile navbar then restores focus", () => {
    const view = fixture();
    assert.equal(view.pressEscape().defaultPrevented, true);
    assert.equal(view.hides, 1);
    assert.equal(view.focused, 0);
    view.finishHide();
    assert.equal(view.focused, 1);
});

test("Escape does not change a desktop or closed navbar", () => {
    for (const options of [{mobile: false}, {open: false}]) {
        const view = fixture(options);
        assert.equal(view.pressEscape().defaultPrevented, false);
        assert.equal(view.hides, 0);
    }
});

test("an open modal takes precedence over the mobile navbar", () => {
    const view = fixture({modal: true});
    assert.equal(view.pressEscape().defaultPrevented, false);
    assert.equal(view.hides, 0);
});

test("outside pointer hides the mobile navbar without stealing focus", () => {
    const view = fixture();
    view.pointerDown({closest: () => null});
    assert.equal(view.hides, 1);
    assert.equal(view.focused, 0);
});

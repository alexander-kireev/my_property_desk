const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function loadHelper() {
    class FakeElement {
        constructor(options = {}) { Object.assign(this, options); }
        closest(selector) { return this.ancestors?.[selector] || null; }
        querySelector(selector) { return this.children?.[selector] || null; }
        matches(selector) { return this.match?.[selector] || false; }
        getClientRects() { return this.rects || [1]; }
        focus(options) { this.focusOptions = options; }
    }
    const dashboardToggle = new FakeElement();
    const document = {
        addEventListener() {},
        getElementById(id) { return id === 'dashboardAddToggle' ? dashboardToggle : null; },
    };
    const window = {};
    const context = {document, window, Element: FakeElement,
        getComputedStyle: () => ({display: 'block', visibility: 'visible'}),
        requestAnimationFrame: callback => callback()};
    const source = fs.readFileSync(path.join(__dirname, '..', 'static/js/modal-state.js'), 'utf8');
    vm.runInNewContext(source, context);
    return {helper: window.WorkspaceModalReturnFocus, FakeElement, dashboardToggle};
}

test('Bootstrap dropdown item returns to durable menu toggle; direct button remains itself', () => {
    const {helper, FakeElement} = loadHelper();
    const toggle = new FakeElement();
    const dropdown = new FakeElement({children: {'[data-bs-toggle="dropdown"]': toggle}});
    const menu = new FakeElement({ancestors: {'.dropdown': dropdown}});
    const item = new FakeElement({ancestors: {'.dropdown-menu': menu}});
    const direct = new FakeElement();
    assert.equal(helper.resolve(item), toggle);
    assert.equal(helper.resolve(direct), direct);
});

test('Dashboard Add and row-action menu items resolve to visible toggles', () => {
    const {helper, FakeElement, dashboardToggle} = loadHelper();
    const addItem = new FakeElement({ancestors: {'#dashboardAddMenu': new FakeElement()}});
    const rowToggle = new FakeElement();
    const rowActions = new FakeElement({children: {'.dashboard-more-button': rowToggle}});
    const rowMenu = new FakeElement({ancestors: {'.dashboard-row-actions': rowActions}});
    const rowItem = new FakeElement({ancestors: {'.dashboard-row-menu': rowMenu}});
    assert.equal(helper.resolve(addItem), dashboardToggle);
    assert.equal(helper.resolve(rowItem), rowToggle);
});

test('settled restoration focuses only connected visible targets without scrolling', () => {
    const {helper, FakeElement} = loadHelper();
    const visible = new FakeElement({isConnected: true});
    const hidden = new FakeElement({isConnected: true, ancestors: {'[hidden], .dropdown-menu:not(.show), .dashboard-row-menu:not(:popover-open)': new FakeElement()}});
    helper.restore(visible);
    helper.restore(hidden);
    assert.equal(visible.focusOptions.preventScroll, true);
    assert.equal(hidden.focusOptions, undefined);
});

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const alignSource = readFileSync(path.join(root, "static/js/workspace-header-align.js"), "utf8");

function alignedHeights(width, height, property = true) {
    const list = {style: {}, getBoundingClientRect: () => ({height: 72})};
    const detail = {style: {}, getBoundingClientRect: () => ({height: 104})};
    const workspace = {
        dataset: {alignFrom: "992"},
        querySelector: (selector) => selector === "[data-list-header]" ? list : detail,
        closest: () => property ? {} : null,
    };
    const context = {
        document: {
            querySelectorAll: () => [workspace],
            addEventListener: (_event, callback) => callback(),
        },
        window: {
            innerWidth: width,
            matchMedia: (query) => ({matches: query.includes("min-width: 1200px")
                ? width >= 1200
                : property ? width <= 1299.98 && height <= 750 : width <= 1199.98 && height <= 700}),
            requestAnimationFrame: (callback) => { callback(); return 1; },
            addEventListener: () => {},
        },
    };
    vm.runInNewContext(alignSource, context);
    return [list.style.minHeight, detail.style.minHeight];
}

test("shared headers align at 1200, but not at 1199 or short intermediate viewports", () => {
    for (const property of [true, false]) {
        assert.deepEqual(alignedHeights(1199, 800, property), ["", ""]);
        assert.deepEqual(alignedHeights(1200, 800, property), ["104px", "104px"]);
    }
    assert.deepEqual(alignedHeights(1200, 700, true), ["", ""]);
});

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const css = readFileSync(path.join(root, "static/css/property-workspace.css"), "utf8");
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

test("Property list and detail get separate intermediate single-panel caps", () => {
    assert.match(css, /@media \(min-width: 768px\) and \(max-width: 991\.98px\) \{\s*\.property-command-centre \{ max-width: 720px; margin-inline: auto; \}\s*\.property-command-centre:has\(\.property-workspace\.show-detail\) \{ max-width: 800px; \}/);
    assert.match(css, /@media \(max-width: 991\.98px\), \(max-width: 1299\.98px\) and \(max-height: 750px\) \{[\s\S]*?\.property-workspace \{ display: block; \}/);
    assert.match(css, /@media \(max-width: 767\.98px\)/);
});

test("intermediate Property detail uses two filter rows and content-driven results", () => {
    assert.match(css, /@media \(min-width: 768px\) and \(max-width: 991\.98px\) \{[\s\S]*?\.property-related-filters \{ grid-template-columns: repeat\(3, minmax\(0, 1fr\)\); \}[\s\S]*?\.property-related-search \{ grid-column: span 2; \}/);
    assert.match(css, /@media \(min-width: 992px\) and \(max-width: 1199\.98px\) \{[\s\S]*?\.property-related-scroll \{ flex: 0 0 auto; \}/);
    assert.match(css, /\.property-heading-row\.workspace-detail-header-layout \{\s*grid-template-columns: minmax\(0, 1fr\) auto;/);
});

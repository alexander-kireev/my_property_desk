const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/workspace-header-align.js"), "utf8");

function openWorkspace({ width, minimumWidth, listHeight, detailHeight, kind }) {
    const frames = [];
    const handlers = {};
    const header = (naturalHeight) => ({
        style: { minHeight: "" },
        // The content measurement excludes the 1px separator border.
        scrollHeight: naturalHeight - 1,
        getBoundingClientRect() {
            return { height: Math.max(naturalHeight, Number.parseFloat(this.style.minHeight) || 0) };
        },
    });
    const list = header(listHeight);
    const detail = header(detailHeight);
    const workspace = {
        dataset: { alignFrom: String(minimumWidth) },
        querySelector: (selector) => selector === "[data-list-header]" ? list : detail,
        closest: (selector) => kind === "properties" && selector === '[data-workspace-scroll-root="properties"]' ? workspace : null,
    };
    const browser = {
        innerWidth: width,
        innerHeight: 900,
        requestAnimationFrame(callback) { frames.push(callback); return frames.length; },
        addEventListener(name, callback) { handlers[name] = callback; },
        matchMedia(query) {
            const minWidth = query.match(/min-width:\s*([\d.]+)px/);
            const maxWidth = query.match(/max-width:\s*([\d.]+)px/);
            const maxHeight = query.match(/max-height:\s*([\d.]+)px/);
            return {matches: (!minWidth || this.innerWidth >= Number(minWidth[1]))
                && (!maxWidth || this.innerWidth <= Number(maxWidth[1]))
                && (!maxHeight || this.innerHeight <= Number(maxHeight[1]))};
        },
    };
    vm.runInNewContext(source, {
        document: {
            addEventListener: (_name, callback) => { handlers.ready = callback; },
            querySelectorAll: () => [workspace],
            fonts: { ready: { then: () => {} } },
        },
        window: browser,
    });
    handlers.ready();
    const flush = () => { while (frames.length) frames.shift()(); };
    return { list, detail, browser, flush, resize: () => handlers.resize() };
}

for (const [name, kind, minimumWidth] of [["Properties", "properties", 992], ["Contacts", "contacts", 992]]) {
    test(`${name} separators align using border-box height in the roomy desktop layout`, () => {
        const page = openWorkspace({ width: 1280, minimumWidth, listHeight: 120, detailHeight: 225.4, kind });
        page.flush();
        assert.equal(page.list.getBoundingClientRect().height, 226);
        assert.equal(page.detail.getBoundingClientRect().height, 226);
    });

    test(`${name} keeps independent header heights in the intermediate split layout`, () => {
        const page = openWorkspace({ width: minimumWidth, minimumWidth, listHeight: 120, detailHeight: 225.4, kind });
        page.flush();
        assert.equal(page.list.getBoundingClientRect().height, 120);
        assert.equal(page.detail.getBoundingClientRect().height, 225.4);
    });

    test(`${name} alignment clears below the single-column breakpoint`, () => {
        const page = openWorkspace({ width: 1280, minimumWidth, listHeight: 120, detailHeight: 225.4, kind });
        page.flush();
        page.browser.innerWidth = minimumWidth - 1;
        page.resize();
        page.flush();
        assert.equal(page.list.style.minHeight, "");
        assert.equal(page.detail.style.minHeight, "");
    });
}

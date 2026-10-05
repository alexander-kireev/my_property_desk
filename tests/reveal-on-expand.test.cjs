const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/reveal-on-expand.js"), "utf8");
const dashboardSource = readFileSync(path.join(__dirname, "../static/js/dashboard.js"), "utf8");
const propertySource = readFileSync(path.join(__dirname, "../static/js/property-workspace.js"), "utf8");

function fixture(rowBounds, panelBounds, {
    reducedMotion = false, nested = false, navbarBottom = 70,
    panePadding = 0, paneOverflowY = "auto", paneScrollHeight = 900,
} = {}) {
    const body = {};
    const moves = [];
    const frames = [];
    const navbar = navbarBottom === null ? null : {
        getClientRects: () => [{}],
        getBoundingClientRect: () => ({top: 0, bottom: navbarBottom}),
    };
    const browser = {
        innerHeight: 600,
        matchMedia: () => ({matches: reducedMotion}),
        scrollBy: (move) => moves.push(move),
    };
    const pane = nested ? {
        parentElement: body,
        clientHeight: 400,
        scrollHeight: paneScrollHeight,
        getBoundingClientRect: () => ({top: 100, bottom: 500}),
        scrollBy: (move) => moves.push(move),
    } : body;
    const node = (bounds) => ({
        parentElement: pane,
        getClientRects: () => [{}],
        getBoundingClientRect: () => bounds,
    });
    vm.runInNewContext(source, {
        document: {body, querySelector: (selector) => selector === ".app-navbar" ? navbar : null},
        window: browser,
        requestAnimationFrame: (callback) => { frames.push(callback); return frames.length; },
        getComputedStyle: (element) => ({
            overflowY: element === pane && nested ? paneOverflowY : "visible",
            position: element === navbar ? "sticky" : "static",
            scrollPaddingTop: element === pane && nested ? `${panePadding}px` : "0px",
        }),
    });
    return {
        reveal: browser.WorkspaceReveal, row: node(rowBounds), panel: node(panelBounds), moves,
        flush: () => { while (frames.length) frames.shift()(); },
    };
}

test("expanded row and panel move together when the panel ends below the viewport", () => {
    const view = fixture({top: 300, bottom: 370}, {top: 370, bottom: 780});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves.length, 1);
    assert.equal(view.moves[0].top, 180);
    assert.equal(view.moves[0].behavior, "smooth");
});

test("an oversized expansion aligns its heading below the sticky navbar", () => {
    const view = fixture({top: 500, bottom: 570}, {top: 570, bottom: 1200});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves.length, 1);
    assert.equal(view.moves[0].top, 422);
});

test("an oversized expansion shows the maximum content even when a small preview was already visible", () => {
    const view = fixture({top: 150, bottom: 220}, {top: 220, bottom: 1200});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves[0].top, 72);
});

test("the safe top follows the actual sticky navbar height", () => {
    const view = fixture({top: 150, bottom: 220}, {top: 220, bottom: 1200}, {navbarBottom: 96});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves[0].top, 46);
});

test("without sticky chrome, the page retains a small breathing space", () => {
    const view = fixture({top: 0, bottom: 70}, null, {navbarBottom: null});
    view.reveal.reveal(view.row);
    assert.equal(view.moves[0].top, -8);
});

test("a fully visible expanded task does not scroll", () => {
    const view = fixture({top: 150, bottom: 220}, {top: 220, bottom: 450});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves.length, 0);
});

test("nested task panes scroll smoothly without moving the document", () => {
    const view = fixture({top: 300, bottom: 370}, {top: 370, bottom: 650}, {nested: true});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves.length, 1);
    assert.equal(view.moves[0].top, 150);
    assert.equal(view.moves[0].behavior, "smooth");
});

test("a nested pane honors its own scroll padding for tall expansions", () => {
    const view = fixture({top: 300, bottom: 370}, {top: 370, bottom: 900}, {
        nested: true, panePadding: 24,
    });
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves[0].top, 176);
});

test("a clipped but non-scrolling ancestor does not steal the page reveal", () => {
    const view = fixture({top: 500, bottom: 570}, {top: 570, bottom: 1200}, {
        nested: true, paneOverflowY: "auto", paneScrollHeight: 400,
    });
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves[0].top, 422);
});

test("reduced-motion preference keeps expansion scrolling immediate", () => {
    const view = fixture({top: 300, bottom: 370}, {top: 370, bottom: 780}, {reducedMotion: true});
    view.reveal.revealRange(view.row, view.panel);
    assert.equal(view.moves[0].behavior, "instant");
});

test("queued reveals measure after the final layout preparation", () => {
    const view = fixture({top: 500, bottom: 570}, {top: 570, bottom: 1200});
    let prepared = false;
    view.reveal.queueRange(view.row, view.panel, () => { prepared = true; });
    assert.equal(view.moves.length, 0);
    view.flush();
    assert.equal(prepared, true);
    assert.equal(view.moves[0].top, 422);
});

test("a panel closed before the next frame does not trigger a stale scroll", () => {
    const view = fixture({top: 500, bottom: 570}, {top: 570, bottom: 1200});
    view.reveal.queueRange(view.row, view.panel);
    view.panel.hidden = true;
    view.flush();
    assert.equal(view.moves.length, 0);
});

test("Dashboard and Property expansions use the shared range reveal", () => {
    assert.match(dashboardSource, /function revealExpandedRow\(row\) \{[\s\S]*?WorkspaceReveal\?\.queueRange\(/);
    assert.doesNotMatch(dashboardSource, /scrollIntoView\(/);
    assert.match(propertySource, /querySelectorAll\("\.property-related-record, \.property-record"\)/);
    assert.match(propertySource, /WorkspaceReveal\?\.queueRange\([\s\S]*?record\.querySelector\("summary"\),\s*record\.lastElementChild/);
});

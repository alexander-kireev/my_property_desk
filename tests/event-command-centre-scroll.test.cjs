const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/event-command-centre.js"), "utf8");

function eventPage({agendaSelected = false, initialAgenda = false, listSelected = true} = {}) {
    const calls = [];
    const frames = [];
    const panel = {hidden: true, classList: {contains: (name) => name === "event-mobile-expanded"}};
    const row = {
        href: "?selected=7&tab=details",
        nextElementSibling: listSelected ? panel : null,
        addEventListener: (_event, handler) => { row.click = handler; },
        setAttribute: (name, value) => calls.push([name, value]),
    };
    const agendaPanel = {hidden: false, classList: {contains: (name) => name === "event-mobile-expanded"}};
    const agendaEntry = {classList: {toggle: (name, value) => calls.push([name, value])}};
    const agendaRow = {
        href: "?agenda_day=2026-10-01&view=calendar&selected=7&tab=calendar",
        nextElementSibling: agendaSelected ? agendaPanel : null,
        parentElement: agendaEntry,
        addEventListener: (_event, handler) => { agendaRow.click = handler; },
        setAttribute: (name, value) => calls.push([name, value]),
    };
    const day = {
        dataset: {
            calendarDayHref: "?day=2026-10-01#eventResults",
            calendarAgendaHref: "?agenda_day=2026-10-01&view=calendar#eventAgenda",
        },
        addEventListener: (_event, handler) => { day.click = handler; },
    };
    const document = {
        addEventListener: (_event, handler) => { document.ready = handler; },
        getElementById: (id) => id === "eventWorkspace" && initialAgenda
            ? {classList: {contains: (name) => name === "show-mobile-calendar"}} : null,
        querySelector: (selector) => selector === ".event-mobile-agenda-entry.is-expanded > .event-mobile-agenda-row"
            && agendaSelected ? agendaRow : null,
        querySelectorAll: (selector) => {
            if (selector === "[data-calendar-day-href]") return [day];
            if (selector === ".event-command-entry > [data-workspace-scroll-row]") return [row];
            if (selector === ".event-mobile-agenda-entry > .event-mobile-agenda-row") return [agendaRow];
            return [];
        },
    };
    const browser = {
        location: {
            search: "",
            assign: (href) => calls.push(["navigate", href]),
        },
        matchMedia: () => ({matches: true}),
        ExpandableText: {refresh: (element) => calls.push(["refresh", element])},
        WorkspaceReveal: {queueRange: (first, last, prepare) => frames.push(() => {
            prepare?.();
            calls.push(["revealRange", first, last]);
        })},
    };
    vm.runInNewContext(source, {
        document, window: browser,
        URLSearchParams,
        requestAnimationFrame: (callback) => frames.push(callback),
    });
    document.ready();
    return {calls, frames, panel, row, day, agendaPanel, agendaRow};
}

test("below 860, opening a selected event reveals the expanded range", () => {
    const page = eventPage();
    page.row.click({button: 0, preventDefault() {}});
    while (page.frames.length) page.frames.shift()();

    assert.equal(page.panel.hidden, false);
    assert.ok(page.calls.some(([name, first, last]) =>
        name === "revealRange" && first === page.row && last === page.panel));
});

test("first selection uses explicit reveal after navigation without a competing row hash", () => {
    const page = eventPage({listSelected: false});
    page.row.click({button: 0, preventDefault() {}});
    assert.ok(page.calls.some(([name, href]) => name === "navigate" && href === page.row.href));
});

test("below 860, an empty calendar day navigates to its agenda, not the filtered list", () => {
    const page = eventPage();
    let prevented = false;
    page.day.click({
        button: 0,
        target: {closest: () => null},
        preventDefault() { prevented = true; },
    });

    assert.equal(prevented, true);
    assert.ok(page.calls.some(([name, href]) =>
        name === "navigate" && href === page.day.dataset.calendarAgendaHref));
});

test("below 860, agenda selection stays on Calendar and selected rows toggle in place", () => {
    const unselected = eventPage();
    unselected.agendaRow.click({button: 0, preventDefault() {}});
    assert.ok(unselected.calls.some(([name, href]) => name === "navigate" && href === unselected.agendaRow.href));

    const selected = eventPage({agendaSelected: true});
    selected.agendaRow.click({button: 0, preventDefault() {}});
    assert.equal(selected.agendaPanel.hidden, true);
    assert.ok(selected.calls.some(([name, value]) => name === "aria-expanded" && value === "false"));
    selected.agendaRow.click({button: 0, preventDefault() {}});
    while (selected.frames.length) selected.frames.shift()();
    assert.equal(selected.agendaPanel.hidden, false);
    assert.ok(selected.calls.some(([name, first, last]) =>
        name === "revealRange" && first === selected.agendaRow && last === selected.agendaPanel));
});

test("a selected Calendar agenda event reveals its inline details after navigation", () => {
    const page = eventPage({agendaSelected: true, initialAgenda: true});
    while (page.frames.length) page.frames.shift()();
    assert.ok(page.calls.some(([name, first, last]) =>
        name === "revealRange" && first === page.agendaRow && last === page.agendaPanel));
});

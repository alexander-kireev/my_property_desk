const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");

function clockFixture() {
    let now = new Date(2026, 9, 7, 2);
    let refresh;
    const greeting = {},
        date = {},
        events = [],
        listeners = {},
        window = {};
    class LocalDate extends Date {
        constructor() {
            super(now);
        }
    }
    const document = {
        hidden: false,
        querySelector: (selector) => (selector.includes("data-dashboard") ? greeting : date),
        addEventListener: (name, callback) => {
            listeners[name] = callback;
        },
        dispatchEvent: (event) => events.push(event),
    };
    vm.runInNewContext(fs.readFileSync("static/js/dashboard-greeting.js", "utf8"), {
        Date: LocalDate,
        document,
        window,
        CustomEvent: class {
            constructor(type, options) {
                this.type = type;
                this.detail = options.detail;
            }
        },
        setInterval: (callback) => {
            refresh = callback;
        },
    });
    return {
        greeting,
        date,
        events,
        listeners,
        document,
        window,
        tick(value) {
            now = value;
            refresh();
        },
        setTime(value) {
            now = value;
        },
    };
}

test("greeting and dashboard clock follow browser-local time", () => {
    const view = clockFixture();
    for (const [hour, expected] of [
        [0, "Hello"],
        [4, "Hello"],
        [5, "Good morning"],
        [11, "Good morning"],
        [12, "Good afternoon"],
        [17, "Good afternoon"],
        [18, "Good evening"],
        [23, "Good evening"],
    ]) {
        view.tick(new Date(2026, 9, 7, hour));
        assert.equal(view.greeting.textContent, expected);
    }
    assert.equal(view.date.textContent, "Wednesday, 7 October 2026");
    assert.equal(view.window.DashboardClock.today(), "2026-10-07");
    assert.equal(view.events.length, 0);
});

test("midnight and returning to a sleeping tab emit one date change per local day", () => {
    const view = clockFixture();
    view.tick(new Date(2026, 9, 8, 0));
    assert.equal(view.date.textContent, "Thursday, 8 October 2026");
    assert.equal(view.events.length, 1);
    assert.equal(view.events[0].type, "dashboard:date-change");
    assert.equal(view.events[0].detail.today, "2026-10-08");
    view.tick(new Date(2026, 9, 8, 0, 1));
    assert.equal(view.events.length, 1);
    view.setTime(new Date(2026, 10, 1, 8));
    view.document.hidden = true;
    view.listeners.visibilitychange();
    assert.equal(view.events.length, 1);
    view.document.hidden = false;
    view.listeners.visibilitychange();
    assert.equal(view.events[1].detail.today, "2026-11-01");
    assert.equal(view.window.DashboardClock.today(), "2026-11-01");
});

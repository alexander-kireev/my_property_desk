const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { launchBrowser } = require("./support.cjs");
let browser;
before(async () => { browser = await launchBrowser(); });
after(async () => { await browser?.close(); });

for (const route of ["/events/", "/properties/", "/dashboard/"]) {
    test(`shared Event controls initialize once and preserve form rules on ${route}`, async t => {
        if (!process.env.PMS_BROWSER_SESSION) throw Error("Set PMS_BROWSER_SESSION to the local test session.");
        const session = JSON.parse(fs.readFileSync(process.env.PMS_BROWSER_SESSION, "utf8"));
        const base = process.env.PMS_TEST_BASE || "http://127.0.0.1:8024";
        const context = await browser.newContext();
        t.after(() => context.close());
        await context.addCookies([{name: session.cookie_name, value: session.cookie_value, url: base}]);
        const page = await context.newPage();
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(base + route);
        const result = await page.evaluate(() => {
            const form = document.querySelector("[data-event-form][data-event-tabs]");
            if (!form) throw Error("Expected Event form not rendered");
            const api = window.EventForm.forForm(form);
            window.EventForm.forForm(form);
            const field = name => form.querySelector(`[name="${name}"]`);
            const allDay = field("all_day");
            const start = field("start_time");
            allDay.checked = false;
            allDay.dispatchEvent(new Event("change", {bubbles:true}));
            const timedEnabled = !start.disabled;
            start.value = "10:30";
            api.refresh();
            const preserved = start.value;
            allDay.checked = true;
            allDay.dispatchEvent(new Event("change", {bubbles:true}));
            const cleared = start.disabled && start.value === "";
            field("user_participation_required").checked = false;
            field("user_participation_required").dispatchEvent(new Event("change", {bubbles:true}));
            const presenceDisabled = field("user_presence_required").disabled;
            api.activateTab("participants");
            const participantsVisible = !form.querySelector('[data-event-panel="participants"]').hidden;
            const search = form.querySelector("[data-contact-search]");
            search.value = "zz-no-such-contact";
            search.dispatchEvent(new Event("input", {bubbles:true}));
            const searchStatus = form.querySelector("[data-contact-picker-status]").textContent;
            let submitted = false;
            form.addEventListener("submit", event => { event.preventDefault(); submitted=true; });
            const enter = new KeyboardEvent("keydown", {key:"Enter",bubbles:true,cancelable:true});
            search.dispatchEvent(enter);
            const title = field("title");
            title.dispatchEvent(new Event("invalid", {cancelable:true}));
            return {timedEnabled,preserved,cleared,presenceDisabled,participantsVisible,searchStatus,
                prevented:enter.defaultPrevented,submitted,detailsVisible:!form.querySelector('[data-event-panel="details"]').hidden};
        });
        assert.deepEqual(result, {timedEnabled:true,preserved:"10:30",cleared:true,presenceDisabled:true,participantsVisible:true,
            searchStatus:"0 selected · 0 matching",prevented:true,submitted:false,detailsVisible:true});
        assert.deepEqual(errors, []);
    });
}

const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { launchBrowser } = require("./support.cjs");
let browser;
before(async () => { browser = await launchBrowser(); });
after(async () => { await browser?.close(); });

async function fixture(t, searchable = false) {
    const page = await browser.newPage();
    t.after(() => page.close());
    await page.setContent(`<form id="form"><button id="before" type="button">Before</button>
        <label for="choice">Choice</label><select id="choice" class="form-select" name="${searchable ? "property" : "state"}">
        <option value="a">Alpha</option><option value="b" disabled>Beta</option><option value="c">Charlie</option></select>
        <button id="after" type="button">After</button></form>`);
    await page.addScriptTag({path: path.resolve("static/js/searchable-select.js")});
    await page.evaluate(() => {
        window.changes = 0;
        document.querySelector("select").addEventListener("change", () => window.changes++);
        document.dispatchEvent(new Event("DOMContentLoaded"));
    });
    return page;
}

test("keyboard selection skips disabled choices and emits one native change", async t => {
    const page = await fixture(t);
    await page.locator(".app-select-trigger").press("ArrowDown");
    await page.locator(".app-select-trigger").press("Enter");
    assert.equal(await page.locator("#choice").inputValue(), "c");
    assert.equal(await page.evaluate(() => window.changes), 1);
    assert.equal(await page.locator(".app-select-trigger").getAttribute("aria-expanded"), "false");
});

test("search handles no matches and Escape returns focus to the trigger", async t => {
    const page = await fixture(t, true);
    await page.locator(".app-select-trigger").click();
    await page.locator(".app-select-search").fill("missing");
    assert.equal(await page.locator(".app-select-empty").textContent(), "No matching choices");
    await page.locator(".app-select-search").press("Enter");
    assert.equal(await page.locator("#choice").inputValue(), "a");
    await page.locator(".app-select-search").press("Escape");
    assert.equal(await page.evaluate(() => document.activeElement.id), "choice_control");
});

test("Tab and Shift+Tab leave the search popup in document order", async t => {
    const page = await fixture(t, true);
    await page.locator(".app-select-trigger").click();
    await page.locator(".app-select-search").press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.id), "after");
    await page.locator(".app-select-trigger").click();
    await page.locator(".app-select-search").press("Shift+Tab");
    assert.equal(await page.evaluate(() => document.activeElement.id), "before");
});

test("repeated initialization and destroy/recreate do not duplicate controls or listeners", async t => {
    const page = await fixture(t);
    await page.evaluate(() => {
        window.SearchableSelect.init(document);
        window.SearchableSelect.init(document);
    });
    assert.equal(await page.locator(".app-select-trigger").count(), 1);
    await page.evaluate(() => window.SearchableSelect.destroyWithin(document));
    assert.equal(await page.locator(".app-select-popup").count(), 0);
    assert.equal(await page.locator("label").getAttribute("for"), "choice");
    assert.equal(await page.locator("#choice").isVisible(), true);
    await page.evaluate(() => window.SearchableSelect.init(document));
    await page.locator(".app-select-trigger").press("ArrowDown");
    await page.locator(".app-select-trigger").press("Enter");
    assert.equal(await page.evaluate(() => window.changes), 1);
});

test("refresh mirrors native disabled state and closes an open popup", async t => {
    const page = await fixture(t);
    await page.locator(".app-select-trigger").click();
    await page.evaluate(() => {
        const select = document.querySelector("select");
        select.disabled = true;
        window.SearchableSelect.refresh(select);
    });
    assert.equal(await page.locator(".app-select-trigger").isDisabled(), true);
    assert.equal(await page.locator(".app-select-popup").isVisible(), false);
});

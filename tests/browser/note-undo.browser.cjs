const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { launchBrowser } = require("./support.cjs");
let browser;
before(async () => {
    browser = await launchBrowser();
});
after(async () => {
    await browser?.close();
});

test("failed contact-note Undo changes success feedback into an accessible error", async (t) => {
    const page = await browser.newPage();
    t.after(() => page.close());
    await page.route("https://notes.test/**", (route) => route.fulfill({ status: 410, body: "" }));
    await page.setContent(`<input name="csrfmiddlewaretoken" value="test-token">
        <div class="note-undo-toast" data-note-undo-toast data-url="https://notes.test/undo/"
             data-token="test-undo" role="status" aria-live="polite">
            <span class="app-feedback-icon" aria-hidden="true">✓</span>
            <strong data-note-undo-message>Note deleted.</strong>
            <button type="button" data-note-undo>Undo</button>
            <button type="button" data-note-undo-close>Dismiss notification</button>
        </div>`);
    for (const file of ["foundation", "components"])
        await page.addStyleTag({ path: path.resolve(`static/css/${file}.css`) });
    await page.addScriptTag({ path: path.resolve("static/js/note-board.js") });
    const toast = page.locator("[data-note-undo-toast]");
    assert.equal(
        await toast.evaluate((e) => getComputedStyle(e).backgroundColor),
        "rgb(237, 242, 231)",
    );
    await page.getByRole("button", { name: "Undo", exact: true }).click();
    await page.getByText("This note can no longer be undone.", { exact: true }).waitFor();
    assert.equal(await toast.getAttribute("role"), "alert");
    assert.equal(await toast.getAttribute("aria-live"), "assertive");
    assert.equal(await toast.locator(".app-feedback-icon").textContent(), "!");
    assert.equal(
        await toast.evaluate((e) => getComputedStyle(e).backgroundColor),
        "rgb(251, 240, 243)",
    );
    assert.equal(
        await toast
            .locator(".app-feedback-icon")
            .evaluate((e) => getComputedStyle(e).backgroundColor),
        "rgb(123, 38, 63)",
    );
    assert.equal(await page.locator("[data-note-undo]").isVisible(), false);
    await page.getByRole("button", { name: "Dismiss notification" }).click();
    assert.equal(await toast.count(), 0);
});

const { launchBrowser } = require("./browser/support.cjs");
const assert = require("node:assert/strict");
const path = require("node:path");
(async () => {
    const browser = await launchBrowser();
    try {
        const page = await browser.newPage({ viewport: { width: 375, height: 640 } });
        await page.setContent(
            '<form><label for="date">Scheduled date</label><input id="date" name="date" type="date" value="2026-10-07" min="2026-10-03" max="2026-11-20"></form>',
        );
        await page.addStyleTag({ path: path.resolve("static/css/components.css") });
        await page.addScriptTag({ path: path.resolve("static/js/date-picker.js") });
        await page.evaluate(() => document.dispatchEvent(new Event("DOMContentLoaded")));
        await page.locator("#date").click();
        assert.equal(await page.locator(".app-date-popup").count(), 1);
        await page.keyboard.press("Escape");
        await page.locator("#date").focus();
        await page.keyboard.press("Space");
        assert.equal(await page.locator(".app-date-popup").count(), 1);
        await page.keyboard.press("Escape");
        await page.getByRole("button", { name: "Choose Scheduled date" }).click();
        await page.locator('[data-date="2026-10-07"]').press("ArrowRight");
        await page.keyboard.press("Enter");
        assert.equal(await page.locator("#date").inputValue(), "2026-10-08");
        assert.equal(
            await page.evaluate(() => new FormData(document.querySelector("form")).get("date")),
            "2026-10-08",
        );
        await page.getByRole("button", { name: "Choose Scheduled date" }).click();
        assert.equal(await page.locator('[data-date="2026-10-02"]').isDisabled(), true);
        const bounds = await page.locator(".app-date-popup").boundingBox();
        assert.ok(
            bounds.x >= 0 && bounds.x + bounds.width <= 375 && bounds.y + bounds.height <= 640,
        );
        await page.getByRole("button", { name: "Next month" }).click();
        await page.getByRole("button", { name: "Previous month" }).click();
        // October starts before min: returning to it must still expose a date
        // in the tab order, including when focus remains on a header button.
        await page.keyboard.press("Tab");
        await page.keyboard.press("Tab");
        assert.equal(await page.evaluate(() => document.activeElement.dataset.date), "2026-10-03");
        await page.keyboard.press("PageDown");
        assert.equal(await page.evaluate(() => document.activeElement.dataset.date), "2026-11-01");
        await page.keyboard.press("PageUp");
        assert.equal(await page.evaluate(() => document.activeElement.dataset.date), "2026-10-03");
        await page.keyboard.press("Home");
        assert.equal(await page.evaluate(() => document.activeElement.dataset.date), "2026-10-03");
        await page.keyboard.press("End");
        assert.equal(await page.evaluate(() => document.activeElement.dataset.date), "2026-10-04");
        await page.getByRole("button", { name: "Next month" }).click();
        await page.locator('[data-date="2026-11-12"]').click();
        assert.equal(await page.locator("#date").inputValue(), "2026-11-12");
        await page.getByRole("button", { name: "Choose Scheduled date" }).click();
        await page.keyboard.press("Escape");
        assert.equal(await page.locator(".app-date-popup").count(), 0);
        assert.equal(
            await page
                .getByRole("button", { name: "Choose Scheduled date" })
                .evaluate((e) => e === document.activeElement),
            true,
        );
        // Empty/out-of-range fields open at a valid boundary without changing
        // the input until the user explicitly selects a date.
        for (const [value, min, max, expected] of [
            ["", "2099-03-15", "2099-04-20", "2099-03-15"],
            ["2099-05-01", "2099-03-15", "2099-04-20", "2099-04-20"],
            ["", "2001-01-01", "2001-01-20", "2001-01-20"],
        ]) {
            await page.locator("#date").evaluate(
                (input, limits) => {
                    [input.value, input.min, input.max] = limits;
                },
                [value, min, max],
            );
            await page.getByRole("button", { name: "Choose Scheduled date" }).click();
            assert.equal(await page.evaluate(() => document.activeElement.dataset.date), expected);
            assert.equal(await page.locator('[data-date][tabindex="0"]:enabled').count(), 1);
            assert.equal(await page.locator("#date").inputValue(), value);
            await page.keyboard.press(expected === min ? "ArrowLeft" : "ArrowRight");
            assert.equal(await page.evaluate(() => document.activeElement.dataset.date), expected);
            await page.keyboard.press("Enter");
            assert.equal(await page.locator("#date").inputValue(), expected);
        }
        await page.evaluate(() => {
            const dialog = document.createElement("dialog");
            dialog.innerHTML =
                '<label for="dynamic">Deadline</label><input id="dynamic" type="date">';
            document.body.append(dialog);
            dialog.showModal();
        });
        await page.getByRole("button", { name: "Choose Deadline" }).click();
        assert.equal(await page.locator("dialog .app-date-popup").count(), 1);
        await page.getByRole("button", { name: "Today", exact: true }).click();
        assert.ok(await page.locator("#dynamic").inputValue());
        await page.getByRole("button", { name: "Choose Deadline" }).click();
        await page.getByRole("button", { name: "Clear date" }).click();
        assert.equal(await page.locator("#dynamic").inputValue(), "");
        console.log(
            "Date picker: keyboard selection, form value, range limits, mobile bounds, month navigation, Escape focus, dynamic modal, Today and Clear passed.",
        );
    } finally {
        await browser.close();
    }
})().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

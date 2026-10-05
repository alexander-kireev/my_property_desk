const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { launchBrowser } = require("./support.cjs");
const base = process.env.PMS_TEST_BASE || "http://127.0.0.1:8024";
let browser;
before(async () => {
    browser = await launchBrowser();
});
after(async () => {
    await browser?.close();
});

async function pageFor(t, path) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    t.after(() => context.close());
    const session = JSON.parse(fs.readFileSync(process.env.PMS_BROWSER_SESSION, "utf8"));
    await context.addCookies([
        { name: session.cookie_name, value: session.cookie_value, url: base },
    ]);
    const page = await context.newPage();
    // This batch checks client behaviour; no test may change application records.
    await page.route("**/*", (route) =>
        ["GET", "HEAD"].includes(route.request().method()) ? route.continue() : route.abort(),
    );
    await page.goto(base + path);
    await page.waitForLoadState("networkidle");
    return page;
}

test("Profile labels stay in their own dialogs and help references resolve", async (t) => {
    const page = await pageFor(t, "/accounts/profile/");
    const result = await page.evaluate(() => {
        const ids = [...document.querySelectorAll("[id]")].map((e) => e.id);
        return {
            unique: new Set(ids).size === ids.length,
            labelsCorrect: [...document.querySelectorAll(".modal label[for]")].every(
                (label) => label.control?.closest(".modal") === label.closest(".modal"),
            ),
            missing: [...document.querySelectorAll("[aria-describedby]")].flatMap((e) =>
                e
                    .getAttribute("aria-describedby")
                    .split(/\s+/)
                    .filter((id) => !document.getElementById(id)),
            ),
        };
    });
    assert.deepEqual(result, { unique: true, labelsCorrect: true, missing: [] });
});

test("Dashboard Add Event error describes and focuses the visible property control, then clears on reopen", async (t) => {
    const page = await pageFor(t, "/dashboard/");
    await page.route("**/dashboard/action/", (route) =>
        route.fulfill({
            status: 400,
            json: { errors: { property: ["Example relationship error"] } },
        }),
    );
    await page.locator("#dashboardAddToggle").click();
    await page.locator('[data-add="event"]').click();
    const form = page.locator("#dashboardAddEventModal form");
    await form.locator('[name="title"]').fill("Error association check");
    await form.evaluate((e) =>
        e.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
    );
    await page.getByText("Example relationship error", { exact: true }).waitFor();
    assert.deepEqual(
        await form.locator('[name="property"]').evaluate((field) => {
            const trigger = field.closest(".app-select").querySelector(".app-select-trigger");
            return {
                focused: document.activeElement === trigger,
                invalid: trigger.getAttribute("aria-invalid"),
                description: document.getElementById(trigger.getAttribute("aria-describedby"))
                    ?.textContent,
            };
        }),
        { focused: true, invalid: "true", description: "Example relationship error" },
    );
    await page.locator('#dashboardAddEventModal [data-bs-dismiss="modal"]').first().click();
    await page.locator("#dashboardAddEventModal").waitFor({ state: "hidden" });
    await page.locator("#dashboardAddToggle").click();
    await page.locator('[data-add="event"]').click();
    assert.equal(await form.locator('[aria-invalid="true"]').count(), 0);
    assert.equal(await form.locator('[aria-describedby*="dashboard_error"]').count(), 0);
});

test("all Dashboard tab groups use arrow keys, one tab stop, and associated panels", async (t) => {
    const page = await pageFor(t, "/dashboard/");
    for (const [start, next] of [
        ["workTabTask", "workTabIssue"],
        ["dayTabTasks", "dayTabDeadlines"],
        ["dayViewToggle", "notesViewToggle"],
    ]) {
        await page.locator("#" + start).focus();
        await page.keyboard.press("ArrowRight");
        assert.equal(await page.evaluate(() => document.activeElement.id), next);
        assert.deepEqual(
            await page
                .locator("#" + next)
                .evaluate((tab) => ({
                    selected: tab.getAttribute("aria-selected"),
                    stops: tab
                        .closest("[role=tablist]")
                        .querySelectorAll('[role=tab][tabindex="0"]').length,
                    panel: document
                        .getElementById(tab.getAttribute("aria-controls"))
                        ?.getAttribute("aria-labelledby"),
                })),
            { selected: "true", stops: 1, panel: next },
        );
        await page.keyboard.press("Home");
        assert.equal(await page.evaluate(() => document.activeElement.id), start);
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('[data-dashboard-panel="operations"]').click();
    await page.locator("#workTabTask").focus();
    await page.keyboard.press("ArrowLeft");
    assert.equal(await page.evaluate(() => document.activeElement.id), "workTabEvent");
});

test("Bootstrap Event and Issue tabs have reciprocal panel labels", async (t) => {
    const page = await pageFor(t, "/events/");
    for (const path of ["/events/", "/issues/"]) {
        await page.goto(base + path);
        await page.waitForLoadState("networkidle");
        const tabs = page.locator('[data-bs-toggle="tab"]');
        assert.ok((await tabs.count()) > 0);
        for (const tab of await tabs.all()) {
            const linked = await tab.evaluate(
                (e) =>
                    document.querySelector(e.dataset.bsTarget)?.getAttribute("aria-labelledby") ===
                        e.id && e.getAttribute("aria-controls") === e.dataset.bsTarget.slice(1),
            );
            assert.equal(linked, true);
        }
        await tabs.first().focus();
        await page.keyboard.press("ArrowRight");
        assert.equal(await tabs.nth(1).getAttribute("aria-selected"), "true");
    }
});

test("required Contact method stays focusable and submits the selected value", async (t) => {
    const page = await pageFor(t, "/contacts/");
    await page.locator('[data-bs-target="#addContactMethodModal"]').first().click();
    await page.locator("#addContactMethodModal.show").waitFor();
    const field = page.locator("#add_contact_method_type");
    assert.deepEqual(
        await field.evaluate((e) => ({
            valid: e.reportValidity(),
            focused: document.activeElement === e,
        })),
        { valid: false, focused: true },
    );
    await field.selectOption("email");
    await page.locator("#add_contact_method_value").fill("test@example.com");
    assert.deepEqual(
        await field.evaluate((e) => ({
            value: new FormData(e.form).get("type"),
            valid: e.form.checkValidity(),
        })),
        { value: "email", valid: true },
    );
});

test("Dashboard Add and Edit fields match the 75-character work title constraint", async (t) => {
    const page = await pageFor(t, "/dashboard/");
    for (const kind of ["task", "issue", "event"]) {
        await page.locator("#dashboardAddToggle").click();
        await page.locator(`[data-add="${kind}"]`).click();
        const modal = page.locator(kind === "event" ? "#dashboardAddEventModal" : "#workDialog");
        const title = modal.locator('[name="title"]');
        assert.equal(await title.getAttribute("maxlength"), "75");
        await title.fill("");
        await title.pressSequentially("A".repeat(76));
        assert.equal((await title.inputValue()).length, 75);
        await modal.locator('[data-bs-dismiss="modal"], [data-close-dialog]').first().click();
        await modal.waitFor({ state: "hidden" });
        await page.locator(`[data-kind="${kind}"][role="tab"]`).click();
        const row = page.locator('#workList [data-kind="' + kind + '"]').first();
        await row.locator(".dashboard-row-toggle").click();
        await row.locator('[data-action="edit"]').click();
        assert.equal(
            await page.locator('#workDialog [name="title"]').getAttribute("maxlength"),
            "75",
        );
        await page.locator("#workDialog [data-close-dialog]").first().click();
        await page.locator("#workDialog").waitFor({ state: "hidden" });
    }
});

test("public footer links navigate to existing routes and Back returns", async (t) => {
    const page = await browser.newPage();
    t.after(() => page.close());
    for (const [label, path] of [
        ["About", "/about/"],
        ["Contact", "/contact/"],
    ]) {
        await page.goto(base + "/accounts/login/");
        await page.locator("footer").getByRole("link", { name: label, exact: true }).click();
        assert.equal(new URL(page.url()).pathname, path);
        await page.goBack();
        assert.equal(new URL(page.url()).pathname, "/accounts/login/");
    }
});

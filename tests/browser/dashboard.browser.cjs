const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { launchBrowser } = require("./support.cjs");
let browser;
let session;
const base = process.env.PMS_TEST_BASE || "http://127.0.0.1:8024";
before(async () => {
    if (!process.env.PMS_BROWSER_SESSION) throw new Error("Set PMS_BROWSER_SESSION to a local test-session JSON file.");
    session = JSON.parse(fs.readFileSync(process.env.PMS_BROWSER_SESSION, "utf8"));
    browser = await launchBrowser();
});
after(async () => { await browser?.close(); });

async function fixture(t, {returning = false} = {}) {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    t.after(() => context.close());
    await context.addCookies([{name: session.cookie_name, value: session.cookie_value, url: base}]);
    const page = await context.newPage();
    const calls = [];
    let reply = async route => route.fulfill({status: 400, json: {error: "Test request blocked"}});
    // Every mutation is intercepted, even if a test forgets to supply a response.
    await page.route("**/dashboard/action/", async route => {
        calls.push(new URLSearchParams(route.request().postData()));
        await reply(route);
    });
    if (returning) await page.addInitScript(() => {
        if (location.pathname !== "/dashboard/") return;
        history.replaceState({pomDashboardReturn: {url: "/dashboard/", kind: "task", filter: "all", secondaryFilter: "any", shown: 40, expanded: null, search: "", scrollTop: 0}}, "");
        const original = performance.getEntriesByType.bind(performance);
        performance.getEntriesByType = type => type === "navigation" ? [{type: "back_forward"}] : original(type);
    });
    await page.goto(base + "/dashboard/");
    await page.waitForFunction(() => document.querySelector("#selectedDayHeading")?.textContent.includes(","));
    return {page, calls, respond: handler => { reply = handler; }};
}

async function openTask(page) {
    await page.locator("#dashboardAddToggle").click();
    await page.locator('[data-add="task"]').click();
    await page.locator('#workForm [name="title"]').fill("Browser characterization");
}

test("work submit blocks duplicates and retains server validation errors", async t => {
    const view = await fixture(t);
    let release;
    view.respond(async route => {
        await new Promise(resolve => { release = resolve; });
        await route.fulfill({status: 400, json: {errors: {title: ["Example validation error"]}}});
    });
    await openTask(view.page);
    await view.page.locator("#workForm").evaluate(form => {
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
    });
    await view.page.waitForFunction(() => document.querySelector('#workForm [type="submit"]').disabled);
    await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal(view.calls.length, 1);
    release();
    await view.page.getByText("Example validation error", {exact: true}).waitFor();
    assert.equal(await view.page.locator("#workDialog").isVisible(), true);
    assert.equal(await view.page.locator('#workForm [name="title"]').inputValue(), "Browser characterization");
});

test("successful save followed by refresh failure reports the saved operation accurately", async t => {
    const view = await fixture(t);
    view.respond(async route => {
        await view.page.route("**/dashboard/data/", r => r.fulfill({status: 503, json: {}}));
        await route.fulfill({json: {id: 999999, changed: true}});
    });
    await openTask(view.page);
    await view.page.locator('#workForm [type="submit"]').click();
    await view.page.locator("#dashboardToastTitle").filter({hasText: "Task added, but Dashboard could not refresh"}).waitFor();
    await view.page.waitForFunction(() => !document.querySelector("#workDialog").classList.contains("show"));
});

test("quick action exposes Undo and failed Undo can be retried", async t => {
    const view = await fixture(t);
    view.respond(route => route.fulfill({json: {undo_token: "mock-token"}}));
    await view.page.locator("#workList .dashboard-row-toggle").first().click();
    await view.page.locator('#workList [data-action="finish"]').first().click();
    await view.page.locator("#dashboardToastUndo").waitFor();
    view.respond(route => route.fulfill({status: 503, json: {error: "Temporary test failure"}}));
    await view.page.locator("#dashboardToastUndo").click();
    await view.page.getByText("Temporary test failure", {exact: true}).waitFor();
    assert.equal(await view.page.locator("#dashboardToastUndo").isEnabled(), true);
    view.respond(route => route.fulfill({json: {ok: true}}));
    await view.page.locator("#dashboardToastUndo").click();
    await view.page.getByText("Action undone.", {exact: true}).waitFor();
    assert.equal(view.calls.filter(fields => fields.get("action") === "undo").length, 2);
});

test("later refresh does not reapply the initial Back search state", async t => {
    const view = await fixture(t, {returning: true});
    await view.page.locator("#workSearch").fill("new search");
    view.respond(route => route.fulfill({json: {ok: true}}));
    await view.page.locator("#notesViewToggle").click();
    await view.page.locator("#noteContent").fill("Mock note");
    await view.page.locator("#noteForm").evaluate(form => form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true})));
    await view.page.getByText("Note added.", {exact: true}).waitFor();
    assert.equal(await view.page.locator("#workSearch").inputValue(), "new search");
});

test("Notes submit blocks concurrent duplicate requests", async t => {
    const view = await fixture(t);
    const pending = [];
    view.respond(route => new Promise(resolve => pending.push(async () => { await route.fulfill({json: {ok: true}}); resolve(); })));
    await view.page.locator("#noteForm").evaluate(form => {
        document.getElementById("noteContent").value = "Mock note";
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
        form.dispatchEvent(new Event("submit", {bubbles: true, cancelable: true}));
    });
    await new Promise(resolve => setTimeout(resolve, 150));
    const count = view.calls.length;
    await Promise.all(pending.map(release => release()));
    assert.equal(count, 1);
});

test("calendar shortcuts select their tab and a bare date returns to Tasks", async t => {
    const {page} = await fixture(t);
    await page.locator('#calendarGrid [data-category="events"]').first().click();
    assert.equal(await page.locator('#dayTabEvents').getAttribute('aria-selected'), 'true');
    await page.locator('#calendarGrid .dashboard-date-button').first().click();
    assert.equal(await page.locator('#dayTabTasks').getAttribute('aria-selected'), 'true');
    assert.match(await page.locator('#selectedDayHeading').textContent(), /\w+, \d+ \w+ \d{4}/);
});

test("a second More click closes the record action menu", async t => {
    const {page} = await fixture(t);
    await page.setViewportSize({width:375,height:800});
    await page.locator('#workList .dashboard-row-toggle').first().click();
    const toggle = page.locator('#workList [data-action="more"]').first();
    await toggle.click();
    await page.waitForFunction(() => document.querySelector('#workList [data-action="more"]').getAttribute('aria-expanded') === 'true');
    await toggle.click();
    await page.waitForFunction(() => document.querySelector('#workList [data-action="more"]').getAttribute('aria-expanded') === 'false');
});

test("each record type opens edit on a phone and cancels without writing", async t => {
    const {page,calls} = await fixture(t);
    await page.setViewportSize({width:375,height:800});
    for (const kind of ['task','issue','event']) {
        await page.locator(`[data-kind="${kind}"][role="tab"]`).click();
        await page.locator('#workList .dashboard-row-toggle').first().click();
        await page.locator('#workList [data-action="edit"]').first().click();
        await page.waitForFunction(() => document.activeElement?.name === 'title');
        assert.equal(await page.locator('#workDialogHeading').textContent(), `Edit ${kind}`);
        assert.ok(await page.locator('#workForm [name="title"]').inputValue());
        await page.locator('#workDialog [data-close-dialog]').first().click();
        await page.waitForFunction(() => !document.querySelector('#workDialog').classList.contains('show'));
    }
    assert.equal(calls.length,0);
});

test("Issue confirmation keeps linked-task choice and focuses the safe action", async t => {
    const {page,calls} = await fixture(t);
    await page.locator('[data-kind="issue"][role="tab"]').click();
    await page.locator('#workList .dashboard-row-toggle').first().click();
    await page.locator('#workList [data-action="finish"]').first().click();
    await page.waitForFunction(() => document.activeElement?.id === 'confirmCancel');
    assert.equal(await page.locator('#confirmAction').evaluate(e => e.classList.contains('dashboard-danger-button')),false);
    assert.equal(await page.locator('#confirmLinkedTasks').isChecked(),false);
    await page.locator('#confirmCancel').click();
    await page.waitForFunction(() => !document.querySelector('#confirmDialog').classList.contains('show'));
    const more=page.locator('#workList [data-action="more"]').first();
    await more.click();
    await page.locator('.dashboard-row-menu:popover-open [data-action="delete"]').click();
    await page.waitForFunction(() => document.activeElement?.id === 'confirmCancel');
    assert.equal(await page.locator('#confirmAction').evaluate(e => e.classList.contains('dashboard-danger-button')),true);
    await page.locator('#confirmCancel').click();
    assert.equal(calls.length,0);
});

test("a record past the first forty can expand its long description", async t => {
    const {page} = await fixture(t);
    const data=await page.evaluate(async () => (await fetch(document.querySelector('#dashboard').dataset.dataUrl)).json());
    const first=data.records.task[0];
    data.records.task=Array.from({length:60},(_,i)=>({...first,id:90000+i,title:`Long list task ${i}`,date:null,description:'A long description for browser coverage. '.repeat(50)}));
    await page.route('**/dashboard/data/',route=>route.fulfill({json:data}));
    await page.reload();
    await page.locator('#workList [data-id="90000"]').waitFor();
    await page.locator('#workList').evaluate(list=>{list.scrollTop=list.scrollHeight;list.dispatchEvent(new Event('scroll'));});
    const row=page.locator('#workList [data-id="90059"]').first();
    await row.locator('.dashboard-row-toggle').click();
    const toggle=row.locator('[data-expandable-toggle]');
    await toggle.waitFor({state:'visible'});
    await toggle.click();
    assert.match(await toggle.textContent(), /See less/);
});

test("dragging a timed Event opens edit with the proposed date before any write", async t => {
    const {page,calls}=await fixture(t);
    const data=await page.evaluate(async () => (await fetch(document.querySelector('#dashboard').dataset.dataUrl)).json());
    data.records.event=[{...data.records.event[0],id:99001,title:'Timed drag test',all_day:false,date:data.today,start_time:'09:00',end_time:'10:00'}];
    await page.route('**/dashboard/data/',route=>route.fulfill({json:data}));
    await page.reload();
    await page.locator('[data-kind="event"][role="tab"]').click();
    const row=page.locator('#workList [data-id="99001"]').first();
    await row.waitFor();
    const date=await page.locator('#calendarGrid [data-day]').first().getAttribute('data-day');
    await page.evaluate(date => {
        const transfer=new DataTransfer();
        document.querySelector('#workList [data-id="99001"]').dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:transfer}));
        document.querySelector(`#calendarGrid [data-day="${date}"]`).dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
    },date);
    await page.waitForFunction(() => document.activeElement?.name==='title');
    assert.equal(await page.locator('#workForm [name="scheduled_date"]').inputValue(),date);
    assert.equal(await page.locator('#workForm [name="start_time"]').inputValue(),'09:00');
    assert.equal(calls.length,0);
    await page.locator('#workDialog [data-close-dialog]').first().click();
});

test("Notes edit survives a failed save and Cancel restores the displayed content", async t => {
    const {page,calls}=await fixture(t);
    await page.locator('#notesViewToggle').click();
    const note=page.locator('#notesList [data-note]').first();
    const content=await note.locator('p').textContent();
    await note.hover();
    await note.locator('[data-note-action="edit"]').click();
    await note.locator('textarea').fill('Edited locally for test');
    await note.locator('[data-note-action="save"]').click();
    await page.getByText('Test request blocked',{exact:true}).waitFor();
    assert.equal(await note.locator('textarea').inputValue(),'Edited locally for test');
    assert.equal(await note.locator('[data-note-action="save"]').isEnabled(),true);
    await note.locator('[data-note-action="cancel"]').click();
    assert.equal(await note.locator('p').textContent(),content);
    assert.equal(calls.length,1);
});

async function notesRefreshFixture(t) {
    const view = await fixture(t);
    const data = await view.page.evaluate(async () => (await fetch(document.querySelector('#dashboard').dataset.dataUrl)).json());
    data.notes = [{id:90001,content:'Saved note',created:'6 Oct 2026'},{id:90002,content:'Other note',created:'6 Oct 2026'}];
    await view.page.route('**/dashboard/data/', r => r.fulfill({json:data}));
    await view.page.reload();
    await view.page.locator('#notesViewToggle').click();
    await view.page.locator('[data-note="90001"] [data-note-action="edit"]').click();
    return {...view,data};
}

async function finishFirstTask(page) {
    const toggle=page.locator('#workList .dashboard-row-toggle').first();
    if(await toggle.getAttribute('aria-expanded')!=='true') await toggle.click();
    await page.locator('#workList [data-action="finish"]').first().click();
}

test('note draft survives unrelated actions and missing saved note; Cancel discards it', async t => {
    const {page,data,respond}=await notesRefreshFixture(t);
    respond(r=>r.fulfill({json:{changed:true}}));
    const editor=page.locator('[data-note="90001"] textarea');
    await editor.fill('My unsaved draft');
    await finishFirstTask(page);
    await page.getByText('Task completed.',{exact:true}).waitFor();
    assert.equal(await editor.inputValue(),'My unsaved draft');
    data.notes=data.notes.filter(n=>n.id!==90002);
    await page.locator('[data-note="90002"] [data-note-action="delete"]').click();
    await page.waitForFunction(()=>!document.querySelector('[data-note="90002"]'));
    assert.equal(await editor.inputValue(),'My unsaved draft');
    data.notes=[];
    await finishFirstTask(page);
    await page.getByText('This note is no longer available. Copy your draft before cancelling.').waitFor();
    assert.equal(await editor.inputValue(),'My unsaved draft');
    assert.equal(await page.locator('[data-note="90001"] [data-note-action="save"]').isDisabled(),true);
    await page.locator('[data-note="90001"] [data-note-action="cancel"]').click();
    assert.equal(await page.locator('#notesList textarea').count(),0);
});

test('slow note save keeps newer typing and a later save closes the correct draft', async t => {
    const {page,data,respond}=await notesRefreshFixture(t);
    let release;
    respond(async r=>{await new Promise(resolve=>{release=resolve});data.notes[0].content='Submitted draft';await r.fulfill({json:{changed:true}})});
    const editor=page.locator('[data-note="90001"] textarea');
    await editor.fill('Submitted draft');
    await page.locator('[data-note="90001"] [data-note-action="save"]').click();
    await page.waitForFunction(()=>document.querySelector('[data-note="90001"] [data-note-action="save"]').disabled);
    await editor.fill('New typing while saving');
    release();
    await page.getByText('Note updated.',{exact:true}).waitFor();
    assert.equal(await editor.inputValue(),'New typing while saving');
    respond(async r=>{data.notes[0].content='New typing while saving';await r.fulfill({json:{changed:true}})});
    await page.locator('[data-note="90001"] [data-note-action="save"]').click();
    await page.locator('[data-note="90001"] p').filter({hasText:'New typing while saving'}).waitFor();
    assert.equal(await page.locator('#notesList textarea').count(),0);
});

for (const newestFails of [false,true]) {
    test(`overlapping refreshes retain newest result (latest failure: ${newestFails})`, async t => {
        const {page,data,respond}=await notesRefreshFixture(t);
        await page.locator('[data-note="90001"] [data-note-action="cancel"]').click();
        respond(r=>r.fulfill({json:{changed:true}}));
        const pending=[];
        await page.unroute('**/dashboard/data/');
        await page.route('**/dashboard/data/',r=>{pending.push(r)});
        async function waitForRequests(count) {
            for(let tries=0;pending.length<count&&tries<200;tries++)await new Promise(resolve=>setTimeout(resolve,25));
            assert.equal(pending.length,count);
        }
        await page.locator('#noteContent').fill('Added note');
        await page.locator('#noteForm [type="submit"]').click();
        await waitForRequests(1);
        await finishFirstTask(page);
        await waitForRequests(2);
        if(newestFails) await pending[1].fulfill({status:503,json:{}});
        else {
            const latest=structuredClone(data);latest.notes[0].content='Newer server result';
            await pending[1].fulfill({json:latest});
            await page.getByText('Newer server result',{exact:true}).waitFor();
        }
        await pending[0].fulfill({json:data});
        await page.waitForFunction(()=>!document.querySelector('#noteForm [type="submit"]').disabled);
        assert.equal(await page.locator('[data-note="90001"] p').innerText(),newestFails?'Saved note':'Newer server result');
        if(newestFails) assert.match(await page.locator('#dashboardToastTitle').innerText(),/Note added, but Dashboard could not refresh/);
    });
}

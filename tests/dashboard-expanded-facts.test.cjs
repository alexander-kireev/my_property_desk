const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const browser = {};
vm.runInNewContext(readFileSync(path.join(__dirname, "../static/js/dashboard-records.js"), "utf8"), {window: browser});
const recordRow = (item, area) => browser.DashboardRecords.recordRow(item, area, {
    expanded: null, today: "2026-09-30",
    urls: {taskUrl: "/tasks/", issueUrl: "/issues/", eventUrl: "/events/"},
});
const base = {id: 1, title: "Record", description: "", state: "active", property: "", issue_id: null,
    date: "", due: "", start_time: "", end_time: "", all_day: true};

test("unrelated expanded records omit relationship fact chips in either list", () => {
    for (const kind of ["task", "issue", "event"]) {
        for (const area of ["queue", "day"]) {
            const html = recordRow({...base, kind}, area);
            assert.doesNotMatch(html, /dashboard-property-fact|dashboard-issue-fact|Property: None|Issue: None/);
        }
    }
});

test("linked facts show names without deleted relationship labels", () => {
    const task = recordRow({...base, kind: "task", issue_id: 3, issue_title: "Roof leak",
        issue_deleted: true, property: "Inherited property"}, "day");
    assert.match(task, /dashboard-issue-fact/);
    assert.match(task, /Roof leak/);
    assert.doesNotMatch(task, /Deleted issue/);
    assert.doesNotMatch(task, /dashboard-property-fact|<span class="dashboard-issue-label">/);

    const event = recordRow({...base, kind: "event", property: "Canal View", property_deleted: true,
        date: "2026-09-29"}, "queue");
    assert.match(event, /dashboard-property-fact/);
    assert.match(event, /Canal View/);
    assert.doesNotMatch(event, /Deleted property/);
    assert.doesNotMatch(event, /Property:<\/span>/);
});

test("collapsed subtitles omit absent relationships without leading separators in both areas", () => {
    for (const area of ["queue", "day"]) {
        const task = recordRow({...base, kind: "task", due: "2026-10-01"}, area);
        assert.match(task, /<strong class="dashboard-task-title" title="Record">Record<\/strong>\s*<small class="dashboard-task-context" aria-hidden="true"><\/small>/);
        if (area === "queue") assert.match(task, /dashboard-task-timing">Due soon 1 Oct 2026/);
        else assert.doesNotMatch(task, /dashboard-task-timing/);
        assert.doesNotMatch(task, /Unscheduled · Due/);
        assert.doesNotMatch(task, /Standalone|No property/);

        const issue = recordRow({...base, kind: "issue", due: "2026-10-02"}, area);
        assert.match(issue, /<strong title="Record">Record<\/strong>\s*<small class="dashboard-row-context" aria-hidden="true"><\/small>/);
        if (area === "queue") assert.match(issue, /dashboard-row-timing">Due soon 2 Oct 2026/);
        else assert.doesNotMatch(issue, /dashboard-row-timing/);
        assert.doesNotMatch(issue, /No property|<small> ·/);

        const event = recordRow({...base, kind: "event", state: "scheduled", date: "2026-10-03"}, area);
        const eventSummary = event.slice(0, event.indexOf("dashboard-row-detail"));
        assert.match(event, /<strong title="Record">Record<\/strong>\s*<small class="dashboard-row-context" aria-hidden="true"><\/small>/);
        if (area === "queue") {
            assert.match(event, /dashboard-row-timing"><span>3 Oct 2026/);
            assert.doesNotMatch(eventSummary, /data-state="scheduled"/);
        } else {
            assert.match(event, /dashboard-row-timing"><span>All day<\/span><\/span>/);
            assert.match(eventSummary, /data-state="scheduled"/);
        }
        assert.doesNotMatch(event, /No property|<small> ·/);
    }
});

test("collapsed linked subtitles retain direct names and dates without deleted labels", () => {
    for (const area of ["queue", "day"]) {
        const propertyTask = recordRow({...base, kind: "task", property: "Canal View", property_deleted: true}, area);
        assert.match(propertyTask, /dashboard-task-context[^>]*>Canal View<\/small>/);
        assert.doesNotMatch(propertyTask, /Deleted property/);
        if (area === "queue") assert.match(propertyTask, /No date/);
        else assert.doesNotMatch(propertyTask, /No date/);

        const issueTask = recordRow({...base, kind: "task", issue_id: 5, issue_title: "Roof leak", issue_deleted: true,
            property: "Inherited property", date: "2026-10-04"}, area);
        assert.match(issueTask, /dashboard-task-context[^>]*>Roof leak<\/small>/);
        assert.doesNotMatch(issueTask, /Deleted issue/);
        if (area === "queue") assert.match(issueTask, /Scheduled 4 Oct 2026/);
        else assert.doesNotMatch(issueTask, /Scheduled 4 Oct 2026/);
        assert.doesNotMatch(issueTask.slice(0, issueTask.indexOf("dashboard-row-detail")), /Inherited property|Standalone/);

        for (const kind of ["issue", "event"]) {
            const linked = recordRow({...base, kind, property: "Hill House", date: "2026-10-05",
                due: kind === "issue" ? "2026-10-06" : ""}, area);
            assert.match(linked, /dashboard-row-context[^>]*>Hill House<\/small>/);
            assert.doesNotMatch(linked, /No property|<small> ·/);
        }
    }
});

test("Operations tasks prioritise due dates and highlight overdue timing", () => {
    const task = recordRow({...base, kind: "task", property: "Canal View",
        date: "2026-09-29", due: "2026-09-28"}, "queue");
    assert.match(task, /dashboard-task-context[^>]*>Canal View<\/small>/);
    assert.match(task, /dashboard-task-timing is-overdue">Overdue 28 Sep 2026<\/span>/);
    assert.doesNotMatch(task.slice(0, task.indexOf("dashboard-row-detail")), /Scheduled 29 Sep 2026/);
    assert.match(task, /<span>Scheduled 29 Sep 2026<\/span>/);
});

test("Operations issues use a short deadline label", () => {
    const issue = recordRow({...base, kind: "issue", due: "2026-10-13"}, "queue");
    const summary = issue.slice(0, issue.indexOf("dashboard-row-detail"));
    assert.match(summary, /dashboard-row-timing">Due by 13 Oct 2026<\/span>/);
    assert.doesNotMatch(summary, /Resolve by/);
});

test("Selected day deadlines retain their type without repeating the selected date", () => {
    for (const kind of ["task", "issue"]) {
        const html = recordRow({...base, kind, due: "2026-09-29"}, "due");
        const summary = html.slice(0, html.indexOf("dashboard-row-detail"));
        assert.doesNotMatch(summary, /dashboard-(task|row)-timing/);
        assert.match(summary, /dashboard-type-cue/);
        assert.doesNotMatch(summary, /aria-hidden="true"><span class="dashboard-type-cue"/);
        assert.doesNotMatch(html, /29 Sep 2026/);
    }
});

test("Selected day Event times retain start-only, range and all-day meaning", () => {
    for (const [start_time, end_time, all_day, expected] of [
        ["09:00", "", false, "09:00"],
        ["09:00", "10:00", false, "09:00–10:00"],
        ["", "", true, "All day"],
    ]) {
        const html = recordRow({...base, kind: "event", date: "2026-10-03", start_time, end_time, all_day}, "day");
        const summary = html.slice(0, html.indexOf("dashboard-row-detail"));
        assert.ok(summary.includes(expected));
        assert.doesNotMatch(summary, /3 Oct 2026/);
        assert.doesNotMatch(html, /Date 3 Oct 2026/);
    }
});


test("Selected day keeps only dates different from its heading", () => {
    const item = {...base, kind: "task", date: "2026-10-01", due: "2026-10-05"};
    const scheduled = recordRow(item, "day");
    assert.doesNotMatch(scheduled, /Scheduled 1 Oct 2026|Unscheduled/);
    assert.match(scheduled, /Due 5 Oct 2026/);
    const deadline = recordRow(item, "due");
    assert.match(deadline, /Scheduled 1 Oct 2026/);
    assert.doesNotMatch(deadline, /Due 5 Oct 2026/);
    for (const area of ["day", "due"]) {
        assert.doesNotMatch(recordRow({...item, due: item.date}, area), /1 Oct 2026|Unscheduled/);
    }
    const queue = recordRow(item, "queue");
    assert.match(queue, /Scheduled 1 Oct 2026/);
    assert.match(queue, /Due 5 Oct 2026/);
});

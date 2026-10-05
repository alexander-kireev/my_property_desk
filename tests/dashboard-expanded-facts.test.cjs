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
        assert.match(task, /dashboard-task-timing">Due soon 1 Oct 2026<\/span>[\s\S]*<span class="dashboard-row-chevron">/);
        assert.doesNotMatch(task, /Unscheduled · Due/);
        assert.doesNotMatch(task, /Standalone|No property/);

        const issue = recordRow({...base, kind: "issue", due: "2026-10-02"}, area);
        assert.match(issue, /<strong title="Record">Record<\/strong>\s*<small class="dashboard-row-context" aria-hidden="true"><\/small>/);
        assert.match(issue, /dashboard-row-timing">Due soon 2 Oct 2026<\/span>/);
        assert.doesNotMatch(issue, /No property|<small> ·/);

        const event = recordRow({...base, kind: "event", date: "2026-10-03"}, area);
        assert.match(event, /<strong title="Record">Record<\/strong>\s*<small class="dashboard-row-context" aria-hidden="true"><\/small>/);
        assert.match(event, /dashboard-row-timing"><span>3 Oct 2026 ·<\/span><span>All day<\/span><\/span>/);
        assert.doesNotMatch(event, /No property|<small> ·/);
    }
});

test("collapsed linked subtitles retain direct names and dates without deleted labels", () => {
    for (const area of ["queue", "day"]) {
        const propertyTask = recordRow({...base, kind: "task", property: "Canal View", property_deleted: true}, area);
        assert.match(propertyTask, /dashboard-task-context[^>]*>Canal View<\/small>[\s\S]*dashboard-task-timing">No date/);
        assert.doesNotMatch(propertyTask, /Deleted property/);
        assert.match(propertyTask, /No date/);

        const issueTask = recordRow({...base, kind: "task", issue_id: 5, issue_title: "Roof leak", issue_deleted: true,
            property: "Inherited property", date: "2026-10-04"}, area);
        assert.match(issueTask, /dashboard-task-context[^>]*>Roof leak<\/small>/);
        assert.doesNotMatch(issueTask, /Deleted issue/);
        assert.match(issueTask, /Scheduled 4 Oct 2026/);
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

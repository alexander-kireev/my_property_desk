const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const browser = {};
vm.runInNewContext(fs.readFileSync('static/js/dashboard-records.js','utf8'), {window:browser});
const display = browser.DashboardRecords;
test('issue week includes Monday and Sunday and excludes adjacent dates', () => {
    const issue = ['2026-09-27','2026-09-28','2026-10-04','2026-10-05',''].map(due => ({due,title:'Issue',description:'',property:''}));
    const result = display.visibleRecords({issue}, {kind:'issue',filter:'week',secondaryFilter:'any',search:'',today:'2026-09-30'});
    assert.deepEqual(Array.from(result, item => item.due), ['2026-09-28','2026-10-04']);
});
test('date-only formatting and week start remain stable across month boundaries', () => {
    assert.equal(display.isoDate(display.mondayOf('2026-10-04')), '2026-09-28');
    assert.equal(display.longDate('2026-10-05'), 'Monday, 5 October 2026');
});
test('row rendering escapes user text and preserves full record navigation', () => {
    const html = display.recordRow({id:7,kind:'task',title:'<img src=x onerror="bad()">',description:'<script>bad()</script>',property:'A & B',date:'',due:''}, 'queue',
        {expanded:null,today:'2026-10-05',urls:{taskUrl:'/tasks/'}});
    assert.ok(html.includes('&lt;img'));
    assert.ok(html.includes('A &amp; B'));
    assert.ok(!html.includes('<script>'));
    assert.ok(html.includes('/tasks/?selected=7&amp;open=detail'));
});

test('each priority matches exactly for tasks and issues alongside schedule and search', () => {
    for (const kind of ['task', 'issue']) {
        const records = ['Urgent', 'High', 'Medium', 'Low'].map((priority, index) => ({
            id: index, priority, title: 'Boiler inspection', description: '', property: '',
            date: '2026-10-06', due: '2026-10-06',
        }));
        for (const priority of ['Urgent', 'High', 'Medium', 'Low']) {
            const options = {kind, filter: kind === 'task' ? 'today' : 'week',
                secondaryFilter: 'priority-' + priority.toLowerCase(), search: 'boiler', today: '2026-10-06'};
            assert.deepEqual(Array.from(display.visibleRecords({[kind]: records}, options), item => item.priority), [priority]);
            assert.equal(display.visibleRecords({[kind]: records}, {...options, search: 'unmatched'}).length, 0);
        }
        assert.equal(display.visibleRecords({[kind]: records}, {kind, filter: 'all', secondaryFilter: 'any', search: '', today: '2026-10-06'}).length, 4);
    }
});

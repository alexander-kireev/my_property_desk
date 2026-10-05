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

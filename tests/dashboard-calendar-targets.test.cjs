const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const js=fs.readFileSync(path.join(root,'static/js/dashboard.js'),'utf8');

test('A bare date click returns to Tasks while category shortcuts keep their own tab',()=>{
    assert.match(js,/const category = event\.target\.closest\("\[data-category\]"\);\s*dayTab = category \? category\.dataset\.category : "tasks";\s*selectDay\(day\.dataset\.day\);/);
});

test('Selected day uses one full date heading and issue week covers Monday through Sunday',()=>{
    assert.match(js,/get\("selectedDayHeading"\)\.textContent = longDate\(selected\);/);
    assert.doesNotMatch(js,/selectedDayNumber|selectedDayMonth/);
    assert.match(js,/filter === "week" && \(!item\.due \|\| item\.due < isoDate\(mondayOf\(data\.today\)\) \|\| item\.due > isoDate\(weekEnd\)\)/);
});

test('More menus remember their pointer-down state so a second pointer click closes them',()=>{
    assert.match(js,/button\.dataset\.dashboardMenuWasOpen = String\(Boolean\(menu && menu\.matches\(":popover-open"\)\)\)/);
    assert.match(js,/const wasOpenAtPointerDown = button\.dataset\.dashboardMenuWasOpen === "true";/);
});

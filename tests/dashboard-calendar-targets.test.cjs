const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const css=fs.readFileSync(path.join(root,'static/css/dashboard.css'),'utf8');
const js=fs.readFileSync(path.join(root,'static/js/dashboard.js'),'utf8');

test('Dashboard keeps seven near-square calendar columns with compact direct category controls',()=>{
    assert.match(css,/\.dashboard-calendar-grid\s*\{[^}]*grid-template-columns:\s*repeat\(7,minmax\(0,1fr\)\)/s);
    assert.match(css,/\.dashboard-day\s*\{[^}]*aspect-ratio:\s*1\s*\/\s*1\.08;/s);
    assert.match(css,/\.dashboard-date-button\s*\{[^}]*height:\s*24px;[^}]*min-height:\s*24px;/s);
    assert.match(css,/\.dashboard-day-category\s*\{[^}]*width:\s*100%;[^}]*min-height:\s*15px;/s);
    assert.match(css,/@media \(max-width:\s*860px\)[\s\S]*\.dashboard-day\s*\{[^}]*grid-template-columns:\s*repeat\(3,minmax\(0,1fr\)\)/s);
    assert.match(css,/@media \(max-width:\s*860px\)[\s\S]*\.dashboard-count-label\s*\{[^}]*display:\s*none;/s);
});

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

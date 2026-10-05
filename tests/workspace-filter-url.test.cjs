const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('clearing one filter removes blank keys and retains meaningful navigation context', () => {
    const window = {location: {href: 'http://localhost/tasks/?search=roof&state=active&property=&sort=-created_at&page=2&selected=17&open=detail', assign(url) { this.next = url; }}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/workspace-filter-url.js'), 'utf8'), {window, URL});
    window.WorkspaceFilterUrl.clear('search');
    const result = new URL(window.location.next);
    assert.equal(result.searchParams.has('search'), false);
    assert.equal(result.searchParams.has('property'), false);
    assert.equal(result.searchParams.get('state'), 'active');
    assert.equal(result.searchParams.get('sort'), '-created_at');
    assert.equal(result.searchParams.get('page'), '2');
    assert.equal(result.searchParams.get('selected'), '17');
    assert.equal(result.searchParams.get('open'), 'detail');
});

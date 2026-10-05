const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function api(fetch) {
    const context = {window: {}, URLSearchParams, fetch};
    vm.runInNewContext(fs.readFileSync('static/js/dashboard-api.js', 'utf8'), context);
    return context.window.DashboardApi.create({actionUrl:'/action/',dataUrl:'/data/',csrfToken:'test-token'});
}
test('write keeps CSRF, credentials, repeated fields and server validation detail', async () => {
    let request;
    const client = api(async (url, options) => {
        request = {url, options};
        return {ok:false, json:async () => ({errors:{title:['Required']}})};
    });
    const fields = new URLSearchParams([['contacts','1'],['contacts','2']]);
    await assert.rejects(client.send(fields), error => {
        assert.equal(error.fieldErrors.title[0], 'Required');
        return true;
    });
    assert.equal(request.url, '/action/');
    assert.equal(request.options.credentials, 'same-origin');
    assert.equal(request.options.headers['X-CSRFToken'], 'test-token');
    assert.deepEqual(request.options.body.getAll('contacts'), ['1','2']);
});
test('network, invalid JSON and read failures retain actionable messages', async () => {
    await assert.rejects(api(async () => {throw Error('offline');}).send({}), /Could not connect/);
    await assert.rejects(api(async () => ({ok:false,json:async () => {throw Error('HTML');}})).send({}), /server could not process/);
    await assert.rejects(api(async () => ({ok:false})).load(), /Dashboard could not load/);
});

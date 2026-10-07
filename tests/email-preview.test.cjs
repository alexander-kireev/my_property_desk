const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');
const sandbox = {
    document: {createElement: () => ({getContext: () => null}), addEventListener() {}},
    window: {}, ResizeObserver: class { observe() {} },
};
vm.runInNewContext(fs.readFileSync('static/js/email-preview.js', 'utf8'), sandbox);
const fit = sandbox.window.EmailPreview.fitMiddle;
const measure = (text) => [...text].reduce((width, char) => width + (char === 'i' ? 2 : 8), 0);
test('short email remains complete', () => assert.equal(fit('a@b.co', 200, measure), 'a@b.co'));
test('middle fitting uses glyph widths while preserving both ends', () => {
    const thin = 'kiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii@example.com';
    const wide = 'contact44444444444444444444444444444444444444@example.com';
    const a = fit(thin, 150, measure);
    const b = fit(wide, 150, measure);
    assert.ok(a.length > b.length);
    for (const [full, preview] of [[thin, a], [wide, b]]) {
        assert.ok(measure(preview) <= 150);
        const [prefix, suffix] = preview.split('…');
        assert.ok(full.startsWith(prefix));
        assert.ok(full.endsWith(suffix));
        assert.ok(prefix && suffix);
    }
});
test('long domains and zero room do not cause an endless fitting loop', () => {
    assert.equal(fit('a@long.example.com', 0, measure), '…');
    assert.ok(measure(fit('a@' + 'long'.repeat(30) + '.com', 120, measure)) <= 120);
});

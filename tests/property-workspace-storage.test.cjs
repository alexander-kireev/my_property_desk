const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

for (const navigationType of ["navigate", "reload"]) {
    test(`Property disclosure remains usable when storage is denied on ${navigationType}`, () => {
        const listeners = {};
        const workspace = {
            addEventListener: (name, callback) => { listeners[name] = callback; },
            querySelectorAll: () => [],
        };
        const deny = () => { throw new Error("Storage disabled"); };
        const context = {
            document: {querySelector: () => workspace, addEventListener: (_name, callback) => callback()},
            window: {location: {pathname: "/properties/1/", search: ""},
                performance: {getEntriesByType: () => [{type: navigationType}]}, addEventListener() {}},
            sessionStorage: {getItem: deny, setItem: deny, removeItem: deny}, URL,
        };
        assert.doesNotThrow(() => vm.runInNewContext(fs.readFileSync("static/js/property-workspace.js", "utf8"), context));
        assert.doesNotThrow(() => listeners.focusin({target: {closest: () => null}}));
    });
}

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/expandable-text.js"), "utf8");
const styles = readFileSync(path.join(__dirname, "../static/css/site.css"), "utf8");
const propertyStyles = readFileSync(path.join(__dirname, "../static/css/property-workspace.css"), "utf8");
const sharedTemplate = readFileSync(path.join(__dirname, "../templates/includes/expandable_text.html"), "utf8");
const taskInlineTemplate = readFileSync(path.join(__dirname, "../task/templates/task/includes/mobile_task_details.html"), "utf8");
const taskTemplate = readFileSync(path.join(__dirname, "../task/templates/task/tasks.html"), "utf8");

function fixture({singleLine = false, fitCard = false, inlineEnd = false, overflow = true} = {}) {
    const handlers = new Map();
    const reveals = [];
    const classes = new Set([
        ...(singleLine ? ["expandable-text--single-line"] : []),
        ...(fitCard ? ["expandable-text--fit-card"] : []),
        ...(inlineEnd ? ["expandable-text--inline-end"] : []),
    ]);
    const contentClasses = new Set();
    const styles = new Map();
    const content = {
        classList: {
            add: (name) => contentClasses.add(name),
            remove: (name) => contentClasses.delete(name),
            toggle: (name, enabled) => enabled ? contentClasses.add(name) : contentClasses.delete(name),
        },
        getClientRects: () => [1],
        childNodes: [{nodeType: 3, textContent: "A".repeat(200)}],
        get scrollHeight() { return overflow ? 100 : 60; },
        clientHeight: 60,
        get scrollWidth() { return overflow ? 200 : 100; },
        clientWidth: 100,
        style: {
            setProperty: (name, value) => styles.set(name, value),
            removeProperty: (name) => styles.delete(name),
            getPropertyValue: (name) => styles.get(name) || "",
        },
        getBoundingClientRect: () => ({top: 100}),
    };
    const attributes = new Map([["aria-expanded", "false"]]);
    const toggle = {
        hidden: true,
        textContent: "See more",
        getAttribute: (name) => attributes.get(name),
        setAttribute: (name, value) => attributes.set(name, value),
        closest: () => wrapper,
    };
    const preview = inlineEnd ? {
        hidden: true,
        text: "",
        replaceChildren: function (textNode) { this.text = textNode.textContent; },
        getBoundingClientRect: function () { return {height: Math.ceil((this.text.length + 10) / 20) * 20}; },
        append: () => {},
    } : null;
    const wrapper = {
        classList: {contains: (name) => classes.has(name)},
        matches: (selector) => selector === "[data-expandable-text]",
        querySelector: (selector) => selector === "[data-expandable-content]" ? content
            : selector === "[data-expandable-toggle]" ? toggle
                : selector === "[data-expandable-preview]" ? preview : null,
        closest: () => ({getBoundingClientRect: () => ({bottom: 300})}),
        append: () => {},
    };
    const document = {
        addEventListener: (name, callback) => handlers.set(name, callback),
        querySelectorAll: () => [wrapper],
        createTextNode: (value) => ({textContent: value}),
    };
    const window = {
        addEventListener: (name, callback) => handlers.set(name, callback),
        matchMedia: () => ({matches: true}),
        WorkspaceReveal: {
            afterLayout: (callback) => callback(),
            revealRange: (first, last) => reveals.push([first, last]),
        },
    };
    vm.runInNewContext(source, {
        document, window, requestAnimationFrame: (callback) => callback(),
        getComputedStyle: (node) => node === content ? {lineHeight: "20px"} : {paddingBottom: "20px"},
    });
    return {handlers, window, wrapper, content, preview, contentClasses, toggle, styles, reveals, setOverflow: (value) => { overflow = value; }};
}

test("three-line descriptions expose and toggle disclosure only when overflowing", () => {
    const view = fixture();
    view.window.ExpandableText.refresh();
    assert.equal(view.toggle.hidden, false);
    view.handlers.get("click")({target: {closest: () => view.toggle}});
    assert.equal(view.toggle.getAttribute("aria-expanded"), "true");
    assert.equal(view.toggle.textContent, "See less");
    assert.equal(view.contentClasses.has("is-expanded"), true);
    view.setOverflow(false);
    view.handlers.get("resize")();
    assert.equal(view.toggle.hidden, true);
    assert.equal(view.toggle.getAttribute("aria-expanded"), "false");
});

test("See more still reveals content when its section has no heading", () => {
    const view = fixture();
    view.window.ExpandableText.refresh();
    view.handlers.get("click")({target: {closest: () => view.toggle}});
    assert.equal(view.reveals.length, 1);
    assert.equal(view.reveals[0][1], view.wrapper);
});

test("single-line addresses detect horizontal overflow", () => {
    const view = fixture({singleLine: true});
    view.window.ExpandableText.refresh();
    assert.equal(view.toggle.hidden, false);
    view.setOverflow(false);
    view.window.ExpandableText.refresh();
    assert.equal(view.toggle.hidden, true);
});

test("shared preview clamps descriptions to three lines and addresses to one", () => {
    assert.match(styles, /\.expandable-text-content:not\(\.is-expanded\)[\s\S]*?-webkit-line-clamp:\s*3/);
    assert.match(styles, /\.expandable-text--single-line \.expandable-text-content:not\(\.is-expanded\)[\s\S]*?white-space:\s*nowrap/);
});

test("side-by-side description uses available card height for extra preview lines", () => {
    const view = fixture({fitCard: true});
    view.window.ExpandableText.refresh();
    assert.equal(view.styles.get("--expandable-lines"), "7");
    view.window.matchMedia = () => ({matches: false});
    view.window.ExpandableText.refresh();
    assert.equal(view.styles.has("--expandable-lines"), false);
});

test("Task inline description alone opts into an inline, accessible disclosure", () => {
    assert.match(sharedTemplate, /\{% if inline_end_toggle %\} expandable-text--inline-end\{% endif %\}/);
    assert.match(taskInlineTemplate, /inline_end_toggle=True/);
    assert.match(sharedTemplate, /aria-controls="\{\{ text_id \}\}/);
    assert.match(sharedTemplate, /aria-expanded="false" hidden data-expandable-toggle/);
    assert.match(styles, /\.expandable-text--inline-end \.expandable-text-toggle:not\(\[hidden\]\)\s*\{[^}]*background: var\(--bs-tertiary-bg\);/s);
    const view = fixture();
    view.window.ExpandableText.refresh();
    view.handlers.get("click")({target: {closest: () => view.toggle}});
    assert.equal(view.toggle.getAttribute("aria-expanded"), "true");
    assert.equal(view.toggle.textContent, "See less");
});

test("desktop Task description reserves the last preview line for an inline See more", () => {
    assert.match(taskTemplate, /text_id="task-detail-description" fit_card=True inline_end_toggle=True/);
    assert.match(sharedTemplate, /data-expandable-preview/);
    assert.match(styles, /\.expandable-text--inline-end \.expandable-text-preview\s*\{[^}]*overflow-wrap: anywhere;/s);
    const view = fixture({inlineEnd: true});
    view.window.ExpandableText.refresh();
    assert.equal(view.content.hidden, true);
    assert.equal(view.preview.hidden, false);
    assert.equal(view.toggle.hidden, false);
    assert.ok(view.preview.text.endsWith("… "));
    assert.ok(view.preview.getBoundingClientRect().height <= 60);
    view.handlers.get("click")({target: {closest: () => view.toggle}});
    assert.equal(view.content.hidden, false);
    assert.equal(view.preview.hidden, true);
    assert.equal(view.toggle.textContent, "See less");
});

test("Task See more controls use the Dashboard disclosure style at all widths", () => {
    assert.match(styles, /\.task-detail-scroll \.expandable-text--inline-end \.expandable-text-toggle:not\(\[hidden\]\),\s*\.task-inline-description \.expandable-text--inline-end \.expandable-text-toggle:not\(\[hidden\]\),[^{]*\{[^}]*background: var\(--bs-body-bg\);[^}]*color: var\(--bs-link-color\);[^}]*font-size: \.85rem;[^}]*font-weight: 600;/s);
});

test("Task inline preview uses separate cards and compact two-column facts", () => {
    assert.match(taskInlineTemplate, /class="task-inline-section task-inline-description"/);
    assert.match(taskInlineTemplate, /<h3 class="task-inline-section-title">Details<\/h3>/);
    assert.match(taskInlineTemplate, /<dl class="task-inline-facts">/);
    assert.match(taskInlineTemplate, /class="task-inline-fact"><dt>Status<\/dt>/);
    assert.match(taskInlineTemplate, /class="task-inline-fact"><dt>Priority<\/dt>/);
    assert.match(taskInlineTemplate, /class="task-inline-fact"><dt>Created<\/dt>/);
    assert.match(taskInlineTemplate, /class="task-inline-fact"><dt>Scheduled<\/dt>/);
    assert.match(taskInlineTemplate, /class="task-inline-fact"><dt>Deadline<\/dt>/);
    assert.match(taskInlineTemplate, /\{% if task.issue or task.property %\}[\s\S]*class="task-inline-fact task-inline-relationship"/);
    assert.match(styles, /:is\(\.task-inline-relationship, \.issue-inline-relationship, \.event-inline-relationship\) :is\(\.task-related-link, \.task-related-deleted\)\s*\{[^}]*max-width: min\(100%, 16rem\)/s);
    assert.match(styles, /@media \(min-width: 600px\) and \(max-width: 860px\)[\s\S]*?:is\(\.task-inline-facts, \.issue-inline-facts, \.event-inline-facts\)\s*\{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/s);
    assert.match(styles, /:is\(\.task-inline-actions, \.issue-inline-actions, \.event-mobile-inline-actions\) \.work-mobile-open \{[^}]*white-space: nowrap;/s);
});

test("Property summaries grow for wrapped badges and header address shares one line with its control", () => {
    assert.match(propertyStyles, /\.property-related-summary\s*\{[^}]*height:\s*auto;[^}]*min-height:\s*4\.5rem/s);
    assert.match(propertyStyles, /\.property-heading-address\s*\{[^}]*display:\s*flex;/s);
    assert.match(propertyStyles, /\.property-heading-address \.expandable-text-toggle\s*\{[^}]*flex:\s*0 0 auto;/s);
});

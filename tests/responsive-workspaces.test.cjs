const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const read = (file) => readFileSync(path.join(__dirname, "..", file), "utf8");
const readAll = (...files) => files.map(read).join("\n");
const readCss = (file) => read(file).replace(/\s+/g, " ");
const dashboardCss = readCss("static/css/dashboard.css");
const dashboardJs = read("static/js/dashboard.js") + read("static/js/dashboard-dialogs.js");
const siteCss = [
    "static/css/foundation.css",
    "static/css/components.css",
    "static/css/issue-page.css",
    "static/css/task-page.css",
    "static/css/contact-page.css",
    "static/css/workspace.css",
].map(readCss).join(" ");
const eventComponentsCss = readCss("static/css/event-components.css");
const eventCss = readCss("static/css/event-page.css");
const eventJs = read("static/js/event-command-centre.js");
const taskPage = readAll(
    "task/templates/task/tasks.html",
    "task/templates/task/includes/task_list_panel.html",
    "task/templates/task/includes/task_detail_panel.html",
    "task/templates/task/includes/task_modals.html",
);
const issuePage = readAll(
    "issue/templates/issue/issues.html",
    "issue/templates/issue/includes/issue_list_panel.html",
    "issue/templates/issue/includes/issue_detail_panel.html",
    "issue/templates/issue/includes/issue_modals.html",
);
const eventPage = readAll(
    "event/templates/event/events.html",
    "event/templates/event/includes/event_list_panel.html",
    "event/templates/event/includes/event_right_panel.html",
    "event/templates/event/includes/event_calendar_panel.html",
    "event/templates/event/includes/event_detail_panel.html",
    "event/templates/event/includes/event_modals.html",
);

test("Event CSS keeps reusable forms separate from the My Work page", () => {
    const dashboard = read("pages/templates/pages/dashboard.html");
    const property = read("property/templates/property/workspace.html");
    const events = read("event/templates/event/events.html");
    assert.match(eventComponentsCss, /\.event-duration \{/);
    assert.match(eventComponentsCss, /\.event-contact-picker-heading \{/);
    assert.doesNotMatch(eventComponentsCss, /\.event-command-centre \{/);
    assert.match(eventCss, /\.event-command-centre \{/);
    assert.doesNotMatch(eventCss, /\.event-contact-picker-heading \{/);
    assert.match(dashboard, /css\/event-components\.css/);
    assert.match(property, /css\/event-components\.css/);
    assert.doesNotMatch(dashboard + property, /css\/event-page\.css/);
    assert.match(events, /css\/event-components\.css[\s\S]*css\/event-page\.css/);
});

test("Dashboard has distinct intermediate and compact panel boundaries", () => {
    assert.match(dashboardCss, /min-width: 861px\) and \(max-width: 1100px/);
    assert.match(dashboardCss, /@media \(max-width: 860px\)/);
    assert.match(dashboardCss, /\[data-active-panel="day"\] > \.dashboard-right-panel/);
    assert.match(dashboardCss, /@media \(max-width: 1100px\) \{\s*\.dashboard-view-switch \{ display: none; \}/);
    assert.match(dashboardJs, /if \(window\.matchMedia\("\(max-width: 1100px\)"\)\.matches\) \{\s*activatePanel\("day"\)/);
    assert.match(dashboardJs, /dashboard\.querySelector\("\.dashboard-board"\)\.dataset\.activePanel = activePanel/);
});

test("Dashboard caps only its single-panel board and tabs from 768 through 860px", () => {
    assert.match(dashboardCss, /\.dashboard-shell \{ position: relative; max-width: 1600px; min-height: 0; margin: auto; \}/);
    assert.match(dashboardCss, /@media \(min-width: 768px\) and \(max-width: 860px\) \{\s*\.dashboard-shell \{ max-width: 720px; \}\s*\}/);
    assert.match(dashboardCss, /@media \(max-width: 860px\) \{\s*\.dashboard-main \{ padding-inline: 10px; \}/);
    assert.doesNotMatch(dashboardCss, /@media \(max-width: 767px\)[\s\S]*?\.dashboard-shell \{ max-width: 720px/);
});

test("Task relationship labels say Not linked while retaining standalone values", () => {
    const fields = read("task/templates/task/includes/task_form_fields.html");
    const mobileDetails = read("task/templates/task/includes/mobile_task_details.html");
    assert.match(fields, /value="standalone"[^>]*>Not linked<\/option>/);
    assert.match(fields, /relationship_standalone">Not linked<\/label>/);
    assert.match(dashboardJs, /\[\s*\["standalone", "Not linked"\]/);
    assert.doesNotMatch(fields + taskPage + mobileDetails + dashboardJs, />Standalone<|"Standalone"|No linked record|No linked property or issue/);
    assert.doesNotMatch(taskPage + mobileDetails, />Not linked</);
});

test("My Work single-panel width cap and issue row sizing preserve responsive boundaries", () => {
    assert.match(siteCss, /@media \(min-width: 768px\) and \(max-width: 860px\) \{\s*:is\(\.task-command-centre, \.issue-command-centre, \.event-command-centre\) \{ max-width: 720px; margin-inline: auto; \}/);
    assert.match(siteCss, /@media \(min-width: 700px\) and \(max-width: 860px\) \{\s*\.task-command-centre \{ max-width: 680px; margin-inline: auto; \}/);
    assert.match(siteCss, /\.task-list-column \{ border-right: 0 !important; \}/);
    assert.match(siteCss, /\.task-command-row \.task-command-badges \{ justify-content: flex-start; \}/);
    assert.match(siteCss, /\.work-pill \{[^}]*justify-content: center;[^}]*inline-size: 6rem;[^}]*min-height: 1\.7rem;/s);
    assert.match(siteCss, /\.issue-list-row \{ min-height: 5\.65rem; padding: 1rem 1\.25rem; \}/);
    assert.match(siteCss, /\.issue-command-row-grid \{ display: grid;/);
});

test("relationship details keep a single-line box without deleted badges or unlinked placeholders", () => {
    const paths = [
        "task/templates/task/includes/task_detail_panel.html", "task/templates/task/includes/mobile_task_details.html",
        "issue/templates/issue/includes/issue_detail_panel.html", "issue/templates/issue/includes/mobile_issue_details.html",
        "event/templates/event/includes/event_detail_panel.html", "event/templates/event/includes/mobile_event_details.html",
    ];
    const templates = [...paths, "templates/includes/related_record_link.html"].map(read).join("\n");
    assert.match(siteCss, /\.task-related-copy \{[^}]*text-overflow: ellipsis;[^}]*white-space: nowrap/s);
    assert.match(siteCss, /\.task-related-deleted \{[^}]*border: 1px solid/s);
    assert.doesNotMatch(templates, /Deleted property|Deleted issue|>Not linked</);
    assert.match(templates, /task-related-deleted/);
});

test("shared modal cleanup removes record boxes and footer dividers", () => {
    for (const path of [
        "task/templates/task/tasks.html", "issue/templates/issue/issues.html",
        "event/templates/event/events.html", "property/templates/property/includes/workspace_modals.html",
        "contact/templates/contact/contacts.html", "pages/templates/pages/dashboard.html",
    ]) assert.doesNotMatch(read(path), /modal-context|dashboard-confirm-context/);
    assert.match(siteCss, /\.modal \.modal-footer \{ border-top: 0; \}/);
    assert.match(siteCss, /\.modal \[data-task-relationship\] \{ display: grid; grid-template-columns: 140px minmax\(0, 1fr\)/);
    assert.match(siteCss, /\.modal \[data-task-relationship\] > \.task-relationship-label \{ grid-column: 1;/);
    assert.match(siteCss, /\.modal \[data-task-relationship\] > \.task-relationship-options \{ grid-column: 2; min-width: 0; \}/);
    assert.match(read("task/templates/task/includes/task_form_fields.html"), /<span class="task-relationship-label"\s+id="[^"]+">Related to<\/span>\s*<div class="task-relationship-options">\s*<div class="d-flex flex-wrap gap-2"\s+role="radiogroup"\s+aria-labelledby="[^"]+">/);
});

test("navbar toggler and links use the same soft-white color", () => {
    assert.match(siteCss, /\.app-navbar \{[^}]*flex-shrink: 0;/s);
    assert.match(siteCss, /\.app-navbar \.navbar-collapse \{[^}]*max-height: calc\(100dvh - 4\.9rem\);[^}]*overflow-y: auto;/s);
    assert.match(siteCss, /\.app-navbar \.nav-link \{\s*color: #f5f7fa;/);
    assert.match(siteCss, /\.app-navbar \.navbar-toggler\[aria-expanded="true"\] \{[^}]*border: 1px solid #f5f7fa;[^}]*opacity: 1;/s);
    assert.match(siteCss, /\.app-navbar \.navbar-toggler-icon \{[^}]*background-image: url\([^;]*%23f5f7fa/s);
});

test("My Work uses the same 860px inline boundary across layout and input", () => {
    assert.match(siteCss, /@media \(max-width: 860px\), \(max-width: 1199\.98px\) and \(max-height: 700px\)/);
    for (const file of ["task", "issue"]) {
        assert.match(read(`static/js/${file}-command-centre.js`), /matchMedia\("\(max-width: 860px\)"\)/);
    }
    assert.match(eventCss, /@media \(max-width: 860px\)/);
    assert.match(eventCss, /#eventCalendarPanel,\s*\.event-mobile-agenda \{ display: none !important/);
    assert.match(eventJs, /matchMedia\("\(max-width: 860px\)"\)/);
});

test("compact tabs and linked-task rows retain readable layouts", () => {
    const events = eventPage;
    assert.match(siteCss, /\.my-work-section-nav \.nav \{ display: grid; grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
    assert.match(siteCss, /@container issue-tasks \(max-width: 32rem\)/);
    assert.match(siteCss, /\.issue-linked-task-grid \{ display: grid; grid-template-columns:/);
    assert.match(siteCss, /\.issue-linked-tasks-card \{\s*container: linked-task-card \/ inline-size;\s*border: 1px solid/);
    assert.match(issuePage, /issue-task-scroll">\s*<div class="issue-linked-tasks-card">/);
    assert.match(eventCss, /\.event-mobile-participant-row \.event-participant-remove \{\s*width: 2\.75rem;\s*height: 2\.75rem/);
    assert.match(eventCss, /@media \(max-width: 575\.98px\) \{\s*\.event-participant-methods \{\s*grid-template-columns: minmax\(0, 1fr\)/);
    assert.doesNotMatch(eventCss, /\.event-participant-methods > :empty/);
    assert.match(eventCss, /\.event-calendar-day\.today \.event-calendar-day-number::after \{[\s\S]*?background: var\(--pom-accent\);/);
    assert.match(eventCss, /\.event-calendar-day\.agenda-selected \{\s*background: var\(--pom-selected\);\s*box-shadow: inset 0 0 0 2px var\(--bs-emphasis-color\);/);
    assert.match(eventCss, /\.event-calendar-count-label \{ display: none; \}/);
    assert.match(eventCss, /\.event-mobile-agenda-entry\.is-selected::before \{[\s\S]*?background: var\(--pom-accent\);/);
    assert.match(events, /class="event-mobile-agenda-title event-command-title"/);
    assert.match(events, /class="event-mobile-agenda-context event-command-context"/);
    assert.match(eventCss, /\.event-participants-card \{\s*width: 100%;\s*\}/);
    assert.match(eventCss, /@media \(min-width: 861px\) and \(max-width: 1199\.98px\) \{[\s\S]*?\.event-participants-card \{ max-width: 37rem; margin-inline: auto; \}/);
    assert.match(eventCss, /\.event-mobile-inline-actions \{ margin-top: 0; container: event-actions \/ inline-size; \}/);
    assert.match(eventCss, /@container event-actions \(max-width: 24rem\) \{\s*\.event-mobile-inline-actions \.work-mobile-open \{ display: none; \}\s*\.event-mobile-inline-actions \.work-mobile-open-menu-item \{ display: list-item; \}/);
});

test("Issue Tasks uses its tab row for Add task and starts the pane with task rows", () => {
    assert.match(issuePage, /class="issue-detail-tabs[^\"]*">[\s\S]*?data-bs-target="#issueTasksPanel"[\s\S]*?class="btn btn-sm theme-action issue-add-task-button app-add-control"/);
    assert.match(issuePage, /class="issue-linked-tasks-card">\s*<div class="issue-task-list">/);
    assert.doesNotMatch(issuePage, /issue-task-toolbar|Work linked to this issue/);
    assert.match(siteCss, /\.issue-detail-tabs:has\(\[data-bs-target="#issueTasksPanel"\]\.active\) \.issue-add-task-button \{ display: inline-flex; \}/);
    assert.match(siteCss, /\.issue-task-title \{[^}]*font-weight: 600;/);
    assert.match(siteCss, /\.task-command-title \{[^}]*font-weight: 600;/);
});

test("narrow task actions keep the primary controls and move secondary actions into a kebab", () => {
    const mobileTask = read("task/templates/task/includes/mobile_task_details.html");
    assert.match(siteCss, /:is\(\.task-inline-more, \.issue-inline-more, \.event-inline-more\) \{ display: none; \}/);
    assert.match(siteCss, /:is\(\s*\.task-inline-actions > \.task-inline-secondary-action, \.issue-inline-actions > \.issue-inline-secondary-action, \.event-mobile-inline-actions > \.event-inline-secondary-action\s*\) \{ display: none; \}/);
    assert.match(siteCss, /:is\(\s*\.task-inline-actions > \.task-inline-more, \.issue-inline-actions > \.issue-inline-more, \.event-mobile-inline-actions > \.event-inline-more\s*\) \{ display: block; \}/);
    assert.match(mobileTask, /class="dropdown task-inline-more"/);
    assert.match(mobileTask, /aria-label="More task actions"/);
    assert.match(mobileTask, /data-bs-target="#dismissTaskModal">Dismiss task/);
    assert.match(mobileTask, /data-bs-target="#deleteTaskModal">Delete task/);
    assert.match(mobileTask, /class="btn btn-sm btn-outline-secondary work-mobile-open"/);
});

test("issue-linked task actions compact when their pane narrows", () => {
    assert.match(siteCss, /\.issue-linked-tasks-card \{\s*container: linked-task-card \/ inline-size;/);
    assert.match(siteCss, /@container linked-task-card \(max-width: 38rem\) \{\s*\.issue-task-details-actions > \.issue-task-secondary-action \{ display: none; \}\s*\.issue-task-details-actions > \.issue-task-more \{ display: block; \}/);
    assert.match(siteCss, /\.issue-task-more \.task-menu-button \{ min-width: 2rem; min-height: 2rem; width: 2rem; height: 2rem;/);
    assert.match(issuePage, /class="dropdown issue-task-more"/);
    assert.match(issuePage, /class="dropdown-item" type="submit">Dismiss task/);
    assert.match(issuePage, /class="dropdown-item text-danger" type="submit">Delete task/);
    assert.match(issuePage, /issue-task-open-record"[^>]*>Open record →<\/a>/);
});

test("mobile issue actions use the same compact menu as mobile tasks", () => {
    const mobileIssue = read("issue/templates/issue/includes/mobile_issue_details.html");
    assert.match(mobileIssue, /class="dropdown issue-inline-more"/);
    assert.match(mobileIssue, /aria-label="More issue actions"/);
    assert.match(mobileIssue, /data-bs-target="#dismissIssueModal">Dismiss issue/);
    assert.match(mobileIssue, /data-bs-target="#deleteIssueModal">Delete issue/);
    assert.match(mobileIssue, /class="btn btn-sm btn-outline-secondary work-mobile-open"/);
});

test("mobile Open record stays right until its action row is too narrow", () => {
    const taskMobile = read("task/templates/task/includes/mobile_task_details.html");
    const issueMobile = read("issue/templates/issue/includes/mobile_issue_details.html");
    assert.match(siteCss, /\.work-mobile-expanded:not\(\[hidden\]\) \{\s*display: block;\s*container: mobile-work \/ inline-size;/);
    assert.match(siteCss, /\.work-mobile-open \{\s*display: inline-flex;\s*align-items: center;\s*margin-left: auto;/);
    assert.match(siteCss, /@container mobile-work \(max-width: 19rem\) \{\s*:is\(\.task-inline-actions, \.issue-inline-actions, \.event-mobile-inline-actions\) \.work-mobile-open \{ display: none; \}\s*\.work-mobile-open-menu-item \{ display: list-item; \}/);
    for (const template of [taskMobile, issueMobile]) {
        assert.match(template, /class="work-mobile-open-menu-item">\s*<a class="dropdown-item"[^>]*>Open record<\/a>\s*<\/li>/);
    }
});

test("Events share work cards and disclosure while retaining a mobile calendar", () => {
    const events = eventPage;
    const inline = read("event/templates/event/includes/mobile_event_details.html");
    const scrollJs = read("static/js/workspace-list-scroll.js");
    assert.match(events, /class="event-command-row-grid"/);
    assert.match(events, /class="event-detail-description-column"/);
    assert.match(events, /class="event-detail-facts-column"/);
    assert.match(inline, /class="work-mobile-expanded event-mobile-expanded"/);
    assert.match(inline, /class="event-inline-section event-inline-description"/);
    assert.match(inline, /class="event-inline-section event-inline-participants"/);
    assert.match(inline, /class="dropdown event-inline-more"/);
    assert.match(events, /data-event-mobile-view="calendar"/);
    assert.match(eventCss, /\.event-workspace\.show-mobile-calendar #eventCalendarPanel \{ display: block !important;/);
    assert.match(eventJs, /window\.WorkspaceReveal\?\.queueRange\(\s*row, expanded/);
    assert.match(eventCss, /\.event-command-list \{\s*overflow-x: clip;\s*overflow-y: visible;/);
    assert.match(events, /data-calendar-agenda-href="\?\{\{ day_query_base \}\}&amp;agenda_day=/);
    assert.doesNotMatch(events, /event-mobile-agenda-arrow/);
    assert.match(scrollJs, /events: workPageScroll/);
});

test("Event Add and Apply controls share the same compact button footprint", () => {
    const events = eventPage;
    assert.match(events, /class="btn btn-sm theme-action work-add-button app-add-control"/);
    assert.match(events, /icon="plus" only %} Add event<\/button>/);
    assert.match(events, /class="event-control-row">[\s\S]*?class="btn btn-sm theme-action" type="submit">Apply<\/button>/);
    assert.match(siteCss, /\.event-list-controls :is\(\.work-add-button, \.event-control-row \.theme-action\) \{\s*width: 6\.5rem;\s*height: 2rem;/);
});

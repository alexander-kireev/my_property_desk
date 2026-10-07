// Keep Dashboard data, filters and selected views together. The helper modules handle forms, Notes and messages.
document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("dashboard");
    if (!dashboard) return;

    const get = (id) => document.getElementById(id);
    const { escapeHtml, parseDate, isoDate, prettyDate, longDate } = window.DashboardRecords;
    function visibleRecords() {
        return window.DashboardRecords.visibleRecords(data.records, {
            kind,
            filter,
            secondaryFilter,
            search: get("workSearch").value,
            today: data.today,
        });
    }
    function recordRow(item, area) {
        return window.DashboardRecords.recordRow(item, area, {
            expanded,
            today: data.today,
            urls: dashboard.dataset,
        });
    }

    const cookie = document.cookie.split("; ").find((part) => part.startsWith("csrftoken="));
    const csrfToken = cookie ? decodeURIComponent(cookie.slice(10)) : "";
    const filters = {
        task: [
            ["all", "All active"],
            ["unscheduled", "Unscheduled"],
            ["today", "Today"],
            ["other", "Other scheduled"],
        ],
        issue: [
            ["all", "All open"],
            ["overdue", "Overdue"],
            ["week", "Resolve by this week"],
            ["undated", "No resolve-by date"],
        ],
        event: [
            ["all", "All scheduled"],
            ["week", "This week"],
            ["month", "This month"],
        ],
    };
    const priorities = [
        ["any", "Any priority"],
        ["priority-urgent", "Urgent"],
        ["priority-high", "High"],
        ["priority-medium", "Medium"],
        ["priority-low", "Low"],
    ];
    // Page data and the user's current view
    let data = {
        records: { task: [], issue: [], event: [] },
        notes: [],
        properties: [],
        issues: [],
        today: "",
    };
    let kind = "task";
    let filter = "unscheduled";
    let secondaryFilter = "any";
    let selected = "";
    let dayTab = "tasks";
    let rightView = "day";
    let activePanel = "operations";
    let dayScroll = 0;
    let notesScroll = 0;
    let month = null;
    let shown = 40;
    let expanded = null;
    let returning =
        window.performance?.getEntriesByType?.("navigation")?.[0]?.type === "back_forward"
            ? window.history.state?.pomDashboardReturn
            : null;
    if (
        returning?.url === `${window.location.pathname}${window.location.search}` &&
        ["task", "issue", "event"].includes(returning.kind)
    ) {
        kind = returning.kind;
        filter = returning.filter;
        // Old "high" meant High or Urgent; reset it rather than silently changing its meaning.
        secondaryFilter = priorities.some(([value]) => value === returning.secondaryFilter)
            ? returning.secondaryFilter
            : "any";
        shown = returning.shown;
        expanded = returning.expanded;
    }

    let dragged = null;

    const quickPending = new Set();
    // Connect helpers to the same page data and refresh function.
    const api = window.DashboardApi.create({
        actionUrl: dashboard.dataset.actionUrl,
        dataUrl: dashboard.dataset.dataUrl,
        csrfToken,
    });
    const send = api.send;
    const { message, showUndo } = window.DashboardFeedback.create({ get, send, load });
    const notes = window.DashboardNotes.create({
        get,
        getNotes: () => data.notes,
        send,
        load,
        message,
        showUndo,
        escapeHtml,
    });
    const renderNotes = notes.render;

    const { openWork, openAddEvent, openConfirm } = window.DashboardDialogs.create({
        get,
        getData: () => data,
        getSelectedDate: () => selected,
        findRecord,
        send,
        load,
        message,
        onSaved,
        escapeHtml,
    });

    // Show the saved record in its list. Let the caller report a failed refresh separately from a failed save.
    async function onSaved(type, operation, result) {
        kind = type;
        filter = "all";
        secondaryFilter = "any";
        const added = operation === "added";
        if (added) {
            get("workSearch").value = "";
            shown = 40;
            expanded = null;
        }
        await load({ keepScroll: !added });
        if (!added) return;
        const index = visibleRecords().findIndex((item) => item.id === result.id);
        if (index < 0) return;
        shown = Math.max(shown, index + 1);
        expanded = `queue-${kind}-${result.id}`;
        renderQueue();
        revealExpandedRow(
            get("workList").querySelector(`[data-area="queue"][data-id="${result.id}"]`),
        );
    }

    function findRecord(type, id) {
        return data.records[type].find((item) => item.id === Number(id));
    }

    // Reload records while keeping list positions and restoring a browser Back visit.

    let latestRefresh = null;

    function load(options = {}) {
        const refresh = { promise: null };
        latestRefresh = refresh;
        refresh.promise = refreshData(refresh, options);
        return refresh.promise;
    }

    async function refreshData(refresh, { keepScroll = true } = {}) {
        const queueScroll = keepScroll ? get("workList").scrollTop : 0;
        const dayScroll = keepScroll ? get("dayList").scrollTop : 0;
        let freshData;
        try {
            freshData = await api.load();
        } catch (error) {
            if (refresh !== latestRefresh) return latestRefresh.promise;
            throw error;
        }
        // Older callers await the replacement refresh, including its failure, without rendering stale data.
        if (refresh !== latestRefresh) return latestRefresh.promise;
        data = freshData;
        // The API's date is a server fallback; the visible dashboard uses the
        // same local day as its greeting, including responses crossing midnight.
        data.today = window.DashboardClock?.today() || data.today;
        if (!selected) selected = data.today;
        if (!month) month = parseDate(`${selected.slice(0, 7)}-01`);
        render();
        if (returning?.url === `${window.location.pathname}${window.location.search}`) {
            get("workSearch").value = returning.search || "";
            renderQueue();
        }
        get("workList").scrollTop =
            returning?.url === `${window.location.pathname}${window.location.search}`
                ? returning.scrollTop || 0
                : queueScroll;
        get("dayList").scrollTop = dayScroll;
        if (returning?.expanded) {
            const row = get("workList").querySelector(
                `[data-area="queue"][data-kind="${kind}"][data-id="${returning.expanded.split("-").at(-1)}"]`,
            );
            row?.querySelector(".dashboard-row-toggle")?.focus({ preventScroll: true });
        }
        // Restore the Back visit once; later refreshes must keep the user's new search and selection.
        returning = null;
    }

    // Operations list: filters, rows and loading more records

    function syncDescriptionControls(list) {
        window.ExpandableText?.refresh(list);
    }

    function renderQueue() {
        const items = visibleRecords();
        for (const type of ["task", "issue", "event"]) {
            const count = type === kind ? items.length : data.records[type].length;
            get("dashboard").querySelector(`[data-count="${type}"]`).textContent = count;
        }
        document.querySelectorAll("[data-kind][role=tab]").forEach((button) => {
            const selected = button.dataset.kind === kind;
            button.setAttribute("aria-selected", String(selected));
            button.tabIndex = selected ? 0 : -1;
            button.classList.toggle("active", selected);
            if (selected) get("workList").setAttribute("aria-labelledby", button.id);
        });
        get("workSearch").placeholder = `Search ${kind}s`;
        get("workFilterLabel").textContent = {
            task: "Filter tasks by schedule",
            issue: "Filter issues by deadline",
            event: "Filter events by date",
        }[kind];
        const options = get("workFilter");
        options.innerHTML = filters[kind]
            .map(([value, label]) => `<option value="${value}">${label}</option>`)
            .join("");
        options.value = filter;
        window.SearchableSelect?.refresh(options);
        const secondary = get("workSecondaryFilter");
        get("workSecondaryWrap").hidden = kind === "event";
        secondary.innerHTML = priorities
            .map(([value, label]) => `<option value="${value}">${label}</option>`)
            .join("");
        secondary.value = secondaryFilter;
        window.SearchableSelect?.refresh(secondary);
        get("dashboard")
            .querySelector(".dashboard-filter-controls")
            .classList.toggle("is-single", kind === "event");
        get("workList").innerHTML = items.length
            ? items
                  .slice(0, shown)
                  .map((item) => recordRow(item, "queue"))
                  .join("")
            : '<p class="dashboard-empty">No records match this search and filter.</p>';
        syncDescriptionControls(get("workList"));
    }
    function appendMore() {
        const list = get("workList");
        if (list.scrollTop + list.clientHeight < list.scrollHeight - 100) return;
        const items = visibleRecords();
        if (shown >= items.length) return;
        const previous = shown;
        shown += 40;
        list.insertAdjacentHTML(
            "beforeend",
            items
                .slice(previous, shown)
                .map((item) => recordRow(item, "queue"))
                .join(""),
        );
    }
    // Calendar and selected-day views
    function calendarStart() {
        const start = new Date(month);
        start.setUTCDate(1 - ((start.getUTCDay() + 6) % 7));
        return start;
    }
    function countByDate(items, field) {
        const counts = new Map();
        for (const item of items) {
            if (item[field]) counts.set(item[field], (counts.get(item[field]) || 0) + 1);
        }
        return counts;
    }
    function renderCalendar() {
        const year = month.getUTCFullYear();
        const monthNumber = month.getUTCMonth();
        const monthSelect = get("calendarMonth");
        const yearSelect = get("calendarYear");
        if (!monthSelect.options.length)
            monthSelect.innerHTML = Array.from(
                { length: 12 },
                (_, index) =>
                    `<option value="${index}">${new Date(Date.UTC(2026, index, 1)).toLocaleDateString("en-GB", { month: "long", timeZone: "UTC" })}</option>`,
            ).join("");
        yearSelect.innerHTML = Array.from(
            { length: 21 },
            (_, index) => `<option value="${year - 10 + index}">${year - 10 + index}</option>`,
        ).join("");
        monthSelect.value = String(monthNumber);
        yearSelect.value = String(year);
        window.SearchableSelect?.refresh(monthSelect);
        window.SearchableSelect?.refresh(yearSelect);
        const start = calendarStart();
        const lastDay = new Date(Date.UTC(year, monthNumber + 1, 0));
        const weeks = Math.ceil((lastDay.getUTCDate() + ((month.getUTCDay() + 6) % 7)) / 7);
        const show = (kind) =>
            get("dashboard").querySelector(`[data-calendar-filter="${kind}"]`).checked;
        const scheduledTasks = countByDate(show("tasks") ? data.records.task : [], "date");
        const scheduledEvents = countByDate(show("events") ? data.records.event : [], "date");
        const showDeadlines = show("deadlines");
        const taskDeadlines = countByDate(showDeadlines ? data.records.task : [], "due");
        const issueDeadlines = countByDate(showDeadlines ? data.records.issue : [], "due");
        const grid = get("calendarGrid");
        const calendarIcons = {
            tasks: escapeHtml(grid.dataset.taskIcon),
            events: escapeHtml(grid.dataset.eventIcon),
            deadlines: escapeHtml(grid.dataset.deadlineIcon),
        };
        const cells = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
            (day) => `<span class="dashboard-weekday">${day}</span>`,
        );
        for (let index = 0; index < weeks * 7; index++) {
            const date = new Date(start);
            date.setUTCDate(start.getUTCDate() + index);
            const value = isoDate(date);
            const tasks = scheduledTasks.get(value) || 0;
            const events = scheduledEvents.get(value) || 0;
            const due = (taskDeadlines.get(value) || 0) + (issueDeadlines.get(value) || 0);
            const dateLabel = longDate(value);
            const otherClass = date.getUTCMonth() !== monthNumber ? "other" : "";
            const selectedClass = value === selected ? "selected" : "";
            const isToday = value === data.today;
            const todayClass = isToday ? "today" : "";
            const todayAttribute = isToday ? 'aria-current="date"' : "";
            const taskNoun = tasks === 1 ? "task" : "tasks";
            const eventNoun = events === 1 ? "event" : "events";
            const deadlineNoun = due === 1 ? "deadline" : "deadlines";
            let taskButton = "";
            let eventButton = "";
            let dueButton = "";
            if (tasks) {
                taskButton = `<button type="button" class="dashboard-day-category"
                    data-category="tasks" aria-label="${tasks} scheduled ${taskNoun} on ${dateLabel}; show Tasks"><img src="${calendarIcons.tasks}" alt="" aria-hidden="true"><span aria-hidden="true">${tasks}</span></button>`;
            }
            if (events) {
                eventButton = `<button type="button" class="dashboard-day-category"
                    data-category="events" aria-label="${events} ${eventNoun} on ${dateLabel}; show Events"><img src="${calendarIcons.events}" alt="" aria-hidden="true"><span aria-hidden="true">${events}</span></button>`;
            }
            if (due) {
                dueButton = `<button type="button" class="dashboard-day-category"
                    data-category="deadlines" aria-label="${due} ${deadlineNoun} on ${dateLabel}; show Deadlines"><img src="${calendarIcons.deadlines}" alt="" aria-hidden="true"><span aria-hidden="true">${due}</span></button>`;
            }
            const categories = `<div class="dashboard-calendar-metrics">
                ${taskButton || '<span class="dashboard-calendar-slot" aria-hidden="true"></span>'}
                ${eventButton || '<span class="dashboard-calendar-slot" aria-hidden="true"></span>'}
                ${dueButton || '<span class="dashboard-calendar-slot" aria-hidden="true"></span>'}
            </div>`;
            cells.push(`<div class="dashboard-day ${otherClass} ${selectedClass} ${todayClass}" data-day="${value}">
                <button type="button" class="dashboard-date-button" aria-label="Select ${dateLabel}" ${todayAttribute}>
                    <strong>${date.getUTCDate()}</strong>
                </button>
                ${categories}
            </div>`);
        }
        grid.innerHTML = cells.join("");
    }
    function renderDay() {
        get("selectedDayHeading").textContent = longDate(selected);
        const tasks = data.records.task.filter((item) => item.date === selected);
        const events = data.records.event.filter((item) => item.date === selected);
        const dueTasks = data.records.task.filter((item) => item.due === selected);
        const dueIssues = data.records.issue.filter((item) => item.due === selected);
        const due = [...dueTasks, ...dueIssues];
        const groups = { tasks, deadlines: due, events };
        for (const tab of get("dashboard").querySelectorAll("[data-day-tab]")) {
            const selectedTab = tab.dataset.dayTab === dayTab;
            tab.setAttribute("aria-selected", String(selectedTab));
            tab.tabIndex = selectedTab ? 0 : -1;
            tab.classList.toggle("active", selectedTab);
            get("dashboard").querySelector(`[data-day-count="${tab.dataset.dayTab}"]`).textContent =
                groups[tab.dataset.dayTab].length;
        }
        get("dayList").setAttribute(
            "aria-labelledby",
            { tasks: "dayTabTasks", deadlines: "dayTabDeadlines", events: "dayTabEvents" }[dayTab],
        );
        const items = groups[dayTab];
        const area = dayTab === "deadlines" ? "due" : "day";
        const empty = {
            tasks: "No tasks scheduled for this day.",
            deadlines: "No task or issue deadlines for this day.",
            events: "No events scheduled for this day.",
        };
        get("dayList").innerHTML = items.length
            ? items.map((item) => recordRow(item, area)).join("")
            : `<p class="dashboard-empty">${empty[dayTab]}</p>`;
        syncDescriptionControls(get("dayList"));
    }

    function render() {
        renderQueue();
        renderCalendar();
        renderDay();
        renderNotes();
    }
    // Choose visible panels for desktop, narrow windows and phones.
    function syncPanelNavigation() {
        const compact = window.matchMedia("(max-width: 860px)").matches;
        const intermediate = window.matchMedia(
            "(min-width: 861px) and (max-width: 1100px)",
        ).matches;
        const nav = dashboard.querySelector(".dashboard-panel-nav");
        nav.hidden = !compact && !intermediate;
        get("dayView").setAttribute(
            "aria-labelledby",
            nav.hidden ? "dayViewToggle" : "dashboardPanelDay",
        );
        get("notesView").setAttribute(
            "aria-labelledby",
            nav.hidden ? "notesViewToggle" : "dashboardPanelNotes",
        );
        if (intermediate && activePanel === "calendar") activePanel = "operations";
        dashboard.dataset.activePanel = activePanel;
        dashboard.querySelector(".dashboard-board").dataset.activePanel = activePanel;
        nav.querySelectorAll("[data-dashboard-panel]").forEach((button) => {
            const active = button.dataset.dashboardPanel === activePanel;
            button.classList.toggle("active", active);
            if (active) button.setAttribute("aria-current", "page");
            else button.removeAttribute("aria-current");
        });
    }
    function activatePanel(panel) {
        activePanel = panel;
        if (panel === "day" || panel === "notes") showRightView(panel);
        syncPanelNavigation();
    }
    function showRightView(view) {
        if (rightView !== view) {
            if (rightView === "day") dayScroll = get("dayList").scrollTop;
            else notesScroll = get("notesList").scrollTop;
        }
        rightView = view;
        get("dayView").hidden = view !== "day";
        get("notesView").hidden = view !== "notes";
        get("dayViewToggle").setAttribute("aria-selected", String(view === "day"));
        get("notesViewToggle").setAttribute("aria-selected", String(view === "notes"));
        get("dayViewToggle").tabIndex = view === "day" ? 0 : -1;
        get("notesViewToggle").tabIndex = view === "notes" ? 0 : -1;
        get("dayViewToggle").classList.toggle("active", view === "day");
        get("notesViewToggle").classList.toggle("active", view === "notes");
        if (view === "day") {
            get("dayList").scrollTop = dayScroll;
            syncDescriptionControls(get("dayList"));
        } else get("notesList").scrollTop = notesScroll;
        if (activePanel === "day" || activePanel === "notes") {
            activePanel = view;
            syncPanelNavigation();
        }
    }
    function selectDay(value) {
        const changed = selected !== value;
        selected = value;
        month = parseDate(`${value.slice(0, 7)}-01`);
        renderCalendar();
        renderDay();
        showRightView("day");
        if (window.matchMedia("(max-width: 1100px)").matches) {
            activatePanel("day");
            if (window.matchMedia("(max-width: 860px)").matches) {
                dashboard.querySelector('[data-dashboard-panel="day"]').focus();
            }
        }
        if (changed) {
            dayScroll = 0;
            get("dayList").scrollTop = 0;
        }
    }

    // Move dates and deadlines, keeping save failures separate from refresh failures.
    async function changeDate(type, id, date, field = "date") {
        const item = findRecord(type, id);
        if (!item || (field === "deadline" ? item.due : item.date) === date)
            return { ok: true, changed: false };
        let result;
        try {
            result = await send({ action: field, kind: type, id, date });
        } catch (error) {
            message(error.message, { error: true });
            return { ok: false, error: error.message };
        }
        if (result.changed === false) return { ok: true, changed: false };
        const label = { task: "Task", issue: "Issue", event: "Event" }[type];
        const verb =
            field === "deadline"
                ? "deadline moved"
                : type === "task" && !item.date
                  ? "scheduled"
                  : "rescheduled";
        message(`${label} ${verb}.`, { detail: prettyDate(date) });
        try {
            await load();
        } catch {
            message("Date changed, but Dashboard could not refresh. Reload the page.", {
                error: true,
            });
        }
        return { ok: true, changed: true };
    }
    function moveDraggedTo(targetDate, item) {
        const record = findRecord(item.type, item.id);
        if (!record || (item.field === "deadline" ? record.due : record.date) === targetDate)
            return;
        // Timed Events need the edit form so the user can review their times before saving.
        if (item.type === "event" && !record.all_day) {
            openWork("event", item.id, targetDate);
            return;
        }
        changeDate(item.type, item.id, targetDate, item.field);
    }
    async function clearDraggedDate(item) {
        const action = item.field === "deadline" ? "clear_deadline" : "unschedule";
        const detail = item.field === "deadline" ? "deadline removed" : "unscheduled";
        const label = { task: "Task", issue: "Issue" }[item.type];
        try {
            const result = await send({ action, kind: item.type, id: item.id });
            if (result.changed === false) return;
            kind = item.type;
            filter =
                item.field === "date" ? "unscheduled" : item.type === "issue" ? "undated" : "all";
            secondaryFilter = "any";
            shown = 40;
            expanded = null;
            get("workSearch").value = "";
            try {
                await load({ keepScroll: false });
                message(`${label} ${detail}.`);
            } catch {
                message(`${label} ${detail}, but Dashboard could not refresh. Reload the page.`, {
                    error: true,
                });
            }
        } catch (error) {
            message(error.message, { error: true });
        }
    }
    function closeActionMenus() {
        document
            .querySelectorAll(".dashboard-row-menu:popover-open")
            .forEach((menu) => menu.hidePopover());
    }
    // The browser may close a popover before click; remember its state from pointerdown.
    function openActionMenu(button) {
        const menu = document.getElementById(button.getAttribute("aria-controls"));
        const wasOpenAtPointerDown = button.dataset.dashboardMenuWasOpen === "true";
        delete button.dataset.dashboardMenuWasOpen;
        if (wasOpenAtPointerDown || menu.matches(":popover-open")) {
            if (menu.matches(":popover-open")) menu.hidePopover();
            return;
        }
        closeActionMenus();
        menu.showPopover();
        const trigger = button.getBoundingClientRect();
        const width = menu.offsetWidth,
            height = menu.offsetHeight;
        menu.style.left = `${Math.max(8, Math.min(trigger.right - width, window.innerWidth - width - 8))}px`;
        menu.style.top = `${Math.max(8, trigger.bottom + height + 5 <= window.innerHeight ? trigger.bottom + 5 : trigger.top - height - 5)}px`;
    }
    function revealExpandedRow(row) {
        if (!row) return;
        window.WorkspaceReveal?.queueRange(
            row.querySelector(".dashboard-row-toggle"),
            row.querySelector(".dashboard-row-detail"),
        );
    }
    // Row actions and the list state to restore after browser Back
    function clickRecord(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (!row) return;
        if (event.target.closest("[data-expandable-toggle]")) return;
        const type = row.dataset.kind,
            id = Number(row.dataset.id),
            area = row.dataset.area;
        const recordLink = event.target.closest("a[href]");
        if (
            recordLink?.textContent.trim() === "Open record" &&
            area === "queue" &&
            !event.defaultPrevented &&
            !event.metaKey &&
            !event.ctrlKey &&
            !event.shiftKey &&
            !event.altKey
        ) {
            const state = window.history.state;
            window.history.replaceState(
                {
                    ...(state && typeof state === "object" ? state : {}),
                    pomDashboardReturn: {
                        url: `${window.location.pathname}${window.location.search}`,
                        kind,
                        filter,
                        secondaryFilter,
                        shown,
                        expanded,
                        search: get("workSearch").value,
                        scrollTop: get("workList").scrollTop,
                    },
                },
                "",
                window.location.href,
            );
        }
        const button = event.target.closest("[data-action]");
        if (button) {
            const action = button.dataset.action;
            if (action === "more") {
                openActionMenu(button);
                return;
            }
            const returnFocus = window.WorkspaceModalReturnFocus?.resolve(button) || button;
            closeActionMenus();
            if (action === "edit") openWork(type, id, null, returnFocus);
            else if (
                action === "finish" &&
                type === "issue" &&
                findRecord(type, id)?.active_linked_tasks
            )
                openConfirm(type, id, action, returnFocus);
            else if (action === "finish") performQuickAction(type, id);
            else openConfirm(type, id, action, returnFocus);
            return;
        }
        if (event.target.closest(".dashboard-row-toggle")) {
            const queueScroll = get("workList").scrollTop;
            const dayScroll = get("dayList").scrollTop;
            expanded = expanded === `${area}-${type}-${id}` ? null : `${area}-${type}-${id}`;
            renderQueue();
            renderDay();
            get("workList").scrollTop = queueScroll;
            get("dayList").scrollTop = dayScroll;
            const list = area === "queue" ? get("workList") : get("dayList");
            const selectedRow = list.querySelector(
                `[data-area="${area}"][data-kind="${type}"][data-id="${id}"]`,
            );
            selectedRow?.querySelector(".dashboard-row-toggle")?.focus({ preventScroll: true });
            if (expanded) revealExpandedRow(selectedRow);
        }
    }
    function highlightDate(value) {
        document
            .querySelectorAll(".dashboard-day.linked-hover")
            .forEach((day) => day.classList.remove("linked-hover"));
        if (value)
            document
                .querySelector(`.dashboard-day[data-day="${value}"]`)
                ?.classList.add("linked-hover");
    }
    // Decide which records can be dragged and where they may be dropped.
    const operationsDropTarget = dashboard.querySelector(".dashboard-operations");
    function acceptsWorkDrop(item) {
        const record = item && findRecord(item.type, item.id);
        return Boolean(
            record &&
            ((item.source === "day" &&
                item.type === "task" &&
                item.field === "date" &&
                record.date) ||
                (item.source === "due" &&
                    ["task", "issue"].includes(item.type) &&
                    item.field === "deadline" &&
                    record.due)),
        );
    }
    function clearWorkDropState() {
        operationsDropTarget.classList.remove("accepts-drop", "drag-over");
        delete operationsDropTarget.dataset.dropHint;
    }
    function beginDrag(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (
            !row ||
            !row.draggable ||
            event.target.closest("a, input, select, textarea, .dashboard-row-actions")
        )
            return;
        dragged = {
            type: row.dataset.kind,
            id: Number(row.dataset.id),
            source: row.dataset.area,
            field: row.dataset.area === "due" || row.dataset.kind === "issue" ? "deadline" : "date",
        };
        event.dataTransfer.setData("text/plain", `${dragged.type}:${dragged.id}`);
        event.dataTransfer.effectAllowed = "move";
        if (acceptsWorkDrop(dragged)) {
            operationsDropTarget.dataset.dropHint =
                dragged.field === "deadline"
                    ? "Drop here to remove the deadline"
                    : "Drop here to unschedule the task";
            operationsDropTarget.classList.add("accepts-drop");
        }
    }

    // Tab, filter and list controls
    // Activate through the existing click handlers so keyboard and mouse preserve the same state.
    dashboard
        .querySelectorAll(".dashboard-tabs[role=tablist], .dashboard-view-switch")
        .forEach((group) => {
            const tabs = [...group.querySelectorAll('[role="tab"]')];
            group.addEventListener("keydown", (event) => {
                const index = tabs.indexOf(event.target);
                if (index < 0) return;
                let nextIndex;
                if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
                else if (event.key === "ArrowLeft")
                    nextIndex = (index + tabs.length - 1) % tabs.length;
                else if (event.key === "Home") nextIndex = 0;
                else if (event.key === "End") nextIndex = tabs.length - 1;
                else return;
                event.preventDefault();
                tabs[nextIndex].click();
                tabs[nextIndex].focus();
            });
        });
    document.querySelectorAll("[data-kind][role=tab]").forEach((button) =>
        button.addEventListener("click", () => {
            kind = button.dataset.kind;
            filter = "all";
            secondaryFilter = "any";
            shown = 40;
            expanded = null;
            get("workSearch").value = "";
            get("workList").scrollTop = 0;
            renderQueue();
        }),
    );
    document.querySelectorAll("[data-day-tab]").forEach((button) =>
        button.addEventListener("click", () => {
            dayTab = button.dataset.dayTab;
            expanded = null;
            dayScroll = 0;
            get("dayList").scrollTop = 0;
            renderDay();
        }),
    );
    dashboard
        .querySelectorAll("[data-dashboard-panel]")
        .forEach((button) =>
            button.addEventListener("click", () => activatePanel(button.dataset.dashboardPanel)),
        );
    get("dayViewToggle").addEventListener("click", () => activatePanel("day"));
    get("notesViewToggle").addEventListener("click", () => activatePanel("notes"));
    get("workSearch").addEventListener("input", () => {
        shown = 40;
        get("workList").scrollTop = 0;
        renderQueue();
    });
    get("workFilter").addEventListener("change", (event) => {
        filter = event.target.value;
        shown = 40;
        get("workList").scrollTop = 0;
        renderQueue();
    });
    get("workSecondaryFilter").addEventListener("change", (event) => {
        secondaryFilter = event.target.value;
        shown = 40;
        get("workList").scrollTop = 0;
        renderQueue();
    });
    get("workList").addEventListener("scroll", appendMore);
    for (const list of [get("workList"), get("dayList")])
        list.addEventListener("scroll", closeActionMenus);
    window.addEventListener("resize", () => {
        syncPanelNavigation();
        closeActionMenus();
        syncDescriptionControls(get("workList"));
        if (rightView === "day") syncDescriptionControls(get("dayList"));
    });
    syncPanelNavigation();
    document.addEventListener(
        "toggle",
        (event) => {
            if (!event.target.classList?.contains("dashboard-row-menu")) return;
            const trigger = document.querySelector(`[aria-controls="${event.target.id}"]`);
            if (trigger) trigger.setAttribute("aria-expanded", String(event.newState === "open"));
        },
        true,
    );
    get("workList").addEventListener("click", clickRecord);
    get("dayList").addEventListener("click", clickRecord);
    for (const list of [get("workList"), get("dayList")]) {
        list.addEventListener(
            "pointerdown",
            (event) => {
                const button = event.target.closest('[data-action="more"]');
                if (!button) return;
                const menu = document.getElementById(button.getAttribute("aria-controls"));
                button.dataset.dashboardMenuWasOpen = String(
                    Boolean(menu && menu.matches(":popover-open")),
                );
            },
            true,
        );
    }
    get("workList").addEventListener("pointerover", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row) highlightDate(row.dataset.scheduledDate);
    });
    get("workList").addEventListener("pointerout", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row && !row.contains(event.relatedTarget)) highlightDate(null);
    });
    // Drag feedback and drop handlers
    for (const area of [get("workList"), get("dayList")]) {
        area.addEventListener("dragstart", beginDrag);
        area.addEventListener("dragend", () => {
            dragged = null;
            highlightDate(null);
            clearWorkDropState();
            document
                .querySelectorAll(".dashboard-day.drag-over")
                .forEach((day) => day.classList.remove("drag-over"));
            get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over");
        });
    }
    operationsDropTarget.addEventListener("dragover", (event) => {
        if (!acceptsWorkDrop(dragged)) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        operationsDropTarget.classList.add("drag-over");
    });
    operationsDropTarget.addEventListener("dragleave", (event) => {
        if (!operationsDropTarget.contains(event.relatedTarget))
            operationsDropTarget.classList.remove("drag-over");
    });
    operationsDropTarget.addEventListener("drop", (event) => {
        if (!acceptsWorkDrop(dragged)) return;
        event.preventDefault();
        const item = dragged;
        dragged = null;
        clearWorkDropState();
        clearDraggedDate(item);
    });
    get("dashboard")
        .querySelectorAll("[data-calendar-filter]")
        .forEach((checkbox) => {
            checkbox.addEventListener("change", renderCalendar);
        });
    get("calendarGrid").addEventListener("click", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day) return;
        const category = event.target.closest("[data-category]");
        dayTab = category ? category.dataset.category : "tasks";
        selectDay(day.dataset.day);
    });
    get("calendarGrid").addEventListener("dragover", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day || !canDropOnDate(dragged, day.dataset.day)) return;
        event.preventDefault();
        day.classList.add("drag-over");
    });
    get("calendarGrid").addEventListener("dragleave", (event) => {
        const day = event.target.closest("[data-day]");
        if (day && !day.contains(event.relatedTarget)) day.classList.remove("drag-over");
    });
    get("calendarGrid").addEventListener("drop", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day || !canDropOnDate(dragged, day.dataset.day)) return;
        event.preventDefault();
        const item = dragged;
        dragged = null;
        day.classList.remove("drag-over");
        moveDraggedTo(day.dataset.day, item);
    });
    function acceptsDayDrop(item) {
        return (
            item &&
            ((dayTab === "tasks" && item.type === "task" && item.field === "date") ||
                (dayTab === "deadlines" && item.field === "deadline") ||
                (dayTab === "events" && item.type === "event"))
        );
    }
    async function performQuickAction(type, id) {
        const key = `${type}:${id}`;
        if (quickPending.has(key)) return;
        quickPending.add(key);
        try {
            const result = await send({ action: "finish", kind: type, id });
            const title = {
                task: "Task completed.",
                issue: "Issue resolved.",
                event: "Event marked as occurred.",
            }[type];
            if (result.undo_token) showUndo(type, id, result.undo_token, title);
            else message(title);
            try {
                await load();
            } catch {
                message("Action succeeded, but Dashboard could not refresh. Reload the page.", {
                    error: true,
                });
            }
        } catch (error) {
            message(error.message, { error: true });
        } finally {
            quickPending.delete(key);
        }
    }
    function canDropOnDate(item, date) {
        const record = item && findRecord(item.type, item.id);
        return !!record && (item.field === "deadline" ? record.due : record.date) !== date;
    }
    get("dayList").addEventListener("dragover", (event) => {
        if (acceptsDayDrop(dragged) && canDropOnDate(dragged, selected)) {
            event.preventDefault();
            get("dashboard").querySelector(".dashboard-day-plan").classList.add("drag-over");
        }
    });
    get("dayList").addEventListener("dragleave", (event) => {
        if (!get("dayList").contains(event.relatedTarget))
            get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over");
    });
    get("dayList").addEventListener("drop", (event) => {
        if (!acceptsDayDrop(dragged) || !canDropOnDate(dragged, selected)) return;
        event.preventDefault();
        const item = dragged;
        dragged = null;
        get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over");
        moveDraggedTo(selected, item);
    });
    // Calendar month controls
    function setPeriod(year, monthNumber) {
        month = new Date(Date.UTC(year, monthNumber, 1));
        if (!selected.startsWith(isoDate(month).slice(0, 7))) selected = isoDate(month);
        renderCalendar();
        renderDay();
        get("calendarGrid").parentElement.scrollTop = 0;
    }
    get("calendarMonth").addEventListener("change", () =>
        setPeriod(month.getUTCFullYear(), Number(get("calendarMonth").value)),
    );
    get("calendarYear").addEventListener("change", () =>
        setPeriod(Number(get("calendarYear").value), month.getUTCMonth()),
    );
    get("previousPeriod").addEventListener("click", () =>
        setPeriod(month.getUTCFullYear(), month.getUTCMonth() - 1),
    );
    get("nextPeriod").addEventListener("click", () =>
        setPeriod(month.getUTCFullYear(), month.getUTCMonth() + 1),
    );
    get("calendarToday").addEventListener("click", () => selectDay(data.today));
    // Add menu and dialog launch buttons
    function closeAddMenu({ restoreFocus = false } = {}) {
        get("dashboardAddMenu").hidden = true;
        get("dashboardAddToggle").setAttribute("aria-expanded", "false");
        if (restoreFocus) get("dashboardAddToggle").focus();
    }
    get("dashboardAddToggle").addEventListener("click", () => {
        const opening = get("dashboardAddMenu").hidden;
        get("dashboardAddMenu").hidden = !opening;
        get("dashboardAddToggle").setAttribute("aria-expanded", String(opening));
    });
    document.querySelectorAll("[data-add]").forEach((button) =>
        button.addEventListener("click", () => {
            const returnFocus = window.WorkspaceModalReturnFocus?.resolve(button) || button;
            closeAddMenu();
            if (button.dataset.add === "event") openAddEvent(returnFocus);
            else openWork(button.dataset.add, null, null, returnFocus);
        }),
    );
    document.addEventListener("pointerdown", (event) => {
        if (!get("dashboardAddMenu").hidden && !event.target.closest(".dashboard-add-wrap"))
            closeAddMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !get("dashboardAddMenu").hidden)
            closeAddMenu({ restoreFocus: true });
    });
    // Recompute date-relative views after midnight or returning to a sleeping
    // tab. Keep the selected date, viewed month and scroll positions unchanged.
    document.addEventListener("dashboard:date-change", ({ detail }) => {
        if (!month || data.today === detail.today) return;
        const queueScroll = get("workList").scrollTop;
        const selectedScroll = get("dayList").scrollTop;
        data.today = detail.today;
        renderQueue();
        renderCalendar();
        renderDay();
        get("workList").scrollTop = queueScroll;
        get("dayList").scrollTop = selectedScroll;
    });

    // Load the initial page after its controls and helper modules are ready.
    load().catch((error) => message(error.message, { error: true }));
});

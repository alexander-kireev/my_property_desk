document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("dashboard");
    if (!dashboard) return;

    const get = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
    const parseDate = (value) => new Date(`${value}T12:00:00Z`);
    const isoDate = (value) => value.toISOString().slice(0, 10);
    const prettyDate = (value) => parseDate(value).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"}).replace("Sept", "Sep");
    const longDate = (value) => parseDate(value).toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC"});
    const mondayOf = (value) => {
        const day = parseDate(value);
        day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
        return day;
    };
    const cookie = document.cookie.split("; ").find((part) => part.startsWith("csrftoken="));
    const csrfToken = cookie ? decodeURIComponent(cookie.slice(10)) : "";
    const filters = {
        task: [["all", "All active"], ["unscheduled", "Unscheduled"], ["today", "Scheduled for today"], ["other", "Other scheduled"]],
        issue: [["all", "All open"], ["overdue", "Overdue"], ["week", "Resolve by this week"], ["undated", "No resolve-by date"]],
        event: [["all", "All scheduled"], ["week", "This week"], ["month", "This month"]],
    };
    const priorities = [["any", "Any priority"], ["high", "High or urgent"]];
    let data = {records: {task: [], issue: [], event: []}, notes: [], properties: [], issues: [], today: ""};
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
    const returning = window.performance?.getEntriesByType?.("navigation")?.[0]?.type === "back_forward"
        ? window.history.state?.pomDashboardReturn : null;
    if (returning?.url === `${window.location.pathname}${window.location.search}`
        && ["task", "issue", "event"].includes(returning.kind)) {
        kind = returning.kind;
        filter = returning.filter;
        secondaryFilter = returning.secondaryFilter;
        shown = returning.shown;
        expanded = returning.expanded;
    }
    let editingNote = null;
    let recordTarget = null;
    let confirmTarget = null;
    let dragged = null;
    let toastTimer = null;
    let toastRemaining = 0;
    let toastStarted = 0;
    let toastPauseable = false;
    let workPending = false;
    let eventAddPending = false;
    let confirmPending = false;
    const quickPending = new Set();

    function stopToastTimer() {
        if (!toastTimer) return;
        clearTimeout(toastTimer);
        toastTimer = null;
        toastRemaining -= Date.now() - toastStarted;
    }
    function startToastTimer() {
        if (toastTimer || toastRemaining <= 0) return;
        toastStarted = Date.now();
        toastTimer = setTimeout(hideToast, toastRemaining);
    }
    function hideToast() {
        const toast = get("dashboardToast");
        if (toast.hidden) return;
        stopToastTimer();
        toastRemaining = 0;
        toast.classList.add("leaving");
        setTimeout(() => { if (toast.classList.contains("leaving")) toast.hidden = true; }, 180);
    }
    function presentToast(title, {detail = "", error = false, undoAction = null, duration = null} = {}) {
        const toast = get("dashboardToast");
        const undoButton = get("dashboardToastUndo");
        const undoWasFocused = document.activeElement === undoButton;
        stopToastTimer();
        window.AppFeedback?.dismiss();
        toast.classList.remove("leaving");
        toast.classList.toggle("error", error);
        toast.setAttribute("role", error ? "alert" : "status");
        toast.setAttribute("aria-live", error ? "assertive" : "polite");
        get("dashboardToastIcon").textContent = error ? "!" : "✓";
        get("dashboardToastTitle").textContent = title;
        get("dashboardToastDetail").textContent = detail;
        undoButton.hidden = !undoAction;
        undoButton.disabled = false;
        undoButton.onclick = undoAction;
        toast.hidden = false;
        toastPauseable = Boolean(undoAction);
        toastRemaining = duration ?? (error ? 0 : undoAction ? 10000 : 4200);
        if (toastRemaining && (!toastPauseable || !(toast.matches(":hover") || toast.contains(document.activeElement)))) startToastTimer();
        if (undoWasFocused && !undoAction) get("dashboardToastClose").focus();
    }
    function message(title, options = {}) { presentToast(title, options); }
    function showUndo(type, id, token, title) {
        const attemptUndo = async () => {
            const button = get("dashboardToastUndo");
            button.disabled = true;
            stopToastTimer();
            try {
                await send({action: "undo", kind: type, id, token});
            } catch (error) {
                if (/expired|changed again|does not match/.test(error.message)) {
                    message(error.message, {error: true});
                    try { await load(); } catch (refreshError) { message(refreshError.message, {error: true}); }
                }
                else presentToast(error.message, {error: true, undoAction: attemptUndo, duration: Math.max(1000, toastRemaining)});
                return;
            }
            try { await load(); message("Action undone."); }
            catch { message("Undo succeeded, but Dashboard could not refresh. Reload the page.", {error: true}); }
        };
        presentToast(title, {undoAction: attemptUndo});
    }
    function findRecord(type, id) { return data.records[type].find((item) => item.id === Number(id)); }
    function recordError(body) {
        if (body.error) return body.error;
        if (body.errors) return Object.entries(body.errors).map(([field, values]) => `${field}: ${values.join(", ")}`).join(" · ");
        return "Unable to save. Please try again.";
    }
    async function send(fields) {
        const body = new URLSearchParams(fields);
        let response;
        try {
            response = await fetch(dashboard.dataset.actionUrl, {
                method: "POST", headers: {"X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded"},
                credentials: "same-origin", body,
            });
        } catch {
            throw new Error("Could not connect. Check your connection and try again.");
        }
        const result = await response.json().catch(() => null);
        if (!result) throw new Error("The server could not process that request. Please try again.");
        if (!response.ok) {
            const error = new Error(recordError(result));
            error.fieldErrors = result.errors || null;
            throw error;
        }
        return result;
    }
    async function load({keepScroll = true} = {}) {
        const queueScroll = keepScroll ? get("workList").scrollTop : 0;
        const dayScroll = keepScroll ? get("dayList").scrollTop : 0;
        let response;
        try {
            response = await fetch(dashboard.dataset.dataUrl, {credentials: "same-origin"});
            if (!response.ok) throw new Error("Server response was not successful.");
            data = await response.json();
        } catch {
            throw new Error("Dashboard could not load. Refresh the page to try again.");
        }
        if (!selected) selected = data.today;
        if (!month) month = parseDate(`${selected.slice(0, 7)}-01`);
        render();
        if (returning?.url === `${window.location.pathname}${window.location.search}`) {
            get("workSearch").value = returning.search || "";
            renderQueue();
        }
        get("workList").scrollTop = returning?.url === `${window.location.pathname}${window.location.search}`
            ? returning.scrollTop || 0 : queueScroll;
        get("dayList").scrollTop = dayScroll;
        if (returning?.expanded) {
            const row = get("workList").querySelector(`[data-area="queue"][data-kind="${kind}"][data-id="${returning.expanded.split("-").at(-1)}"]`);
            row?.querySelector(".dashboard-row-toggle")?.focus({preventScroll: true});
        }
    }

    function visibleRecords() {
        const search = get("workSearch").value.trim().toLowerCase();
        const weekEnd = new Date(mondayOf(data.today));
        weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
        return data.records[kind].filter((item) => {
            if (search && !`${item.title} ${item.description} ${item.property} ${item.issue_title || ""}`.toLowerCase().includes(search)) return false;
            if (kind === "task") {
                if (filter === "unscheduled" && item.date) return false;
                if (filter === "today" && item.date !== data.today) return false;
                if (filter === "other" && (!item.date || item.date === data.today)) return false;
                if (secondaryFilter === "high" && !["High", "Urgent"].includes(item.priority)) return false;
            } else if (kind === "issue") {
                if (filter === "overdue" && (!item.due || item.due >= data.today)) return false;
                if (filter === "week" && (!item.due || item.due < isoDate(mondayOf(data.today)) || item.due > isoDate(weekEnd))) return false;
                if (filter === "undated" && item.due) return false;
                if (secondaryFilter === "high" && !["High", "Urgent"].includes(item.priority)) return false;
            } else {
                if (filter === "week" && (item.date < isoDate(mondayOf(data.today)) || item.date > isoDate(weekEnd))) return false;
                if (filter === "month" && !item.date.startsWith(data.today.slice(0, 7))) return false;
            }
            return true;
        });
    }
    function badge(item) {
        if (item.priority) return `<span class="work-pill work-pill--priority-${item.priority_id}" aria-label="${escapeHtml(item.priority)} priority" title="${escapeHtml(item.priority)} priority">${escapeHtml(item.priority)}</span>`;
        if (item.kind === "event") return `<span class="work-pill work-pill--${item.state === "scheduled" ? "active" : "terminal"}">${escapeHtml(item.state.charAt(0).toUpperCase() + item.state.slice(1))}</span>`;
        return "";
    }
    function recordMeta(item) {
        const parts = [];
        if (item.kind === "task") {
            parts.push(item.date ? `Scheduled ${prettyDate(item.date)}` : "Unscheduled");
            if (item.due) parts.push(`Due ${prettyDate(item.due)}`);
        } else if (item.kind === "issue") {
            if (item.due) parts.push(`Resolve by ${prettyDate(item.due)}`);
        } else {
            if (item.date) parts.push(prettyDate(item.date));
            if (item.all_day) parts.push("All day");
            else if (item.start_time) parts.push(`${item.start_time}${item.end_time ? `–${item.end_time}` : ""}`);
        }
        return parts.join(" · ");
    }
    function syncDescriptionControls(list) {
        window.ExpandableText?.refresh(list);
    }
    function recordRow(item, area) {
        const key = `${area}-${item.kind}-${item.id}`;
        const isExpanded = expanded === key;
        const canDrag = ["task", "event", "issue"].includes(item.kind);
        const finish = {task: "Complete", issue: "Resolve", event: "Mark occurred"}[item.kind];
        const fullUrl = `${dashboard.dataset[`${item.kind}Url`]}?selected=${item.id}&open=detail`;
        const chevron = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m5 9 7 7 7-7"/></svg>';
        const typeCue = area === "due" ? `<span class="dashboard-type-cue"><span aria-hidden="true">${{task: "▤", issue: "◇"}[item.kind]}</span> ${item.kind === "task" ? "Task" : "Issue"}</span>` : "";
        const menuId = `dashboard-actions-${key}`;
        const actions = `<div class="dashboard-row-actions">
            <button type="button" class="dashboard-action-primary btn theme-action btn-sm" data-action="finish">${finish}</button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-action="edit">Edit</button>
            ${item.kind === "event" ? '<button type="button" class="dashboard-optional-action btn btn-outline-secondary btn-sm" data-action="cancel">Cancel</button>' : ""}
            <button type="button" class="dashboard-optional-action dashboard-action-danger btn btn-outline-danger btn-sm" data-action="delete">Delete</button>
            <a class="dashboard-optional-action btn btn-outline-secondary btn-sm" href="${escapeHtml(fullUrl)}">Open record</a>
            <button type="button" class="dashboard-more-button btn btn-outline-secondary btn-sm" data-action="more" aria-label="More actions for ${escapeHtml(item.title)}" aria-controls="${menuId}" aria-expanded="false">⋮</button>
            <div class="dashboard-row-menu" id="${menuId}" popover="auto">
                ${item.kind === "event" ? '<button type="button" data-action="cancel">Cancel event</button>' : ""}
                <a href="${escapeHtml(fullUrl)}">Open record</a>
                <button type="button" class="dashboard-action-danger" data-action="delete">Delete</button>
            </div>
        </div>`;
        const taskSummary = item.kind === "task";
        const taskContext = item.issue_id ? item.issue_title : item.property;
        const dueDays = item.due ? Math.round((parseDate(item.due) - parseDate(data.today)) / 86400000) : null;
        const taskTiming = item.due
            ? `${dueDays < 0 ? "Overdue" : dueDays <= 3 ? "Due soon" : "Due"} ${prettyDate(item.due)}`
            : item.date ? `Scheduled ${prettyDate(item.date)}` : "No date";
        const issueTiming = item.due
            ? `${dueDays < 0 ? "Overdue" : dueDays <= 3 ? "Due soon" : "Resolve by"} ${prettyDate(item.due)}`
            : "No target date";
        const eventTiming = `<span>${prettyDate(item.date)} ·</span><span>${item.all_day ? "All day" : `${escapeHtml(item.start_time)}${item.end_time ? `–${escapeHtml(item.end_time)}` : ""}`}</span>`;
        const summary = taskSummary
            ? `<span class="dashboard-task-copy"><strong class="dashboard-task-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong><small class="dashboard-task-context"${taskContext ? ` title="${escapeHtml(taskContext)}"` : ' aria-hidden="true"'}>${typeCue}${escapeHtml(taskContext)}</small></span>
                <span class="dashboard-task-meta">${badge(item)}<span class="dashboard-task-timing${item.due && item.due < data.today ? " is-overdue" : ""}">${taskTiming}</span></span>
                <span class="dashboard-row-chevron">${chevron}</span>`
            : `<span class="dashboard-row-main"><strong title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong><small class="dashboard-row-context"${item.property ? ` title="${escapeHtml(item.property)}"` : typeCue ? "" : ' aria-hidden="true"'}>${typeCue}${escapeHtml(item.property)}</small></span>
                <span class="dashboard-row-side${item.kind === "event" ? " dashboard-event-side" : ""}">${badge(item)}<span class="dashboard-row-timing${item.due && item.due < data.today ? " is-overdue" : ""}">${item.kind === "issue" ? issueTiming : eventTiming}</span></span><span class="dashboard-row-chevron">${chevron}</span>`;
        const issueFact = item.issue_id
            ? `<span class="dashboard-issue-fact" title="${escapeHtml(item.issue_title)}"><span class="dashboard-issue-title">${escapeHtml(item.issue_title)}</span></span>`
            : "";
        const propertyFact = item.property && !(item.kind === "task" && item.issue_id)
            ? `<span class="dashboard-property-fact" title="${escapeHtml(item.property)}"><span class="dashboard-property-name">${escapeHtml(item.property)}</span></span>`
            : "";
        return `<article class="list-group-item ${area === "queue" ? "dashboard-work-row" : "dashboard-day-row"}" data-area="${area}" data-kind="${item.kind}" data-id="${item.id}" ${canDrag ? 'draggable="true"' : ""} ${area === "due" && item.due ? `data-scheduled-date="${item.due}"` : item.date ? `data-scheduled-date="${item.date}"` : ""}>
            <button class="dashboard-row-toggle${taskSummary ? " dashboard-task-toggle" : ""} list-group-item-action" type="button" aria-expanded="${isExpanded}" aria-label="${isExpanded ? "Collapse" : "Expand"} ${escapeHtml(item.title)}">
                ${summary}
            </button>
            <div class="dashboard-row-detail" ${isExpanded ? "" : "hidden"}>
                ${item.description ? `<div class="expandable-text" data-expandable-text><p class="expandable-text-content" id="dashboard-description-${key}" data-expandable-content>${escapeHtml(item.description)}</p><button type="button" class="expandable-text-toggle" aria-controls="dashboard-description-${key}" aria-expanded="false" hidden data-expandable-toggle>See more</button></div>` : `<p class="text-body-secondary">No description.</p>`}
                <div class="dashboard-row-facts">${propertyFact}${issueFact}${item.date ? `<span>${item.kind === "event" ? "Date" : "Scheduled"} ${prettyDate(item.date)}</span>` : item.kind === "task" ? "<span>Unscheduled</span>" : ""}${item.due ? `<span>${item.kind === "issue" ? "Resolve by" : "Due"} ${prettyDate(item.due)}</span>` : ""}${item.kind === "event" && item.start_time ? `<span>${escapeHtml(item.start_time)}${item.end_time ? `–${escapeHtml(item.end_time)}` : ""}</span>` : ""}</div>
                ${actions}
            </div>
        </article>`;
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
            button.classList.toggle("active", selected);
        });
        get("workSearch").placeholder = `Search ${kind}s`;
        get("workFilterLabel").textContent = {
            task: "Filter tasks by schedule",
            issue: "Filter issues by deadline",
            event: "Filter events by date",
        }[kind];
        const options = get("workFilter");
        options.innerHTML = filters[kind].map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
        options.value = filter;
        window.SearchableSelect?.refresh(options);
        const secondary = get("workSecondaryFilter");
        get("workSecondaryWrap").hidden = kind === "event";
        secondary.innerHTML = priorities.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
        secondary.value = secondaryFilter;
        window.SearchableSelect?.refresh(secondary);
        get("dashboard").querySelector(".dashboard-filter-controls").classList.toggle("is-single", kind === "event");
        get("workList").innerHTML = items.length ? items.slice(0, shown).map((item) => recordRow(item, "queue")).join("") : '<p class="dashboard-empty">No records match this search and filter.</p>';
        syncDescriptionControls(get("workList"));
    }
    function appendMore() {
        const list = get("workList");
        if (list.scrollTop + list.clientHeight < list.scrollHeight - 100) return;
        const items = visibleRecords();
        if (shown >= items.length) return;
        const previous = shown;
        shown += 40;
        list.insertAdjacentHTML("beforeend", items.slice(previous, shown).map((item) => recordRow(item, "queue")).join(""));
    }
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
        if (!monthSelect.options.length) monthSelect.innerHTML = Array.from({length: 12}, (_, index) => `<option value="${index}">${new Date(Date.UTC(2026, index, 1)).toLocaleDateString("en-GB", {month: "long", timeZone: "UTC"})}</option>`).join("");
        yearSelect.innerHTML = Array.from({length: 21}, (_, index) => `<option value="${year - 10 + index}">${year - 10 + index}</option>`).join("");
        monthSelect.value = String(monthNumber);
        yearSelect.value = String(year);
        window.SearchableSelect?.refresh(monthSelect);
        window.SearchableSelect?.refresh(yearSelect);
        const start = calendarStart();
        const lastDay = new Date(Date.UTC(year, monthNumber + 1, 0));
        const weeks = Math.ceil((lastDay.getUTCDate() + ((month.getUTCDay() + 6) % 7)) / 7);
        const show = (kind) => get("dashboard").querySelector(`[data-calendar-filter="${kind}"]`).checked;
        const scheduledTasks = countByDate(show("tasks") ? data.records.task : [], "date");
        const scheduledEvents = countByDate(show("events") ? data.records.event : [], "date");
        const taskDeadlines = countByDate(show("tasks") ? data.records.task : [], "due");
        const issueDeadlines = countByDate(show("issues") ? data.records.issue : [], "due");
        const cells = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => `<span class="dashboard-weekday">${day}</span>`);
        for (let index = 0; index < weeks * 7; index++) {
            const date = new Date(start);
            date.setUTCDate(start.getUTCDate() + index);
            const value = isoDate(date);
            const tasks = scheduledTasks.get(value) || 0;
            const events = scheduledEvents.get(value) || 0;
            const due = (taskDeadlines.get(value) || 0) + (issueDeadlines.get(value) || 0);
            const dateLabel = longDate(value);
            cells.push(`<div class="dashboard-day ${date.getUTCMonth() !== monthNumber ? "other" : ""} ${value === selected ? "selected" : ""} ${value === data.today ? "today" : ""}" data-day="${value}">
                <button type="button" class="dashboard-date-button" aria-label="Select ${dateLabel}" ${value === data.today ? 'aria-current="date"' : ""}><strong>${date.getUTCDate()}${value === data.today ? '<span class="dashboard-today-dot" aria-hidden="true"></span>' : ""}</strong></button>
                ${tasks ? `<button type="button" class="dashboard-day-count dashboard-day-category" data-category="tasks" aria-label="${tasks} scheduled task${tasks === 1 ? "" : "s"} on ${dateLabel}; show Tasks">${tasks}<span class="dashboard-count-label"> task${tasks === 1 ? "" : "s"}</span></button>` : ""}
                ${events ? `<button type="button" class="dashboard-event-count dashboard-day-category" data-category="events" aria-label="${events} event${events === 1 ? "" : "s"} on ${dateLabel}; show Events">${events}<span class="dashboard-count-label"> event${events === 1 ? "" : "s"}</span></button>` : ""}
                ${due ? `<button type="button" class="dashboard-due-count dashboard-day-category" data-category="deadlines" aria-label="${due} deadline${due === 1 ? "" : "s"} on ${dateLabel}; show Deadlines">${due}<span class="dashboard-count-label"> due</span></button>` : ""}
            </div>`);
        }
        const grid = get("calendarGrid");
        grid.innerHTML = cells.join("");
    }
    function renderDay() {
        get("selectedDayHeading").textContent = longDate(selected);
        const tasks = data.records.task.filter((item) => item.date === selected);
        const events = data.records.event.filter((item) => item.date === selected);
        const dueTasks = data.records.task.filter((item) => item.due === selected);
        const dueIssues = data.records.issue.filter((item) => item.due === selected);
        const due = [...dueTasks, ...dueIssues];
        get("selectedDayCount").textContent = `${tasks.length} task${tasks.length === 1 ? "" : "s"} · ${events.length} event${events.length === 1 ? "" : "s"} · ${due.length} deadline${due.length === 1 ? "" : "s"}`;
        const groups = {tasks, deadlines: due, events};
        for (const tab of get("dashboard").querySelectorAll("[data-day-tab]")) {
            const selectedTab = tab.dataset.dayTab === dayTab;
            tab.setAttribute("aria-selected", String(selectedTab));
            tab.classList.toggle("active", selectedTab);
            get("dashboard").querySelector(`[data-day-count="${tab.dataset.dayTab}"]`).textContent = groups[tab.dataset.dayTab].length;
        }
        get("dayList").setAttribute("aria-labelledby", {tasks: "dayTabTasks", deadlines: "dayTabDeadlines", events: "dayTabEvents"}[dayTab]);
        const items = groups[dayTab];
        const area = dayTab === "deadlines" ? "due" : "day";
        const empty = {tasks: "No tasks scheduled for this day.", deadlines: "No task or issue deadlines for this day.", events: "No events scheduled for this day."};
        get("dayList").innerHTML = items.length ? items.map((item) => recordRow(item, area)).join("") : `<p class="dashboard-empty">${empty[dayTab]}</p>`;
        syncDescriptionControls(get("dayList"));
    }
    function renderNotes() {
        get("notesCount").textContent = data.notes.length;
        get("notesList").innerHTML = data.notes.length ? data.notes.map((note) => `<article class="dashboard-note" data-note="${note.id}">
            ${editingNote === note.id ? `<textarea maxlength="250" aria-label="Edit note">${escapeHtml(note.content)}</textarea><div class="dashboard-note-edit-actions"><button type="button" data-note-action="cancel">Cancel</button><button type="button" data-note-action="save">Save</button></div>` : `<p>${escapeHtml(note.content)}</p><div class="dashboard-note-actions"><button type="button" data-note-action="edit" aria-label="Edit note"><svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M12.9 1.7a1.5 1.5 0 0 1 2.1 2.1l-9.5 9.5-3.1.8.8-3.1 9.7-9.3Zm-8.8 9.9-.3 1.1 1.1-.3 8.2-8.2-.8-.8-8.2 8.2Z"/></svg></button><button type="button" class="dashboard-note-delete" data-note-action="delete" aria-label="Delete note"><svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M3.3 2.3 8 7l4.7-4.7 1 1L9 8l4.7 4.7-1 1L8 9l-4.7 4.7-1-1L7 8 2.3 3.3l1-1Z"/></svg></button></div><small>${escapeHtml(note.created)}</small>`}
        </article>`).join("") : '<p class="dashboard-empty">No notes yet.</p>';
    }
    function render() { renderQueue(); renderCalendar(); renderDay(); renderNotes(); }
    function syncPanelNavigation() {
        const compact = window.matchMedia("(max-width: 860px)").matches;
        const intermediate = window.matchMedia("(min-width: 861px) and (max-width: 1100px)").matches;
        const nav = dashboard.querySelector(".dashboard-panel-nav");
        nav.hidden = !compact && !intermediate;
        get("dayView").setAttribute("aria-labelledby", nav.hidden ? "dayViewToggle" : "dashboardPanelDay");
        get("notesView").setAttribute("aria-labelledby", nav.hidden ? "notesViewToggle" : "dashboardPanelNotes");
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
        get("dayViewToggle").classList.toggle("active", view === "day");
        get("notesViewToggle").classList.toggle("active", view === "notes");
        if (view === "day") {
            get("dayList").scrollTop = dayScroll;
            syncDescriptionControls(get("dayList"));
        }
        else get("notesList").scrollTop = notesScroll;
        if (activePanel === "day" || activePanel === "notes") {
            activePanel = view;
            syncPanelNavigation();
        }
    }
    function selectDay(value) {
        const changed = selected !== value;
        selected = value;
        month = parseDate(`${value.slice(0, 7)}-01`);
        renderCalendar(); renderDay();
        showRightView("day");
        if (window.matchMedia("(max-width: 1100px)").matches) {
            activatePanel("day");
            if (window.matchMedia("(max-width: 860px)").matches) {
                dashboard.querySelector('[data-dashboard-panel="day"]').focus();
            }
        }
        if (changed) { dayScroll = 0; get("dayList").scrollTop = 0; }
    }

    function formField(name, label, value = "", type = "text") {
        return `<div class="dashboard-form-row"><label for="dashboard-field-${name}">${label}</label><div class="dashboard-form-control"><input id="dashboard-field-${name}" class="form-control" name="${name}" type="${type}" value="${escapeHtml(value)}" ${name === "title" ? 'maxlength="100" required' : ""}><span class="dashboard-field-error" data-error-for="${name}" role="alert"></span></div></div>`;
    }
    function selectField(name, label, choices, selectedValue) {
        return `<div class="dashboard-form-row"><label for="dashboard-field-${name}">${label}</label><div class="dashboard-form-control"><select id="dashboard-field-${name}" class="form-select" name="${name}">${choices.map(([value, text]) => `<option value="${escapeHtml(value)}" ${String(value) === String(selectedValue ?? "") ? "selected" : ""}>${escapeHtml(text)}</option>`).join("")}</select><span class="dashboard-field-error" data-error-for="${name}" role="alert"></span></div></div>`;
    }
    function choicesWithCurrent(choices, id, title) {
        if (id && !choices.some(([value]) => String(value) === String(id))) {
            return [...choices, [id, title]];
        }
        return choices;
    }
    function workFields(type, item) {
        const properties = choicesWithCurrent(
            [["", "No property"], ...data.properties.map((property) => [property.id, property.name])],
            item?.property_id, item?.property,
        );
        const priorities = [[1, "Low"], [2, "Medium"], [3, "High"], [4, "Urgent"]];
        let html = formField("title", "Title", item?.title);
        html += `<div class="dashboard-form-row"><label for="dashboard-field-description">Description</label><div class="dashboard-form-control"><textarea id="dashboard-field-description" class="form-control" name="description" maxlength="1000">${escapeHtml(item?.description)}</textarea><span class="dashboard-field-error" data-error-for="description" role="alert"></span></div></div>`;
        if (type === "task") {
            const relationship = item?.issue_id ? "issue" : item?.property_id ? "property" : "standalone";
            html += selectField("relationship_type", "Related to", [["standalone", "Not linked"], ["property", "Property"], ["issue", "Issue"]], relationship);
            html += `<div data-relation="property">${selectField("property", "Property", properties, item?.property_id)}</div>`;
            const issues = choicesWithCurrent(
                [["", "No issue"], ...data.issues.map((issue) => [issue.id, issue.title])],
                item?.issue_id, item?.issue_title,
            );
            html += `<div data-relation="issue">${selectField("issue", "Issue", issues, item?.issue_id)}</div>`;
            html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
            html += formField("scheduled_date", "Scheduled date", item?.date, "date");
            html += formField("completion_deadline", "Completion deadline", item?.due, "date");
        } else if (type === "issue") {
            html += selectField("property", "Property", properties, item?.property_id);
            html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
            html += formField("resolution_deadline", "Resolve by", item?.due, "date");
        } else {
            html += selectField("property", "Property", properties, item?.property_id);
            html += formField("scheduled_date", "Date", item?.date || selected, "date");
            html += `<div class="dashboard-form-row"><span>Time</span><label class="dashboard-check"><input class="form-check-input" name="all_day" type="checkbox" ${item?.all_day ?? true ? "checked" : ""}> All day</label></div>`;
            html += `<div class="dashboard-event-time-row"><div data-time-field>${formField("start_time", "Start time (HH:MM)", item?.start_time)}</div>`;
            html += `<div data-time-field>${formField("end_time", "End time (HH:MM)", item?.end_time)}</div></div>`;
            html += `<div class="dashboard-form-row dashboard-requirements"><span>Requirements</span><div><label class="dashboard-check"><input class="form-check-input" name="user_participation_required" type="checkbox" ${item?.user_participation_required ? "checked" : ""}> My participation is required</label><label class="dashboard-check"><input class="form-check-input" name="user_presence_required" type="checkbox" ${item?.user_presence_required ? "checked" : ""}> My physical presence is required</label></div></div>`;
        }
        return html;
    }
    function openWork(type, id = null, proposedDate = null, returnFocus = document.activeElement) {
        const item = id ? findRecord(type, id) : null;
        recordTarget = {type, id};
        get("workDialogHeading").textContent = `${id ? "Edit" : "Add"} ${type}`;
        window.SearchableSelect?.destroyWithin(get("workFormFields"));
        get("workFormFields").innerHTML = workFields(type, item);
        window.SearchableSelect?.init(get("workFormFields"));
        if (proposedDate) get("workForm").elements.namedItem("scheduled_date").value = proposedDate;
        get("workFormErrors").textContent = "";
        updateRelationshipFields();
        updateEventTimeFields();
        get("workDialog")._dashboardReturnFocus = window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
        bootstrap.Modal.getOrCreateInstance(get("workDialog")).show();
    }
    const addEventForm = get("dashboardAddEventForm");
    const addEventModal = get("dashboardAddEventModal");
    function activateAddEventTab(name, {focus = false} = {}) {
        addEventForm.querySelectorAll("[data-event-tab]").forEach((tab) => {
            const active = tab.dataset.eventTab === name;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
            if (active && focus) tab.focus();
        });
        addEventForm.querySelectorAll("[data-event-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.eventPanel !== name;
        });
        addEventForm.querySelector(".event-form-body").scrollTop = 0;
    }
    function updateAddEventTime({clear = false} = {}) {
        const allDay = addEventForm.elements.namedItem("all_day");
        const timed = !allDay.checked;
        for (const name of ["start_time", "end_time"]) {
            const field = addEventForm.elements.namedItem(name);
            if (clear && allDay.checked) field.value = "";
            field.disabled = !timed;
        }
        addEventForm.querySelectorAll("[data-duration-choice]").forEach((choice) => {
            choice.checked = (choice.value === "all_day") === allDay.checked;
        });
    }
    function updateAddEventPresence() {
        const participation = addEventForm.elements.namedItem("user_participation_required");
        const presence = addEventForm.elements.namedItem("user_presence_required");
        presence.disabled = !participation.checked;
        if (!participation.checked) presence.checked = false;
    }
    function updateAddEventContacts() {
        const search = get("dashboardEventContactsSearch").value.trim().toLocaleLowerCase();
        const options = [...addEventForm.querySelectorAll("[data-contact-option]")];
        let matching = 0;
        let selectedCount = 0;
        options.forEach((option) => {
            option.hidden = !(option.dataset.searchText || option.textContent).toLocaleLowerCase().includes(search);
            if (!option.hidden) matching += 1;
            if (option.querySelector('input[type="checkbox"]')?.checked) selectedCount += 1;
        });
        addEventForm.querySelector("[data-contact-empty]").hidden = !search || matching > 0 || options.length === 0;
        addEventForm.querySelector("[data-contact-picker-status]").textContent = `${selectedCount} selected${search ? ` · ${matching} matching` : ""}`;
        addEventForm.querySelector("[data-contact-tab-count]").textContent = selectedCount;
    }
    function clearAddEventErrors() {
        addEventForm.querySelectorAll("[data-dashboard-event-error]").forEach((error) => error.remove());
        addEventForm.querySelectorAll('[aria-invalid="true"]').forEach((field) => field.removeAttribute("aria-invalid"));
    }
    function showAddEventErrors(error) {
        const errors = error.fieldErrors;
        if (!errors) {
            const message = document.createElement("p");
            message.className = "invalid-feedback d-block";
            message.dataset.dashboardEventError = "true";
            message.textContent = error.message;
            get("dashboardAddEventDetailsPanel").prepend(message);
            activateAddEventTab("details");
            return;
        }
        let firstField = null;
        for (const [name, messages] of Object.entries(errors)) {
            const panel = name === "contacts" ? get("dashboardAddEventParticipantsPanel") : get("dashboardAddEventDetailsPanel");
            const field = name === "contacts" ? get("dashboardEventContactsSearch") : addEventForm.elements.namedItem(name);
            const message = document.createElement("p");
            message.className = "invalid-feedback d-block";
            message.dataset.dashboardEventError = "true";
            message.textContent = messages.join(" ");
            if (field instanceof HTMLElement) {
                field.setAttribute("aria-invalid", "true");
                (name === "contacts" ? panel.querySelector(".event-contact-picker") : field.parentElement).append(message);
                firstField ||= field;
            } else panel.prepend(message);
        }
        activateAddEventTab(firstField?.name === "contacts" || firstField?.id === "dashboardEventContactsSearch" ? "participants" : "details");
        firstField?.focus();
    }
    function openAddEvent(returnFocus = document.activeElement) {
        addEventForm.reset();
        clearAddEventErrors();
        addEventForm.elements.namedItem("scheduled_date").value = selected || data.today;
        get("dashboardEventContactsSearch").value = "";
        window.SearchableSelect?.refresh(addEventForm.elements.namedItem("property"));
        updateAddEventTime();
        updateAddEventPresence();
        updateAddEventContacts();
        activateAddEventTab("details");
        addEventModal._dashboardReturnFocus = window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
        bootstrap.Modal.getOrCreateInstance(addEventModal).show();
    }
    function showWorkErrors(error) {
        const errors = error.fieldErrors;
        if (!errors) { get("workFormErrors").textContent = error.message; return; }
        const summary = [...(errors.__all__ || [])];
        let firstInvalid = null;
        for (const [name, messages] of Object.entries(errors)) {
            if (name === "__all__") continue;
            const field = get("workForm").elements.namedItem(name);
            const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find((element) => element.dataset.errorFor === name);
            if (!field || !slot || field.closest("[hidden]")) { summary.push(...messages); continue; }
            slot.textContent = messages.join(" ");
            slot.id = `workError_${name}`;
            field.setAttribute("aria-invalid", "true");
            field.setAttribute("aria-describedby", slot.id);
            field.classList.add("is-invalid");
            const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
            if (trigger) { trigger.setAttribute("aria-invalid", "true"); trigger.setAttribute("aria-describedby", slot.id); }
            firstInvalid ||= field;
        }
        get("workFormErrors").textContent = summary.join(" ");
        if (firstInvalid) (firstInvalid.closest(".app-select")?.querySelector(".app-select-trigger") || firstInvalid).focus();
    }
    function clearWorkErrors() {
        get("workFormErrors").textContent = "";
        get("workFormFields").querySelectorAll("[name]").forEach(clearFieldError);
    }
    function updateRelationshipFields() {
        const relation = get("workForm").elements.namedItem("relationship_type")?.value;
        get("workForm").querySelectorAll("[data-relation]").forEach((section) => {
            section.hidden = section.dataset.relation !== relation;
        });
    }
    function updateEventTimeFields({clear = false} = {}) {
        const allDay = get("workForm").elements.namedItem("all_day");
        get("workForm").querySelectorAll("[data-time-field]").forEach((section) => {
            const input = section.querySelector("input");
            if (clear && allDay?.checked) input.value = "";
            input.disabled = !!allDay?.checked;
        });
    }
    function openConfirm(type, id, action, returnFocus = document.activeElement) {
        confirmTarget = {type, id, action};
        const item = findRecord(type, id);
        const linkedCount = type === "issue" ? (action === "finish" ? item.active_linked_tasks : action === "delete" ? item.linked_tasks : 0) : 0;
        get("confirmLinkedTasksWrap").hidden = !linkedCount;
        get("confirmLinkedTasks").checked = false;
        get("confirmLinkedTasksLabel").textContent = action === "finish"
            ? `Also dismiss ${linkedCount} active linked task${linkedCount === 1 ? "" : "s"}`
            : `Also delete ${linkedCount} linked task${linkedCount === 1 ? "" : "s"}, including historical tasks`;
        const copy = action === "delete" ? {
            heading: `Delete ${type}?`,
            text: `This ${type} will be removed from your workspace.`,
            cancel: `Keep ${type}`,
            submit: `Delete ${type}`,
        } : action === "cancel" ? {
            heading: "Cancel event?",
            text: "The event will be marked as cancelled and retained in your history.",
            cancel: "Keep event",
            submit: "Cancel event",
        } : {
            heading: "Resolve issue?",
            text: "The issue will be marked as resolved and retained in your history.",
            cancel: "Keep issue",
            submit: "Resolve issue",
        };
        get("confirmHeading").textContent = copy.heading;
        get("confirmText").textContent = copy.text;
        get("confirmCancel").textContent = copy.cancel;
        get("confirmAction").textContent = copy.submit;
        get("confirmAction").classList.toggle("dashboard-danger-button", action === "delete");
        get("confirmError").textContent = "";
        get("confirmDialog")._dashboardReturnFocus = window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
        bootstrap.Modal.getOrCreateInstance(get("confirmDialog")).show();
    }
    async function changeDate(type, id, date, field = "date") {
        const item = findRecord(type, id);
        if (!item || (field === "deadline" ? item.due : item.date) === date) return {ok: true, changed: false};
        let result;
        try {
            result = await send({action: field, kind: type, id, date});
        } catch (error) { message(error.message, {error: true}); return {ok: false, error: error.message}; }
        if (result.changed === false) return {ok: true, changed: false};
        const label = {task: "Task", issue: "Issue", event: "Event"}[type];
        const verb = field === "deadline" ? "deadline moved" : type === "task" && !item.date ? "scheduled" : "rescheduled";
        message(`${label} ${verb}.`, {detail: prettyDate(date)});
        try { await load(); }
        catch { message("Date changed, but Dashboard could not refresh. Reload the page.", {error: true}); }
        return {ok: true, changed: true};
    }
    function moveDraggedTo(targetDate, item) {
        const record = findRecord(item.type, item.id);
        if (!record || (item.field === "deadline" ? record.due : record.date) === targetDate) return;
        if (item.type === "event" && !record.all_day) {
            openWork("event", item.id, targetDate);
            return;
        }
        changeDate(item.type, item.id, targetDate, item.field);
    }
    async function clearDraggedDate(item) {
        const action = item.field === "deadline" ? "clear_deadline" : "unschedule";
        const detail = item.field === "deadline" ? "deadline removed" : "unscheduled";
        const label = {task: "Task", issue: "Issue"}[item.type];
        try {
            const result = await send({action, kind: item.type, id: item.id});
            if (result.changed === false) return;
            kind = item.type;
            filter = item.field === "date" ? "unscheduled" : item.type === "issue" ? "undated" : "all";
            secondaryFilter = "any";
            shown = 40;
            expanded = null;
            get("workSearch").value = "";
            try { await load({keepScroll: false}); message(`${label} ${detail}.`); }
            catch { message(`${label} ${detail}, but Dashboard could not refresh. Reload the page.`, {error: true}); }
        } catch (error) { message(error.message, {error: true}); }
    }
    function closeActionMenus() {
        document.querySelectorAll(".dashboard-row-menu:popover-open").forEach((menu) => menu.hidePopover());
    }
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
        const width = menu.offsetWidth, height = menu.offsetHeight;
        menu.style.left = `${Math.max(8, Math.min(trigger.right - width, window.innerWidth - width - 8))}px`;
        menu.style.top = `${Math.max(8, trigger.bottom + height + 5 <= window.innerHeight ? trigger.bottom + 5 : trigger.top - height - 5)}px`;
    }
    function revealExpandedRow(row) {
        if (!row) return;
        window.WorkspaceReveal?.queueRange(
            row.querySelector(".dashboard-row-toggle"), row.querySelector(".dashboard-row-detail"),
        );
    }
    function clickRecord(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (!row) return;
        if (event.target.closest("[data-expandable-toggle]")) return;
        const type = row.dataset.kind, id = Number(row.dataset.id), area = row.dataset.area;
        const recordLink = event.target.closest('a[href]');
        if (recordLink?.textContent.trim() === "Open record" && area === "queue"
            && !event.defaultPrevented && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
            const state = window.history.state;
            window.history.replaceState({...(state && typeof state === "object" ? state : {}),
                pomDashboardReturn: {
                    url: `${window.location.pathname}${window.location.search}`,
                    kind, filter, secondaryFilter, shown, expanded,
                    search: get("workSearch").value, scrollTop: get("workList").scrollTop,
                },
            }, "", window.location.href);
        }
        const button = event.target.closest("[data-action]");
        if (button) {
            const action = button.dataset.action;
            if (action === "more") { openActionMenu(button); return; }
            const returnFocus = window.WorkspaceModalReturnFocus?.resolve(button) || button;
            closeActionMenus();
            if (action === "edit") openWork(type, id, null, returnFocus);
            else if (action === "finish" && type === "issue" && findRecord(type, id)?.active_linked_tasks) openConfirm(type, id, action, returnFocus);
            else if (action === "finish") performQuickAction(type, id);
            else openConfirm(type, id, action, returnFocus);
            return;
        }
        if (event.target.closest(".dashboard-row-toggle")) {
            const queueScroll = get("workList").scrollTop;
            const dayScroll = get("dayList").scrollTop;
            expanded = expanded === `${area}-${type}-${id}` ? null : `${area}-${type}-${id}`;
            renderQueue(); renderDay();
            get("workList").scrollTop = queueScroll;
            get("dayList").scrollTop = dayScroll;
            const list = area === "queue" ? get("workList") : get("dayList");
            const selectedRow = list.querySelector(`[data-area="${area}"][data-kind="${type}"][data-id="${id}"]`);
            selectedRow?.querySelector(".dashboard-row-toggle")?.focus({preventScroll: true});
            if (expanded) revealExpandedRow(selectedRow);
        }
    }
    function highlightDate(value) {
        document.querySelectorAll(".dashboard-day.linked-hover").forEach((day) => day.classList.remove("linked-hover"));
        if (value) document.querySelector(`.dashboard-day[data-day="${value}"]`)?.classList.add("linked-hover");
    }
    const operationsDropTarget = dashboard.querySelector(".dashboard-operations");
    function acceptsWorkDrop(item) {
        const record = item && findRecord(item.type, item.id);
        return Boolean(record && ((item.source === "day" && item.type === "task" && item.field === "date" && record.date)
            || (item.source === "due" && ["task", "issue"].includes(item.type) && item.field === "deadline" && record.due)));
    }
    function clearWorkDropState() {
        operationsDropTarget.classList.remove("accepts-drop", "drag-over");
        delete operationsDropTarget.dataset.dropHint;
    }
    function beginDrag(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (!row || !row.draggable || event.target.closest("a, input, select, textarea, .dashboard-row-actions")) return;
        dragged = {type: row.dataset.kind, id: Number(row.dataset.id), source: row.dataset.area,
            field: row.dataset.area === "due" || row.dataset.kind === "issue" ? "deadline" : "date"};
        event.dataTransfer.setData("text/plain", `${dragged.type}:${dragged.id}`);
        event.dataTransfer.effectAllowed = "move";
        if (acceptsWorkDrop(dragged)) {
            operationsDropTarget.dataset.dropHint = dragged.field === "deadline" ? "Drop here to remove the deadline" : "Drop here to unschedule the task";
            operationsDropTarget.classList.add("accepts-drop");
        }
    }

    document.querySelectorAll("[data-kind][role=tab]").forEach((button) => button.addEventListener("click", () => {
        kind = button.dataset.kind; filter = "all"; secondaryFilter = "any"; shown = 40; expanded = null;
        get("workSearch").value = ""; get("workList").scrollTop = 0; renderQueue();
    }));
    document.querySelectorAll("[data-day-tab]").forEach((button) => button.addEventListener("click", () => {
        dayTab = button.dataset.dayTab;
        expanded = null;
        dayScroll = 0;
        get("dayList").scrollTop = 0;
        renderDay();
    }));
    dashboard.querySelectorAll("[data-dashboard-panel]").forEach((button) => button.addEventListener("click", () => activatePanel(button.dataset.dashboardPanel)));
    get("dayViewToggle").addEventListener("click", () => activatePanel("day"));
    get("notesViewToggle").addEventListener("click", () => activatePanel("notes"));
    get("workSearch").addEventListener("input", () => { shown = 40; get("workList").scrollTop = 0; renderQueue(); });
    get("workFilter").addEventListener("change", (event) => { filter = event.target.value; shown = 40; get("workList").scrollTop = 0; renderQueue(); });
    get("workSecondaryFilter").addEventListener("change", (event) => {
        secondaryFilter = event.target.value;
        shown = 40; get("workList").scrollTop = 0; renderQueue();
    });
    get("workList").addEventListener("scroll", appendMore);
    for (const list of [get("workList"), get("dayList")]) list.addEventListener("scroll", closeActionMenus);
    window.addEventListener("resize", () => {
        syncPanelNavigation();
        closeActionMenus();
        syncDescriptionControls(get("workList"));
        if (rightView === "day") syncDescriptionControls(get("dayList"));
    });
    syncPanelNavigation();
    document.addEventListener("toggle", (event) => {
        if (!event.target.classList?.contains("dashboard-row-menu")) return;
        const trigger = document.querySelector(`[aria-controls="${event.target.id}"]`);
        if (trigger) trigger.setAttribute("aria-expanded", String(event.newState === "open"));
    }, true);
    get("workList").addEventListener("click", clickRecord);
    get("dayList").addEventListener("click", clickRecord);
    for (const list of [get("workList"), get("dayList")]) {
        list.addEventListener("pointerdown", (event) => {
            const button = event.target.closest('[data-action="more"]');
            if (!button) return;
            const menu = document.getElementById(button.getAttribute("aria-controls"));
            button.dataset.dashboardMenuWasOpen = String(Boolean(menu && menu.matches(":popover-open")));
        }, true);
    }
    get("workList").addEventListener("pointerover", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row) highlightDate(row.dataset.scheduledDate);
    });
    get("workList").addEventListener("pointerout", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row && !row.contains(event.relatedTarget)) highlightDate(null);
    });
    for (const area of [get("workList"), get("dayList")]) {
        area.addEventListener("dragstart", beginDrag);
        area.addEventListener("dragend", () => {
            dragged = null; highlightDate(null);
            clearWorkDropState();
            document.querySelectorAll(".dashboard-day.drag-over").forEach((day) => day.classList.remove("drag-over"));
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
        if (!operationsDropTarget.contains(event.relatedTarget)) operationsDropTarget.classList.remove("drag-over");
    });
    operationsDropTarget.addEventListener("drop", (event) => {
        if (!acceptsWorkDrop(dragged)) return;
        event.preventDefault();
        const item = dragged;
        dragged = null;
        clearWorkDropState();
        clearDraggedDate(item);
    });
    get("dashboard").querySelectorAll("[data-calendar-filter]").forEach((checkbox) => {
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
        event.preventDefault(); day.classList.add("drag-over");
    });
    get("calendarGrid").addEventListener("dragleave", (event) => {
        const day = event.target.closest("[data-day]");
        if (day && !day.contains(event.relatedTarget)) day.classList.remove("drag-over");
    });
    get("calendarGrid").addEventListener("drop", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day || !canDropOnDate(dragged, day.dataset.day)) return;
        event.preventDefault();
        const item = dragged; dragged = null;
        day.classList.remove("drag-over");
        moveDraggedTo(day.dataset.day, item);
    });
    function acceptsDayDrop(item) {
        return item && (dayTab === "tasks" && item.type === "task" && item.field === "date" ||
            dayTab === "deadlines" && item.field === "deadline" ||
            dayTab === "events" && item.type === "event");
    }
    async function performQuickAction(type, id) {
        const key = `${type}:${id}`;
        if (quickPending.has(key)) return;
        quickPending.add(key);
        try {
            const result = await send({action: "finish", kind: type, id});
            const title = {task: "Task completed.", issue: "Issue resolved.", event: "Event marked as occurred."}[type];
            if (result.undo_token) showUndo(type, id, result.undo_token, title);
            else message(title);
            try { await load(); }
            catch { message("Action succeeded, but Dashboard could not refresh. Reload the page.", {error: true}); }
        } catch (error) { message(error.message, {error: true}); }
        finally { quickPending.delete(key); }
    }
    function canDropOnDate(item, date) {
        const record = item && findRecord(item.type, item.id);
        return !!record && (item.field === "deadline" ? record.due : record.date) !== date;
    }
    get("dayList").addEventListener("dragover", (event) => { if (acceptsDayDrop(dragged) && canDropOnDate(dragged, selected)) { event.preventDefault(); get("dashboard").querySelector(".dashboard-day-plan").classList.add("drag-over"); } });
    get("dayList").addEventListener("dragleave", (event) => { if (!get("dayList").contains(event.relatedTarget)) get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over"); });
    get("dayList").addEventListener("drop", (event) => {
        if (!acceptsDayDrop(dragged) || !canDropOnDate(dragged, selected)) return;
        event.preventDefault();
        const item = dragged; dragged = null;
        get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over");
        moveDraggedTo(selected, item);
    });
    function setPeriod(year, monthNumber) {
        month = new Date(Date.UTC(year, monthNumber, 1));
        if (!selected.startsWith(isoDate(month).slice(0, 7))) selected = isoDate(month);
        renderCalendar(); renderDay();
        get("calendarGrid").parentElement.scrollTop = 0;
    }
    get("calendarMonth").addEventListener("change", () => setPeriod(month.getUTCFullYear(), Number(get("calendarMonth").value)));
    get("calendarYear").addEventListener("change", () => setPeriod(Number(get("calendarYear").value), month.getUTCMonth()));
    get("previousPeriod").addEventListener("click", () => setPeriod(month.getUTCFullYear(), month.getUTCMonth() - 1));
    get("nextPeriod").addEventListener("click", () => setPeriod(month.getUTCFullYear(), month.getUTCMonth() + 1));
    get("calendarToday").addEventListener("click", () => selectDay(data.today));
    function closeAddMenu({restoreFocus = false} = {}) {
        get("dashboardAddMenu").hidden = true;
        get("dashboardAddToggle").setAttribute("aria-expanded", "false");
        if (restoreFocus) get("dashboardAddToggle").focus();
    }
    get("dashboardAddToggle").addEventListener("click", () => {
        const opening = get("dashboardAddMenu").hidden;
        get("dashboardAddMenu").hidden = !opening;
        get("dashboardAddToggle").setAttribute("aria-expanded", String(opening));
    });
    document.querySelectorAll("[data-add]").forEach((button) => button.addEventListener("click", () => {
        const returnFocus = window.WorkspaceModalReturnFocus?.resolve(button) || button;
        closeAddMenu();
        if (button.dataset.add === "event") openAddEvent(returnFocus);
        else openWork(button.dataset.add, null, null, returnFocus);
    }));
    addEventForm.querySelectorAll("[data-event-tab]").forEach((tab, index, tabs) => {
        tab.addEventListener("click", () => activateAddEventTab(tab.dataset.eventTab));
        tab.addEventListener("keydown", (event) => {
            const next = event.key === "ArrowRight" ? tabs[(index + 1) % tabs.length]
                : event.key === "ArrowLeft" ? tabs[(index - 1 + tabs.length) % tabs.length]
                    : event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[tabs.length - 1] : null;
            if (next) { event.preventDefault(); activateAddEventTab(next.dataset.eventTab, {focus: true}); }
        });
    });
    addEventForm.querySelectorAll("[data-duration-choice]").forEach((choice) => choice.addEventListener("change", () => {
        addEventForm.elements.namedItem("all_day").checked = choice.value === "all_day";
        updateAddEventTime({clear: choice.value === "all_day"});
    }));
    addEventForm.elements.namedItem("user_participation_required").addEventListener("change", updateAddEventPresence);
    addEventForm.elements.namedItem("user_presence_required").addEventListener("change", (event) => {
        if (event.target.checked) {
            addEventForm.elements.namedItem("user_participation_required").checked = true;
            updateAddEventPresence();
        }
    });
    get("dashboardEventContactsSearch").addEventListener("input", updateAddEventContacts);
    get("dashboardEventContactsSearch").addEventListener("keydown", (event) => {
        if (event.key === "Enter") event.preventDefault();
    });
    addEventForm.querySelector(".event-contact-picker").addEventListener("change", updateAddEventContacts);
    addEventForm.addEventListener("invalid", (event) => {
        const panel = event.target.closest("[data-event-panel]");
        if (panel?.hidden) activateAddEventTab(panel.dataset.eventPanel);
    }, true);
    addEventForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (eventAddPending) return;
        eventAddPending = true;
        clearAddEventErrors();
        const saveButton = addEventForm.querySelector('[type="submit"]');
        saveButton.disabled = true;
        const fields = new FormData(addEventForm);
        fields.set("action", "add");
        fields.set("kind", "event");
        try {
            const result = await send(fields);
            eventAddPending = false;
            bootstrap.Modal.getOrCreateInstance(addEventModal).hide();
            kind = "event";
            filter = "all";
            secondaryFilter = "any";
            get("workSearch").value = "";
            shown = 40;
            expanded = null;
            try {
                await load({keepScroll: false});
                const index = visibleRecords().findIndex((item) => item.id === result.id);
                if (index >= 0) {
                    shown = Math.max(shown, index + 1);
                    expanded = `queue-event-${result.id}`;
                    renderQueue();
                    revealExpandedRow(get("workList").querySelector(`[data-area="queue"][data-id="${result.id}"]`));
                }
                message("Event added.");
            } catch { message("Event added, but Dashboard could not refresh. Reload the page.", {error: true}); }
        } catch (error) { showAddEventErrors(error); }
        finally { eventAddPending = false; saveButton.disabled = false; }
    });
    document.addEventListener("pointerdown", (event) => {
        if (!get("dashboardAddMenu").hidden && !event.target.closest(".dashboard-add-wrap")) closeAddMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !get("dashboardAddMenu").hidden) closeAddMenu({restoreFocus: true});
    });
    get("workForm").addEventListener("change", (event) => {
        if (event.target.name === "relationship_type") updateRelationshipFields();
        if (event.target.name === "all_day") updateEventTimeFields({clear: event.target.checked});
        if (event.target.name === "user_presence_required" && event.target.checked) {
            get("workForm").elements.namedItem("user_participation_required").checked = true;
        }
        if (event.target.name === "user_participation_required" && !event.target.checked) {
            get("workForm").elements.namedItem("user_presence_required").checked = false;
        }
    });
    function clearFieldError(field) {
        if (!field?.name) return;
        field.classList.remove("is-invalid");
        field.removeAttribute("aria-invalid");
        field.removeAttribute("aria-describedby");
        const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
        trigger?.removeAttribute("aria-invalid");
        trigger?.removeAttribute("aria-describedby");
        const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find((element) => element.dataset.errorFor === field.name);
        if (slot) slot.textContent = "";
    }
    get("workForm").addEventListener("input", (event) => clearFieldError(event.target));
    get("workForm").addEventListener("change", (event) => clearFieldError(event.target));
    get("workForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const saveButton = get("workForm").querySelector('[type="submit"]');
        if (workPending) return;
        workPending = true;
        clearWorkErrors();
        saveButton.disabled = true;
        const fields = new FormData(get("workForm"));
        fields.set("action", recordTarget.id ? "edit" : "add");
        fields.set("kind", recordTarget.type);
        if (recordTarget.id) fields.set("id", recordTarget.id);
        if (recordTarget.type === "task") {
            if (fields.get("relationship_type") !== "property") fields.set("property", "");
            if (fields.get("relationship_type") !== "issue") fields.set("issue", "");
        }
        try {
            const operation = recordTarget.id ? "updated" : "added";
            const label = {task: "Task", issue: "Issue", event: "Event"}[recordTarget.type];
            const result = await send(fields);
            workPending = false;
            bootstrap.Modal.getOrCreateInstance(get("workDialog")).hide();
            if (result.changed !== false) {
                kind = recordTarget.type; filter = "all"; secondaryFilter = "any";
                if (operation === "added") {
                    get("workSearch").value = "";
                    shown = 40;
                    expanded = null;
                }
                try {
                    await load({keepScroll: operation !== "added"});
                    if (operation === "added") {
                        const index = visibleRecords().findIndex((item) => item.id === result.id);
                        if (index >= 0) {
                            shown = Math.max(shown, index + 1);
                            expanded = `queue-${kind}-${result.id}`;
                            renderQueue();
                            revealExpandedRow(get("workList").querySelector(`[data-area="queue"][data-id="${result.id}"]`));
                        }
                    }
                    message(`${label} ${operation}.`);
                }
                catch { message(`${label} ${operation}, but Dashboard could not refresh. Reload the page.`, {error: true}); }
            }
        } catch (error) { showWorkErrors(error); }
        finally { workPending = false; saveButton.disabled = false; }
    });
    get("confirmAction").addEventListener("click", async () => {
        const confirmButton = get("confirmAction");
        if (confirmPending) return;
        confirmPending = true;
        confirmButton.disabled = true;
        try {
            const {type, action} = confirmTarget;
            await send({action, kind: type, id: confirmTarget.id,
                confirm_linked_tasks: action === "finish" && type === "issue" ? "yes" : "",
                affect_linked_tasks: get("confirmLinkedTasks").checked ? "yes" : ""});
            confirmPending = false;
            bootstrap.Modal.getOrCreateInstance(get("confirmDialog")).hide();
            const label = {task: "Task", issue: "Issue", event: "Event"}[type];
            const verb = action === "finish" ? {task: "completed", issue: "resolved", event: "marked as occurred"}[type] : action === "cancel" ? "cancelled" : "deleted";
            try { await load(); message(`${label} ${verb}.`); }
            catch { message(`${label} ${verb}, but Dashboard could not refresh. Reload the page.`, {error: true}); }
        } catch (error) { get("confirmError").textContent = error.message; }
        finally { confirmPending = false; confirmButton.disabled = false; }
    });
    document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => {
        const dialog = button.closest(".dashboard-dialog");
        if ((dialog.id === "workDialog" && workPending) || (dialog.id === "confirmDialog" && confirmPending)) return;
        bootstrap.Modal.getOrCreateInstance(dialog).hide();
    }));
    for (const [id, pending] of [["workDialog", () => workPending], ["confirmDialog", () => confirmPending]]) {
        get(id).addEventListener("hide.bs.modal", (event) => { if (pending()) event.preventDefault(); });
        get(id).addEventListener("hidden.bs.modal", () => {
            const previous = get(id)._dashboardReturnFocus;
            window.WorkspaceModalReturnFocus?.restore(previous);
        });
    }
    get("workDialog").addEventListener("shown.bs.modal", () => get("workForm").elements.namedItem("title").focus());
    addEventModal.addEventListener("hide.bs.modal", (event) => { if (eventAddPending) event.preventDefault(); });
    addEventModal.addEventListener("hidden.bs.modal", () => {
        const previous = addEventModal._dashboardReturnFocus;
        window.WorkspaceModalReturnFocus?.restore(previous);
    });
    addEventModal.addEventListener("shown.bs.modal", () => addEventForm.elements.namedItem("title").focus());
    get("confirmDialog").addEventListener("shown.bs.modal", () => get("confirmCancel").focus());

    get("noteForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await send({action: "add", kind: "note", content: get("noteContent").value.trim()});
            get("noteContent").value = "";
            try { await load(); get("notesList").scrollTop = 0; message("Note added."); }
            catch { message("Note added, but Dashboard could not refresh. Reload the page.", {error: true}); }
        } catch (error) { message(error.message, {error: true}); }
    });
    get("notesList").addEventListener("click", async (event) => {
        const button = event.target.closest("[data-note-action]");
        if (!button) return;
        const note = button.closest("[data-note]");
        const id = Number(note.dataset.note);
        const action = button.dataset.noteAction;
        if (action === "edit") { editingNote = id; renderNotes(); get("notesList").querySelector(`[data-note="${id}"] textarea`).focus(); return; }
        if (action === "cancel") { editingNote = null; renderNotes(); return; }
        const currentNote = data.notes.find((item) => item.id === id);
        const editedContent = action === "save" ? note.querySelector("textarea").value.trim() : "";
        if (action === "save" && currentNote && editedContent === currentNote.content) {
            editingNote = null; renderNotes(); return;
        }
        try {
            let result;
            if (action === "delete") result = await send({action: "delete", kind: "note", id});
            else {
                result = await send({action: "edit", kind: "note", id, content: editedContent});
                if (result.changed === false) { editingNote = null; renderNotes(); return; }
            }
            editingNote = null;
            try { await load(); if (result.undo_token) showUndo("note", id, result.undo_token, "Note deleted."); else message("Note updated."); }
            catch { message("Note changed, but Dashboard could not refresh. Reload the page.", {error: true}); }
        } catch (error) { message(error.message, {error: true}); }
    });
    get("dashboardToastClose").addEventListener("click", hideToast);
    const toastElement = get("dashboardToast");
    toastElement.addEventListener("mouseenter", () => { if (toastPauseable) stopToastTimer(); });
    toastElement.addEventListener("mouseleave", () => { if (toastPauseable) startToastTimer(); });
    toastElement.addEventListener("focusin", () => { if (toastPauseable) stopToastTimer(); });
    toastElement.addEventListener("focusout", () => {
        queueMicrotask(() => { if (toastPauseable && !toastElement.contains(document.activeElement)) startToastTimer(); });
    });
    document.addEventListener("pointerdown", (event) => {
        if (!toastElement.hidden && !toastPauseable && !toastElement.classList.contains("error")
            && !toastElement.contains(event.target)) hideToast();
    });
    load().catch((error) => message(error.message, {error: true}));
});

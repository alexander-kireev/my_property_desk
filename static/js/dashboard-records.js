// Format Dashboard dates, filter records and build row HTML from the supplied data.
(() => {
    const escapeHtml = (value) =>
        String(value ?? "").replace(
            /[&<>"']/g,
            (character) =>
                ({
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#39;",
                })[character],
        );

    // Use UTC for date-only values so the browser timezone cannot change their calendar day.
    const parseDate = (value) => new Date(`${value}T12:00:00Z`);

    const isoDate = (value) => value.toISOString().slice(0, 10);

    const prettyDate = (value) =>
        parseDate(value)
            .toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
                timeZone: "UTC",
            })
            .replace("Sept", "Sep");

    const longDate = (value) =>
        parseDate(value).toLocaleDateString("en-GB", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "UTC",
        });

    const mondayOf = (value) => {
        const day = parseDate(value);
        day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
        return day;
    };

    // Apply the Operations list filters without changing the server's record order.
    function visibleRecords(records, { kind, filter, secondaryFilter, search, today }) {
        search = search.trim().toLowerCase();
        const weekEnd = new Date(mondayOf(today));
        weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
        return records[kind].filter((item) => {
            if (
                search &&
                !`${item.title} ${item.description} ${item.property} ${item.issue_title || ""}`
                    .toLowerCase()
                    .includes(search)
            )
                return false;
            if (kind === "task") {
                if (filter === "unscheduled" && item.date) return false;
                if (filter === "today" && item.date !== today) return false;
                if (filter === "other" && (!item.date || item.date === today)) return false;
                if (secondaryFilter === "high" && !["High", "Urgent"].includes(item.priority))
                    return false;
            } else if (kind === "issue") {
                if (filter === "overdue" && (!item.due || item.due >= today)) return false;
                if (
                    filter === "week" &&
                    (!item.due ||
                        item.due < isoDate(mondayOf(today)) ||
                        item.due > isoDate(weekEnd))
                )
                    return false;
                if (filter === "undated" && item.due) return false;
                if (secondaryFilter === "high" && !["High", "Urgent"].includes(item.priority))
                    return false;
            } else {
                if (
                    filter === "week" &&
                    (item.date < isoDate(mondayOf(today)) || item.date > isoDate(weekEnd))
                )
                    return false;
                if (filter === "month" && !item.date.startsWith(today.slice(0, 7))) return false;
            }
            return true;
        });
    }

    function badge(item) {
        if (item.priority)
            return `<span class="work-pill work-pill--priority-${item.priority_id}" aria-label="${escapeHtml(item.priority)} priority" title="${escapeHtml(item.priority)} priority">${escapeHtml(item.priority)}</span>`;
        if (item.kind === "event")
            return `<span class="work-pill work-pill--${item.state === "scheduled" ? "active" : "terminal"}">${escapeHtml(item.state.charAt(0).toUpperCase() + item.state.slice(1))}</span>`;
        return "";
    }

    // One action set serves both the wide row and its compact overflow menu.
    function rowActions(item, key, fullUrl) {
        const finish = { task: "Complete", issue: "Resolve", event: "Mark occurred" }[item.kind];
        const menuId = `dashboard-actions-${key}`;
        let cancelButton = "";
        let cancelMenuItem = "";
        if (item.kind === "event") {
            cancelButton = `<button type="button"
                class="dashboard-optional-action btn btn-outline-secondary btn-sm"
                data-action="cancel">Cancel</button>`;
            cancelMenuItem = '<button type="button" data-action="cancel">Cancel event</button>';
        }
        return `<div class="dashboard-row-actions">
            <button type="button" class="dashboard-action-primary btn theme-action btn-sm"
                data-action="finish">${finish}</button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-action="edit">Edit</button>
            ${cancelButton}
            <button type="button"
                class="dashboard-optional-action dashboard-action-danger btn btn-outline-danger btn-sm"
                data-action="delete">Delete</button>
            <a class="dashboard-optional-action btn btn-outline-secondary btn-sm"
                href="${escapeHtml(fullUrl)}">Open record</a>
            <button type="button" class="dashboard-more-button btn btn-outline-secondary btn-sm"
                data-action="more" aria-label="More actions for ${escapeHtml(item.title)}"
                aria-controls="${menuId}" aria-expanded="false">⋮</button>
            <div class="dashboard-row-menu" id="${menuId}" popover="auto">
                ${cancelMenuItem}
                <a href="${escapeHtml(fullUrl)}">Open record</a>
                <button type="button" class="dashboard-action-danger" data-action="delete">Delete</button>
            </div>
        </div>`;
    }

    function eventTime(item) {
        let text = escapeHtml(item.start_time);
        if (item.end_time) text += `–${escapeHtml(item.end_time)}`;
        return text;
    }

    function rowTiming(item, today) {
        if (item.kind === "event") {
            const time = item.all_day ? "All day" : eventTime(item);
            return `<span>${prettyDate(item.date)} ·</span><span>${time}</span>`;
        }
        if (item.due) {
            const days = Math.round((parseDate(item.due) - parseDate(today)) / 86400000);
            let label = item.kind === "issue" ? "Resolve by" : "Due";
            if (days < 0) label = "Overdue";
            else if (days <= 3) label = "Due soon";
            return `${label} ${prettyDate(item.due)}`;
        }
        if (item.kind === "issue") return "No target date";
        if (item.date) return `Scheduled ${prettyDate(item.date)}`;
        return "No date";
    }

    function rowSummary(item, area, today) {
        const chevron = `<span class="dashboard-row-chevron">
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="m5 9 7 7 7-7"/>
            </svg>
        </span>`;
        let typeCue = "";
        if (area === "due") {
            const symbol = { task: "▤", issue: "◇" }[item.kind];
            const label = item.kind === "task" ? "Task" : "Issue";
            typeCue = `<span class="dashboard-type-cue"><span aria-hidden="true">${symbol}</span> ${label}</span>`;
        }
        const overdueClass = item.due && item.due < today ? " is-overdue" : "";
        const timing = rowTiming(item, today);
        if (item.kind === "task") {
            const context = item.issue_id ? item.issue_title : item.property;
            const contextAttribute = context
                ? `title="${escapeHtml(context)}"`
                : 'aria-hidden="true"';
            return `<span class="dashboard-task-copy">
                <strong class="dashboard-task-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong>
                <small class="dashboard-task-context" ${contextAttribute}>${typeCue}${escapeHtml(context)}</small>
            </span>
            <span class="dashboard-task-meta">
                ${badge(item)}
                <span class="dashboard-task-timing${overdueClass}">${timing}</span>
            </span>
            ${chevron}`;
        }
        let contextAttribute = "";
        if (item.property) contextAttribute = `title="${escapeHtml(item.property)}"`;
        else if (!typeCue) contextAttribute = 'aria-hidden="true"';
        const eventClass = item.kind === "event" ? " dashboard-event-side" : "";
        return `<span class="dashboard-row-main">
            <strong title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong>
            <small class="dashboard-row-context" ${contextAttribute}>${typeCue}${escapeHtml(item.property)}</small>
        </span>
        <span class="dashboard-row-side${eventClass}">
            ${badge(item)}
            <span class="dashboard-row-timing${overdueClass}">${timing}</span>
        </span>
        ${chevron}`;
    }

    function rowFacts(item) {
        const facts = [];
        if (item.property && !(item.kind === "task" && item.issue_id)) {
            facts.push(`<span class="dashboard-property-fact" title="${escapeHtml(item.property)}">
                <span class="dashboard-property-name">${escapeHtml(item.property)}</span>
            </span>`);
        }
        if (item.issue_id) {
            facts.push(`<span class="dashboard-issue-fact" title="${escapeHtml(item.issue_title)}">
                <span class="dashboard-issue-title">${escapeHtml(item.issue_title)}</span>
            </span>`);
        }
        if (item.date) {
            const label = item.kind === "event" ? "Date" : "Scheduled";
            facts.push(`<span>${label} ${prettyDate(item.date)}</span>`);
        } else if (item.kind === "task") facts.push("<span>Unscheduled</span>");
        if (item.due) {
            const label = item.kind === "issue" ? "Resolve by" : "Due";
            facts.push(`<span>${label} ${prettyDate(item.due)}</span>`);
        }
        if (item.kind === "event" && item.start_time) facts.push(`<span>${eventTime(item)}</span>`);
        return facts.join("");
    }

    function rowDescription(item, key) {
        if (!item.description) return '<p class="text-body-secondary">No description.</p>';
        return `<div class="expandable-text" data-expandable-text>
            <p class="expandable-text-content" id="dashboard-description-${key}" data-expandable-content>${escapeHtml(item.description)}</p>
            <button type="button" class="expandable-text-toggle"
                aria-controls="dashboard-description-${key}" aria-expanded="false"
                hidden data-expandable-toggle>See more</button>
        </div>`;
    }

    /**
     * Build a row for Operations (queue), Selected day (day) or Deadlines (due).
     * The area-kind-id key stays unique when a record appears in more than one list.
     * today is a YYYY-MM-DD date; urls supplies the three workspace destinations.
     */
    function recordRow(item, area, { expanded, today, urls }) {
        const key = `${area}-${item.kind}-${item.id}`;
        const isExpanded = expanded === key;
        const canDrag = ["task", "event", "issue"].includes(item.kind);
        const fullUrl = `${urls[`${item.kind}Url`]}?selected=${item.id}&open=detail`;
        const rowClass = area === "queue" ? "dashboard-work-row" : "dashboard-day-row";
        const taskClass = item.kind === "task" ? " dashboard-task-toggle" : "";
        const date = area === "due" && item.due ? item.due : item.date;
        const dateAttribute = date ? `data-scheduled-date="${date}"` : "";
        const action = isExpanded ? "Collapse" : "Expand";
        return `<article class="list-group-item ${rowClass}"
            data-area="${area}" data-kind="${item.kind}" data-id="${item.id}"
            ${canDrag ? 'draggable="true"' : ""} ${dateAttribute}>
            <button class="dashboard-row-toggle${taskClass} list-group-item-action" type="button"
                aria-expanded="${isExpanded}" aria-label="${action} ${escapeHtml(item.title)}">
                ${rowSummary(item, area, today)}
            </button>
            <div class="dashboard-row-detail" ${isExpanded ? "" : "hidden"}>
                ${rowDescription(item, key)}
                <div class="dashboard-row-facts">${rowFacts(item)}</div>
                ${rowActions(item, key, fullUrl)}
            </div>
        </article>`;
    }

    window.DashboardRecords = {
        escapeHtml,
        parseDate,
        isoDate,
        prettyDate,
        longDate,
        mondayOf,
        visibleRecords,
        recordRow,
    };
})();

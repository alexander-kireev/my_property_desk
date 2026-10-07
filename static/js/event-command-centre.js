// Handle Event list/calendar navigation, phone details and filters. Event forms use event-form.js.
document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("eventWorkspace");
    const parameters = new URLSearchParams(window.location.search);

    // The view can change without navigation; submit the current view with participants.
    const participantsModal = document.getElementById("addEventContactsModal");
    participantsModal?.addEventListener("show.bs.modal", () => {
        const form = participantsModal.querySelector("[data-participant-origin]");
        if (!form) return;
        const action = new URL(form.action);
        const current = new URL(window.location.href);
        for (const name of ["view", "agenda_day", "tab", "open"]) {
            action.searchParams.delete(name);
            if (current.searchParams.has(name)) {
                action.searchParams.set(name, current.searchParams.get(name));
            }
        }
        form.action = action.href;
    });

    if (parameters.get("focus") === "participants") {
        const controls = document.querySelectorAll('[data-bs-target="#addEventContactsModal"]');
        requestAnimationFrame(() => {
            const visibleControl = [...controls].find((control) => control.getClientRects().length);
            visibleControl?.focus();
        });
    }

    // Switch between the phone list and calendar without leaving the page.
    document.querySelectorAll("[data-event-mobile-view]").forEach((button) => {
        button.addEventListener("click", () => {
            const calendar = button.dataset.eventMobileView === "calendar";
            workspace?.classList.toggle("show-mobile-calendar", calendar);
            document.querySelectorAll("[data-event-mobile-view]").forEach((choice) => {
                const active = choice === button;
                choice.classList.toggle("active", active);
                choice.setAttribute("aria-pressed", String(active));
            });
            const url = new URL(window.location.href);
            if (calendar) url.searchParams.set("view", "calendar");
            else url.searchParams.delete("view");
            window.history.replaceState(window.history.state, "", url);
        });
    });

    if (workspace && parameters.get("open") === "detail" && parameters.has("selected")) {
        workspace.classList.add("show-detail");
    }

    const listTab = document.querySelector("[data-event-list-tab]");
    document
        .querySelectorAll(
            '[data-bs-target="#eventCalendarPanel"], [data-bs-target="#eventDetailsPanel"]',
        )
        .forEach((tab) => {
            tab.addEventListener("shown.bs.tab", () => {
                if (listTab)
                    listTab.value =
                        tab.dataset.bsTarget === "#eventCalendarPanel" ? "calendar" : "details";
                const url = new URL(window.location.href);
                url.searchParams.set(
                    "tab",
                    tab.dataset.bsTarget === "#eventCalendarPanel" ? "calendar" : "details",
                );
                window.history.replaceState(window.history.state, "", url);
            });
        });

    // Date clicks open the agenda on phones and select a day on desktop.
    document.querySelectorAll("[data-calendar-day-href]").forEach((day) => {
        day.addEventListener("click", (event) => {
            if (
                event.button !== 0 ||
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey
            )
                return;
            const dateLink = event.target.closest(".event-calendar-day-number");
            if (window.matchMedia("(max-width: 860px)").matches) {
                if (event.target.closest("a, button") && !dateLink) return;
                event.preventDefault();
                window.location.assign(day.dataset.calendarAgendaHref);
                return;
            }
            if (event.target.closest("a, button")) return;
            window.location.assign(day.dataset.calendarDayHref);
        });
    });

    // Expand phone rows separately in the event list and the calendar agenda.
    document
        .querySelectorAll(".event-command-entry > [data-workspace-scroll-row]")
        .forEach((row) => {
            row.addEventListener("click", (event) => {
                if (
                    !window.matchMedia("(max-width: 860px)").matches ||
                    event.button !== 0 ||
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey
                )
                    return;
                const expanded = row.nextElementSibling;
                if (expanded?.classList.contains("event-mobile-expanded")) {
                    event.preventDefault();
                    expanded.hidden = !expanded.hidden;
                    row.setAttribute("aria-expanded", String(!expanded.hidden));
                    if (!expanded.hidden)
                        window.WorkspaceReveal?.queueRange(row, expanded, () =>
                            window.ExpandableText?.refresh(expanded),
                        );
                } else {
                    event.preventDefault();
                    window.location.assign(row.href);
                }
            });
        });

    document
        .querySelectorAll(".event-mobile-agenda-entry > .event-mobile-agenda-row")
        .forEach((row) => {
            row.addEventListener("click", (event) => {
                if (
                    !window.matchMedia("(max-width: 860px)").matches ||
                    event.button !== 0 ||
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey
                )
                    return;
                event.preventDefault();
                const expanded = row.nextElementSibling;
                if (expanded?.classList.contains("event-mobile-expanded")) {
                    expanded.hidden = !expanded.hidden;
                    row.setAttribute("aria-expanded", String(!expanded.hidden));
                    row.parentElement.classList.toggle("is-expanded", !expanded.hidden);
                    if (!expanded.hidden)
                        window.WorkspaceReveal?.queueRange(row, expanded, () =>
                            window.ExpandableText?.refresh(expanded),
                        );
                } else {
                    window.location.assign(row.href);
                }
            });
        });

    if (
        workspace?.classList.contains("show-mobile-calendar") &&
        window.matchMedia("(max-width: 860px)").matches &&
        window.performance?.getEntriesByType?.("navigation")?.[0]?.type !== "back_forward"
    ) {
        const selectedAgendaRow = document.querySelector(
            ".event-mobile-agenda-entry.is-expanded > .event-mobile-agenda-row",
        );
        if (selectedAgendaRow) {
            const expanded = selectedAgendaRow.nextElementSibling;
            window.WorkspaceReveal?.queueRange(selectedAgendaRow, expanded, () =>
                window.ExpandableText?.refresh(expanded),
            );
        }
    }

    // Filters: remove a choice or prevent incompatible participation/presence settings.
    const participationFilter = document.getElementById("eventParticipation");
    const presenceFilter = document.getElementById("eventPresence");
    const compatibilityNote = document.getElementById("eventFilterCompatibility");
    const filterForm = document.getElementById("eventFilterForm");
    filterForm?.querySelectorAll("[data-clear-event-filter]").forEach((button) => {
        button.addEventListener("click", () => {
            window.WorkspaceFilterUrl.clear(button.dataset.clearEventFilter);
        });
    });

    function updateFilterCompatibility() {
        if (!participationFilter || !presenceFilter) return;

        const participationNotRequired = participationFilter.value === "not_required";
        const presenceRequiredOption = presenceFilter.querySelector('option[value="required"]');
        if (presenceRequiredOption) presenceRequiredOption.disabled = participationNotRequired;
        if (participationNotRequired && presenceFilter.value === "required") {
            presenceFilter.value = "";
            window.SearchableSelect?.refresh(presenceFilter);
        }
        if (compatibilityNote) {
            compatibilityNote.textContent = participationNotRequired
                ? "Presence cannot be required when participation is not required."
                : "";
        }
    }

    if (participationFilter) {
        participationFilter.addEventListener("change", updateFilterCompatibility);
        updateFilterCompatibility();
    }
});

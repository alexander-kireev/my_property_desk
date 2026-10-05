document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("eventWorkspace");
    const parameters = new URLSearchParams(window.location.search);

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
    document.querySelectorAll('[data-bs-target="#eventCalendarPanel"], [data-bs-target="#eventDetailsPanel"]').forEach((tab) => {
        tab.addEventListener("shown.bs.tab", () => {
            if (listTab) listTab.value = tab.dataset.bsTarget === "#eventCalendarPanel" ? "calendar" : "details";
        });
    });

    document.querySelectorAll("[data-calendar-day-href]").forEach((day) => {
        day.addEventListener("click", (event) => {
            if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
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

    document.querySelectorAll(".event-command-entry > [data-workspace-scroll-row]").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (!window.matchMedia("(max-width: 860px)").matches
                || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const expanded = row.nextElementSibling;
            if (expanded?.classList.contains("event-mobile-expanded")) {
                event.preventDefault();
                expanded.hidden = !expanded.hidden;
                row.setAttribute("aria-expanded", String(!expanded.hidden));
                if (!expanded.hidden) window.WorkspaceReveal?.queueRange(
                    row, expanded, () => window.ExpandableText?.refresh(expanded),
                );
            } else {
                event.preventDefault();
                window.location.assign(row.href);
            }
        });
    });

    document.querySelectorAll(".event-mobile-agenda-entry > .event-mobile-agenda-row").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (!window.matchMedia("(max-width: 860px)").matches
                || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            const expanded = row.nextElementSibling;
            if (expanded?.classList.contains("event-mobile-expanded")) {
                expanded.hidden = !expanded.hidden;
                row.setAttribute("aria-expanded", String(!expanded.hidden));
                row.parentElement.classList.toggle("is-expanded", !expanded.hidden);
                if (!expanded.hidden) window.WorkspaceReveal?.queueRange(
                    row, expanded, () => window.ExpandableText?.refresh(expanded),
                );
            } else {
                window.location.assign(row.href);
            }
        });
    });

    if (workspace?.classList.contains("show-mobile-calendar")
        && window.matchMedia("(max-width: 860px)").matches
        && window.performance?.getEntriesByType?.("navigation")?.[0]?.type !== "back_forward") {
        const selectedAgendaRow = document.querySelector(".event-mobile-agenda-entry.is-expanded > .event-mobile-agenda-row");
        if (selectedAgendaRow) {
            const expanded = selectedAgendaRow.nextElementSibling;
            window.WorkspaceReveal?.queueRange(
                selectedAgendaRow, expanded, () => window.ExpandableText?.refresh(expanded),
            );
        }
    }

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

    document.querySelectorAll("[data-event-form]").forEach((form) => {
        const allDay = form.querySelector('[name="all_day"]');
        const durationChoices = [...form.querySelectorAll("[data-duration-choice]")];
        const startTime = form.querySelector('[name="start_time"]');
        const endTime = form.querySelector('[name="end_time"]');
        const participation = form.querySelector('[name="user_participation_required"]');
        const presence = form.querySelector('[name="user_presence_required"]');

        function updateTimeFields({clear = false} = {}) {
            if (!allDay || !startTime || !endTime) return;
            if (clear && allDay.checked) {
                startTime.value = "";
                endTime.value = "";
            }
            startTime.disabled = allDay.checked;
            endTime.disabled = allDay.checked;
            durationChoices.forEach((choice) => {
                choice.checked = (choice.value === "all_day") === allDay.checked;
            });
        }

        function updatePresenceField() {
            if (!participation || !presence) return;
            presence.disabled = !participation.checked;
            if (!participation.checked) presence.checked = false;
        }

        if (allDay) {
            allDay.addEventListener("change", () => updateTimeFields({clear: allDay.checked}));
            durationChoices.forEach((choice) => {
                choice.addEventListener("change", () => {
                    allDay.checked = choice.value === "all_day";
                    allDay.dispatchEvent(new Event("change", {bubbles: true}));
                });
            });
            updateTimeFields();
        }
        if (participation) {
            participation.addEventListener("change", updatePresenceField);
            updatePresenceField();
        }
        if (presence) {
            presence.addEventListener("change", () => {
                if (presence.checked && participation) {
                    participation.checked = true;
                    updatePresenceField();
                }
            });
        }
    });

    document.querySelectorAll("[data-event-tabs]").forEach((form) => {
        const tabs = [...form.querySelectorAll("[data-event-tab]")];
        const panels = [...form.querySelectorAll("[data-event-panel]")];
        const body = form.querySelector(".event-form-body");

        function activateTab(name, {focus = false} = {}) {
            tabs.forEach((tab) => {
                const active = tab.dataset.eventTab === name;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-selected", String(active));
                tab.tabIndex = active ? 0 : -1;
                if (active && focus) tab.focus();
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.eventPanel !== name;
            });
            if (body) body.scrollTop = 0;
        }

        tabs.forEach((tab, index) => {
            tab.addEventListener("click", () => activateTab(tab.dataset.eventTab));
            tab.addEventListener("keydown", (event) => {
                let next = null;
                if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
                if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
                if (event.key === "Home") next = tabs[0];
                if (event.key === "End") next = tabs[tabs.length - 1];
                if (next) {
                    event.preventDefault();
                    activateTab(next.dataset.eventTab, {focus: true});
                }
            });
        });

        form.addEventListener("invalid", (event) => {
            const panel = event.target.closest("[data-event-panel]");
            if (panel?.hidden) activateTab(panel.dataset.eventPanel);
        }, true);

        activateTab(tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.eventTab || "details");
    });

    document.querySelectorAll("[data-contact-picker]").forEach((picker) => {
        const search = picker.querySelector("[data-contact-search]");
        const options = [...picker.querySelectorAll("[data-contact-option]")];
        const empty = picker.querySelector("[data-contact-empty]");
        const status = picker.querySelector("[data-contact-picker-status]");
        const tabCount = picker.closest(".modal")?.querySelector("[data-contact-tab-count]");

        function updatePicker() {
            const query = search?.value.trim().toLocaleLowerCase() || "";
            let visible = 0;
            let selected = 0;

            options.forEach((option) => {
                const checkbox = option.querySelector('input[type="checkbox"]');
                const matches = (option.dataset.searchText || option.textContent).toLocaleLowerCase().includes(query);
                option.hidden = !matches;
                if (matches) visible += 1;
                if (checkbox?.checked) selected += 1;
            });

            if (empty) empty.hidden = !query || visible > 0 || options.length === 0;
            if (status) status.textContent = `${selected} selected${query ? ` · ${visible} matching` : ""}`;
            if (tabCount) tabCount.textContent = selected;
        }

        search?.addEventListener("input", updatePicker);
        search?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") event.preventDefault();
        });
        picker.addEventListener("change", updatePicker);
        updatePicker();
    });

});

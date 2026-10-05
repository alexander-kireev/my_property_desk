// Set up Event fields, tabs and participant search on Events, Property and Dashboard. Each page submits its own forms.
(() => {
    const forms = new WeakMap(),
        tabControllers = new WeakMap(),
        pickers = new WeakMap();
    // All-day times and the participation/presence dependency
    function initForm(form) {
        if (forms.has(form)) return forms.get(form);

        const allDay = form.querySelector('[name="all_day"]');
        const durationChoices = [...form.querySelectorAll("[data-duration-choice]")];
        const startTime = form.querySelector('[name="start_time"]');
        const endTime = form.querySelector('[name="end_time"]');
        const participation = form.querySelector('[name="user_participation_required"]');
        const presence = form.querySelector('[name="user_presence_required"]');

        function updateTimeFields({ clear = false } = {}) {
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
            allDay.addEventListener("change", () => updateTimeFields({ clear: allDay.checked }));
            durationChoices.forEach((choice) => {
                choice.addEventListener("change", () => {
                    allDay.checked = choice.value === "all_day";
                    allDay.dispatchEvent(new Event("change", { bubbles: true }));
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

        const api = { updateTimeFields, updatePresenceField };
        forms.set(form, api);
        return api;
    }

    // Tabs, keyboard navigation and showing the panel with an invalid field
    function initTabs(form) {
        if (tabControllers.has(form)) return tabControllers.get(form);

        const tabs = [...form.querySelectorAll("[data-event-tab]")];
        const panels = [...form.querySelectorAll("[data-event-panel]")];
        const body = form.querySelector(".event-form-body");

        function activateTab(name, { focus = false } = {}) {
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
                    activateTab(next.dataset.eventTab, { focus: true });
                }
            });
        });

        form.addEventListener(
            "invalid",
            (event) => {
                const panel = event.target.closest("[data-event-panel]");
                if (panel?.hidden) activateTab(panel.dataset.eventPanel);
            },
            true,
        );

        activateTab(
            tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.eventTab ||
                "details",
        );

        const api = { activateTab };
        tabControllers.set(form, api);
        return api;
    }

    // Participant search and selected counts
    function initPicker(picker) {
        if (pickers.has(picker)) return pickers.get(picker);

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
                const matches = (option.dataset.searchText || option.textContent)
                    .toLocaleLowerCase()
                    .includes(query);
                option.hidden = !matches;
                if (matches) visible += 1;
                if (checkbox?.checked) selected += 1;
            });

            if (empty) empty.hidden = !query || visible > 0 || options.length === 0;
            if (status)
                status.textContent = `${selected} selected${query ? ` · ${visible} matching` : ""}`;
            if (tabCount) tabCount.textContent = selected;
        }

        search?.addEventListener("input", updatePicker);
        search?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") event.preventDefault();
        });
        picker.addEventListener("change", updatePicker);
        updatePicker();

        const api = { updatePicker };
        pickers.set(picker, api);
        return api;
    }
    function matching(root, selector) {
        return [...(root.matches?.(selector) ? [root] : []), ...root.querySelectorAll(selector)];
    }
    // Repeated calls are safe: each form, tab group and picker keeps its existing listeners.
    function init(root = document) {
        matching(root, "[data-event-form]").forEach(initForm);
        matching(root, "[data-event-tabs]").forEach(initTabs);
        matching(root, "[data-contact-picker]").forEach(initPicker);
    }
    /**
     * Set up a form once and return controls for its tabs and dependent fields.
     * Call refresh() after resetting values; it updates controls without clearing saved times.
     * activateTab(name, {focus}) changes the visible panel and can focus its tab button.
     */
    function forForm(form) {
        init(form);
        return {
            activateTab: (...args) => tabControllers.get(form)?.activateTab(...args),
            refresh() {
                forms.get(form)?.updateTimeFields();
                forms.get(form)?.updatePresenceField();
                matching(form, "[data-contact-picker]").forEach((picker) =>
                    pickers.get(picker)?.updatePicker(),
                );
            },
        };
    }
    window.EventForm = { init, forForm };
    document.addEventListener("DOMContentLoaded", () => init());
})();

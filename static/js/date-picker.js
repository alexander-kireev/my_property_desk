// Enhance native date fields, including fields added by dynamically loaded modals.
// Keep their ISO form values while providing a shared, keyboard-accessible calendar.
(() => {
    let active = null;
    const iso = (date) =>
        `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    // Noon avoids midnight offset changes when moving between local calendar days.
    const parse = (value) => (value ? new Date(`${value}T12:00:00`) : new Date());
    function close(restore = false) {
        if (!active) return;
        const { popup, button } = active;
        popup.remove();
        button.setAttribute("aria-expanded", "false");
        active = null;
        if (restore) button.focus();
    }
    function open(input, button) {
        if (active?.input === input) {
            close(true);
            return;
        }
        close();
        if (input.disabled || input.readOnly) return;
        const popup = document.createElement("div");
        popup.className = "app-date-popup";
        popup.setAttribute("role", "dialog");
        popup.setAttribute("aria-label", "Choose date");
        // Stay inside the owning modal's focus trap and native dialog top layer.
        (input.closest(".modal, dialog") || document.body).append(popup);
        active = { input, button, popup };
        button.setAttribute("aria-expanded", "true");
        const allowed = (value) =>
            (!input.min || value >= input.min) && (!input.max || value <= input.max);
        const clamp = (date) => {
            const value = iso(date);
            if (input.min && value < input.min) return parse(input.min);
            if (input.max && value > input.max) return parse(input.max);
            return date;
        };
        let cursor = clamp(parse(input.value));
        function choose(value) {
            input.value = value;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dispatchEvent(new Event("change", { bubbles: true }));
            close(true);
        }
        function action(label, callback, text = label) {
            const element = document.createElement("button");
            element.type = "button";
            element.textContent = text;
            element.setAttribute("aria-label", label);
            element.addEventListener("click", callback);
            return element;
        }
        function position() {
            // Fixed positioning avoids clipping by a scrolling form container.
            const rect = input.getBoundingClientRect();
            popup.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - popup.offsetWidth - 8))}px`;
            popup.style.top = `${Math.max(8, rect.bottom + popup.offsetHeight + 8 <= innerHeight ? rect.bottom + 4 : rect.top - popup.offsetHeight - 4)}px`;
        }
        function render() {
            popup.replaceChildren();
            const header = document.createElement("div");
            header.className = "app-date-header";
            const shift = (amount) => {
                cursor = clamp(new Date(cursor.getFullYear(), cursor.getMonth() + amount, 1, 12));
                render();
                popup
                    .querySelector(`[aria-label="${amount < 0 ? "Previous" : "Next"} month"]`)
                    ?.focus();
            };
            const title = document.createElement("strong");
            title.textContent = cursor.toLocaleDateString("en-GB", {
                month: "long",
                year: "numeric",
            });
            title.setAttribute("aria-live", "polite");
            header.append(
                action("Previous month", () => shift(-1), "‹"),
                title,
                action("Next month", () => shift(1), "›"),
            );
            popup.append(header);
            const grid = document.createElement("div");
            grid.className = "app-date-grid";
            ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].forEach((day) => {
                const label = document.createElement("span");
                label.textContent = day;
                grid.append(label);
            });
            const start = new Date(cursor.getFullYear(), cursor.getMonth(), 1, 12);
            start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
            for (let i = 0; i < 42; i++) {
                const date = new Date(start);
                date.setDate(start.getDate() + i);
                const value = iso(date);
                const day = action(
                    date.toLocaleDateString("en-GB", { dateStyle: "full" }),
                    () => choose(value),
                    String(date.getDate()),
                );
                day.dataset.date = value;
                day.disabled = !allowed(value);
                day.tabIndex = !day.disabled && value === iso(cursor) ? 0 : -1;
                day.classList.toggle("outside-month", date.getMonth() !== cursor.getMonth());
                day.setAttribute("aria-pressed", String(value === input.value));
                if (value === iso(new Date())) day.setAttribute("aria-current", "date");
                day.addEventListener("keydown", (event) => {
                    let next = new Date(date);
                    const offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
                    if (event.key in offsets) next.setDate(next.getDate() + offsets[event.key]);
                    else if (event.key === "Home")
                        next.setDate(next.getDate() - ((next.getDay() + 6) % 7));
                    else if (event.key === "End")
                        next.setDate(next.getDate() + 6 - ((next.getDay() + 6) % 7));
                    else if (event.key === "PageUp" || event.key === "PageDown")
                        next = new Date(
                            next.getFullYear(),
                            next.getMonth() + (event.key === "PageUp" ? -1 : 1),
                            1,
                            12,
                        );
                    else return;
                    event.preventDefault();
                    cursor = clamp(next);
                    if (!allowed(iso(cursor))) return;
                    render();
                    popup.querySelector(`[data-date="${iso(cursor)}"]`)?.focus();
                });
                grid.append(day);
            }
            popup.append(grid);
            const footer = document.createElement("div");
            footer.className = "app-date-footer";
            const today = action("Today", () => choose(iso(new Date())));
            today.disabled = !allowed(iso(new Date()));
            footer.append(
                action("Clear date", () => choose(""), "Clear"),
                today,
            );
            popup.append(footer);
            position();
        }
        render();
        (
            popup.querySelector('[data-date][tabindex="0"]:not(:disabled)') ||
            popup.querySelector("button")
        )?.focus();
    }
    function enhance() {
        document
            .querySelectorAll('input[type="date"]:not([data-date-enhanced])')
            .forEach((input) => {
                input.dataset.dateEnhanced = "true";
                const wrapper = document.createElement("div");
                wrapper.className = "app-date-field";
                input.before(wrapper);
                wrapper.append(input);
                const button = document.createElement("button");
                button.type = "button";
                button.className = "app-date-trigger";
                button.setAttribute(
                    "aria-label",
                    `Choose ${input.labels?.[0]?.textContent.trim() || "date"}`,
                );
                button.setAttribute("aria-haspopup", "dialog");
                button.setAttribute("aria-expanded", "false");
                button.innerHTML =
                    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/></svg>';
                button.addEventListener("click", () => open(input, button));
                wrapper.append(button);
                // Keep the native date value/typing, but use our calendar for
                // field clicks as well as the explicit calendar button.
                input.addEventListener("click", (event) => {
                    event.preventDefault();
                    open(input, button);
                });
                input.addEventListener("keydown", (event) => {
                    if (
                        (event.altKey && event.key === "ArrowDown") ||
                        event.key === " " ||
                        event.key === "F4"
                    ) {
                        event.preventDefault();
                        open(input, button);
                    }
                });
            });
    }
    // Close on focus leaving the popup or on layout changes; Escape alone
    // restores the trigger so it does not also dismiss the containing modal.
    document.addEventListener("pointerdown", (event) => {
        if (active && !active.popup.contains(event.target) && !active.button.contains(event.target))
            close();
    });
    document.addEventListener(
        "keydown",
        (event) => {
            if (active && event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                close(true);
            }
        },
        true,
    );
    document.addEventListener("focusin", (event) => {
        if (active && !active.popup.contains(event.target) && event.target !== active.button)
            close();
    });
    document.addEventListener("hidden.bs.modal", () => close());
    window.addEventListener("resize", () => close());
    document.addEventListener(
        "scroll",
        (event) => {
            if (active && !active.popup.contains(event.target)) close();
        },
        true,
    );
    function init() {
        enhance();
        new MutationObserver(enhance).observe(document.body, { childList: true, subtree: true });
    }
    if (document.readyState === "loading")
        document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();

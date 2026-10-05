document.addEventListener("DOMContentLoaded", () => {
    const commandCentre = document.querySelector(".task-command-centre");

    if (!commandCentre) {
        return;
    }

    document.querySelectorAll(".task-command-row[aria-expanded]").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (!window.matchMedia("(max-width: 860px)").matches || event.button !== 0 ||
                event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const expanded = row.nextElementSibling;
            if (expanded?.classList.contains("work-mobile-expanded")) {
                event.preventDefault();
                expanded.hidden = !expanded.hidden;
                row.setAttribute("aria-expanded", String(!expanded.hidden));
                if (!expanded.hidden) window.WorkspaceReveal?.queueRange(
                    row, expanded, () => window.ExpandableText?.refresh(expanded),
                );
            }
        });
    });

    const filterForm = document.getElementById("taskFilterForm");
    if (filterForm) {
        filterForm.querySelectorAll("[data-clear-task-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                window.WorkspaceFilterUrl.clear(button.dataset.clearTaskFilter);
            });
        });
    }
});

document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("issueWorkspace");
    const parameters = new URLSearchParams(window.location.search);

    if (workspace && ["detail", "edit"].includes(parameters.get("open"))) {
        workspace.classList.add("show-detail");
    }

    document.querySelectorAll(".issue-list-row[aria-expanded]").forEach((row) => {
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

    document.querySelectorAll(".issue-task-summary[role='button']").forEach((summary) => {
        summary.addEventListener("keydown", (event) => {
            if (event.target !== summary || !["Enter", " "].includes(event.key)) return;
            event.preventDefault();
            summary.click();
        });
    });

    const filterForm = document.getElementById("issueFilterForm");
    filterForm?.querySelectorAll("[data-clear-issue-filter]").forEach((button) => {
        button.addEventListener("click", () => {
            const field = filterForm.elements.namedItem(button.dataset.clearIssueFilter);
            if (field) {
                field.value = "";
                filterForm.requestSubmit();
            }
        });
    });

    document.querySelectorAll(".issue-task-details").forEach((details) => {
        details.addEventListener("shown.bs.collapse", () => {
            const row = details.closest(".issue-task-row");
            window.WorkspaceReveal?.queueRange(
                row.querySelector(".issue-task-summary"), details,
                () => window.ExpandableText?.refresh(details),
            );
        });
    });

    const editForm = document.getElementById("editIssueTaskForm");
    document.querySelectorAll(".issue-edit-task").forEach((button) => {
        button.addEventListener("click", () => {
            if (!editForm) {
                return;
            }

            editForm.action = button.dataset.action;
            editForm.querySelector('[name="title"]').value = button.dataset.title;
            editForm.querySelector('[name="description"]').value = button.dataset.description;
            editForm.querySelector('[name="priority"]').value = button.dataset.priority;
            window.SearchableSelect?.refresh(editForm.querySelector('[name="priority"]'));
            editForm.querySelector('[name="scheduled_date"]').value = button.dataset.scheduled;
            editForm.querySelector('[name="completion_deadline"]').value = button.dataset.deadline;
            editForm.querySelector('[name="scheduled_date"]').dispatchEvent(new Event("change"));
            editForm.querySelector('[name="issue"]').value = button.dataset.issue;
            editForm.querySelector('[name="issue"]').dispatchEvent(new Event("change"));
            const issueChoice = editForm.querySelector(
                '[name="relationship_type"][value="issue"]'
            );
            issueChoice.checked = true;
            issueChoice.dispatchEvent(new Event("change"));
        });
    });

});

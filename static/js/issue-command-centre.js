// Restore Issue links after browser Back, expand phone details and populate the linked Task editor.
document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("issueWorkspace");
    const parameters = new URLSearchParams(window.location.search);
    const returnKey = "pomIssueRelatedReturn";
    const currentUrl = `${window.location.pathname}${window.location.search}`;

    // Remember the related link so browser Back can reopen and focus it.
    workspace?.addEventListener("click", (event) => {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        )
            return;
        const link = event.target.closest(
            ".issue-task-open-record, #issueDetailsPanel .task-related-link",
        );
        if (!link) return;
        const task = link.closest(".issue-task-row");
        const state = window.history.state;
        window.history.replaceState(
            {
                ...(state && typeof state === "object" ? state : {}),
                [returnKey]: {
                    url: currentUrl,
                    taskId: task?.querySelector(".issue-task-details")?.id || null,
                    property: link.classList.contains("task-related-link"),
                },
            },
            "",
            window.location.href,
        );
    });

    // Restore related Task or Property links after returning to this Issue.
    const navigationType = window.performance?.getEntriesByType?.("navigation")?.[0]?.type;
    const restoreReturn = () => {
        const returnState = window.history.state?.[returnKey];
        if (returnState?.url !== currentUrl) return;
        if (returnState.taskId) {
            const details = document.getElementById(returnState.taskId);
            if (!details) return;
            const reveal = () =>
                requestAnimationFrame(() => {
                    const link = details.querySelector(".issue-task-open-record");
                    link?.focus({ preventScroll: true });
                    window.WorkspaceReveal?.reveal(link);
                });
            if (details.classList.contains("show")) reveal();
            else {
                details.classList.add("show");
                details
                    .closest(".issue-task-row")
                    ?.querySelector(".issue-task-summary")
                    ?.setAttribute("aria-expanded", "true");
                reveal();
            }
        } else if (returnState.property) {
            requestAnimationFrame(() =>
                requestAnimationFrame(() => {
                    const link = document.querySelector("#issueDetailsPanel .task-related-link");
                    if (!link?.getClientRects().length) return;
                    link.focus({ preventScroll: true });
                    const owner = window.WorkspaceReveal?.scrollOwner(link) || window;
                    const bounds = link.getBoundingClientRect();
                    const visible =
                        owner === window
                            ? {
                                  top:
                                      document.querySelector(".app-navbar")?.getBoundingClientRect()
                                          .bottom || 0,
                                  bottom: innerHeight,
                              }
                            : owner.getBoundingClientRect();
                    if (bounds.top < visible.top + 8)
                        owner.scrollBy({ top: bounds.top - visible.top - 8, behavior: "instant" });
                    else if (bounds.bottom > visible.bottom - 8)
                        owner.scrollBy({
                            top: bounds.bottom - visible.bottom + 8,
                            behavior: "instant",
                        });
                }),
            );
        }
    };
    if (navigationType === "back_forward") restoreReturn();
    window.addEventListener("pageshow", (event) => {
        if (event.persisted || navigationType === "back_forward") setTimeout(restoreReturn, 0);
    });

    if (workspace && ["detail", "edit"].includes(parameters.get("open"))) {
        workspace.classList.add("show-detail");
    }

    // Expand the selected Issue row on phones.
    document.querySelectorAll(".issue-list-row[aria-expanded]").forEach((row) => {
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
            if (expanded?.classList.contains("work-mobile-expanded")) {
                event.preventDefault();
                expanded.hidden = !expanded.hidden;
                row.setAttribute("aria-expanded", String(!expanded.hidden));
                if (!expanded.hidden)
                    window.WorkspaceReveal?.queueRange(row, expanded, () =>
                        window.ExpandableText?.refresh(expanded),
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
            window.WorkspaceFilterUrl.clear(button.dataset.clearIssueFilter);
        });
    });

    document.querySelectorAll(".issue-task-details").forEach((details) => {
        details.addEventListener("shown.bs.collapse", () => {
            const row = details.closest(".issue-task-row");
            window.WorkspaceReveal?.queueRange(
                row.querySelector(".issue-task-summary"),
                details,
                () => window.ExpandableText?.refresh(details),
            );
        });
    });

    // Reuse one edit dialog for all linked Tasks; populate it from the clicked button.
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
            const issueChoice = editForm.querySelector('[name="relationship_type"][value="issue"]');
            issueChoice.checked = true;
            issueChoice.dispatchEvent(new Event("change"));
        });
    });
});

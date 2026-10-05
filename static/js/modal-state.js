const WorkspaceModalReturnFocus = (() => {
    function resolve(origin) {
        if (!(origin instanceof Element)) return null;
        if (origin.closest("#dashboardAddMenu")) return document.getElementById("dashboardAddToggle");
        const dashboardMenu = origin.closest(".dashboard-row-menu");
        if (dashboardMenu) return dashboardMenu.closest(".dashboard-row-actions")?.querySelector(".dashboard-more-button") || null;
        const bootstrapMenu = origin.closest(".dropdown-menu");
        if (bootstrapMenu) {
            const dropdown = bootstrapMenu.closest(".dropdown");
            if (dropdown) return dropdown.querySelector('[data-bs-toggle="dropdown"]');
        }
        return origin;
    }

    function visible(target) {
        if (!target?.isConnected || target.matches(":disabled, [hidden]")) return false;
        if (target.closest("[hidden], .dropdown-menu:not(.show), .dashboard-row-menu:not(:popover-open)")) return false;
        const style = getComputedStyle(target);
        return style.visibility !== "hidden" && style.display !== "none" && !!target.getClientRects().length;
    }

    function restore(target) {
        if (!visible(target)) return;
        requestAnimationFrame(() => {
            if (visible(target)) target.focus({preventScroll: true});
        });
    }

    return {resolve, restore};
})();
window.WorkspaceModalReturnFocus = WorkspaceModalReturnFocus;

document.addEventListener("DOMContentLoaded", () => {
    const hasWorkspaceModals = document.body.matches(".task-command-page, .issue-command-page, .event-command-page, .property-command-page, .dashboard-page");
    document.querySelectorAll(".modal").forEach((modalElement) => {
        if (hasWorkspaceModals || modalElement.hasAttribute("data-modal-return-focus")) {
            modalElement.addEventListener("show.bs.modal", (event) => {
                const explicitTarget = modalElement.dataset.modalReturnFocus
                    ? document.querySelector(modalElement.dataset.modalReturnFocus)
                    : null;
                modalElement._workspaceReturnFocus = WorkspaceModalReturnFocus.resolve(explicitTarget || event.relatedTarget);
            });
            modalElement.addEventListener("hidden.bs.modal", () => {
                WorkspaceModalReturnFocus.restore(modalElement._workspaceReturnFocus);
            });
        }
    });
    document.querySelectorAll("[data-modal-clear-query]").forEach((modalElement) => {
        modalElement.addEventListener("hidden.bs.modal", () => {
            const parameterNames = modalElement.dataset.modalClearQuery
                .split(/\s+/)
                .filter(Boolean);
            const url = new URL(window.location.href);
            let changed = false;

            parameterNames.forEach((name) => {
                if (url.searchParams.has(name)) {
                    url.searchParams.delete(name);
                    changed = true;
                }
            });

            if (changed) {
                window.history.replaceState(
                    window.history.state,
                    "",
                    `${url.pathname}${url.search}${url.hash}`,
                );
            }
        });
    });

    document.querySelectorAll("[data-modal-auto-open]").forEach((trigger) => {
        const modalId = trigger.dataset.modalAutoOpen || trigger.id;
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            bootstrap.Modal.getOrCreateInstance(modalElement).show();
        }
    });
});

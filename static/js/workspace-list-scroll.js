// Restore a workspace list on refresh, browser Back, and navigation within the
// workspace, but not when arriving afresh from another part of the app.
(() => {
    const root = document.querySelector("[data-workspace-scroll-root]");
    if (!root) return;

    const list = root.querySelector("[data-workspace-scroll-list]");
    const query = new URLSearchParams(root.dataset.navigationQuery || "");
    const workspacePath = root.dataset.workspaceScrollPath || window.location.pathname;
    const key = `${workspacePath}?${query.toString()}`;
    const selection = `${window.location.pathname}?selected=${new URLSearchParams(window.location.search).get("selected") || ""}`;
    const selectedRowHash = new URLSearchParams(window.location.search).has("selected")
        && /^#(?:taskRow|issueRow|eventRow|eventAgendaRow)\d+$/.test(window.location.hash);
    if (selectedRowHash) {
        window.history?.replaceState?.(window.history.state, "", window.location.pathname + window.location.search);
    }
    const storageKey = `pom:workspace-list-scroll:${root.dataset.workspaceScrollRoot}`;
    const secondary = root.querySelector(".property-related-scroll, .issue-task-scroll");
    const secondaryKey = `${storageKey}:secondary:${selection}`;
    const intentKey = `${storageKey}:navigation-intent`;
    const workspace = root.dataset.workspaceScrollRoot;
    let pageScrollQuery = "(max-width: 767.98px)";
    if (workspace === "properties") {
        pageScrollQuery = "(max-width: 991.98px), (max-width: 1299.98px) and (max-height: 750px)";
    } else if (workspace === "contacts") {
        pageScrollQuery = "(max-width: 991.98px), (max-width: 1199.98px) and (max-height: 700px)";
    } else if (["tasks", "issues"].includes(workspace)) {
        pageScrollQuery = "(max-width: 860px), (max-width: 1199.98px) and (max-height: 700px)";
    } else if (workspace === "events") {
        pageScrollQuery = "(max-width: 860px), (max-width: 1199.98px) and (max-height: 700px)";
    }
    const usesPageScroll = () => window.matchMedia(pageScrollQuery).matches;
    const navigationType = window.performance?.getEntriesByType?.("navigation")?.[0]?.type || "navigate";

    const read = () => {
        try {
            return JSON.parse(sessionStorage.getItem(storageKey));
        } catch {
            return null;
        }
    };
    const write = (position) => {
        try {
            sessionStorage.setItem(storageKey, JSON.stringify(position));
        } catch {
            // Storage may be unavailable; normal link navigation still works.
        }
    };
    const clear = () => {
        try {
            sessionStorage.removeItem(storageKey);
        } catch {
            // Nothing to clear if storage is unavailable.
        }
    };
    const markInternalNavigation = () => {
        try {
            sessionStorage.setItem(intentKey, key);
        } catch {
            // Navigation still works without session storage.
        }
    };
    const consumeInternalNavigation = () => {
        try {
            const intendedKey = sessionStorage.getItem(intentKey);
            sessionStorage.removeItem(intentKey);
            return intendedKey === key;
        } catch {
            return false;
        }
    };

    const saved = read();
    const internalNavigation = consumeInternalNavigation();
    if (saved && saved.key !== key) clear();
    if (!list) return;
    const shouldRestore = saved?.key === key && (
        internalNavigation || navigationType === "reload" || navigationType === "back_forward"
    );
    if (!shouldRestore && navigationType === "navigate") clear();

    const hiddenMobileDetail = () => usesPageScroll() && !list.getClientRects().length;
    const restore = () => {
        if (secondary && (shouldRestore || navigationType === "back_forward" || navigationType === "reload")) {
            let position;
            try { position = JSON.parse(sessionStorage.getItem(secondaryKey)); } catch { /* Ignore old data. */ }
            if (position?.key === key) {
                secondary.scrollTop = position.top || 0;
            }
        }
        if (hiddenMobileDetail()) {
            window.scrollTo(0, 0);
        } else if (usesPageScroll()) {
            // A date or selected-row anchor is more specific than saved page scroll.
            if (!window.location.hash || selectedRowHash) window.scrollTo(0, shouldRestore ? saved.pageScrollY || 0 : 0);
        } else if (shouldRestore) {
            list.scrollTop = saved.listScrollTop || 0;
        }
        if (!shouldRestore || saved?.selection !== selection) {
            root.querySelectorAll(".task-detail-scroll, .issue-detail-scroll, .event-detail-scroll, .contact-detail-scroll, .property-panel-area").forEach((pane) => { pane.scrollTop = 0; });
        }
        // An explicit selection takes precedence over saved scroll on reload or a
        // changed in-workspace selection. Back/Forward keeps its position.
        const hasExplicitSelection = new URLSearchParams(window.location.search).has("selected")
            || (root.dataset.workspaceScrollRoot === "properties"
                && window.location.pathname !== workspacePath);
        const revealSelection = hasExplicitSelection && (
            (navigationType === "navigate" && !shouldRestore)
            || (["tasks", "issues", "events", "contacts", "properties"].includes(workspace) && (
                navigationType === "reload"
                || (navigationType === "navigate" && saved?.selection !== selection)
            ))
        );
        if (revealSelection) {
            const selected = list.querySelector('[data-workspace-scroll-row][aria-current="true"]');
            if (selected && list.getClientRects().length) {
                const expanded = ["tasks", "issues", "events"].includes(workspace) && window.matchMedia("(max-width: 860px)").matches
                    && selected.nextElementSibling?.classList.contains("work-mobile-expanded")
                    ? selected.nextElementSibling : null;
                if (expanded) window.WorkspaceReveal?.queueRange(
                    selected, expanded, () => window.ExpandableText?.refresh(expanded),
                );
                else window.WorkspaceReveal?.afterLayout(() => window.WorkspaceReveal?.reveal(selected));
            }
        }
    };
    let restored = false;
    const restoreOnce = () => {
        if (restored) return;
        restored = true;
        restore();
    };
    requestAnimationFrame(restoreOnce);
    window.addEventListener("pageshow", (event) => {
        // A bfcache return already carries the browser's exact scroll position.
        if (!event.persisted) requestAnimationFrame(restoreOnce);
    });
    if (secondary) {
        const captureSecondary = () => {
            try {
                sessionStorage.setItem(secondaryKey, JSON.stringify({
                    key, top: secondary.scrollTop,
                }));
            } catch { /* Storage may be unavailable. */ }
        };
        secondary.addEventListener("scroll", captureSecondary, {passive: true});
        window.addEventListener("pagehide", captureSecondary);
    }

    const capturePosition = () => {
        const previous = read();
        const listVisible = Boolean(list.getClientRects().length);
        write({
            key,
            selection,
            listScrollTop: listVisible ? list.scrollTop : previous?.key === key ? previous.listScrollTop : 0,
            pageScrollY: listVisible ? window.scrollY : previous?.key === key ? previous.pageScrollY : 0,
        });
        markInternalNavigation();
    };
    window.addEventListener("pagehide", () => {
        const previous = read();
        write({
            key, selection,
            listScrollTop: list.getClientRects().length ? list.scrollTop : previous?.key === key ? previous.listScrollTop : 0,
            pageScrollY: usesPageScroll() ? window.scrollY : previous?.key === key ? previous.pageScrollY : 0,
        });
    });

    let scrollFrame = null;
    list.addEventListener("scroll", () => {
        if (usesPageScroll() || scrollFrame !== null) return;
        scrollFrame = requestAnimationFrame(() => {
            scrollFrame = null;
            const previous = read();
            write({
                key,
                selection,
                listScrollTop: list.scrollTop,
                pageScrollY: previous?.key === key ? previous.pageScrollY : 0,
            });
        });
    }, { passive: true });

    let pageFrame = null;
    window.addEventListener("scroll", () => {
        if (!usesPageScroll() || !list.getClientRects().length || pageFrame !== null) return;
        pageFrame = requestAnimationFrame(() => {
            pageFrame = null;
            const previous = read();
            write({
                key,
                selection,
                listScrollTop: previous?.key === key ? previous.listScrollTop : 0,
                pageScrollY: window.scrollY,
            });
        });
    }, { passive: true });

    root.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest("a[href]");
        if (!link || (link.target && link.target !== "_self")) return;
        const target = new URL(link.href);
        if (target.origin !== window.location.origin || !target.pathname.startsWith(workspacePath)) return;
        if (target.search === window.location.search && target.hash) return;
        capturePosition();
    });

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (event.defaultPrevented || !form.action) return;
        const target = new URL(form.action);
        const returnUrl = form.elements?.namedItem("next")?.value;
        let returningToWorkspace = false;
        if (returnUrl) {
            try {
                const destination = new URL(returnUrl, window.location.href);
                returningToWorkspace = destination.origin === window.location.origin
                    && destination.pathname.startsWith(workspacePath);
            } catch {
                // An invalid return URL does not affect form submission.
            }
        }
        if ((target.origin === window.location.origin && target.pathname.startsWith(workspacePath)) || returningToWorkspace) {
            capturePosition();
        }
    });
})();

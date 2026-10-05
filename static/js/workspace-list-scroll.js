// Restore list positions on reload, browser Back and links within the same workspace.
// A new visit from another part of the app starts at the top or the selected row.
(() => {
    const root = document.querySelector("[data-workspace-scroll-root]");
    if (!root) return;

    const list = root.querySelector("[data-workspace-scroll-list]");
    const query = new URLSearchParams(root.dataset.navigationQuery || "");
    const workspacePath = root.dataset.workspaceScrollPath || window.location.pathname;
    const key = `${workspacePath}?${query.toString()}`;
    const selection = `${window.location.pathname}?selected=${new URLSearchParams(window.location.search).get("selected") || ""}`;
    const selectedRowHash =
        new URLSearchParams(window.location.search).has("selected") &&
        /^#(?:taskRow|issueRow|eventRow|eventAgendaRow)\d+$/.test(window.location.hash);
    if (selectedRowHash) {
        window.history?.replaceState?.(
            window.history.state,
            "",
            window.location.pathname + window.location.search,
        );
    }
    const storageKey = `pom:workspace-list-scroll:${root.dataset.workspaceScrollRoot}`;
    const secondary = root.querySelector(".property-related-scroll, .issue-task-scroll");
    const secondaryKey = `${storageKey}:secondary:${selection}`;
    const intentKey = `${storageKey}:navigation-intent`;
    const workspace = root.dataset.workspaceScrollRoot;
    const historyStateKey = "pomWorkspaceScroll";
    const readEntry = () => window.history?.state?.[historyStateKey]?.[workspace] || null;
    const writeEntry = (position) => {
        if (!window.history?.replaceState) return;
        const state = window.history.state;
        const current = state && typeof state === "object" ? state : {};
        window.history.replaceState(
            {
                ...current,
                [historyStateKey]: { ...current[historyStateKey], [workspace]: position },
            },
            "",
            window.location.href,
        );
    };
    // Match the CSS sizes where the whole page scrolls instead of an individual list.
    const workPageScroll = "(max-width: 860px), (max-width: 1199.98px) and (max-height: 700px)";
    const pageScrollQueries = {
        properties: "(max-width: 1199.98px), (max-width: 1299.98px) and (max-height: 750px)",
        contacts: "(max-width: 991.98px), (max-width: 1199.98px) and (max-height: 700px)",
        tasks: workPageScroll,
        issues: workPageScroll,
        events: workPageScroll,
    };
    const pageScrollQuery = pageScrollQueries[workspace] || "(max-width: 767.98px)";
    const usesPageScroll = () => window.matchMedia(pageScrollQuery).matches;
    const navigationType =
        window.performance?.getEntriesByType?.("navigation")?.[0]?.type || "navigate";

    // Read and save positions when sessionStorage is available.
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

    // Browser Back uses this history entry; reload and workspace links can use the saved position.
    const saved = read();
    const entry = readEntry();
    const internalNavigation = consumeInternalNavigation();
    if (saved && saved.key !== key) clear();
    if (!list) return;
    const restorePosition = navigationType === "back_forward" && entry?.key === key ? entry : saved;
    const shouldRestore =
        restorePosition?.key === key &&
        (internalNavigation || navigationType === "reload" || navigationType === "back_forward");
    const relatedReturnEntry =
        (workspace === "properties" &&
            window.history?.state?.pomPropertyRelatedReturn?.url ===
                `${window.location.pathname}${window.location.search}` &&
            Boolean(window.history.state.pomPropertyRelatedReturn.key)) ||
        (workspace === "issues" &&
            window.history?.state?.pomIssueRelatedReturn?.url ===
                `${window.location.pathname}${window.location.search}` &&
            Boolean(
                window.history.state.pomIssueRelatedReturn.taskId ||
                window.history.state.pomIssueRelatedReturn.property,
            ));
    const relatedReturn = navigationType === "back_forward" && relatedReturnEntry;
    if (!shouldRestore && navigationType === "navigate") clear();

    const hiddenMobileDetail = () => usesPageScroll() && !list.getClientRects().length;
    // Restore the page or list position, then reveal a newly selected row.
    const restore = () => {
        if (
            secondary &&
            (shouldRestore || navigationType === "back_forward" || navigationType === "reload")
        ) {
            let position;
            try {
                position = JSON.parse(sessionStorage.getItem(secondaryKey));
            } catch {
                // Ignore unreadable saved positions or blocked storage.
            }
            if (position?.key === key) {
                secondary.scrollTop = position.top || 0;
            }
        }
        if (hiddenMobileDetail()) {
            window.scrollTo(
                0,
                relatedReturn && shouldRestore ? restorePosition.pageScrollY || 0 : 0,
            );
        } else if (usesPageScroll()) {
            // A date or selected-row anchor is more specific than saved page scroll.
            if (!window.location.hash || selectedRowHash)
                window.scrollTo(0, shouldRestore ? restorePosition.pageScrollY || 0 : 0);
        } else if (shouldRestore) {
            list.scrollTop = restorePosition.listScrollTop || 0;
        }
        if (!shouldRestore || restorePosition?.selection !== selection) {
            root.querySelectorAll(
                ".task-detail-scroll, .issue-detail-scroll, .event-detail-scroll, .contact-detail-scroll, .property-panel-area",
            ).forEach((pane) => {
                pane.scrollTop = 0;
            });
        }
        // An explicit selection takes precedence over saved scroll on reload or a
        // changed in-workspace selection. Back/Forward keeps its position.
        const hasExplicitSelection =
            new URLSearchParams(window.location.search).has("selected") ||
            (root.dataset.workspaceScrollRoot === "properties" &&
                window.location.pathname !== workspacePath);
        const revealSelection =
            hasExplicitSelection &&
            ((navigationType === "navigate" && !shouldRestore) ||
                (["tasks", "issues", "events", "contacts", "properties"].includes(workspace) &&
                    ((navigationType === "reload" &&
                        !(workspace === "properties" && shouldRestore)) ||
                        (navigationType === "navigate" &&
                            restorePosition?.selection !== selection))));
        if (revealSelection) {
            const selected = list.querySelector('[data-workspace-scroll-row][aria-current="true"]');
            if (selected && list.getClientRects().length) {
                const expanded =
                    ["tasks", "issues", "events"].includes(workspace) &&
                    window.matchMedia("(max-width: 860px)").matches &&
                    selected.nextElementSibling?.classList.contains("work-mobile-expanded")
                        ? selected.nextElementSibling
                        : null;
                if (expanded)
                    window.WorkspaceReveal?.queueRange(selected, expanded, () =>
                        window.ExpandableText?.refresh(expanded),
                    );
                else
                    window.WorkspaceReveal?.afterLayout(() =>
                        window.WorkspaceReveal?.reveal(selected),
                    );
            }
        }
    };
    // Restore on first load and when the browser brings back a cached page.
    let restored = false;
    const restoreOnce = () => {
        if (restored) return;
        restored = true;
        restore();
    };
    requestAnimationFrame(restoreOnce);
    window.addEventListener("pageshow", (event) => {
        // A cached page skips initialization; restore its own history entry again here.
        if (event.persisted) {
            const position = readEntry();
            if (position?.key === key)
                requestAnimationFrame(() => {
                    if (hiddenMobileDetail())
                        window.scrollTo(0, relatedReturnEntry ? position.pageScrollY || 0 : 0);
                    else if (usesPageScroll()) window.scrollTo(0, position.pageScrollY || 0);
                    else list.scrollTop = position.listScrollTop || 0;
                });
        } else requestAnimationFrame(restoreOnce);
    });
    if (secondary) {
        const captureSecondary = () => {
            try {
                sessionStorage.setItem(
                    secondaryKey,
                    JSON.stringify({
                        key,
                        top: secondary.scrollTop,
                    }),
                );
            } catch {
                // Related records still work when their scroll position cannot be saved.
            }
        };
        secondary.addEventListener("scroll", captureSecondary, { passive: true });
        window.addEventListener("pagehide", captureSecondary);
    }

    // Save list and page positions separately so resizing does not mix them up.
    const currentPosition = () => {
        const previous = read();
        const listVisible = Boolean(list.getClientRects().length);
        return {
            key,
            selection,
            listScrollTop: listVisible
                ? list.scrollTop
                : previous?.key === key
                  ? previous.listScrollTop
                  : 0,
            pageScrollY: listVisible
                ? window.scrollY
                : previous?.key === key
                  ? previous.pageScrollY
                  : 0,
        };
    };
    const entryPosition = () => {
        const position = currentPosition();
        return {
            ...position,
            pageScrollY: usesPageScroll() ? window.scrollY : position.pageScrollY,
        };
    };
    const capturePosition = () => {
        const position = currentPosition();
        write(position);
        writeEntry(entryPosition());
        markInternalNavigation();
    };
    window.addEventListener("pagehide", () => {
        const position = currentPosition();
        write(position);
        writeEntry(entryPosition());
    });

    let scrollFrame = null;
    list.addEventListener(
        "scroll",
        () => {
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
        },
        { passive: true },
    );

    let pageFrame = null;
    window.addEventListener(
        "scroll",
        () => {
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
        },
        { passive: true },
    );

    root.addEventListener("click", (event) => {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        )
            return;
        const link = event.target.closest("a[href]");
        if (!link || (link.target && link.target !== "_self")) return;
        const target = new URL(link.href);
        if (target.origin !== window.location.origin) return;
        writeEntry(entryPosition());
        if (!target.pathname.startsWith(workspacePath)) return;
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
                returningToWorkspace =
                    destination.origin === window.location.origin &&
                    destination.pathname.startsWith(workspacePath);
            } catch {
                // An invalid return URL does not affect form submission.
            }
        }
        if (
            (target.origin === window.location.origin &&
                target.pathname.startsWith(workspacePath)) ||
            returningToWorkspace
        ) {
            capturePosition();
        }
    });
})();

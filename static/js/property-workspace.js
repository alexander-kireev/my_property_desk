// Expand narrow Property previews and restore related-record focus after Back or reload.
document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector(".property-command-centre");
    if (!workspace) return;

    // A different row loads its selected details from the server. The open row
    // can still be collapsed and reopened without another request.
    const narrow = window.matchMedia("(max-width: 991.98px)");
    workspace.querySelectorAll(".property-command-row[aria-expanded]").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (
                !narrow.matches ||
                event.button !== 0 ||
                event.metaKey ||
                event.ctrlKey ||
                event.shiftKey ||
                event.altKey
            )
                return;
            const preview = row
                .closest("[data-property-list-entry]")
                ?.querySelector("[data-property-preview]");
            if (!preview) return;
            event.preventDefault();
            preview.hidden = !preview.hidden;
            row.setAttribute("aria-expanded", String(!preview.hidden));
            if (!preview.hidden)
                window.WorkspaceReveal?.queueRange(row, preview, () =>
                    window.ExpandableText?.refresh(preview),
                );
        });
    });
    const returnStateKey = "pomPropertyRelatedReturn";
    const currentUrl = `${window.location.pathname}${window.location.search}`;
    const reloadFocusKey = `pomPropertyReloadFocus:${currentUrl}`;
    const recordKey = (link) => {
        if (!link) return null;
        const url = new URL(link.href, window.location.href);
        const id = url.searchParams.get("selected");
        return url.origin === window.location.origin && id ? `${url.pathname}:${id}` : null;
    };
    const recordLink = (record) => record.querySelector(".property-related-detail-footer a[href]");
    const visibleRecord = (key) =>
        [...workspace.querySelectorAll(".property-related-record")].find(
            (record) => recordKey(recordLink(record)) === key,
        );
    const restoredRecords = new WeakSet();

    // A blocked sessionStorage must not prevent related records from opening.
    function saveReloadFocus(key) {
        try {
            if (key) sessionStorage.setItem(reloadFocusKey, key);
            else sessionStorage.removeItem(reloadFocusKey);
        } catch {
            // Skip saving reload focus; the record links should still work.
        }
    }

    function consumeReloadFocus() {
        try {
            const key = sessionStorage.getItem(reloadFocusKey);
            sessionStorage.removeItem(reloadFocusKey);
            return key;
        } catch {
            return null;
        }
    }

    workspace.addEventListener("click", (event) => {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey
        )
            return;
        const link = event.target.closest(".property-related-detail-footer a[href]");
        if (!link || !workspace.contains(link)) return;
        const key = recordKey(link);
        if (!key) return;
        const state = window.history.state;
        window.history.replaceState(
            {
                ...(state && typeof state === "object" ? state : {}),
                [returnStateKey]: { url: currentUrl, key },
            },
            "",
            window.location.href,
        );
    });

    workspace.addEventListener("focusin", (event) => {
        const key = recordKey(event.target.closest?.(".property-related-detail-footer a[href]"));
        saveReloadFocus(key);
    });

    // Scroll the link into view inside the whole detail pane or below mobile navigation.
    const revealReturnedLink = (link) => {
        const owner = window.WorkspaceReveal?.scrollOwner(link) || window;
        const bounds = link.getBoundingClientRect();
        let top;
        let bottom;
        if (owner === window) {
            const navbar = document.querySelector(".app-navbar");
            top = Math.max(8, navbar?.getBoundingClientRect().bottom || 0);
            top += 8;
            bottom = window.innerHeight - 8;
        } else {
            const ownerBounds = owner.getBoundingClientRect();
            top = ownerBounds.top + 8;
            bottom = ownerBounds.bottom - 8;
        }
        if (bounds.top < top) owner.scrollBy({ top: bounds.top - top, behavior: "instant" });
        else if (bounds.bottom > bottom)
            owner.scrollBy({ top: bounds.bottom - bottom, behavior: "instant" });
    };
    // Open the related record before measuring and focusing its Open record link.
    const restoreReturn = () => {
        const state = window.history.state?.[returnStateKey];
        if (state?.url !== currentUrl || !state.key) return;
        const record = visibleRecord(state.key);
        if (!record) return;
        if (!record.open) {
            restoredRecords.add(record);
            record.open = true;
        }
        const link = recordLink(record);
        requestAnimationFrame(() =>
            requestAnimationFrame(() => {
                if (!link?.getClientRects().length) return;
                link.focus({ preventScroll: true });
                revealReturnedLink(link);
            }),
        );
    };

    workspace.querySelectorAll(".property-related-record, .property-record").forEach((record) => {
        record.addEventListener("toggle", () => {
            // Back restoration reveals the specific link itself; skip the normal whole-row reveal.
            if (restoredRecords.delete(record)) return;
            if (!record.open) return;
            window.WorkspaceReveal?.queueRange(
                record.querySelector("summary"),
                record.lastElementChild,
                () => window.ExpandableText?.refresh(record),
            );
        });
    });

    const navigationType = window.performance?.getEntriesByType?.("navigation")?.[0]?.type;
    if (navigationType === "back_forward") restoreReturn();
    if (navigationType === "reload") {
        const key = consumeReloadFocus();
        if (key) {
            const record = visibleRecord(key);
            if (record) {
                record.open = true;
                requestAnimationFrame(() =>
                    requestAnimationFrame(() => {
                        const link = recordLink(record);
                        if (!link?.getClientRects().length) return;
                        link.focus({ preventScroll: true });
                        revealReturnedLink(link);
                    }),
                );
            }
        }
    }
    window.addEventListener("pageshow", (event) => {
        if (event.persisted) restoreReturn();
    });
});

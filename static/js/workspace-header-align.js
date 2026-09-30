document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-align-headers]").forEach((workspace) => {
        const listHeader = workspace.querySelector("[data-list-header]");
        const detailHeader = workspace.querySelector("[data-detail-header]");
        if (!listHeader || !detailHeader) return;

        const minimumWidth = Number(workspace.dataset.alignFrom) || 992;
        let frame = 0;

        function align() {
            frame = 0;
            listHeader.style.minHeight = "";
            detailHeader.style.minHeight = "";
            const compactQuery = workspace.closest('[data-workspace-scroll-root="properties"]')
                ? "(max-width: 1299.98px) and (max-height: 750px)"
                : "(max-width: 1199.98px) and (max-height: 700px)";
            // Both workspaces keep independent header heights in the intermediate
            // split layout; the roomy desktop layout still aligns the divider.
            if (window.innerWidth < minimumWidth || !window.matchMedia("(min-width: 1200px)").matches || window.matchMedia(compactQuery).matches) return;

            // scrollHeight excludes the bottom border, which leaves the two
            // separator lines out of step when only one header needs growing.
            const height = Math.ceil(Math.max(
                listHeader.getBoundingClientRect().height,
                detailHeader.getBoundingClientRect().height,
            ));
            listHeader.style.minHeight = `${height}px`;
            detailHeader.style.minHeight = `${height}px`;
        }

        function schedule() {
            if (!frame) frame = window.requestAnimationFrame(align);
        }

        schedule();
        document.fonts?.ready.then(schedule);
        window.addEventListener("resize", schedule);
    });
});

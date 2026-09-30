// Reveal the changed row in exactly one scroll owner: its nearest scroll pane,
// or the document if there is no independently scrolling pane.
(() => {
    function visibleTop(owner) {
        if (owner !== window) {
            const padding = parseFloat(getComputedStyle(owner).scrollPaddingTop) || 0;
            return owner.getBoundingClientRect().top + padding;
        }
        const navbar = document.querySelector(".app-navbar");
        if (!navbar || !navbar.getClientRects().length) return 8;
        const position = getComputedStyle(navbar).position;
        const bounds = navbar.getBoundingClientRect();
        return ["fixed", "sticky"].includes(position) && bounds.top <= 0 && bounds.bottom > 0
            ? bounds.bottom + 8 : 8;
    }
    function scrollOwner(element) {
        for (let node = element.parentElement; node && node !== document.body; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 1) return node;
        }
        return window;
    }
    function revealBounds(element, bounds, anchorBounds = null) {
        const owner = scrollOwner(element);
        const viewport = owner === window
            ? {top: visibleTop(owner), bottom: window.innerHeight}
            : {top: visibleTop(owner), bottom: owner.getBoundingClientRect().bottom};
        const height = viewport.bottom - viewport.top;
        if (height <= 0) return;
        let delta = 0;
        if (bounds.height > height) {
            // The full panel cannot fit: consistently put its heading at the
            // safe top so the maximum useful content is visible below it.
            delta = (anchorBounds || bounds).top - viewport.top;
        } else if (bounds.top < viewport.top) delta = bounds.top - viewport.top;
        else if (bounds.bottom > viewport.bottom) delta = bounds.bottom - viewport.bottom;
        if (Math.abs(delta) < 1) return;
        const behavior = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";
        owner.scrollBy({top: delta, behavior});
    }
    function reveal(element) {
        if (!element || !element.getClientRects().length) return;
        revealBounds(element, element.getBoundingClientRect());
    }
    function revealRange(first, last) {
        if (!first || !first.getClientRects().length) return;
        const firstBounds = first.getBoundingClientRect();
        if (!last || !last.getClientRects().length) {
            revealBounds(first, firstBounds);
            return;
        }
        const lastBounds = last.getBoundingClientRect();
        const top = Math.min(firstBounds.top, lastBounds.top);
        const bottom = Math.max(firstBounds.bottom, lastBounds.bottom);
        revealBounds(first, {top, bottom, height: bottom - top}, firstBounds);
    }
    function afterLayout(callback) {
        return requestAnimationFrame(callback);
    }
    function queueRange(first, last, prepare) {
        return afterLayout(() => {
            if (last?.hidden || (last?.getClientRects && !last.getClientRects().length)) return;
            prepare?.();
            revealRange(first, last);
        });
    }
    window.WorkspaceReveal = {reveal, revealRange, queueRange, afterLayout, scrollOwner};
})();

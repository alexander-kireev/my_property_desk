(() => {
    const selector = "[data-expandable-text]";
    const observed = new WeakSet();
    const observedCards = new WeakSet();
    const observer = typeof ResizeObserver === "function"
        ? new ResizeObserver((entries) => entries.forEach(({target}) => refresh(target)))
        : null;

    function fitCardLines(wrapper, content) {
        if (!wrapper.classList.contains("expandable-text--fit-card")) return;
        const card = wrapper.closest(".card-body");
        if (!card || !window.matchMedia("(min-width: 1200px)").matches) {
            content.style.removeProperty("--expandable-lines");
            return;
        }
        if (observer && !observedCards.has(card)) {
            observer.observe(card);
            observedCards.add(card);
        }
        content.style.setProperty("--expandable-lines", "3");
        const contentStyle = getComputedStyle(content);
        const lineHeight = parseFloat(contentStyle.lineHeight) || parseFloat(contentStyle.fontSize) * 1.5;
        const cardPadding = parseFloat(getComputedStyle(card).paddingBottom);
        if (!lineHeight) return;
        const available = card.getBoundingClientRect().bottom
            - content.getBoundingClientRect().top - cardPadding - lineHeight * 1.8;
        content.style.setProperty("--expandable-lines", String(Math.max(3, Math.floor(available / lineHeight))));
    }

    function descriptionText(node) {
        if (node.nodeType === 3) return node.textContent;
        if (node.nodeName === "BR") return "\n";
        return Array.from(node.childNodes || [], descriptionText).join("");
    }

    function fitInlineEndPreview(content, preview, toggle) {
        const fullText = descriptionText(content);
        const characters = typeof Intl.Segmenter === "function"
            ? Array.from(new Intl.Segmenter(undefined, {granularity: "grapheme"}).segment(fullText), ({segment}) => segment)
            : Array.from(fullText);
        const contentStyle = getComputedStyle(content);
        const lineHeight = parseFloat(contentStyle.lineHeight) || parseFloat(contentStyle.fontSize) * 1.5;
        const lineLimit = parseInt(content.style.getPropertyValue("--expandable-lines"), 10) || 3;
        const maxHeight = lineHeight * lineLimit + 1;
        preview.hidden = false;
        toggle.hidden = false;
        preview.append(toggle);

        let low = 0;
        let high = characters.length;
        while (low < high) {
            const middle = Math.ceil((low + high) / 2);
            preview.replaceChildren(document.createTextNode(`${characters.slice(0, middle).join("").trimEnd()}… `), toggle);
            if (preview.getBoundingClientRect().height <= maxHeight) low = middle;
            else high = middle - 1;
        }
        preview.replaceChildren(document.createTextNode(`${characters.slice(0, low).join("").trimEnd()}… `), toggle);
        content.hidden = true;
    }

    function refresh(root = document) {
        const wrappers = root.matches?.(selector) ? [root] : root.querySelectorAll(selector);
        wrappers.forEach((wrapper) => {
            const content = wrapper.querySelector("[data-expandable-content]");
            const toggle = wrapper.querySelector("[data-expandable-toggle]");
            if (!content || !toggle) return;
            const preview = wrapper.querySelector("[data-expandable-preview]");
            if (preview) {
                preview.hidden = true;
                content.hidden = false;
                wrapper.append(toggle);
            }
            if (!content.getClientRects().length) return;
            if (observer && !observed.has(wrapper)) {
                observer.observe(wrapper);
                observed.add(wrapper);
            }
            const expanded = toggle.getAttribute("aria-expanded") === "true";
            content.classList.remove("is-expanded");
            fitCardLines(wrapper, content);
            const overflows = wrapper.classList.contains("expandable-text--single-line")
                ? content.scrollWidth > content.clientWidth + 1
                : content.scrollHeight > content.clientHeight + 1;
            content.classList.toggle("is-expanded", expanded && overflows);
            toggle.hidden = !overflows;
            if (preview && overflows && !expanded) fitInlineEndPreview(content, preview, toggle);
            if (!overflows && expanded) {
                toggle.setAttribute("aria-expanded", "false");
                toggle.textContent = "See more";
            }
        });
    }

    function queueRefresh(root = document) {
        requestAnimationFrame(() => refresh(root));
    }

    document.addEventListener("click", (event) => {
        const toggle = event.target.closest("[data-expandable-toggle]");
        if (toggle) {
            const wrapper = toggle.closest(selector);
            const expanded = toggle.getAttribute("aria-expanded") === "true";
            toggle.setAttribute("aria-expanded", String(!expanded));
            toggle.textContent = expanded ? "See more" : "See less";
            wrapper.querySelector("[data-expandable-content]").classList.toggle("is-expanded", !expanded);
            window.WorkspaceReveal?.afterLayout(() => {
                refresh(wrapper);
                if (!expanded) {
                    const section = wrapper.closest(
                        ".dashboard-row-detail, .property-related-details, .property-record-details, .card-body, .task-inline-section, .issue-inline-section, .event-inline-section"
                    );
                    const anchor = section?.matches?.(".dashboard-row-detail, .property-related-details, .property-record-details")
                        ? section.previousElementSibling
                        : section?.querySelector?.("h3, h4, h5");
                    window.WorkspaceReveal?.revealRange(anchor || section || wrapper, wrapper);
                }
            });
            return;
        }
        queueRefresh();
    });
    document.addEventListener("toggle", (event) => {
        if (event.target.matches("details")) queueRefresh(event.target);
    }, true);
    document.addEventListener("shown.bs.tab", () => queueRefresh());
    document.addEventListener("shown.bs.collapse", () => queueRefresh());
    window.addEventListener("resize", () => queueRefresh());
    document.addEventListener("DOMContentLoaded", () => queueRefresh());
    window.ExpandableText = {refresh, queueRefresh};
})();

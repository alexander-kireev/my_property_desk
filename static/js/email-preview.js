// Fit email previews to their actual rendered width while keeping the full value accessible.
(() => {
    function fitMiddle(value, availableWidth, measure) {
        if (measure(value) <= availableWidth) return value;
        const characters = Array.from(value);
        let low = 0;
        let high = characters.length - 1;
        let result = "…";
        // Search the largest balanced prefix/suffix that fits the proportional font.
        while (low <= high) {
            const kept = Math.floor((low + high) / 2);
            const prefix = Math.ceil(kept * 0.45);
            const suffix = kept - prefix;
            const ending = suffix ? characters.slice(-suffix).join("") : "";
            const candidate = characters.slice(0, prefix).join("") + "…" + ending;
            if (measure(candidate) <= availableWidth) {
                result = candidate;
                low = kept + 1;
            } else {
                high = kept - 1;
            }
        }
        return result;
    }

    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    const registered = new WeakSet();

    function refresh(preview) {
        const width = preview.clientWidth;
        if (!context || !width) return;
        const styles = getComputedStyle(preview);
        context.font = styles.font;
        const spacing = parseFloat(styles.letterSpacing) || 0;
        const measure = (text) => context.measureText(text).width + spacing * text.length;
        const full = preview.dataset.emailPreview;
        const fitted = fitMiddle(full, Math.max(0, width - 1), measure);
        const visual = preview.querySelector("[data-email-visual]");
        if (visual.textContent !== fitted) visual.textContent = fitted;
        preview.classList.add("is-measured");
    }

    const observer = new ResizeObserver((entries) => {
        for (const entry of entries) refresh(entry.target);
    });

    function register(root) {
        const previews = [...root.querySelectorAll("[data-email-preview]")];
        if (root.matches?.("[data-email-preview]")) previews.unshift(root);
        for (const preview of previews) {
            if (registered.has(preview)) continue;
            registered.add(preview);
            observer.observe(preview);
            refresh(preview);
        }
    }

    function refreshAll() {
        document.querySelectorAll("[data-email-preview]").forEach(refresh);
    }

    // Hidden dialogs have no width until opened; resize and font events remeasure them.
    document.addEventListener("DOMContentLoaded", () => {
        register(document);
        new MutationObserver((changes) => {
            for (const change of changes) {
                for (const node of change.addedNodes) {
                    if (node.nodeType === 1) register(node);
                }
            }
        }).observe(document.body, { childList: true, subtree: true });
        document.fonts?.ready.then(refreshAll);
    });
    document.addEventListener("shown.bs.modal", refreshAll);
    document.addEventListener("shown.bs.tab", refreshAll);
    window.EmailPreview = { fitMiddle };
})();

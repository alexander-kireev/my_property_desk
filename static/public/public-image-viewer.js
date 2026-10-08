/* Shared screenshot dialog for the homepage and feature stories. */
(() => {
    const buttons = [...document.querySelectorAll("[data-public-image]")];
    const viewer = document.querySelector("[data-public-viewer]");
    if (!buttons.length || !viewer) return;

    const image = viewer.querySelector("[data-viewer-image]");
    const count = viewer.querySelector("[data-viewer-count]");
    let current = 0;
    let opener = null;

    function show(index) {
        current = (index + buttons.length) % buttons.length;
        const original = buttons[current].querySelector("img");
        image.src = original.currentSrc || original.src;
        image.alt = original.alt;
        count.textContent = `Image ${current + 1} of ${buttons.length}`;
    }

    buttons.forEach((button, index) => {
        button.addEventListener("click", () => {
            opener = button;
            show(index);
            viewer.showModal();
        });
    });
    viewer.querySelector("[data-viewer-prev]").addEventListener("click", () => show(current - 1));
    viewer.querySelector("[data-viewer-next]").addEventListener("click", () => show(current + 1));
    viewer.querySelector("[data-viewer-close]").addEventListener("click", () => viewer.close());
    viewer.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            show(current - 1);
        }
        if (event.key === "ArrowRight") {
            event.preventDefault();
            show(current + 1);
        }
    });
    viewer.addEventListener("close", () => opener?.focus());
    viewer.addEventListener("click", (event) => {
        if (event.target === viewer) viewer.close();
    });
})();

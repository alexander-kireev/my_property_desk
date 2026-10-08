/* The homepage preview carousel; screenshot enlargement belongs to public-image-viewer.js. */
(() => {
    const slides = [...document.querySelectorAll("[data-slide]")];
    const dots = [...document.querySelectorAll("[data-slide-to]")];
    const previous = document.querySelector("[data-slide-prev]");
    const next = document.querySelector("[data-slide-next]");
    if (!slides.length || !previous || !next) return;

    let active = 0;
    function show(index) {
        active = (index + slides.length) % slides.length;
        slides.forEach((slide, position) => {
            slide.hidden = position !== active;
        });
        dots.forEach((dot, position) => {
            if (position === active) dot.setAttribute("aria-current", "true");
            else dot.removeAttribute("aria-current");
        });
    }

    previous.addEventListener("click", () => show(active - 1));
    next.addEventListener("click", () => show(active + 1));
    dots.forEach((dot, index) => dot.addEventListener("click", () => show(index)));
})();

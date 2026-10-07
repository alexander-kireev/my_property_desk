// Match the method cards' bottom edge to the contact list's pagination divider.
document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector(".contact-workspace");
    const pagination = document.querySelector(".contact-pagination");
    if (!workspace || !pagination) return;
    const update = () => {
        workspace.style.setProperty(
            "--contact-pagination-height",
            `${pagination.getBoundingClientRect().height}px`,
        );
    };
    new ResizeObserver(update).observe(pagination);
    update();
});

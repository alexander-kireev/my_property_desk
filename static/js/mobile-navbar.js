(() => {
    const navbar = document.querySelector(".app-navbar");
    const menu = navbar?.querySelector("#siteNavbar");
    const toggle = navbar?.querySelector('.navbar-toggler[aria-controls="siteNavbar"]');
    if (!menu || !toggle) return;

    document.addEventListener("pointerdown", (event) => {
        if (!window.matchMedia("(max-width: 991.98px)").matches) return;
        if (!menu.classList.contains("show")) return;
        if (menu.contains(event.target) || toggle.contains(event.target)) return;
        if (event.target.closest('.modal.show, [role="dialog"][aria-modal="true"]')) return;
        bootstrap.Collapse.getOrCreateInstance(menu, {toggle: false}).hide();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || event.defaultPrevented) return;
        if (!window.matchMedia("(max-width: 991.98px)").matches) return;
        if (!menu.classList.contains("show")) return;
        if (document.querySelector('.modal.show, [role="dialog"][aria-modal="true"]')) return;

        event.preventDefault();
        menu.addEventListener("hidden.bs.collapse", () => toggle.focus({preventScroll: true}), {once: true});
        bootstrap.Collapse.getOrCreateInstance(menu, {toggle: false}).hide();
    });

    // Bootstrap closes the desktop menu on Escape, but hover CSS can keep it visible.
    const workDropdown = navbar.querySelector(".my-work-menu-toggle")?.closest(".dropdown");
    if (workDropdown) {
        workDropdown.addEventListener("hide.bs.dropdown", () => {
            workDropdown.classList.add("app-dropdown-hover-suppressed");
        });
        workDropdown.addEventListener("pointerleave", () => {
            workDropdown.classList.remove("app-dropdown-hover-suppressed");
        });
    }
})();

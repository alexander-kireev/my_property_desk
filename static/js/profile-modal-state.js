// Clear Profile form values and errors after closing a dialog or returning to a cached page.
// A validation error stays visible until its modal is dismissed.
// Reopening the modal, or returning through browser history, starts fresh.
document.addEventListener("DOMContentLoaded", () => {
    const modals = document.querySelectorAll("[data-profile-account-modal]");

    const clearFormStateFromUrl = () => {
        const url = new URL(window.location.href);
        if (!url.searchParams.has("form_state") && !url.searchParams.has("modal")) return;
        url.searchParams.delete("form_state");
        url.searchParams.delete("modal"); // Older links may use modal instead of form_state.
        window.history.replaceState(
            window.history.state,
            "",
            `${url.pathname}${url.search}${url.hash}`,
        );
    };

    const resetModal = (modal) => {
        const form = modal.querySelector("[data-fresh-account-form]");
        if (!form) return;

        form.querySelectorAll("input:not([type=hidden])").forEach((field) => {
            field.value = "";
            field.defaultValue = "";
            field.classList.remove("is-invalid");
            field.removeAttribute("aria-invalid");
            // Remove only error references; keep the password guidance associated with its field.
            const descriptions = (field.getAttribute("aria-describedby") || "")
                .split(/\s+/)
                .filter((id) => id && !document.getElementById(id)?.matches(".invalid-feedback"));
            if (descriptions.length) field.setAttribute("aria-describedby", descriptions.join(" "));
            else field.removeAttribute("aria-describedby");
        });
        form.querySelectorAll(".invalid-feedback, .alert-danger").forEach((error) =>
            error.remove(),
        );
        form.querySelectorAll("[data-validation-help]").forEach((help) => {
            help.hidden = false;
        });
        form.removeAttribute("data-preserve-restored-email");
    };

    modals.forEach((modal) => {
        modal.addEventListener("hidden.bs.modal", () => resetModal(modal));
    });

    // Remove form parameters when the server has not supplied a dialog to reopen.
    if (!document.querySelector("[data-modal-auto-open]")) {
        clearFormStateFromUrl();
    }

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) return;

        modals.forEach((modal) => {
            if (modal.classList.contains("show")) {
                bootstrap.Modal.getOrCreateInstance(modal).hide();
            }
            resetModal(modal);
        });
        clearFormStateFromUrl();
    });
});

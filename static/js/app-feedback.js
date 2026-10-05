// Show Django success/error messages. Dashboard can hide them before displaying its own message.
document.addEventListener("DOMContentLoaded", () => {
    const element = document.querySelector(".app-feedback-toast");
    if (!element) return;
    const toast = window.bootstrap?.Toast.getOrCreateInstance(element);
    toast?.show();
    // Outside clicks dismiss success feedback, while errors remain available.
    if (element.classList.contains("app-feedback-toast--success")) {
        document.addEventListener("pointerdown", (event) => {
            if (element.classList.contains("show") && !element.contains(event.target))
                toast?.hide();
        });
    }
    window.AppFeedback = { dismiss: () => toast?.hide() };
});

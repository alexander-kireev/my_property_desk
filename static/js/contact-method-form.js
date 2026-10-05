// Switch Contact detail labels and input types between email, telephone and other methods.
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-contact-method-form]").forEach((form) => {
        const method = form.querySelector('[name="type"]');
        const value = form.querySelector('[name="value"]');
        const label = form.querySelector("[data-contact-method-value-label]");
        const help = form.querySelector("[data-contact-method-help]");
        if (!method || !value || !label || !help) return;

        function update() {
            const isEmail = method.value === "email";
            const isTelephone = method.value === "telephone";
            label.textContent = isEmail
                ? "Email address"
                : isTelephone
                  ? "Telephone number"
                  : "Contact information";
            value.type = isEmail ? "email" : isTelephone ? "tel" : "text";
            value.placeholder = isEmail ? "name@example.com" : isTelephone ? "+44 7700 900123" : "";
            value.inputMode = isTelephone ? "tel" : "";
            help.hidden =
                !isTelephone || Boolean(value.parentElement.querySelector(".invalid-feedback"));
        }

        // Keep saved or rejected input on load; clear it only when the user chooses another method.
        method.addEventListener("change", () => {
            value.value = "";
            update();
        });
        update();
    });
});

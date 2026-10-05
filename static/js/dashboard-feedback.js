// Show Dashboard messages, pause the Undo countdown and handle Undo requests.
window.DashboardFeedback = {
    // Create once per Dashboard page; get finds elements, send writes and load refreshes the page.
    create({ get, send, load }) {
        let toastTimer = null;
        let toastRemaining = 0;
        let toastStarted = 0;
        let toastPauseable = false;
        // Countdown values are milliseconds; pausing keeps the remaining time.
        function stopToastTimer() {
            if (!toastTimer) return;
            clearTimeout(toastTimer);
            toastTimer = null;
            toastRemaining -= Date.now() - toastStarted;
        }
        function startToastTimer() {
            if (toastTimer || toastRemaining <= 0) return;
            toastStarted = Date.now();
            toastTimer = setTimeout(hideToast, toastRemaining);
        }
        function hideToast() {
            const toast = get("dashboardToast");
            if (toast.hidden) return;
            stopToastTimer();
            toastRemaining = 0;
            toast.classList.add("leaving");
            setTimeout(() => {
                if (toast.classList.contains("leaving")) toast.hidden = true;
            }, 180);
        }
        // Replace the current message and choose whether it closes automatically.
        function presentToast(
            title,
            { detail = "", error = false, undoAction = null, duration = null } = {},
        ) {
            const toast = get("dashboardToast");
            const undoButton = get("dashboardToastUndo");
            const undoWasFocused = document.activeElement === undoButton;
            stopToastTimer();
            window.AppFeedback?.dismiss();
            toast.classList.remove("leaving");
            toast.classList.toggle("error", error);
            toast.setAttribute("role", error ? "alert" : "status");
            toast.setAttribute("aria-live", error ? "assertive" : "polite");
            get("dashboardToastIcon").textContent = error ? "!" : "✓";
            get("dashboardToastTitle").textContent = title;
            get("dashboardToastDetail").textContent = detail;
            undoButton.hidden = !undoAction;
            undoButton.disabled = false;
            undoButton.onclick = undoAction;
            toast.hidden = false;
            toastPauseable = Boolean(undoAction);
            toastRemaining = duration ?? (error ? 0 : undoAction ? 10000 : 4200);
            if (
                toastRemaining &&
                (!toastPauseable ||
                    !(toast.matches(":hover") || toast.contains(document.activeElement)))
            )
                startToastTimer();
            if (undoWasFocused && !undoAction) get("dashboardToastClose").focus();
        }
        function message(title, options = {}) {
            presentToast(title, options);
        }
        // Keep Undo available after a temporary failure; expire it when the server rejects the token.
        function showUndo(type, id, token, title) {
            const attemptUndo = async () => {
                const button = get("dashboardToastUndo");
                button.disabled = true;
                stopToastTimer();
                try {
                    await send({ action: "undo", kind: type, id, token });
                } catch (error) {
                    // These phrases match Django's responses for an unusable Undo token.
                    if (/expired|changed again|does not match/.test(error.message)) {
                        message(error.message, { error: true });
                        try {
                            await load();
                        } catch (refreshError) {
                            message(refreshError.message, { error: true });
                        }
                    } else
                        presentToast(error.message, {
                            error: true,
                            undoAction: attemptUndo,
                            duration: Math.max(1000, toastRemaining),
                        });
                    return;
                }
                try {
                    await load();
                    message("Action undone.");
                } catch {
                    message("Undo succeeded, but Dashboard could not refresh. Reload the page.", {
                        error: true,
                    });
                }
            };
            presentToast(title, { undoAction: attemptUndo });
        }
        get("dashboardToastClose").addEventListener("click", hideToast);
        const toastElement = get("dashboardToast");
        toastElement.addEventListener("mouseenter", () => {
            if (toastPauseable) stopToastTimer();
        });
        toastElement.addEventListener("mouseleave", () => {
            if (toastPauseable) startToastTimer();
        });
        toastElement.addEventListener("focusin", () => {
            if (toastPauseable) stopToastTimer();
        });
        toastElement.addEventListener("focusout", () => {
            queueMicrotask(() => {
                if (toastPauseable && !toastElement.contains(document.activeElement))
                    startToastTimer();
            });
        });
        document.addEventListener("pointerdown", (event) => {
            if (
                !toastElement.hidden &&
                !toastPauseable &&
                !toastElement.classList.contains("error") &&
                !toastElement.contains(event.target)
            )
                hideToast();
        });

        return { message, showUndo };
    },
};

// Toggle note editors rendered by Django and handle their Undo message. Dashboard Notes use dashboard-notes.js.
document.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-note-edit-toggle]");
    const cancelButton = event.target.closest("[data-note-edit-cancel]");

    if (!editButton && !cancelButton) return;

    const note = event.target.closest("[data-note]");
    if (!note) return;

    const display = note.querySelector("[data-note-display]");
    const editor = note.querySelector("[data-note-edit]");
    const toggle = note.querySelector("[data-note-edit-toggle]");
    if (!display || !editor || !toggle) return;

    const isEditing = Boolean(editButton);
    display.hidden = isEditing;
    editor.hidden = !isEditing;
    toggle.setAttribute("aria-expanded", String(isEditing));

    if (isEditing) {
        editor.querySelector("textarea")?.focus();
    } else {
        const field = editor.querySelector("textarea");
        if (field) field.value = note.dataset.savedContent;
        toggle.focus();
    }
});

// Pause the Undo countdown while the user hovers over the message or focuses a control in it.
const noteUndoToast = document.querySelector("[data-note-undo-toast]");
if (noteUndoToast) {
    let remaining = 10000;
    let started = 0;
    let timer;
    const stop = () => {
        if (!timer) return;
        clearTimeout(timer);
        timer = null;
        remaining -= Date.now() - started;
    };
    const start = () => {
        if (timer || remaining <= 0) return;
        started = Date.now();
        timer = setTimeout(() => {
            noteUndoToast.remove();
            timer = null;
        }, remaining);
    };
    noteUndoToast.addEventListener("mouseenter", stop);
    noteUndoToast.addEventListener("mouseleave", start);
    noteUndoToast.addEventListener("focusin", stop);
    noteUndoToast.addEventListener("focusout", () =>
        queueMicrotask(() => {
            if (!noteUndoToast.contains(document.activeElement)) start();
        }),
    );
    noteUndoToast.querySelector("[data-note-undo-close]").addEventListener("click", () => {
        stop();
        noteUndoToast.remove();
    });
    noteUndoToast.querySelector("[data-note-undo]").addEventListener("click", async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        stop();
        try {
            const body = new FormData();
            body.set("token", noteUndoToast.dataset.token);
            const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
            const response = await fetch(noteUndoToast.dataset.url, {
                method: "POST",
                body,
                headers: { "X-CSRFToken": csrf },
            });
            if (!response.ok) throw new Error("This note can no longer be undone.");
            window.location.reload();
        } catch (error) {
            noteUndoToast.querySelector("[data-note-undo-message]").textContent = error.message;
            button.hidden = true;
            start();
        }
    });
    start();
}

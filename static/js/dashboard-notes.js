// Display Dashboard Notes and prevent repeat requests while a note is being saved or deleted.
window.DashboardNotes = {
    // Create once per page. getNotes reads the latest list after load() replaces page data.
    create({ get, getNotes, send, load, message, showUndo, escapeHtml }) {
        let addPending = false;
        const pendingNotes = new Set();
        // A refresh replaces saved notes, but only Save or Cancel should discard the current draft.
        let editDraft = null;
        // Note text and the edit form
        function noteBody(note, missing = false) {
            if (editDraft?.id === note.id) {
                const notice = missing
                    ? '<p role="status">This note is no longer available. Copy your draft before cancelling.</p>'
                    : "";
                return `${notice}<textarea maxlength="250" aria-label="Edit note">${escapeHtml(editDraft.content)}</textarea>
                    <div class="dashboard-note-edit-actions">
                        <button type="button" data-note-action="cancel">Cancel</button>
                        <button type="button" data-note-action="save" ${missing ? "disabled" : ""}>Save</button>
                    </div>`;
            }
            return `<p>${escapeHtml(note.content)}</p>
                <div class="dashboard-note-actions">
                    <button type="button" data-note-action="edit" aria-label="Edit note">
                        <svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M12.9 1.7a1.5 1.5 0 0 1 2.1 2.1l-9.5 9.5-3.1.8.8-3.1 9.7-9.3Zm-8.8 9.9-.3 1.1 1.1-.3 8.2-8.2-.8-.8-8.2 8.2Z"/></svg>
                    </button>
                    <button type="button" class="dashboard-note-delete" data-note-action="delete" aria-label="Delete note">
                        <svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M3.3 2.3 8 7l4.7-4.7 1 1L9 8l4.7 4.7-1 1L8 9l-4.7 4.7-1-1L7 8 2.3 3.3l1-1Z"/></svg>
                    </button>
                </div>
                <small>${escapeHtml(note.created)}</small>`;
        }

        function renderNotes() {
            const notes = getNotes();
            const list = get("notesList");
            const focusedEditor = list.querySelector("textarea:focus");
            const selection = focusedEditor
                ? [focusedEditor.selectionStart, focusedEditor.selectionEnd]
                : null;
            get("notesCount").textContent = notes.length;
            get("notesList").innerHTML = notes.length
                ? notes
                      .map(
                          (note) =>
                              `<article class="dashboard-note" data-note="${note.id}">${noteBody(note)}</article>`,
                      )
                      .join("")
                : '<p class="dashboard-empty">No notes yet.</p>';
            if (editDraft && !notes.some((note) => note.id === editDraft.id)) {
                list.insertAdjacentHTML(
                    "beforeend",
                    `<article class="dashboard-note" data-note="${editDraft.id}">${noteBody(editDraft, true)}</article>`,
                );
            }
            if (selection) {
                const editor = list.querySelector("textarea");
                editor?.focus({ preventScroll: true });
                editor?.setSelectionRange(...selection);
            }
        }

        get("notesList").addEventListener("input", (event) => {
            if (editDraft && event.target.matches("textarea")) {
                editDraft.content = event.target.value;
            }
        });

        // Add a note. Keep its text when saving fails so the user can retry.
        get("noteForm").addEventListener("submit", async (event) => {
            event.preventDefault();
            if (addPending) return;
            addPending = true;
            const submit = get("noteForm").querySelector('[type="submit"]');
            if (submit) submit.disabled = true;
            try {
                await send({
                    action: "add",
                    kind: "note",
                    content: get("noteContent").value.trim(),
                });
                get("noteContent").value = "";
                try {
                    await load();
                    get("notesList").scrollTop = 0;
                    message("Note added.");
                } catch {
                    message("Note added, but Dashboard could not refresh. Reload the page.", {
                        error: true,
                    });
                }
            } catch (error) {
                message(error.message, { error: true });
            } finally {
                addPending = false;
                if (submit) submit.disabled = false;
            }
        });
        // Edit, cancel, save or delete an existing note.
        get("notesList").addEventListener("click", async (event) => {
            const button = event.target.closest("[data-note-action]");
            if (!button) return;
            const note = button.closest("[data-note]");
            const id = Number(note.dataset.note);
            const action = button.dataset.noteAction;
            if (pendingNotes.has(id)) return;
            if (action === "edit") {
                editDraft = { id, content: getNotes().find((item) => item.id === id).content };
                renderNotes();
                get("notesList").querySelector(`[data-note="${id}"] textarea`).focus();
                return;
            }
            if (action === "cancel") {
                editDraft = null;
                renderNotes();
                return;
            }
            const currentNote = getNotes().find((item) => item.id === id);
            const editedContent =
                action === "save" ? note.querySelector("textarea").value.trim() : "";
            const submittedDraft = editDraft;
            function clearSavedDraft() {
                // A slow save must not close another editor or discard text typed while it was pending.
                if (
                    editDraft === submittedDraft &&
                    editDraft?.id === id &&
                    editDraft.content.trim() === editedContent
                )
                    editDraft = null;
            }
            if (action === "save" && currentNote && editedContent === currentNote.content) {
                clearSavedDraft();
                renderNotes();
                return;
            }
            pendingNotes.add(id);
            button.disabled = true;
            try {
                let result;
                if (action === "delete")
                    result = await send({ action: "delete", kind: "note", id });
                else {
                    result = await send({
                        action: "edit",
                        kind: "note",
                        id,
                        content: editedContent,
                    });
                    if (result.changed === false) {
                        clearSavedDraft();
                        renderNotes();
                        return;
                    }
                }
                if (action === "save") clearSavedDraft();
                try {
                    await load();
                    if (result.undo_token) showUndo("note", id, result.undo_token, "Note deleted.");
                    else message("Note updated.");
                } catch {
                    message("Note changed, but Dashboard could not refresh. Reload the page.", {
                        error: true,
                    });
                }
            } catch (error) {
                message(error.message, { error: true });
            } finally {
                pendingNotes.delete(id);
                button.disabled = false;
            }
        });

        return { render: renderNotes };
    },
};

// Build and submit Dashboard dialogs. The page controller updates lists after a successful save.
window.DashboardDialogs = {
    /**
     * Create once per Dashboard page. Read current data through the supplied getters.
     * Record saves await onSaved(type, "added" | "updated", result); confirmations call load().
     * If that refresh fails, report that the save succeeded and the page needs reloading.
     */
    create({
        get,
        getData,
        getSelectedDate,
        findRecord,
        send,
        load,
        message,
        onSaved,
        escapeHtml,
    }) {
        let recordTarget = null;
        let confirmTarget = null;
        let workPending = false;
        let eventAddPending = false;
        let confirmPending = false;
        // Fields for Add Task, Add Issue and editing existing records
        function formField(name, label, value = "", type = "text") {
            const constraints = name === "title" ? 'maxlength="75" required' : "";
            return `<div class="dashboard-form-row">
                <label for="dashboard-field-${name}">${label}</label>
                <div class="dashboard-form-control">
                    <input id="dashboard-field-${name}" class="form-control"
                        name="${name}" type="${type}" value="${escapeHtml(value)}" ${constraints}>
                    <span class="dashboard-field-error" data-error-for="${name}" role="alert"></span>
                </div>
            </div>`;
        }
        function selectField(name, label, choices, selectedValue) {
            const options = choices
                .map(([value, text]) => {
                    const selected = String(value) === String(selectedValue ?? "");
                    return `<option value="${escapeHtml(value)}" ${selected ? "selected" : ""}>${escapeHtml(text)}</option>`;
                })
                .join("");
            return `<div class="dashboard-form-row">
                <label for="dashboard-field-${name}">${label}</label>
                <div class="dashboard-form-control">
                    <select id="dashboard-field-${name}" class="form-select" name="${name}">${options}</select>
                    <span class="dashboard-field-error" data-error-for="${name}" role="alert"></span>
                </div>
            </div>`;
        }
        // Keep the existing relationship selected even when it is absent from the available choices.
        function choicesWithCurrent(choices, id, title) {
            if (id && !choices.some(([value]) => String(value) === String(id))) {
                return [...choices, [id, title]];
            }
            return choices;
        }
        function workFields(type, item) {
            const data = getData();
            const properties = choicesWithCurrent(
                [
                    ["", "No property"],
                    ...data.properties.map((property) => [property.id, property.name]),
                ],
                item?.property_id,
                item?.property,
            );
            const priorities = [
                [1, "Low"],
                [2, "Medium"],
                [3, "High"],
                [4, "Urgent"],
            ];
            // All three work models validate titles at 75 characters.
            let html = formField("title", "Title", item?.title);
            html += `<div class="dashboard-form-row">
                <label for="dashboard-field-description">Description</label>
                <div class="dashboard-form-control">
                    <textarea id="dashboard-field-description" class="form-control"
                        name="description" maxlength="1000">${escapeHtml(item?.description)}</textarea>
                    <span class="dashboard-field-error" data-error-for="description" role="alert"></span>
                </div>
            </div>`;
            if (type === "task") {
                let relationship = "standalone";
                if (item?.issue_id) relationship = "issue";
                else if (item?.property_id) relationship = "property";
                html += selectField(
                    "relationship_type",
                    "Related to",
                    [
                        ["standalone", "Not linked"],
                        ["property", "Property"],
                        ["issue", "Issue"],
                    ],
                    relationship,
                );
                html += `<div data-relation="property">${selectField("property", "Property", properties, item?.property_id)}</div>`;
                const issues = choicesWithCurrent(
                    [["", "No issue"], ...data.issues.map((issue) => [issue.id, issue.title])],
                    item?.issue_id,
                    item?.issue_title,
                );
                html += `<div data-relation="issue">${selectField("issue", "Issue", issues, item?.issue_id)}</div>`;
                html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
                html += formField("scheduled_date", "Scheduled date", item?.date, "date");
                html += formField("completion_deadline", "Completion deadline", item?.due, "date");
            } else if (type === "issue") {
                html += selectField("property", "Property", properties, item?.property_id);
                html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
                html += formField("resolution_deadline", "Resolve by", item?.due, "date");
            } else {
                html += selectField("property", "Property", properties, item?.property_id);
                html += formField(
                    "scheduled_date",
                    "Date",
                    item?.date || getSelectedDate(),
                    "date",
                );
                html += `<div class="dashboard-form-row">
                    <span>Time</span>
                    <label class="dashboard-check">
                        <input class="form-check-input" name="all_day" type="checkbox"
                            ${(item?.all_day ?? true) ? "checked" : ""}> All day
                    </label>
                </div>
                <div class="dashboard-event-time-row">
                    <div data-time-field>${formField("start_time", "Start time (HH:MM)", item?.start_time)}</div>
                    <div data-time-field>${formField("end_time", "End time (HH:MM)", item?.end_time)}</div>
                </div>
                <div class="dashboard-form-row dashboard-requirements">
                    <span>Requirements</span>
                    <div>
                        <label class="dashboard-check">
                            <input class="form-check-input" name="user_participation_required" type="checkbox"
                                ${item?.user_participation_required ? "checked" : ""}> My participation is required
                        </label>
                        <label class="dashboard-check">
                            <input class="form-check-input" name="user_presence_required" type="checkbox"
                                ${item?.user_presence_required ? "checked" : ""}> My physical presence is required
                        </label>
                    </div>
                </div>`;
            }
            return html;
        }
        function openWork(
            type,
            id = null,
            proposedDate = null,
            returnFocus = document.activeElement,
        ) {
            const item = id ? findRecord(type, id) : null;
            recordTarget = { type, id };
            get("workDialogHeading").textContent = `${id ? "Edit" : "Add"} ${type}`;
            window.SearchableSelect?.destroyWithin(get("workFormFields"));
            get("workFormFields").innerHTML = workFields(type, item);
            window.SearchableSelect?.init(get("workFormFields"));
            if (proposedDate)
                get("workForm").elements.namedItem("scheduled_date").value = proposedDate;
            get("workFormErrors").textContent = "";
            updateRelationshipFields();
            updateEventTimeFields();
            get("workDialog")._dashboardReturnFocus =
                window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
            bootstrap.Modal.getOrCreateInstance(get("workDialog")).show();
        }
        // Shared Add Event form and its validation messages
        const addEventForm = get("dashboardAddEventForm");
        const addEventModal = get("dashboardAddEventModal");
        const eventForm = window.EventForm.forForm(addEventForm);
        const activateAddEventTab = eventForm.activateTab;

        function clearAddEventErrors() {
            const errorIds = new Set(
                [...addEventForm.querySelectorAll("[data-dashboard-event-error]")].map(
                    (error) => error.id,
                ),
            );
            addEventForm.querySelectorAll("[aria-describedby]").forEach((field) => {
                const descriptions = field
                    .getAttribute("aria-describedby")
                    .split(/\s+/)
                    .filter((id) => !errorIds.has(id));
                if (descriptions.length)
                    field.setAttribute("aria-describedby", descriptions.join(" "));
                else field.removeAttribute("aria-describedby");
            });
            addEventForm
                .querySelectorAll("[data-dashboard-event-error]")
                .forEach((error) => error.remove());
            addEventForm
                .querySelectorAll('[aria-invalid="true"]')
                .forEach((field) => field.removeAttribute("aria-invalid"));
        }
        function showAddEventErrors(error) {
            const errors = error.fieldErrors;
            if (!errors) {
                const message = document.createElement("p");
                message.className = "invalid-feedback d-block";
                message.dataset.dashboardEventError = "true";
                message.textContent = error.message;
                get("dashboardAddEventDetailsPanel").prepend(message);
                activateAddEventTab("details");
                return;
            }
            let firstField = null;
            for (const [name, messages] of Object.entries(errors)) {
                const panel =
                    name === "contacts"
                        ? get("dashboardAddEventParticipantsPanel")
                        : get("dashboardAddEventDetailsPanel");
                const field =
                    name === "contacts"
                        ? get("dashboardEventContactsSearch")
                        : addEventForm.elements.namedItem(name);
                const message = document.createElement("p");
                message.className = "invalid-feedback d-block";
                message.dataset.dashboardEventError = "true";
                message.textContent = messages.join(" ");
                if (field instanceof HTMLElement) {
                    message.id = `${field.id}_dashboard_error`;
                    field.setAttribute("aria-invalid", "true");
                    const descriptions = [field.getAttribute("aria-describedby"), message.id]
                        .filter(Boolean)
                        .join(" ");
                    field.setAttribute("aria-describedby", descriptions);
                    (name === "contacts"
                        ? panel.querySelector(".event-contact-picker")
                        : field.parentElement
                    ).append(message);
                    window.SearchableSelect?.refresh(field);
                    firstField ||=
                        field.closest(".app-select")?.querySelector(".app-select-trigger") || field;
                } else panel.prepend(message);
            }
            activateAddEventTab(
                firstField?.name === "contacts" || firstField?.id === "dashboardEventContactsSearch"
                    ? "participants"
                    : "details",
            );
            firstField?.focus();
        }
        function openAddEvent(returnFocus = document.activeElement) {
            addEventForm.reset();
            clearAddEventErrors();
            addEventForm.elements.namedItem("scheduled_date").value =
                getSelectedDate() || getData().today;
            get("dashboardEventContactsSearch").value = "";
            window.SearchableSelect?.refresh(addEventForm.elements.namedItem("property"));
            eventForm.refresh();
            activateAddEventTab("details");
            addEventModal._dashboardReturnFocus =
                window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
            bootstrap.Modal.getOrCreateInstance(addEventModal).show();
        }
        // Validation and dependent fields in the general record editor
        function showWorkErrors(error) {
            const errors = error.fieldErrors;
            if (!errors) {
                get("workFormErrors").textContent = error.message;
                return;
            }
            const summary = [...(errors.__all__ || [])];
            let firstInvalid = null;
            for (const [name, messages] of Object.entries(errors)) {
                if (name === "__all__") continue;
                const field = get("workForm").elements.namedItem(name);
                const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find(
                    (element) => element.dataset.errorFor === name,
                );
                if (!field || !slot || field.closest("[hidden]")) {
                    summary.push(...messages);
                    continue;
                }
                slot.textContent = messages.join(" ");
                slot.id = `workError_${name}`;
                field.setAttribute("aria-invalid", "true");
                field.setAttribute("aria-describedby", slot.id);
                field.classList.add("is-invalid");
                const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
                if (trigger) {
                    trigger.setAttribute("aria-invalid", "true");
                    trigger.setAttribute("aria-describedby", slot.id);
                }
                firstInvalid ||= field;
            }
            get("workFormErrors").textContent = summary.join(" ");
            if (firstInvalid)
                (
                    firstInvalid.closest(".app-select")?.querySelector(".app-select-trigger") ||
                    firstInvalid
                ).focus();
        }
        function clearWorkErrors() {
            get("workFormErrors").textContent = "";
            get("workFormFields").querySelectorAll("[name]").forEach(clearFieldError);
        }
        function updateRelationshipFields() {
            const relation = get("workForm").elements.namedItem("relationship_type")?.value;
            get("workForm")
                .querySelectorAll("[data-relation]")
                .forEach((section) => {
                    section.hidden = section.dataset.relation !== relation;
                });
        }
        function updateEventTimeFields({ clear = false } = {}) {
            const allDay = get("workForm").elements.namedItem("all_day");
            get("workForm")
                .querySelectorAll("[data-time-field]")
                .forEach((section) => {
                    const input = section.querySelector("input");
                    if (clear && allDay?.checked) input.value = "";
                    input.disabled = !!allDay?.checked;
                });
        }
        // Confirmation text and optional changes to linked Tasks
        function openConfirm(type, id, action, returnFocus = document.activeElement) {
            confirmTarget = { type, id, action };
            const item = findRecord(type, id);
            const linkedCount =
                type === "issue"
                    ? action === "finish"
                        ? item.active_linked_tasks
                        : action === "delete"
                          ? item.linked_tasks
                          : 0
                    : 0;
            get("confirmLinkedTasksWrap").hidden = !linkedCount;
            get("confirmLinkedTasks").checked = false;
            get("confirmLinkedTasksLabel").textContent =
                action === "finish"
                    ? `Also dismiss ${linkedCount} active linked task${linkedCount === 1 ? "" : "s"}`
                    : `Also delete ${linkedCount} linked task${linkedCount === 1 ? "" : "s"}, including historical tasks`;
            const copy =
                action === "delete"
                    ? {
                          heading: `Delete ${type}?`,
                          text: `This ${type} will be removed from your workspace.`,
                          cancel: `Keep ${type}`,
                          submit: `Delete ${type}`,
                      }
                    : action === "cancel"
                      ? {
                            heading: "Cancel event?",
                            text: "The event will be marked as cancelled and retained in your history.",
                            cancel: "Keep event",
                            submit: "Cancel event",
                        }
                      : {
                            heading: "Resolve issue?",
                            text: "The issue will be marked as resolved and retained in your history.",
                            cancel: "Keep issue",
                            submit: "Resolve issue",
                        };
            get("confirmHeading").textContent = copy.heading;
            get("confirmText").textContent = copy.text;
            get("confirmCancel").textContent = copy.cancel;
            get("confirmAction").textContent = copy.submit;
            get("confirmAction").classList.toggle("dashboard-danger-button", action === "delete");
            get("confirmError").textContent = "";
            get("confirmDialog")._dashboardReturnFocus =
                window.WorkspaceModalReturnFocus?.resolve(returnFocus) || returnFocus;
            bootstrap.Modal.getOrCreateInstance(get("confirmDialog")).show();
        }

        // Save the Add Event form
        addEventForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (eventAddPending) return;
            eventAddPending = true;
            clearAddEventErrors();
            const saveButton = addEventForm.querySelector('[type="submit"]');
            saveButton.disabled = true;
            const fields = new FormData(addEventForm);
            fields.set("action", "add");
            fields.set("kind", "event");
            try {
                const result = await send(fields);
                eventAddPending = false;
                bootstrap.Modal.getOrCreateInstance(addEventModal).hide();
                try {
                    await onSaved("event", "added", result);
                    message("Event added.");
                } catch {
                    message("Event added, but Dashboard could not refresh. Reload the page.", {
                        error: true,
                    });
                }
            } catch (error) {
                showAddEventErrors(error);
            } finally {
                eventAddPending = false;
                saveButton.disabled = false;
            }
        });
        // Update and submit the general record editor
        get("workForm").addEventListener("change", (event) => {
            if (event.target.name === "relationship_type") updateRelationshipFields();
            if (event.target.name === "all_day")
                updateEventTimeFields({ clear: event.target.checked });
            if (event.target.name === "user_presence_required" && event.target.checked) {
                get("workForm").elements.namedItem("user_participation_required").checked = true;
            }
            if (event.target.name === "user_participation_required" && !event.target.checked) {
                get("workForm").elements.namedItem("user_presence_required").checked = false;
            }
        });
        function clearFieldError(field) {
            if (!field?.name) return;
            field.classList.remove("is-invalid");
            field.removeAttribute("aria-invalid");
            field.removeAttribute("aria-describedby");
            const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
            trigger?.removeAttribute("aria-invalid");
            trigger?.removeAttribute("aria-describedby");
            const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find(
                (element) => element.dataset.errorFor === field.name,
            );
            if (slot) slot.textContent = "";
        }
        get("workForm").addEventListener("input", (event) => clearFieldError(event.target));
        get("workForm").addEventListener("change", (event) => clearFieldError(event.target));
        get("workForm").addEventListener("submit", async (event) => {
            event.preventDefault();
            const saveButton = get("workForm").querySelector('[type="submit"]');
            if (workPending) return;
            workPending = true;
            clearWorkErrors();
            saveButton.disabled = true;
            const fields = new FormData(get("workForm"));
            fields.set("action", recordTarget.id ? "edit" : "add");
            fields.set("kind", recordTarget.type);
            if (recordTarget.id) fields.set("id", recordTarget.id);
            if (recordTarget.type === "task") {
                if (fields.get("relationship_type") !== "property") fields.set("property", "");
                if (fields.get("relationship_type") !== "issue") fields.set("issue", "");
            }
            try {
                const operation = recordTarget.id ? "updated" : "added";
                const label = { task: "Task", issue: "Issue", event: "Event" }[recordTarget.type];
                const result = await send(fields);
                workPending = false;
                bootstrap.Modal.getOrCreateInstance(get("workDialog")).hide();
                if (result.changed !== false) {
                    try {
                        await onSaved(recordTarget.type, operation, result);
                        message(`${label} ${operation}.`);
                    } catch {
                        message(
                            `${label} ${operation}, but Dashboard could not refresh. Reload the page.`,
                            { error: true },
                        );
                    }
                }
            } catch (error) {
                showWorkErrors(error);
            } finally {
                workPending = false;
                saveButton.disabled = false;
            }
        });
        // Submit a confirmed action, including the linked Task choice.
        get("confirmAction").addEventListener("click", async () => {
            const confirmButton = get("confirmAction");
            if (confirmPending) return;
            confirmPending = true;
            confirmButton.disabled = true;
            try {
                const { type, action } = confirmTarget;
                await send({
                    action,
                    kind: type,
                    id: confirmTarget.id,
                    confirm_linked_tasks: action === "finish" && type === "issue" ? "yes" : "",
                    affect_linked_tasks: get("confirmLinkedTasks").checked ? "yes" : "",
                });
                confirmPending = false;
                bootstrap.Modal.getOrCreateInstance(get("confirmDialog")).hide();
                const label = { task: "Task", issue: "Issue", event: "Event" }[type];
                const verb =
                    action === "finish"
                        ? { task: "completed", issue: "resolved", event: "marked as occurred" }[
                              type
                          ]
                        : action === "cancel"
                          ? "cancelled"
                          : "deleted";
                try {
                    await load();
                    message(`${label} ${verb}.`);
                } catch {
                    message(`${label} ${verb}, but Dashboard could not refresh. Reload the page.`, {
                        error: true,
                    });
                }
            } catch (error) {
                get("confirmError").textContent = error.message;
            } finally {
                confirmPending = false;
                confirmButton.disabled = false;
            }
        });
        // Keep dialogs open during a request and restore focus after Bootstrap has closed them.
        document.querySelectorAll("[data-close-dialog]").forEach((button) =>
            button.addEventListener("click", () => {
                const dialog = button.closest(".dashboard-dialog");
                if (
                    (dialog.id === "workDialog" && workPending) ||
                    (dialog.id === "confirmDialog" && confirmPending)
                )
                    return;
                bootstrap.Modal.getOrCreateInstance(dialog).hide();
            }),
        );
        for (const [id, pending] of [
            ["workDialog", () => workPending],
            ["confirmDialog", () => confirmPending],
        ]) {
            get(id).addEventListener("hide.bs.modal", (event) => {
                if (pending()) event.preventDefault();
            });
            get(id).addEventListener("hidden.bs.modal", () => {
                const previous = get(id)._dashboardReturnFocus;
                window.WorkspaceModalReturnFocus?.restore(previous);
            });
        }
        get("workDialog").addEventListener("shown.bs.modal", () =>
            get("workForm").elements.namedItem("title").focus(),
        );
        addEventModal.addEventListener("hide.bs.modal", (event) => {
            if (eventAddPending) event.preventDefault();
        });
        addEventModal.addEventListener("hidden.bs.modal", () => {
            const previous = addEventModal._dashboardReturnFocus;
            window.WorkspaceModalReturnFocus?.restore(previous);
        });
        addEventModal.addEventListener("shown.bs.modal", () =>
            addEventForm.elements.namedItem("title").focus(),
        );
        get("confirmDialog").addEventListener("shown.bs.modal", () => get("confirmCancel").focus());

        return { openWork, openAddEvent, openConfirm };
    },
};

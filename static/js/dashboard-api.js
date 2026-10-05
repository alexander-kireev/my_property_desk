// Send Dashboard requests and keep server validation messages available to the forms.
window.DashboardApi = {
    /**
     * send(fields) accepts FormData, URLSearchParams or a plain field object.
     * Failed saves reject with a message and, when supplied by Django, fieldErrors.
     * load() fetches fresh page data; neither method changes the UI.
     */
    create({ actionUrl, dataUrl, csrfToken }) {
        function recordError(body) {
            if (body.error) return body.error;
            if (body.errors)
                return Object.entries(body.errors)
                    .map(([field, values]) => `${field}: ${values.join(", ")}`)
                    .join(" · ");
            return "Unable to save. Please try again.";
        }
        async function send(fields) {
            const body = new URLSearchParams(fields);
            let response;
            try {
                response = await fetch(actionUrl, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": csrfToken,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    credentials: "same-origin",
                    body,
                });
            } catch {
                throw new Error("Could not connect. Check your connection and try again.");
            }
            const result = await response.json().catch(() => null);
            if (!result)
                throw new Error("The server could not process that request. Please try again.");
            if (!response.ok) {
                const error = new Error(recordError(result));
                error.fieldErrors = result.errors || null;
                throw error;
            }
            return result;
        }
        async function load() {
            try {
                const response = await fetch(dataUrl, { credentials: "same-origin" });
                if (!response.ok) throw new Error("Server response was not successful.");
                return await response.json();
            } catch {
                throw new Error("Dashboard could not load. Refresh the page to try again.");
            }
        }
        return { send, load };
    },
};

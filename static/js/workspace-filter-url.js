// Remove a filter while retaining selection, sorting and other navigation context.
(() => {
    function withoutFilter(currentUrl, name) {
        const url = new URL(currentUrl);
        url.searchParams.delete(name);
        // Snapshot the entries because deletion changes the URL's live parameters.
        for (const [key, value] of [...url.searchParams]) {
            if (!value.trim()) url.searchParams.delete(key);
        }
        return url;
    }

    window.WorkspaceFilterUrl = {
        clear(name) {
            window.location.assign(withoutFilter(window.location.href, name).toString());
        },
        withoutFilter,
    };
})();

document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector(".property-command-centre");
    if (!workspace) return;

    workspace.querySelectorAll(".property-related-record, .property-record").forEach((record) => {
        record.addEventListener("toggle", () => {
            if (!record.open) return;
            window.WorkspaceReveal?.queueRange(
                record.querySelector("summary"), record.lastElementChild,
                () => window.ExpandableText?.refresh(record),
            );
        });
    });

});

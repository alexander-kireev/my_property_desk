/* Public contact tabs; both forms submit normally to Django. */
(() => {
    const tabs = [document.getElementById("report-tab"), document.getElementById("message-tab")];
    const panels = [
        document.getElementById("report-panel"),
        document.getElementById("message-panel"),
    ];

    function selectTab(index, focus = true) {
        tabs.forEach((tab, position) => {
            const selected = position === index;
            tab.setAttribute("aria-selected", String(selected));
            tab.tabIndex = selected ? 0 : -1;
            panels[position].hidden = !selected;
        });
        if (focus) tabs[index].focus();
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => selectTab(index));
        tab.addEventListener("keydown", (event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                event.preventDefault();
                selectTab((index + 1) % tabs.length);
            }
        });
    });

    const topic = new URLSearchParams(window.location.search).get("topic");
    if (topic === "suggestion" || topic === "question") {
        selectTab(1, false);
        document.getElementById("id_message-topic").value =
            topic === "suggestion" ? "Suggestion" : "Question";
    }
})();

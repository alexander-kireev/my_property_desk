// The heading, calendar and date filters share the browser's local calendar day.
// Keep date-only values local here; converting through UTC can shift the day.
(() => {
    const today = (now = new Date()) =>
        `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    window.DashboardClock = { today };
    const greeting = document.querySelector("[data-dashboard-greeting]");
    const dateLabel = document.querySelector(".dashboard-greeting-date");
    if (!greeting) return;
    let previousDay = today();
    function update() {
        const now = new Date();
        const currentDay = today(now);
        const hour = now.getHours();
        greeting.textContent =
            hour < 5
                ? "Hello"
                : hour < 12
                  ? "Good morning"
                  : hour < 18
                    ? "Good afternoon"
                    : "Good evening";
        if (dateLabel)
            dateLabel.textContent = now.toLocaleDateString("en-GB", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
            });
        if (currentDay !== previousDay) {
            previousDay = currentDay;
            document.dispatchEvent(
                new CustomEvent("dashboard:date-change", { detail: { today: currentDay } }),
            );
        }
    }
    update();
    setInterval(update, 60000);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) update();
    });
})();

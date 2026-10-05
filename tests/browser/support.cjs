const { chromium } = require("playwright-core");

// Use the installed browser; these focused checks never download browsers.
async function launchBrowser() {
    const executablePath = process.env.PMS_CHROME_PATH;
    return chromium.launch(executablePath ? { executablePath } : { channel: "chrome" });
}

module.exports = { launchBrowser };

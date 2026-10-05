import js from "@eslint/js";
import globals from "globals";

// Lint authored browser code. Local reports, vendor code and the separate
// acceptance project are outside this baseline.
export default [
    {
        ignores: ["static/vendor/**", "build_docs/**", "tests/acceptance/**"],
    },
    {
        files: ["static/js/*.js"],
        languageOptions: {
            ecmaVersion: "latest",
            sourceType: "script",
            globals: { ...globals.browser, bootstrap: "readonly" },
        },
        rules: {
            ...js.configs.recommended.rules,
        },
    },
];

// The two React hook rules and nothing else (ADR 0094, decision 3).
//
// A stale closure is the one class of defect in this frontend that is both
// likely and silent: `tsc` cannot see a dependency list, and a callback that
// captured the first render's socket fails without an error. No style or
// formatting rules on purpose -- formatting is not what breaks here, and a
// large rule set would bury the two rules that matter under warnings nobody
// reads. Runs in `npm run build`, so the image build fails on a violation.
import tsParser from "@typescript-eslint/parser";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "react-hooks": reactHooks },
    linterOptions: {
      // A disable comment that no longer suppresses anything is a stale
      // exception, and an exception nobody can check is the thing this
      // config exists to remove.
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
    },
  },
];

import { spawnSync } from "node:child_process";

// Turnstile site keys are public. This is the key currently served by landfallai.live.
// Set REACT_APP_TURNSTILE_SITE_KEY before building to override it after a rotation.
const currentTurnstileSiteKey = "0x4AAAAAADKjKSXUEv450mzi";
const environment = {
  ...process.env,
  REACT_APP_API_URL: "https://api.landfallai.live",
  REACT_APP_BACKEND_URL: "https://api.landfallai.live",
  REACT_APP_TURNSTILE_SITE_KEY:
    process.env.REACT_APP_TURNSTILE_SITE_KEY || currentTurnstileSiteKey
};

const npmCli = process.env.npm_execpath;
if (!npmCli) {
  throw new Error("npm_execpath is unavailable; run this build through npm");
}

const result = spawnSync(process.execPath, [npmCli, "--prefix", "frontend", "run", "build"], {
  cwd: process.cwd(),
  env: environment,
  stdio: "inherit"
});

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);

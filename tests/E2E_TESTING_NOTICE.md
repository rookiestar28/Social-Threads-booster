# Social-Threads-Booster E2E Notice

All E2E validation for this repository must follow `tests/E2E_TESTING_SOP.md`.

Important repo-specific clarification:

- E2E in this repository means **fixture-based CLI workflow validation** for local Python scripts.
- It does **not** mean browser automation or frontend Playwright unless such tooling is added to the repo in the future.
- Generated E2E artifacts must stay inside the workspace, normally under `.tmp/`.
- If a touched script requires Threads API credentials, record manual smoke evidence when credentials are available; otherwise explicitly record that the credentialed lane was unavailable.

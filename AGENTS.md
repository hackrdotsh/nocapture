# Nocapture

Native Noctalia v5 capture toolbar, initially targeting Niri on Linux.

- Use jj. Keep captures, recordings, and machine-local configuration out of the repository.
- Plugin code lives in `nocapture/`; `bin/nocapture` is only an IPC launcher.
- The Python backend owns Nocapture recordings; do not control the official Noctalia recorder or signal unrelated processes.
- Backend sources live in `backend/nocapture_backend/`. Ruff is approved for Python formatting and linting.
- Keep scripts compatible with Lua 5.4 as well as Luau so the headless tests exercise the actual sources.
- StyLua is approved for this repository. Use `nix run .#fmt` before `nix run .#check`.
- Native UI, compositor capture, clipboard, and video output need a real Wayland session; mocked tests do not prove them.
- Do not enable plugins or change the user's Niri/Noctalia settings without asking.
- For live testing, follow `.agents/skills/verify-nocapture/SKILL.md`. Never accept a portal recording without checking the captured source; row order changes between requests.

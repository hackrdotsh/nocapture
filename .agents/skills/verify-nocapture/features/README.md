# Feature map

Nocapture has a Noctalia desktop UI and a Python capture CLI. Use the isolated
fixture described in the parent skill for screenshot and UI work. Real portal
video needs the host compositor and a controlled test window.

| Feature | Entry points | Recipe | Coverage |
|---|---|---|---|
| Screenshot and styling | Toolbar; `nocapture-engine screenshot` | [Screenshots](screenshots.md) | Region, display, window, wallpaper, shadow, clipboard |
| Recording and GIF | Toolbar; `nocapture-engine record/stop/status` | [Recording](recording.md) | Window MP4/GIF; KMS modes blocked without permissions |
| Audio isolation | Toolbar audio selector; `record --audio` | [Audio](audio.md) | Real application isolation; system/mic combined video needs KMS |
| Cancellation and failures | Escape, Close, stop, invalid targets | [Lifecycle](lifecycle.md) | Regression tests and live cancellation |

Snapshots and command logs are named inside the explicit instance directory.
The verification report records the boundary actually exercised, including
failures; none of these recipes imply that future changes have passed.

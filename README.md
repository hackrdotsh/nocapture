# Nocapture

A native Noctalia v5 capture toolbar for Niri/Wayland, inspired by macOS's **⌘⇧5**.

## Capture modes

| Target | PNG screenshot | MP4 video | Animated GIF | Audio |
|---|---|---|---|---|
| Selected region | Yes | Yes | Yes | None, system, microphone, or both |
| Window | Yes | Yes, through a window-only portal picker | Yes | None or one application's audio |
| Full display, including all visible windows | Yes | Yes | Yes | None, system, microphone, or both |

Window screenshots can include the **current Noctalia wallpaper** as a padded
background and an optional **macOS-inspired soft shadow**. Shadow-only exports
retain transparent space around the window. Padding is configurable.

Select **Screenshot**, **Video**, or **GIF**, then a target. For window screenshots,
choose a window from the list. For window recordings, choose the window in the
system picker; its contents are captured rather than a rectangle of the desktop.
Moving or covering it does not intentionally change the source to other windows.

**Application audio is explicit:** choose the application whose audio belongs to
the window you select. The backend captures that application's audio, not the
system mix. Play audio before opening the toolbar so the application appears in
the list. Applications can share audio across multiple windows; isolation is by
application name, not by tab or individual window. If no source is available,
Nocapture fails rather than falling back to system audio.

GIFs have no audio. Recording first creates an MP4, then builds a palette and
converts it to a looping GIF on stop. The toolbar reports conversion in progress.
The source video is retained if conversion fails.

## Install and run

Build with Nix, then install `packages.<system>.default` through Home Manager or
your preferred Nix profile workflow. The package includes `nocapture`,
`nocapture-engine`, the plugin, and runtime dependencies. Both executables must
be on **Noctalia's PATH**, not just in a terminal's development shell.

```sh
nix build
./result/bin/nocapture --help
```

After reviewing the plugin, register the checkout for hot reload:

```sh
noctalia msg plugins source add nocapture-dev path "$PWD"
noctalia msg plugins enable 0xhckr/nocapture
nocapture
```

These commands change your Noctalia configuration; builds and tests do not run
them automatically. The packaged plugin is also available at
`result/share/noctalia/plugins/nocapture`. Register the parent directory as a path
source if you want the built version rather than a live checkout.

Noctalia v5 with plugin API 24 or newer is required; v4 is not supported. Region
and display recording use GPU Screen Recorder's KMS capture and need its host
permissions. On NixOS, the usual setup is:

```nix
programs.gpu-screen-recorder.enable = true;
```

This creates a privileged capture-helper wrapper; review that permission before
enabling it. Nocapture does not enable it, run sudo, or change your system config.
Window recording instead requires a desktop portal implementing **window**
ScreenCast and PipeWire. A portal without window support is rejected.

The bundled GPU Screen Recorder has a small, source-pinned Nix patch:
`-w portal` requests windows only and rejects unsupported source types. Region
and display capture remain unchanged. This prevents the window picker from
offering a monitor capture as a substitute. Nocapture uses GPU encoding with
the backend's CPU fallback if GPU encoding is unavailable.

Nocapture owns its recorder process and a private control socket. It does **not**
use or require `noctalia/screen_recorder`, change its settings, or stop its
recordings. Do not run two capture engines concurrently if your GPU cannot
support that workload.

Optional Niri binding once installed:

```kdl
binds {
    Mod+Shift+5 { spawn "nocapture"; }
}
```

Optional Noctalia bar widget:

```toml
[widget.nocapture]
type = "0xhckr/nocapture:bar"
```

Add `"nocapture"` to a bar's `start`, `center`, or `end` list. No bar widget is
required to use the toolbar or stop a recording.

## Settings and commands

The plugin settings configure screenshot/recording folders, window padding,
video FPS, GIF FPS, and maximum GIF width. Defaults: `~/Pictures/Nocapture`,
`~/Videos/Nocapture`, 96px padding, 30 FPS video, and 15 FPS/1280px GIFs.
Screenshots are saved and copied to the clipboard. Captures use unique filenames.

```sh
nocapture                 # Toggle toolbar
nocapture show            # Open toolbar (also while recording)
nocapture hide            # Close toolbar, without stopping a recording
nocapture stop            # Finalize only Nocapture's recording
nocapture status          # JSON state: starting/recording/stopping/converting/saved/error
nocapture doctor          # Check shell/plugin/engine presence, not capture permissions

nocapture-engine screenshot window --wallpaper --shadow
nocapture-engine record region --audio system
nocapture-engine record display --output eDP-1 --format gif
nocapture-engine record window --audio application --application 'Firefox'
```

Direct `record` runs in the foreground until stopped with Ctrl+C or `nocapture
stop`. The Noctalia UI runs it in the background. Selection cancellation produces
no completed capture. Stopping during GIF conversion does not cancel conversion.
Worker diagnostics live in `$XDG_RUNTIME_DIR/nocapture-<uid>/recording.log`.

## Development and verification

```sh
direnv allow
nix develop
nix run .#fmt
nix run .#check
nix flake check
nix run .#test
noctalia plugins lint nocapture
```

Development apps run from the repository root. `.#dev` runs the launcher source.
The tests exercise the actual Luau scripts with a mocked host; Python tests check
image pixels, real FFmpeg GIF conversion, and subprocess start/stop/single-owner
behavior using a synthetic recorder. No real desktop or microphone is captured
by tests. x86-64 and ARM64 Linux are declared; only available builders are tested.

Before calling live capture verified, manually check all three targets on Niri:
cancel selectors, inspect PNG/clipboard output, compare the window background
to its display's wallpaper, play MP4/GIF output, move/occlude a recorded window,
and play two applications simultaneously to verify audio isolation. Repeat with
mixed-scale monitors. Build success and synthetic media tests do not establish
compositor, permission, GPU, or portal compatibility.

Current limitations: no annotation editor, countdown, combined multi-monitor
desktop video, or automatic window-to-audio mapping. Full display means one
selected display, not all connected monitors. The visual toolbar and real
capture/audio paths still require live verification.

## Upstream contracts

- [Noctalia plugin API](https://docs.noctalia.dev/noctalia/plugins/development/)
- [GPU Screen Recorder](https://git.dec05eba.com/gpu-screen-recorder/about/)
- [ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)

Nocapture is MIT licensed. Runtime dependencies retain their own licenses;
GPU Screen Recorder is GPL-3.0-only.

# Nocapture

A native Noctalia v5 capture toolbar inspired by macOS's **⌘⇧5**, initially for
Niri on Wayland. One floating panel selects screenshot or recording, then region,
display, or window. It uses Noctalia's palette and native controls.

## First version

- Region and display screenshots use Noctalia's built-in capture UI and output settings.
- Window screenshots capture Niri's focused window, using Niri's output settings.
- Recording uses the official `noctalia/screen_recorder` service. Region selection
  uses slurp; display captures the focused monitor; window mode opens the desktop
  portal picker (which may also offer monitors).
- Stop recording is always available; this version does not display recording
  status or a timer. The official recorder widget can provide those.
- The toolbar closes before invoking a capture. Escape dismisses it.

This is an initial implementation, not full macOS feature parity. No annotation,
countdown, unified save destination, or custom selection overlay yet. Capture
compatibility depends on your compositor, GPU, portal backend, and installed
versions. Noctalia v4 is not supported.

## Try it

Requirements: running Noctalia v5 with plugin API 24 or newer, Niri, native
`gpu-screen-recorder` and `slurp` on **Noctalia's PATH**, and a working ScreenCast
portal for window recording. The recorder plugin must support IPC source overrides
(`start region`, `start focused`, `start portal`; upstream 1.3.6 does).

From this repository, after reviewing the local plugin source:

```sh
noctalia msg plugins source add nocapture-dev path "$PWD"
noctalia msg plugins enable 0xhckr/nocapture
noctalia msg plugins enable noctalia/screen_recorder
nix run . -- doctor
nix run .
```

These commands change Noctalia's local plugin configuration; the project does not
run them automatically. Lua edits hot-reload. Reload Noctalia's config after
manifest edits. Disabling or reloading the official recorder stops active captures.

Optional bar widget, in your Noctalia configuration:

```toml
[widget.nocapture]
type = "0xhckr/nocapture:bar"
```

Add `"nocapture"` to a bar's `start`, `center`, or `end` list. The toolbar also
works without a bar widget.

For a Niri keybinding, first install the package with your preferred Nix/Home
Manager workflow so `nocapture` is on PATH, then add:

```kdl
binds {
    Mod+Shift+5 { spawn "nocapture"; }
}
```

`nix build` includes the plugin at `result/share/noctalia/plugins/nocapture` and
the launcher at `result/bin/nocapture`. Register `result/share/noctalia/plugins`
as a Noctalia path source if using the built package instead of this checkout.
The package does not replace or bundle your running Noctalia shell.

## Commands

```sh
nocapture           # Toggle toolbar
nocapture show      # Open toolbar
nocapture hide      # Close toolbar
nocapture stop      # Stop the official recorder's current recording
nocapture doctor    # Check plugins and native capture tools
```

Screenshot destinations and clipboard behavior belong to `[shell.screenshot]`
in Noctalia; window screenshots use Niri's `screenshot-path`. Recording options,
audio sources, and destinations belong to the official recorder's settings.

## Development

```sh
direnv allow
nix develop
nix run .#fmt
nix run .#check
nix flake check
nix build
nix run . -- --help
```

Development apps run from the repository root. `.#dev` runs the source launcher;
`.#test` runs behavioral tests. Both Linux x86-64 and ARM64 are declared; only
available builders are tested. StyLua formats the Lua-compatible Luau sources.

`tests/run.lua` exercises the actual plugin scripts with a mock host: mode routing,
close-before-capture, duplicate clicks, missing tools, disabled recorder, stale
callbacks, and command failures. `tests/cli.sh` checks the real launcher with a
fake Noctalia executable. These are not compositor integration tests.

Before calling capture behavior verified, test the live toolbar on Niri: cancel
both selectors; capture all three targets; inspect the PNG and clipboard; record
each target, stop, and play the MP4; confirm the toolbar is absent from the
capture; repeat on mixed-scale displays. Never commit the captures.

## Upstream contracts

- [Noctalia plugin API](https://docs.noctalia.dev/noctalia/plugins/development/)
- [Official recorder](https://github.com/noctalia-dev/official-plugins/tree/main/screen_recorder)
- [Noctalia screenshot widget](https://docs.noctalia.dev/noctalia/bar/widgets/screenshot/)

MIT licensed.

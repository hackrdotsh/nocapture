---
name: verify-nocapture
description: Verify Nocapture's Noctalia UI, screenshot output, recording lifecycle, and audio isolation after changes.
---

# Verify Nocapture

Run from the repository root on Linux with Nix and a running Wayland desktop.
Noctalia v5 must already be installed. The harness uses a separate Niri instance,
private D-Bus, temporary XDG directories, and synthetic video. It does not enable
plugins in the user's shell or change system capture permissions.

## Automated baseline

```sh
nix run .#check
nix flake check
noctalia plugins lint nocapture
```

## Launch and identify

Choose an unused absolute directory outside the repository:

```sh
nix run .#live -- --instance /tmp/opencode/nocapture-check launch
nix run .#live -- --instance /tmp/opencode/nocapture-check doctor
```

`identity.json` records the package store path, revision, and creation time.
`processes.json` records owned PIDs and start times. `env.json` contains an
allowlisted environment without credentials. The nested Niri opens as a window
on the main desktop; keep it visible while testing rendering.

## Drive and observe

```sh
nix run .#live -- --instance /tmp/opencode/nocapture-check exec -- nocapture show
nix run .#live -- --instance /tmp/opencode/nocapture-check snapshot toolbar.png
```

Inspect the screenshot before selecting controls. Coordinates are **logical**
pixels. The pointer helper supports clicks and drag selections:

```sh
nix run .#live -- --instance /tmp/opencode/nocapture-check pointer 450 400
nix run .#live -- --instance /tmp/opencode/nocapture-check pointer 40 70 440 370
nix run .#live -- --instance /tmp/opencode/nocapture-check exec -- wtype -k Escape
```

Do not select portal rows by numeric index: their order changes between requests.
Select by the visible test-window name and verify the recorded frames contain
the test pattern. A completed file alone is not evidence of the right source.

Follow the [feature map](features/README.md). Read the [observed verification
report](../../../docs/verification.md) for tested paths and blockers.

## Evidence

The harness retains command arguments, output, exit codes, snapshots, and
captures in the instance directory. Keep evidence outside source control.
Compare PNG contents against the clipboard and sample video frames. For audio,
use distinct 440/880/1320 Hz sources and measure recorded amplitudes with:

```sh
nix run .#live -- --instance /tmp/opencode/nocapture-check spectrum /path/to/recording.mp4
```

An application-audio pass needs the selected tone present and other tones absent,
not merely an audio stream in ffprobe. Delete unintended captures if a picker
selects a non-test source; retain only a numeric failure record.

## Cleanup

```sh
nix run .#live -- --instance /tmp/opencode/nocapture-check cleanup
```

Cleanup checks PID start times before signalling owned process groups and keeps
evidence. It can be repeated. Close any separately created host fixture windows
and stop their private audio services using their own recorded PIDs.

## Coverage limits

Nested Niri 26.04 cannot supply portal video frames (`no GBM device available`).
Use an explicitly controlled test window on the real compositor for video.
Full-display and region video require the privileged KMS helper; do not grant
permissions without approval. A missing helper is **blocked**, not passed.
One physical display does not establish mixed-monitor coverage, and an x86-64
build does not establish ARM64 runtime coverage.

Maintain this map using the shared `maintain-verification-skill` workflow when
capture paths or their entry points change.

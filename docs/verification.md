# Live verification — 2026-10-20

Tested the working revision based on `734678ae`, including the regression fixes
recorded with this report. The package was built from the checkout and exercised
through real Noctalia v5 and Niri 26.04. Test media and logs are outside the repo.

## Results

| Path | Result | Evidence |
|---|---|---|
| Noctalia toolbar | Passed | Real dark/light rendering, mode and target controls, Escape dismissal |
| Display screenshot | Passed | Isolated Niri display, 1500×1125 PNG |
| Region screenshot | Passed | Real slurp drag, 401×301 PNG at scale 1 |
| Fractional scaling | Passed | Same selection at scale 1.5 produced 601×451 physical pixels, within pixel rounding |
| Window screenshot | Passed | 726×454 raw PNG from the selected test window |
| Wallpaper, shadow, both | Passed | Three 918×646 styled captures; combined result visually inspected |
| Screenshot clipboard | Passed | Saved PNG and `wl-paste` data matched byte for byte |
| Screenshot process completion | Passed after fix | CLI returns while the clipboard provider continues serving data |
| Window MP4 with application audio | Passed | Real portal selection, moving test-pattern video, AAC audio |
| Application isolation | Passed | Selected 440 Hz signal; other app at 880 Hz rejected by 97.4 dB and simulated microphone at 1320 Hz by 95.5 dB |
| Silent window MP4 | Passed | Real video, no requested audio; frame samples contain the selected pattern |
| Window movement/resize/occlusion | Passed | Per-second test-pattern fractions stayed 0.868–0.882 while moving/resizing and covering the selected window |
| Window GIF | Passed | Correct selected source; 640×426, 33 frames, looping silent output |
| Slurp cancellation | Passed after fix | Exit 0, `state=cancelled`, no new capture file |
| Portal cancellation | Passed after fix | Exit 0, `state=cancelled`, null path/source, no saved notification |
| Missing window | Passed | Nonzero exit with an actionable message, rather than a completed capture |
| Region/full-display MP4 and GIF | **Blocked** | Privileged KMS helper absent; user chose to leave permissions unchanged |
| Live system/mic/both audio with region/display video | **Blocked** | Same KMS prerequisite; command routing is covered by tests, not live combined capture |
| Multiple physical monitors | **Not tested** | One physical display available; fractional scaling was tested separately |
| ARM64 runtime | **Not tested** | Tests/build ran on x86-64 Linux |

Nested Niri was used for screenshots and shell UI. Its portal cannot provide
video (`no GBM device available`), so video used a dedicated moving test window
on the real compositor. Audio was generated on private PipeWire/Pulse devices;
the user's default audio devices and physical microphone were not changed.

The pinned recorder does not support audio-only capture without `-w`. An attempted
independent audio-only probe was rejected; it is not counted as live verification
of the blocked combined audio modes.

## Defects found and fixed

1. `wl-copy` forks a persistent provider. Inheriting stdout/stderr kept the
   caller's captured pipes open and could hang the CLI and toolbar completion
   callback. Its standard streams are now detached. A regression test fails by
   timeout before the fix and completes in roughly 0.16 seconds after it.
2. The installed slurp prints `selection cancelled` to stderr on Escape. This
   normal cancellation was treated as failure. Both spellings are recognized;
   unrelated picker errors remain failures.
3. Cancelled recordings could retain an output path in JSON and trigger a false
   “Capture saved” notification. Cancellation now clears paths, and the UI only
   announces successful saved results.

## Test-method corrections

Portal row order changed between invocations. Two scripted runs selected the
wrong source; frame-content validation detected this. Those recordings were
deleted and are **not** counted as passes. Subsequent runs selected the visible
test-window label and verified the resulting frames.

A first nested capture probe was inconclusive because the nested window was
covered. Tests were repeated with it visible. A test expectation initially used
ceil instead of the capture tools' pixel rounding at scale 1.5; the actual
601×451 result was checked against the logical selection, not forced to 602×452.

## Reproduction and evidence

Follow `.agents/skills/verify-nocapture/SKILL.md`. The `.#live` harness was launched
from a fresh directory, exercised, and cleaned up while retaining evidence.
The automated suite includes 13 plugin tests, 16 Python tests, and CLI tests.

Local evidence:

- `/tmp/opencode/nocapture-live/`: original controlled fixtures, validated
  recordings, screenshot captures, spectrum measurements, and test logs.
- `/tmp/opencode/nocapture-repro/`: fresh harness run, dark/light UI snapshots,
  fractional-scale capture, cancellation and invalid-window results.

Captures remain untracked. No permanent shell, Niri, system permission, or audio
configuration changes were made. KMS testing requires a separately approved
helper setup and a new live run; this report does not claim that coverage.

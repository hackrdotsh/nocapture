# Cancellation and failures

- Open and Escape the toolbar: no capture should start.
- Escape slurp: exit zero with `state=cancelled`, no file and no saved notification.
- Cancel the window portal: same outcome, with no stale saved path in JSON.
- Stop a recording: finalize only Nocapture's process; an unrelated process must
  remain alive. Opening or closing the toolbar does not stop recording.
- Try a missing window ID: fail clearly and leave no empty capture.
- Kill a synthetic encoder or make GIF conversion fail: report error and retain
  any recoverable source video.
- Start twice: only one worker may own the capture socket/lock.
- If a desktop/portal prerequisite is unavailable, record its exact diagnostic
  and do not call the mode verified.

Regression tests cover clipboard-provider pipe inheritance and false saved
notifications. Live tests must also check the real slurp cancellation message:
it can write `selection cancelled` to stderr despite normal cancellation.

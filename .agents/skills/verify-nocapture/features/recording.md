# Recording

## Preconditions and entry points

Use a moving test pattern with a uniquely named host window. The nested fixture
is sufficient for controls but not video frames on Niri 26.04. The actual entry
point is `nocapture-engine record window --format mp4` or the toolbar Video mode.

## Drive and verify

1. Open the portal, inspect its source labels, select the test window by name,
   and confirm Share. Never assume the first row is the test source.
2. Wait for `nocapture status` to report recording. Capture several seconds.
3. Move/resize the test window and cover it with another controlled window.
4. Run `nocapture stop`; wait for saved. ffprobe must report a video stream, and
   sampled frames must still be the moving test pattern rather than the cover
   or another application.
5. Repeat with `--format gif`. Verify multiple frames, configured maximum width,
   a loop, and no audio. Failed conversion must retain its source MP4.
6. For region/display recordings repeat with a privileged KMS helper installed.
   Without that prerequisite, mark the modes blocked and do not run sudo.

Retain command logs, state transitions, frame-content checks, and output metadata.
Stop only the recorded Nocapture worker. Keep separate fixture-process ownership
records, and close those processes after tests.

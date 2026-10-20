# Audio

Use synthetic tones on private virtual audio devices, never the user's physical
microphone. Do not change the host's default sink or source.

- Play 440 Hz from the selected test application and 880 Hz from another app.
- Add a 1320 Hz source to a private simulated microphone.
- Record the test window with `--audio application --application <test name>`.
- Decode a nonempty interior second to mono samples and measure all three tones.
  The selected tone must be present, with each other tone at least 40 dB lower.
- Record with `--audio none`; ffprobe must report no audio stream.
- System, microphone, and both modes must contain the corresponding test tones;
  these combined Nocapture video paths need a usable KMS capture helper.

Source selection is by application, not a browser tab or individual audio stream.
Keep the spectrum JSON and known fixture frequencies. Stop the private audio
services and players using their exact recorded PIDs.

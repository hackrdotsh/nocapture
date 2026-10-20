# Screenshots

## Preconditions and entry points

Launch the isolated fixture and run `doctor`. Keep its parent window visible.
Open `nocapture show` through the harness. Select Screenshot and Region, Display,
or Window. For window captures, select the named test-pattern window.

## Drive and verify

- Capture a region with the pointer drag helper. The PNG must match the selected
  geometry (slurp's inclusive endpoints may add one pixel).
- Capture the display. It must contain the isolated desktop and no toolbar.
- Capture a window with neither styling toggle, each toggle alone, and both.
  The raw capture must have no padding; styling must preserve central window
  pixels, add configured padding, use the fixture wallpaper, and render a soft
  shadow with transparent margins when there is no wallpaper.
- Compare `wl-paste --type image/png` with the saved file, byte for byte.
- Capture via the CLI under a subprocess that captures stdout/stderr. It must
  exit while the clipboard provider remains alive.
- Repeat after changing the nested output scale to 1.5. Keep pointer coordinates
  logical, not screenshot pixels.

Retain the toolbar snapshot, result JSON, PNG dimensions, and clipboard hashes.
Never snapshot the user's desktop when a controlled nested display suffices.
Close the toolbar between runs; keep captures as evidence outside the repository.

# Golden frames

One PNG per skin and orientation, rendered from the `mock` provider with the example
configuration (`config.example.yaml`: Chicago coordinates, Fahrenheit, 12-hour clock) at a
fixed instant:

```bash
uv run paperwhite gallery -c config.example.yaml -o tests/goldens --now 2026-09-18T21:45:00+00:00
```

`tests/test_goldens.py` re-renders each frame and compares it with the file here. A golden
changes only on purpose: regenerate with the command above, look at the before/after, and
describe the visual change in the pull request. Fonts are bundled and Pillow is pinned in
`uv.lock`, so the same commit renders the same bytes on Linux, which is where the goldens
are made and where the service runs; regenerate them on Linux. On macOS the bundled
FreeType places the footer text one pixel off, so the test compares with a looser bound
there (1 % of pixels instead of 0.1 %).

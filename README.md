# AbletonOSC for LiveRemote

This is the control-surface script that connects **LiveRemote** (the iPad/iPhone
remote for Ableton Live) to Live on your Mac. It's an enhanced build of
[ideoforms/AbletonOSC](https://github.com/ideoforms/AbletonOSC) — same core,
plus the endpoints LiveRemote's browser search, fixed-length recording,
drum-pad names, and multi-device support depend on. **LiveRemote needs this
build; the stock upstream script will connect but leave features degraded.**

## Install (about two minutes, one time)

1. **Download**: tap the green **Code** button above → **Download ZIP**, and
   unzip it.
2. **Copy the `AbletonOSC` folder** (the one *inside* the unzipped download)
   into Live's User Library Remote Scripts folder:

   ```
   Macintosh HD → Music → Ableton → User Library → Remote Scripts
   ```

   That's `~/Music/Ableton/User Library/Remote Scripts` — if the
   `Remote Scripts` folder doesn't exist yet, create it with exactly that
   name. (Windows: `\Users\[you]\Documents\Ableton\User Library\Remote
   Scripts`.)
3. **Restart Ableton Live.**
4. In Live, open **Settings → Link, Tempo & MIDI** and choose **AbletonOSC**
   in any empty **Control Surface** slot. Leave its Input and Output set to
   **None** — it doesn't use MIDI ports.
5. Live shows *"AbletonOSC: Listening for OSC on port 11000"* in the status
   bar. You're done — open LiveRemote on the iPad, enter your Mac's name from
   **System Settings → General → Sharing**, and connect.

> **macOS may ask Live for Local Network permission** the first time — allow
> it, or the iPad can't reach the script.

## Updating

Delete the old `AbletonOSC` folder from `Remote Scripts`, copy the new one in,
and restart Live. LiveRemote will tell you in-app when a feature needs a newer
script build than the one installed.

> **Heads-up on Live updates:** major Live updates occasionally reset the
> Control Surface list. If LiveRemote stops connecting after an update, just
> re-select AbletonOSC in the Control Surface slot.

## What's different from upstream AbletonOSC?

- Library-wide browser search (`/live/browser/search`)
- Fixed-length session recording (`/live/clip_slot/fire_length`)
- Clip quantise endpoint with unwarped-audio guards (`/live/clip/quantize`)
- Drum-rack pad names for the pads and sequencer (`/live/track/get/drum_pads`)
- Return-track names for the mixer's sends (`/live/song/get/return_track_names`)
- Replies broadcast to every connected device, not just the most recent one
- Assorted robustness fixes (empty-clip-slot queries, logger noise, reload)

Upstream credit: [AbletonOSC](https://github.com/ideoforms/AbletonOSC) by
Daniel John Jones and contributors, MIT licensed — see [LICENSE.md](LICENSE.md).
This build keeps the same license.

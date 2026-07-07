# The Bridge — JUCE VST3 Plugin

Referenced from [[00-overview]] decision 2. This is the highest-risk, highest-manual-effort layer: Claude generates the C++, but the user compiles it and validates it by ear/eye in a real DAW — there is no way to run or hear an audio plugin in Claude's environment.

## Plugin type & host integration

- **VST3 only.** JUCE 8 bundles the VST3 SDK, so no separate Steinberg SDK download is required. VST2 is deprecated and requires a legacy Steinberg license — explicitly out of scope. AU/AAX (Mac/Pro Tools) are out of scope; Windows + VST3 covers the demo.
- **Master-bus insert, audio pass-through.** `processBlock()` does not modify the audio signal — DAWpro is an analyzer, not an effect. Input buffer is copied out to the capture ring buffer, then passed through untouched.
- **Test DAW: REAPER.** Free, fully-functional unlimited trial (occasional nag screen, no feature limits) — better for iterative dev/test than Ableton's expiring 90-day trial.

## Continuous capture (the "silent" part)

A lock-free circular buffer (`juce::AbstractFifo` over a fixed-size `juce::AudioBuffer<float>`) sized for the last **60 seconds** of stereo audio at the host's sample rate, continuously overwritten while the transport plays. Written from `processBlock()` (audio thread) — must be allocation-free and wait-free on that thread, since JUCE's real-time audio thread cannot block or allocate without causing dropouts/glitches in the DAW.

Metadata captured alongside, read each block via `AudioPlayHead::getCurrentPosition()`:
- BPM (`bpm`)
- Time signature (`timeSigNumerator`/`timeSigDenominator`)
- Playhead position / `isPlaying`

This metadata is cheap to read every block and stored as the "current" values, not buffered historically — only the latest snapshot at trigger time matters.

## Explicit-trigger send (the "not continuous to AI" part)

Plugin editor has one primary control: an **"Analyze" button** (plus a text field for the backend URL, defaulting to `http://localhost:8000`, and a status label). On click:

1. Snapshot the current ring-buffer contents into a `juce::AudioBuffer` copy (message thread, safe to allocate here).
2. Encode as WAV in memory (`juce::WavAudioFormat`).
3. Spawn a background `juce::Thread` (or `juce::ThreadPoolJob`) that does the multipart POST to `/analyze` (per [[01-json-contract]]) using `juce::URL::DownloadTask` / `WebInputStream` — **never on the audio thread or the message thread**, since network I/O must not block the UI or risk audio thread contention.
4. Status label reflects request state (`Sending...` → `Sent, check dashboard` / `Error: ...`). The plugin does not poll `/jobs/{id}` itself or render results — that's the dashboard's job ([[06-dashboard]]); the plugin's scope ends at "handed off successfully."

This keeps the plugin's C++ surface area small: no JSON result parsing, no charting, no polling loop inside the plugin UI.

## Build system

- **CMake**, not Projucer-generated Visual Studio projects — scriptable, and Claude can generate/modify `CMakeLists.txt` directly without needing the Projucer GUI.
- JUCE referenced via `add_subdirectory()` pointing at the unzipped `juce-8.0.14-windows` folder (already downloaded).
- Toolchain: Visual Studio Build Tools 2022 (Desktop C++ workload) + CMake, both already installed by the user.
- Build target: `VST3` only (`juce_add_plugin(... FORMATS VST3 ...)`).

## Manual test plan (user-driven)

1. Build via CMake + Build Tools; confirm `.vst3` output lands in the standard VST3 folder (`C:\Program Files\Common Files\VST3`) or is manually copied there.
2. Load REAPER, insert DAWpro on the master bus of a project with audio playing.
3. Confirm **pass-through is transparent** — audio sounds identical with the plugin loaded vs. bypassed.
4. Play audio for >60s, click Analyze, confirm the backend receives a WAV + correct BPM/time-sig (check via backend logs, per [[04-backend-engine]]).
5. Confirm the dashboard ([[06-dashboard]]) picks up the resulting job via polling.

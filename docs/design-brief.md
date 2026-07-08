# DAWpro — Frontend Design Brief

For handoff to a design-focused pass (Claude design / Figma / whoever). This covers the dashboard's visual design only — the JUCE plugin UI is out of scope here (it's a native, utilitarian VST editor, not a place for visual design investment).

## Product

DAWpro is an AI mixing mentor for self-taught music producers — "your mentor, not your ghost producer." A VST plugin captures audio from inside a DAW; a web dashboard shows the AI's comparative analysis (project vs. a reference track) as visual feedback the producer explores themselves, rather than being told exactly what to change. Tone: guiding and encouraging, not clinical or bossy. See `docs/plan/00-overview.md` for full context.

## Tech stack (hard constraint — design within this, not around it)

- **Next.js 15** (App Router) + **TypeScript**
- **Tailwind CSS** for all styling — no CSS-in-JS, no separate stylesheet system. Design decisions should be expressible as Tailwind utility classes and a `tailwind.config.ts` theme extension (colors, spacing, fonts), not one-off arbitrary values scattered through components.
- **WaveSurfer.js** for waveform rendering (already integrated, renders into a plain `<div>` container it controls internally — treat it as a black box you can size/border/frame, not something to redesign pixel-by-pixel)
- No component library (no MUI/Chakra/shadcn currently installed) — if the design calls for one, that's a decision to flag back, not assume

## Current state

A functional but visually minimal scaffold already exists and works end-to-end (dark zinc/emerald/sky palette, system default styling — placeholder, not a design decision to preserve). Relevant files:

- `dashboard/app/login/page.tsx` — email/password auth
- `dashboard/app/dashboard/page.tsx` + `components/DashboardView.tsx` — persona list/creator, session list/creator
- `dashboard/app/session/[id]/page.tsx` + `components/SessionView.tsx` — main analysis view
- `components/Waveform.tsx`, `components/EqComparisonChart.tsx`, `components/ChatPanel.tsx` — the three visualization pieces
- `dashboard/tailwind.config.ts` — currently empty theme, ready for a real palette/type scale

## Reference mockup

The original pitch poster (`coding-fest-2026_poster-template_final (1).pdf (1).pdf`, in the repo root) includes a dashboard mockup screenshot to use as the visual starting point: dark background, a "Comparative Mentorship" heading, a frequency spectrum analyzer, a waveform strip, MIDI/timing sync indicators, session/track tabs, genre/label chips (e.g. "TRAP", "SESSION LABEL"), an "APPLY CORRECTION" action button, and a mentor chat panel with feedback bubbles. Treat this as tone/mood reference, not a pixel spec — the actual component structure is defined by what's already built (see above), not the mockup's exact layout.

## Screens to design

1. **`/login`** — simple auth (email + password, sign in/sign up toggle). Low design investment needed; get it clean and on-brand, not elaborate.
2. **`/dashboard`** — persona management (skill level, feedback tone, preferred genres) + session list + "new session" flow. This is where a producer picks who's mentoring them and starts/resumes a project.
3. **`/session/[id]`** — the main screen. Needs the most design attention:
   - Waveform (project audio)
   - Comparative EQ chart (5 frequency bands, project vs. reference, currently hand-rolled bars — could become a real curve/spectrum visualization matching the poster's "frequency spectrum analyzer" mood)
   - Timing markers overlaid on the waveform (severity-colored: info/warning/critical)
   - Mentor feedback panel (chat-bubble style — summary + a list of issues, each with a title/description/severity)
   - Upload control (reference track vs. "my project audio" for testing without the plugin) + sonic-intention/genre text inputs
   - In-flight status/progress indicator (analysis takes 10-60+ seconds — this needs to not feel broken while waiting)

## Data shapes driving the UI (don't design fields that don't exist)

See `dashboard/lib/types.ts` for the authoritative shapes. Key ones:
- `AnalysisResult`: `summary` (string), `eq_comparison` (5 fixed bands with project/reference dB), `timing_markers` (time + label + severity), `issues` (title + description + severity), `mix_score` (0-100, optional)
- `JobStatus.status`: `queued → separating_stems → extracting_features → analyzing → done|failed` — the progress indicator has these five real states to represent, not a generic spinner
- `Persona`: `skill_level` (beginner/intermediate/advanced), `feedback_tone` (guided/direct/technical), `preferred_genres` (string list)
- Severity everywhere is `info | warning | critical` — needs a consistent color/icon language across the EQ chart, timing markers, and chat panel

## Constraints

- **Desktop-first, not mobile.** This is used alongside a DAW on a producer's main monitor — don't spend design budget on responsive/mobile layouts.
- **Dark theme only** for now (no light/dark toggle requirement) — matches the poster mood and typical DAW/audio-tool aesthetics.
- **Accessibility baseline**: sufficient contrast for a dark theme, visible focus states on all inputs/buttons — skip anything beyond that (no full WCAG audit needed at this stage).
- Keep the component boundaries that already exist (`Waveform`, `EqComparisonChart`, `ChatPanel`, `DashboardView`, `SessionView`) — redesign what's inside them freely, but a from-scratch component architecture isn't the ask here.

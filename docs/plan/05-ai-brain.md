# The Brain — Gemini 2.5 Pro + LangChain

Referenced from [[00-overview]] decision 6. Invoked from the `analyzing` stage in [[04-backend-engine]], reads persona data per [[02-accounts-and-personas]], and must emit exactly the `AnalysisResult` shape from [[01-json-contract]].

## Access path: Google AI Studio

`GEMINI_API_KEY` from aistudio.google.com, consumed via `langchain-google-genai`'s `ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=...)`. No GCP project, billing account, or IAM setup — Vertex AI's enterprise features (VPC controls, quota mgmt, regional residency) have no use case for a local-only demo.

## Structured output

Use LangChain's `with_structured_output(AnalysisResult)` (Pydantic model from [[01-json-contract]]) rather than free-text parsing — Gemini 2.5 Pro supports native structured/JSON-mode output, so this is a direct binding, not a fragile regex/parse-and-hope step.

```python
llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=settings.gemini_api_key)
structured_llm = llm.with_structured_output(AnalysisResult)
result = structured_llm.invoke(prompt_messages)
```

## Prompt design

**System prompt** (persona-aware, built per-request from the fetched persona row):

```
You are DAWpro, a mentor for a self-taught music producer — not a ghost producer.
Skill level: {persona.skill_level}
Feedback tone: {persona.feedback_tone}
Preferred genres: {persona.preferred_genres}

Rules:
- Music is subjective. Never give specific prescriptive instructions
  (e.g. exact dB cuts, exact plugin settings) unless the user has explicitly
  asked for a direct fix. Default to guiding the producer toward the right
  question or area to explore themselves.
- Tailor feedback to the exact genre and acoustic profile of the project,
  not generic mixing advice.
- Ground every claim in the provided audio feature data — do not invent
  measurements you weren't given.
```

**User/human message** — the structured input, not prose the model has to parse loosely:

```python
{
  "sonic_intention": request.sonic_intention,
  "genre": request.genre,
  "project_features": { ... Librosa output for the captured/uploaded project audio ... },
  "reference_features": { ... Librosa output for the session's reference track ... },
}
```

This mirrors the poster's stated scenario directly: trap beat / trance track in Ableton → user states intention → DAWpro cross-references extracted stems and flags specific clashes, without dictating exact fixes.

## Guardrail is enforced twice

Once structurally (the `AnalysisResult.issues[].description` field is documented in [[01-json-contract]] as "guidance-toward-exploration, not a prescriptive fix") and once in the system prompt above. Belt-and-suspenders because this is DAWpro's core stated differentiator ("your mentor, not your ghost producer") — worth over-enforcing rather than risking a demo where Gemini free-lances a "cut 3dB at 200Hz" instruction.

## Session continuity (Layer 2)

`human_payload` also carries `session_history`: up to 5 issues raised in
earlier analyses of the same project (`session_id`), built by
`backend/app/session_history.py`'s `build_session_history()`. It queries
`analysis_results` for the session (same shape as `sessions_store.
list_analyses()`, which already backs the plugin's history panel), keeps the
most recent issue per distinct `related_band` plus up to 3 recent
band-agnostic ones, and — critically — does **not** compute a resolved/ignored
verdict itself. Each entry carries the band's measured value both when it was
flagged (`flagged_project_db`/`flagged_reference_db`) and now
(`current_project_db`/`current_reference_db`, looked up from the current
`Measurements.eq_comparison`); the system prompt instructs Gemini to compare
the two and say what changed, citing the current number, rather than
asserting a fix without evidence. Same "never state what you weren't given"
discipline as the measurement guardrail above, just applied to history.

Genre and skill tier don't need separate memory plumbing — they're already on
the `Persona` row and injected into the system prompt on every request.
Likewise "what the user is working on" is already the required
`sonic_intention` field on every `/analyze` call. Neither needed new state;
only cross-analysis issue history did.

## Genre and technique knowledge (Layer 3)

`human_payload` also carries `knowledge_context`: up to 5 chunks from
`backend/app/knowledge/`, retrieved by `retrieve_knowledge()`
(`knowledge/retrieval.py`). This is **deterministic tag/trigger matching, not
semantic/vector search** — the genre string (and persona's preferred genres)
is matched against a small alias table, and a fixed set of technique chunks
each fire off a predicate evaluated against the already-built `Measurements`
(low crest factor, low-mid buildup vs. reference, wide low-band stereo width,
loose rhythmic cohesion — thresholds documented in `retrieval.py`, flagged as
heuristic where they aren't from a cited source). Skill-tier pitfall chunks
only ride along when their paired technique trigger fires *and* the persona
is at the matching tier, so they're never generic filler.

This mirrors the spec's own description of the retrieval query — "built from
the combination of detected problems and user genre, not from the user's
words alone" — which describes structured signals, not free text to embed.
It also keeps the same discipline as the measurement guardrail and Layer 2's
history: `knowledge/base.py`'s chunks each cite a `source` (a real reference,
not an invented number) or say `"heuristic"` when the number is our own
threshold choice, and the system prompt explicitly tells Gemini
`knowledge_context` is background, not a fact about the user's own audio —
only `measurements` is that.

**On prompt order**: the spec's stated order is audio features → user
profile/history → retrieved knowledge → system instruction. The system
instruction is necessarily its own leading `SystemMessage` in the Gemini/
LangChain call (not reorderable to last), so `human_payload`'s `HumanMessage`
carries the three data layers in the stated order instead — same intent
(ground the model in data before it reasons), adapted to how a system-message
API actually works.

## Loudness measurement, corrected against the actual specs

Layer 1's original LUFS/true-peak/LRA implementation leaned on `pyloudnorm`
for integrated loudness and a hand-rolled approximation (re-running the
integrated-loudness meter over overlapping slices) for short-term LUFS and
LRA. After reading the actual specs — [ITU-R BS.1770-5](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.1770-5-202311-I!!PDF-E.pdf)
(the loudness/true-peak algorithm itself) and [EBU R128](https://tech.ebu.ch/docs/r/r128.pdf)
(which defines LRA on top of it) — `backend/app/pipeline/features.py` now
implements the algorithm directly:

- **K-weighting**: the exact two-stage IIR filter from BS.1770-5 Annex 1
  Tables 1-2 (head-effect shelf + RLB high-pass), applied at the coefficients'
  specified 48kHz (audio is resampled to 48kHz first, which the spec
  explicitly permits over re-deriving coefficients for other rates).
- **Integrated loudness**: the real two-stage energy-domain gating from eq.
  (5)-(7) — absolute gate at -70 LUFS, then a relative gate 10 LU below the
  absolute-gated mean — not pyloudnorm's black-box output.
- **Short-term LUFS / LRA**: R128 defines LRA as built from short-term
  loudness on a 3-second window but doesn't give the hop or LRA's own gating
  in closed form (that's EBU Tech 3342, not fetched) - so the hop (100ms) and
  LRA's relative gate (20 LU, stricter than integrated loudness's 10 LU) use
  the values from the de facto reference implementation (`libebur128`),
  documented as such in `features.py` rather than presented as directly
  spec-quoted.

Verified against the spec's own published ground-truth case (a single-channel
997Hz 0dBFS sine must read -3.01 LKFS, BS.1770-5 p.7) - the implementation
matches to four decimal places, and a channel-summation sanity check (two
identical channels read exactly +3.01dB louder than one, per eq. (2)'s power
summation) also holds exactly. `pyloudnorm` was dropped as a dependency once
this replaced it. True-peak (`_true_peak_dbtp`) was already conceptually
aligned with Annex 2's 4x-oversample-and-filter approach and didn't need a
rewrite, just a corrected citation.

## Knowledge base sources (Layer 3 content)

The original 10-chunk knowledge base was seeded from web search snippets.
Five books in `books/` (user-supplied) were read for deeper, more citable
content — each via a dedicated extraction pass (page-cited candidate facts
only, no invented claims), then hand-selected into `knowledge/base.py`:

- **Two of the five yielded nothing usable**: `berklee-online-music-production-handbook.pdf`
  is a recruiting/marketing handbook (interviews, student stories), not a
  technical reference. `Pro+Techniques+for+Sound+Design+.pdf` is a game/film
  sound-design sampler with no music-genre content, though its transient-
  shaping section directly filled a real gap (see below).
- **`Mixing_Techniques_for_Audio_-_FINAL.pdf`** (a Routledge chapter sampler;
  the useful material is almost entirely Wessel Oltheten's "Advanced
  Techniques" chapter from *Mixing with Impact*) deepened `technique_low_mid_mud`
  (the "broad HF boost reveals masking" diagnostic, reflexive-HPF pitfall)
  and `technique_stereo_bass_mono` (M/S processing, correlation metering, the
  vinyl-cutting mono-bass precedent), and added `technique_thin_low_end` /
  `skill_beginner_hpf_default` as a new pair — symmetric with the existing
  mud trigger, using the same `eq_comparison` delta the mud trigger already
  reads, just in the opposite direction.
- **`The_Art_of_Mastering_in_Music_-_Final.pdf`** (another chapter sampler)
  added `genre_metal` (real spectral-balance figures — sub-40Hz "sludge,"
  55-125Hz "true weight," 200-550Hz mud) and deepened `technique_crest_factor`
  / `skill_beginner_overcompression` with concrete mastering-limiter
  discipline (keep gain reduction to 3-4dB per stage; over-reliance on
  limiting flattens transients).
- **`MakingMusic_DennisDeSantis.pdf`** (Ableton's *Making Music*) is
  creative-process focused, not technical, but its kick/bass monophonic-
  composite technique (with a genuine trance-vs-techno/house convention
  difference) deepened `technique_timing_swing`.
- **`Pro+Techniques+for+Sound+Design+.pdf`**'s gun-sound-design section gave
  the material for `technique_transient_attack` — a chunk that fills a real
  prior gap, since Layer 1 has computed per-onset attack time since it was
  built, but nothing in Layer 3 ever interpreted it until this pass. No
  numeric attack-time threshold exists in the source, so `SOFT_TRANSIENT_MEAN_MS`
  in `retrieval.py` is marked heuristic rather than attributed to the book.

## Second book batch — 5 more sources, key-harmony chunk, reference key added

A second set of 5 books arrived in `books/` (`document.pdf`, `document (1).pdf`,
`feismo.com-music-theory-for-computer-musicians-...pdf`,
`pdfcoffee.com_dance-music-manual-...pdf`,
`toaz.info-the-mixing-engineerx27s-handbook-...pdf`; the leftover
`err.log`/`extracted.txt` in the same folder are just artifacts of an earlier
extraction of a PDF already covered — not new source material). Read the
same way: dedicated extraction pass per book, page-cited candidate facts
only, hand-selected into `knowledge/base.py`.

- **`document.pdf`** (*The Art of Music Production*, Richard James Burgess)
  yielded nothing usable — same pattern as the Berklee handbook: the author
  states in the preface it deliberately excludes EQ/mic/compression content,
  and covers career/industry topics instead.
- **`pdfcoffee.com_dance-music-manual-...pdf`** turned out to be a truncated,
  machine-translated preview (77 pages, cuts off mid-Chapter 3) — despite the
  filename, none of the genre-specific chapters (House, Trance, Techno, DnB,
  etc. — all listed in the TOC) are actually present in this copy, so it
  contributed no new `genre_target` chunks. It did give concrete compression
  technique content: the kick-punch-as-crest-factor framing, and a
  sidechain kick-vs-bass ducking technique explicitly named as used in
  hip-hop/rap/house/big beat, folded into `technique_low_mid_mud` as a
  dynamics-based alternative to EQ cutting.
- **`toaz.info-the-mixing-engineerx27s-handbook-...pdf`** (Bobby Owsinski,
  5th ed., image-based PDF — read via page rendering, not text extraction)
  was the richest single source: added `genre_acoustic` (LUFS-by-genre
  table: acoustic/organic material commonly -12 to -14 LUFS, more dynamic
  range than electronic/pop); deepened `technique_low_mid_mud` with the
  "Six Trouble Frequency Areas" named artifacts (200Hz "mud," 300-500Hz
  "boxy," 800Hz thin/cheap) and the "same frequency, same time = fight for
  attention" framing; deepened `technique_crest_factor` with the
  "hypercompression" failure-mode name and a concrete glue-compression
  target (4:1, fast attack, auto release, 1-3dB gain reduction); deepened
  `technique_timing_swing` with the bass-slightly-behind-kick technique and
  a mute-to-find-the-pulse groove diagnostic; and gave the "boost level, not
  EQ" bass pitfall folded into `skill_beginner_hpf_default`. Two claims this
  agent flagged as not re-verified in its final pass (a Panorama-chapter
  stereo-panning rule, and "Signs of an Amateur Mix") were spot-checked
  directly — the amateur-mix list confirmed verbatim but not used (it's a
  holistic checklist that doesn't map to any single measured trigger, so
  including it would violate the "no untriggered generic advice" rule this
  knowledge base has held throughout); the panning claim wasn't found in the
  page range checked and was dropped rather than guessed at.
- **`document (1).pdf`** (*Making Sound*, Cristofer Odqvist) was the
  richest source for the previously-thinnest chunk: gave real millisecond
  figures for `technique_transient_attack` (slow attack ≥30ms reads
  brighter/more energetic, fast attack ~3ms darkens/mellows — attack time
  controls perceived brightness because brightness lives mostly in the
  transient). Also deepened `technique_stereo_bass_mono` with a second,
  looser mono-bass threshold (the book gives two different numbers — 80Hz
  as the strict perceptual localization limit, 150Hz as a looser practical
  rule of thumb many mixers use — both are kept rather than picking one, per
  the book's own distinction).
- **`feismo.com-music-theory-for-computer-musicians-...pdf`** (Michael
  Hewitt) filled a real, previously-total gap: Layer 1 has detected musical
  key since it was built, but no chunk ever interpreted it. Added
  `technique_key_harmony` (circle-of-fifths note-overlap as the mechanism
  for key compatibility/clash, relative major/minor as the closest
  relationship, and a properly-hedged sharp-is-brighter/flat-is-darker note
  — the book itself flags that as a subjective convention among musicians,
  not an acoustic fact, and the chunk preserves that hedge rather than
  stating it as settled). This needed a small schema change first:
  `Measurements` only carried the *project's* detected key, not the
  reference's, so there was nothing to compare — `reference_key`/
  `reference_key_confidence` were added (`schemas.py`, populated in
  `pipeline/measurements.py.build_measurements()`), and a new
  `_both_keys_detected` trigger in `retrieval.py` fires only when both are
  present with real confidence (the existing `KEY_CONFIDENCE_FLOOR` in
  `features.py` already keeps a low-confidence detection from reaching
  `Measurements.key` at all, so no separate confidence check was needed here).

## Multi-provider LLM support

`llm_provider` (env var, `config.py`) selects which LLM backs the mentor
narrative call: `"gemini"` (default), `"anthropic"`, or `"openai"`. All three
go through the same LangChain `.with_structured_output(MentorNarrative)`
interface, so `_narrative()`'s system prompt, human payload, session
history, knowledge retrieval, and retry logic in `chain.py` are entirely
provider-agnostic — only `_build_llm()` branches on `llm_provider` to
construct `ChatGoogleGenerativeAI`, `ChatAnthropic`, or `ChatOpenAI`.

**Why not AgentKit.** Considered when this was requested: OpenAI's AgentKit
is a visual multi-agent workflow builder (Agent Builder canvas, Connector
Registry, ChatKit embeddable UI), aimed at orchestrating complex multi-step
agent pipelines — a mismatch for "call one LLM with structured output, let
the caller pick the provider." OpenAI is also winding down Agent Builder and
Evals from November 30, 2026. The existing LangChain-based approach already
had the right shape; it just needed extending to more providers, not
replacing with new infrastructure.

**Model IDs.** `anthropic_model` defaults to `claude-opus-5` (this
environment's current strongest Claude model) but is env-overridable rather
than hardcoded without an escape hatch. `openai_model` has **no default at
all** — there was no OpenAI model ID available to hardcode with confidence,
so `analyze()` treats a missing `OPENAI_MODEL` the same as a missing API
key: falls back to the existing "measurements without AI narrative" path
rather than risking a call to a wrong/nonexistent model string. Gemini's
model stays hardcoded to `"gemini-flash-latest"`, a stable alias, unchanged
from before this work.

## Error handling

Wrap the `structured_llm.invoke()` call with a single retry on transient failures (rate limit / timeout) — no elaborate backoff strategy needed at demo scale, just enough to not fail a whole analysis on one flaky call. Any unrecoverable failure surfaces as `JobStatus.status = "failed"` with the exception message in `error` (per [[04-backend-engine]]).

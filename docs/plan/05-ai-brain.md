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

## Error handling

Wrap the `structured_llm.invoke()` call with a single retry on transient failures (rate limit / timeout) — no elaborate backoff strategy needed at demo scale, just enough to not fail a whole analysis on one flaky call. Any unrecoverable failure surfaces as `JobStatus.status = "failed"` with the exception message in `error` (per [[04-backend-engine]]).

#pragma once

#include <juce_audio_utils/juce_audio_utils.h>
#include <atomic>
#include <functional>

// Talks to the FastAPI backend (see docs/plan/01-json-contract.md).
// Everything in here is synchronous network/file I/O - callers must run it
// on a background thread, never the audio or message thread.
namespace UploadClient
{
    struct AnalyzeParams
    {
        juce::String backendUrl;
        juce::String sessionId;
        juce::String personaId;
        juce::String sonicIntention;
        juce::String genre;
        double bpm = 120.0;
        juce::String timeSignature = "4/4";
    };

    struct Response
    {
        bool ok = false;
        juce::String message;    // short, human-readable, for the status line
        juce::String resultJson; // the AnalysisResult body when ok
    };

    // stage is the backend's job status ("separating_stems", "analyzing", ...);
    // progress is 0..1. Called from the worker thread.
    using ProgressFn = std::function<void(const juce::String& stage, float progress)>;

    // POSTs the captured audio to {backendUrl}/analyze, then polls
    // {backendUrl}/jobs/{job_id} until the job finishes.
    //
    // /analyze only hands back a job id - the analysis runs asynchronously
    // behind Demucs and Gemini - so the result has to be collected by polling.
    // Set cancelled to abandon the wait; the backend job keeps running and its
    // result stays retrievable from the dashboard.
    Response analyzeAndAwait(const juce::AudioBuffer<float>& audio,
                              double sampleRate,
                              const AnalyzeParams& params,
                              ProgressFn onProgress,
                              const std::atomic<bool>& cancelled);
}

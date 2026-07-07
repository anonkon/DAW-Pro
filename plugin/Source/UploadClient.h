#pragma once

#include <juce_audio_utils/juce_audio_utils.h>

// Talks to the FastAPI backend's POST /analyze (see docs/plan/01-json-contract.md).
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

    // Encodes `audio` as WAV and POSTs it to {backendUrl}/analyze as
    // multipart/form-data alongside the plugin_capture metadata. Returns a
    // short human-readable result for the plugin's status label.
    juce::String sendCapturedAudio(const juce::AudioBuffer<float>& audio,
                                    double sampleRate,
                                    const AnalyzeParams& params);
}

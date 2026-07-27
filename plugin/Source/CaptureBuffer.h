#pragma once

#include <juce_audio_utils/juce_audio_utils.h>
#include <atomic>

// A rolling buffer of the last `bufferSeconds` of audio, continuously
// overwritten while the host plays - this is what makes capture "silent
// and always-on" without needing a manual start/stop. Single producer
// (audio thread, via push) / single consumer (message thread, via
// snapshot): no locks, no allocation on the audio thread.
//
// snapshot() can race with an in-flight push() at the wrap boundary. For
// an analysis feature (not bit-exact playback) that's an acceptable
// trade-off - a torn frame or two out of tens of thousands doesn't change
// the RMS/spectral features derived from it.
class CaptureBuffer
{
public:
    void prepare(double sampleRateIn, int numChannels, double bufferSeconds = 60.0);
    void push(const juce::AudioBuffer<float>& block) noexcept;

    /** The most recent `maxSamples` of audio, or everything held when
        maxSamples <= 0. Bounding this matters: the full buffer is a minute of
        audio, and every extra second is another second of Demucs separation
        on the backend. */
    juce::AudioBuffer<float> snapshot(int maxSamples = 0) const;

    double getSampleRate() const noexcept { return sampleRate; }
    int getCapacitySamples() const noexcept { return capacitySamples; }

private:
    juce::AudioBuffer<float> storage;
    std::atomic<int64_t> totalSamplesWritten { 0 };
    int capacitySamples = 0;
    double sampleRate = 44100.0;
};

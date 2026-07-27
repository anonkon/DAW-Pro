#pragma once

#include <juce_dsp/juce_dsp.h>
#include <atomic>
#include <vector>

/** Real-time spectrum and stereo correlation for the plugin's meters.
 *
 *  Deliberately mirrors backend/app/pipeline/features.py: FFT size 8192, a
 *  Hann window normalised by its coherent gain, and 64 geometrically spaced
 *  points from 20Hz to 20kHz taking the loudest bin per bucket. The live curve
 *  is drawn over the reference curve returned by the backend, so if the two
 *  used different scaling or bucketing the overlay would be misleading.
 *
 *  One honest difference remains: the backend averages across the whole
 *  capture, while this is a running view of the last fftSize samples. The
 *  smoothing below narrows that gap but does not close it - live is "now",
 *  the reference is "the whole track".
 *
 *  Single producer (audio thread, push) / single consumer (message thread,
 *  computeFrame). Like CaptureBuffer this tolerates a torn read at the wrap
 *  boundary rather than locking the audio thread: a smeared frame is invisible
 *  in a meter that refreshes 24 times a second.
 */
class LiveAnalyser
{
public:
    static constexpr int fftOrder = 13;             // 8192, matching N_FFT
    static constexpr int fftSize = 1 << fftOrder;
    static constexpr int numPoints = 64;            // matching SPECTRUM_POINTS
    static constexpr float hzMin = 20.0f;
    static constexpr float hzMax = 20000.0f;

    struct Frame
    {
        std::vector<float> db;              // numPoints, dBFS
        float correlation = 1.0f;           // -1..+1 L/R Pearson
        bool stereo = false;
        bool valid = false;
    };

    LiveAnalyser();

    void prepare(double sampleRate);
    void push(const juce::AudioBuffer<float>& block) noexcept;

    /** Runs the FFT over the most recent window. Message thread only. */
    Frame computeFrame();

    bool hasSignal() const noexcept { return samplesWritten.load(std::memory_order_relaxed) >= fftSize; }

private:
    void buildBuckets();

    juce::dsp::FFT fft { fftOrder };
    juce::dsp::WindowingFunction<float> window { (size_t) fftSize,
                                                  juce::dsp::WindowingFunction<float>::hann };
    float windowGain = 1.0f;                // sum(window) / 2, the coherent gain

    double currentSampleRate = 44100.0;

    // Two rings so L/R correlation stays measurable; mono sources duplicate.
    std::vector<float> ringLeft, ringRight;
    std::atomic<int64_t> samplesWritten { 0 };
    std::atomic<bool> sourceIsStereo { false };

    std::vector<float> scratch;             // 2 * fftSize, as JUCE requires
    std::vector<float> smoothed;            // EMA state across frames
    bool hasSmoothed = false;

    // Bucket edges precomputed once per sample rate.
    std::vector<float> centres;
    std::vector<int> binLow, binHigh;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(LiveAnalyser)
};

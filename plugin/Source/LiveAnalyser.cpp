#include "LiveAnalyser.h"
#include <cmath>

namespace
{
    // How fast the display follows the signal. Low enough to be readable,
    // high enough that a fader move is visible immediately.
    constexpr float smoothingAlpha = 0.25f;
    constexpr float dbFloor = -100.0f;
}

LiveAnalyser::LiveAnalyser()
{
    ringLeft.assign((size_t) fftSize, 0.0f);
    ringRight.assign((size_t) fftSize, 0.0f);
    scratch.assign((size_t) fftSize * 2, 0.0f);
    smoothed.assign((size_t) numPoints, dbFloor);

    // Coherent gain of the window, so a full-scale sine reads 0 dBFS - the
    // same normalisation features.py applies to the backend's STFT.
    std::vector<float> unit((size_t) fftSize, 1.0f);
    window.multiplyWithWindowingTable(unit.data(), (size_t) fftSize);
    float sum = 0.0f;
    for (float v : unit)
        sum += v;
    windowGain = sum / 2.0f;
}

void LiveAnalyser::prepare(double sampleRate)
{
    currentSampleRate = sampleRate > 0.0 ? sampleRate : 44100.0;
    std::fill(ringLeft.begin(), ringLeft.end(), 0.0f);
    std::fill(ringRight.begin(), ringRight.end(), 0.0f);
    std::fill(smoothed.begin(), smoothed.end(), dbFloor);
    hasSmoothed = false;
    samplesWritten.store(0, std::memory_order_relaxed);
    buildBuckets();
}

void LiveAnalyser::buildBuckets()
{
    centres.assign((size_t) numPoints, 0.0f);
    binLow.assign((size_t) numPoints, 0);
    binHigh.assign((size_t) numPoints, 0);

    const double ratio = std::log((double) hzMax / (double) hzMin) / (numPoints - 1);
    const double binWidth = currentSampleRate / (double) fftSize;
    const int maxBin = fftSize / 2;

    for (int i = 0; i < numPoints; ++i)
    {
        const double hz = hzMin * std::exp(ratio * i);
        centres[(size_t) i] = (float) hz;

        // Geometric midpoints, so buckets tile the axis without gaps.
        const double lo = i == 0 ? hzMin : std::sqrt(hz * hzMin * std::exp(ratio * (i - 1)));
        const double hi = i == numPoints - 1
                              ? hzMax
                              : std::sqrt(hz * hzMin * std::exp(ratio * (i + 1)));

        binLow[(size_t) i] = juce::jlimit(0, maxBin, (int) std::floor(lo / binWidth));
        binHigh[(size_t) i] = juce::jlimit(0, maxBin, (int) std::ceil(hi / binWidth));
    }
}

void LiveAnalyser::push(const juce::AudioBuffer<float>& block) noexcept
{
    const int numSamples = block.getNumSamples();
    const int numChannels = block.getNumChannels();
    if (numSamples <= 0 || numChannels <= 0)
        return;

    sourceIsStereo.store(numChannels >= 2, std::memory_order_relaxed);

    const float* left = block.getReadPointer(0);
    const float* right = numChannels >= 2 ? block.getReadPointer(1) : left;

    const int64_t start = samplesWritten.load(std::memory_order_relaxed);
    for (int i = 0; i < numSamples; ++i)
    {
        const size_t pos = (size_t) ((start + i) % fftSize);
        ringLeft[pos] = left[i];
        ringRight[pos] = right[i];
    }
    samplesWritten.store(start + numSamples, std::memory_order_release);
}

LiveAnalyser::Frame LiveAnalyser::computeFrame()
{
    Frame frame;
    frame.db.assign((size_t) numPoints, dbFloor);

    const int64_t total = samplesWritten.load(std::memory_order_acquire);
    if (total < fftSize)
        return frame; // not enough audio yet

    if (centres.empty())
        buildBuckets();

    // Unwrap the ring into the FFT scratch buffer, oldest sample first.
    const int oldest = (int) (total % fftSize);
    std::fill(scratch.begin(), scratch.end(), 0.0f);

    double sumL = 0.0, sumR = 0.0;
    for (int i = 0; i < fftSize; ++i)
    {
        const size_t pos = (size_t) ((oldest + i) % fftSize);
        const float l = ringLeft[pos];
        const float r = ringRight[pos];
        scratch[(size_t) i] = 0.5f * (l + r); // mono sum, as the backend analyses
        sumL += l;
        sumR += r;
    }

    // --- Stereo correlation over the same window --------------------------
    frame.stereo = sourceIsStereo.load(std::memory_order_relaxed);
    if (frame.stereo)
    {
        const double meanL = sumL / fftSize;
        const double meanR = sumR / fftSize;
        double covariance = 0.0, varianceL = 0.0, varianceR = 0.0;
        for (int i = 0; i < fftSize; ++i)
        {
            const size_t pos = (size_t) ((oldest + i) % fftSize);
            const double dl = ringLeft[pos] - meanL;
            const double dr = ringRight[pos] - meanR;
            covariance += dl * dr;
            varianceL += dl * dl;
            varianceR += dr * dr;
        }
        const double denominator = std::sqrt(varianceL * varianceR);
        // Silence has no correlation to report; claiming 0 would read as a
        // fully decorrelated field rather than "nothing playing".
        frame.correlation = denominator > 1e-12
                                ? (float) juce::jlimit(-1.0, 1.0, covariance / denominator)
                                : 1.0f;
    }

    // --- Spectrum ---------------------------------------------------------
    window.multiplyWithWindowingTable(scratch.data(), (size_t) fftSize);
    fft.performFrequencyOnlyForwardTransform(scratch.data(), true);

    for (int i = 0; i < numPoints; ++i)
    {
        const int lo = binLow[(size_t) i];
        const int hi = juce::jmax(binHigh[(size_t) i], lo + 1);

        // Loudest bin in the bucket, matching the backend. Averaging instead
        // would erase narrow peaks: near 1kHz a bucket spans ~110Hz while a
        // bin is ~5Hz wide, so a tone would vanish between sample points.
        float peak = 0.0f;
        for (int bin = lo; bin < hi && bin <= fftSize / 2; ++bin)
            peak = juce::jmax(peak, scratch[(size_t) bin]);

        const float magnitude = peak / windowGain;
        const float db = juce::jmax(dbFloor, juce::Decibels::gainToDecibels(magnitude, dbFloor));

        frame.db[(size_t) i] = hasSmoothed
                                   ? smoothed[(size_t) i] + smoothingAlpha * (db - smoothed[(size_t) i])
                                   : db;
        smoothed[(size_t) i] = frame.db[(size_t) i];
    }

    hasSmoothed = true;
    frame.valid = true;
    return frame;
}

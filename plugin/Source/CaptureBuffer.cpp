#include "CaptureBuffer.h"

void CaptureBuffer::prepare(double sampleRateIn, int numChannels, double bufferSeconds)
{
    sampleRate = sampleRateIn;
    capacitySamples = juce::jmax(1, (int) (bufferSeconds * sampleRate));
    storage.setSize(numChannels, capacitySamples);
    storage.clear();
    totalSamplesWritten.store(0, std::memory_order_relaxed);
}

void CaptureBuffer::push(const juce::AudioBuffer<float>& block) noexcept
{
    if (capacitySamples == 0)
        return;

    const int numSamples = block.getNumSamples();
    const int64_t start = totalSamplesWritten.load(std::memory_order_relaxed);

    for (int ch = 0; ch < storage.getNumChannels(); ++ch)
    {
        const float* src = block.getReadPointer(juce::jmin(ch, block.getNumChannels() - 1));
        int samplesLeft = numSamples;
        int srcOffset = 0;

        while (samplesLeft > 0)
        {
            const int writePos = (int) ((start + (numSamples - samplesLeft)) % capacitySamples);
            const int chunk = juce::jmin(samplesLeft, capacitySamples - writePos);
            storage.copyFrom(ch, writePos, src + srcOffset, chunk);
            srcOffset += chunk;
            samplesLeft -= chunk;
        }
    }

    totalSamplesWritten.fetch_add(numSamples, std::memory_order_relaxed);
}

juce::AudioBuffer<float> CaptureBuffer::snapshot(int maxSamples) const
{
    const int64_t total = totalSamplesWritten.load(std::memory_order_relaxed);
    const int filled = (int) juce::jmin<int64_t>(total, capacitySamples);

    // maxSamples <= 0 means "everything held", which is the whole buffer.
    const int available = maxSamples > 0 ? juce::jmin(filled, maxSamples) : filled;
    if (available <= 0)
        return {};

    // The newest `available` samples end at the write head and run backwards.
    const int writePos = (int) (total % capacitySamples);
    const int startPos = ((writePos - available) % capacitySamples + capacitySamples) % capacitySamples;
    const int firstChunk = juce::jmin(available, capacitySamples - startPos);
    const int secondChunk = available - firstChunk;

    juce::AudioBuffer<float> result(storage.getNumChannels(), available);
    for (int ch = 0; ch < storage.getNumChannels(); ++ch)
    {
        result.copyFrom(ch, 0, storage, ch, startPos, firstChunk);
        if (secondChunk > 0)
            result.copyFrom(ch, firstChunk, storage, ch, 0, secondChunk);
    }
    return result;
}

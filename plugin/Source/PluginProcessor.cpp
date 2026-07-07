#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "UploadClient.h"

DAWproBridgeProcessor::DAWproBridgeProcessor()
    : AudioProcessor(BusesProperties()
                          .withInput("Input", juce::AudioChannelSet::stereo(), true)
                          .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
}

void DAWproBridgeProcessor::prepareToPlay(double sampleRate, int)
{
    const int numChannels = getTotalNumInputChannels() > 0 ? getTotalNumInputChannels() : 2;
    captureBuffer.prepare(sampleRate, numChannels);
}

bool DAWproBridgeProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    const auto mainOut = layouts.getMainOutputChannelSet();
    if (mainOut != juce::AudioChannelSet::stereo() && mainOut != juce::AudioChannelSet::mono())
        return false;
    return mainOut == layouts.getMainInputChannelSet();
}

void DAWproBridgeProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;

    // Silent, continuous capture - never modifies the signal. This runs
    // every block regardless of whether the user ever clicks Analyze.
    captureBuffer.push(buffer);

    if (auto* currentPlayHead = getPlayHead())
    {
        if (const auto position = currentPlayHead->getPosition())
        {
            if (const auto bpm = position->getBpm())
                currentBpm.store(*bpm, std::memory_order_relaxed);

            if (const auto ts = position->getTimeSignature())
            {
                currentTimeSigNumerator.store(ts->numerator, std::memory_order_relaxed);
                currentTimeSigDenominator.store(ts->denominator, std::memory_order_relaxed);
            }
        }
    }

    // Explicitly not touching `buffer` beyond this point - pass-through,
    // per docs/plan/03-plugin-bridge.md.
    juce::ignoreUnused(buffer);
}

juce::AudioProcessorEditor* DAWproBridgeProcessor::createEditor()
{
    return new DAWproBridgeEditor(*this);
}

juce::String DAWproBridgeProcessor::getStatusMessage() const
{
    const juce::ScopedLock lock(statusLock);
    return statusMessage;
}

void DAWproBridgeProcessor::setStatus(const juce::String& message)
{
    const juce::ScopedLock lock(statusLock);
    statusMessage = message;
}

void DAWproBridgeProcessor::triggerAnalysis(const juce::String& backendUrl,
                                             const juce::String& sessionId,
                                             const juce::String& personaId,
                                             const juce::String& sonicIntention,
                                             const juce::String& genre)
{
    auto audioSnapshot = captureBuffer.snapshot();

    if (audioSnapshot.getNumSamples() == 0)
    {
        setStatus("Nothing captured yet - play some audio first.");
        return;
    }

    UploadClient::AnalyzeParams params;
    params.backendUrl = backendUrl;
    params.sessionId = sessionId;
    params.personaId = personaId;
    params.sonicIntention = sonicIntention;
    params.genre = genre;
    params.bpm = currentBpm.load(std::memory_order_relaxed);
    params.timeSignature = juce::String(currentTimeSigNumerator.load(std::memory_order_relaxed))
                            + "/"
                            + juce::String(currentTimeSigDenominator.load(std::memory_order_relaxed));

    const double sampleRate = captureBuffer.getSampleRate();
    setStatus("Sending...");

    // Never do network I/O on the audio or message thread - hand off to the
    // single-worker pool and let the editor's timer pick up status changes.
    uploadPool.addJob([this, audio = std::move(audioSnapshot), sampleRate, params]() mutable
    {
        const auto result = UploadClient::sendCapturedAudio(audio, sampleRate, params);
        setStatus(result);
    });
}

// This creates instances of the plugin - required JUCE entry point.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new DAWproBridgeProcessor();
}

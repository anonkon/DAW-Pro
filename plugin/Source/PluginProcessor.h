#pragma once

#include <juce_audio_utils/juce_audio_utils.h>
#include "CaptureBuffer.h"
#include <atomic>

class DAWproBridgeProcessor : public juce::AudioProcessor
{
public:
    DAWproBridgeProcessor();
    ~DAWproBridgeProcessor() override = default;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override {}
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return "DAWpro Bridge"; }
    bool acceptsMidi() const override { return false; }
    bool producesMidi() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    void getStateInformation(juce::MemoryBlock&) override {}
    void setStateInformation(const void*, int) override {}

    // Called from the editor's "Analyze" button (message thread). Snapshots
    // the rolling capture buffer and uploads it on a background thread.
    void triggerAnalysis(const juce::String& backendUrl,
                          const juce::String& sessionId,
                          const juce::String& personaId,
                          const juce::String& sonicIntention,
                          const juce::String& genre);

    juce::String getStatusMessage() const;

private:
    void setStatus(const juce::String& message);

    CaptureBuffer captureBuffer;
    std::atomic<double> currentBpm { 120.0 };
    std::atomic<int> currentTimeSigNumerator { 4 };
    std::atomic<int> currentTimeSigDenominator { 4 };

    mutable juce::CriticalSection statusLock;
    juce::String statusMessage { "Idle - play some audio, then click Analyze" };

    juce::ThreadPool uploadPool { 1 };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DAWproBridgeProcessor)
};

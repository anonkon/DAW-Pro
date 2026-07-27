#pragma once

#include <juce_audio_utils/juce_audio_utils.h>
#include "CaptureBuffer.h"
#include "LiveAnalyser.h"
#include <atomic>
#include <vector>

class DAWproBridgeProcessor : public juce::AudioProcessor,
                              public juce::ChangeBroadcaster,
                              private juce::Timer
{
public:
    // Everything the user configures. Lives on the processor rather than the
    // editor so it survives the window closing, and so it can be saved into
    // the host's session.
    struct Settings
    {
        juce::String backendUrl { "http://localhost:8000" };
        juce::String sessionId;
        juce::String personaId;
        juce::String sonicIntention;
        juce::String genre;
        // 0 means the whole rolling buffer; otherwise capture this many bars.
        int captureBars = 16;
        // Wait for the next downbeat before taking the snapshot.
        bool armToBar = false;
    };

    enum class Phase { Idle, Working, Done, Failed };

    struct Status
    {
        Phase phase = Phase::Idle;
        juce::String message { "Idle - play some audio, then click Analyze" };
        float progress = 0.0f;
        juce::String resultJson;   // AnalysisResult from the most recent job
        int activeJobs = 0;        // more than one analysis can be in flight
        bool armed = false;
    };

    struct Connection
    {
        bool reachable = false;
        bool checked = false;
        juce::String sessionsJson { "[]" };
        juce::String historyJson { "[]" };
    };

    DAWproBridgeProcessor();
    ~DAWproBridgeProcessor() override;

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

    void getStateInformation(juce::MemoryBlock&) override;
    void setStateInformation(const void*, int) override;

    Settings getSettings() const;
    void setSettings(const Settings& newSettings);

    Status getStatus() const;
    Connection getConnection() const;

    /** Queues an analysis using the current settings. Safe to call while a
        previous job is still running. */
    void triggerAnalysis();

    /** Polls /health, /sessions and the current session's analyses. */
    void refreshBackend();

    /** Reference spectrum from the most recent analysis, as a JSON array of
        {hz, db} - drawn underneath the live curve. */
    juce::String getReferenceSpectrumJson() const;

    LiveAnalyser::Frame computeLiveFrame() { return liveAnalyser.computeFrame(); }

    float getCaptureLevel() const { return captureLevel.load(std::memory_order_relaxed); }
    double getCurrentBpm() const { return currentBpm.load(std::memory_order_relaxed); }

    /** How many samples the current capture-window setting corresponds to. */
    int captureWindowSamples() const;

private:
    // Picks up an armed capture once the audio thread reports a downbeat.
    // On the processor rather than the editor so arming still fires with the
    // plugin window closed.
    void timerCallback() override;

    void setStatus(Phase phase, const juce::String& message, float progress,
                    const juce::String& resultJson = {});
    void submit(juce::AudioBuffer<float> audio, double sampleRate);
    void cacheReferenceSpectrum(const juce::String& resultJson);

    CaptureBuffer captureBuffer;
    LiveAnalyser liveAnalyser;

    std::atomic<double> currentBpm { 120.0 };
    std::atomic<int> currentTimeSigNumerator { 4 };
    std::atomic<int> currentTimeSigDenominator { 4 };
    std::atomic<float> captureLevel { 0.0f };

    // Set by the message thread when armToBar is on; cleared by the audio
    // thread the moment a downbeat passes, which is the only place the exact
    // bar boundary is known.
    std::atomic<bool> armPending { false };
    std::atomic<bool> armFired { false };
    std::atomic<double> lastPpq { 0.0 };

    mutable juce::CriticalSection stateLock;
    Settings settings;
    Status status;
    Connection connection;
    juce::String referenceSpectrumJson { "[]" };

    std::atomic<int> jobsInFlight { 0 };
    std::atomic<bool> cancelled { false };

    // Two workers so a queued capture is not stuck behind a long poll, plus a
    // separate pool for the lightweight backend metadata requests.
    juce::ThreadPool uploadPool { 2 };
    juce::ThreadPool metadataPool { 1 };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DAWproBridgeProcessor)
};

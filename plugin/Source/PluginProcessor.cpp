#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "UploadClient.h"

namespace
{
    const juce::Identifier stateTag { "DAWproBridge" };

    juce::String fetchJson(const juce::String& url, bool& ok)
    {
        int statusCode = 0;
        const auto options = juce::URL::InputStreamOptions(juce::URL::ParameterHandling::inAddress)
                                  .withConnectionTimeoutMs(4000)
                                  .withStatusCode(&statusCode);

        std::unique_ptr<juce::InputStream> stream(juce::URL(url).createInputStream(options));
        ok = stream != nullptr && statusCode >= 200 && statusCode < 300;
        return ok ? stream->readEntireStreamAsString() : juce::String();
    }
}

DAWproBridgeProcessor::DAWproBridgeProcessor()
    : AudioProcessor(BusesProperties()
                          .withInput("Input", juce::AudioChannelSet::stereo(), true)
                          .withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
    startTimerHz(20);
}

void DAWproBridgeProcessor::timerCallback()
{
    if (stopFired.exchange(false, std::memory_order_acquire))
        submitPlayedSpan();

    if (! armFired.exchange(false, std::memory_order_acquire))
        return;

    // The downbeat has passed, so the window ending here starts on a bar line.
    submit(captureBuffer.snapshot(captureWindowSamples()), captureBuffer.getSampleRate());
}

void DAWproBridgeProcessor::submitPlayedSpan()
{
    if (! getSettings().analyzeOnStop)
        return;

    const auto played = playEndSamples.load(std::memory_order_relaxed)
                      - playStartSamples.load(std::memory_order_relaxed);

    // Anything shorter than this is a stray transport blip (a nudge of the
    // playhead, a stop immediately after a stop), not a take worth analysing.
    const auto minimumSamples = (int64_t) (2.0 * captureBuffer.getSampleRate());
    if (played < minimumSamples)
        return;

    // The rolling buffer only holds the last minute, so a longer pass is
    // necessarily truncated to its most recent portion.
    const auto capped = juce::jmin<int64_t>(played, captureBuffer.getCapacitySamples());
    submit(captureBuffer.snapshot((int) capped), captureBuffer.getSampleRate());
}

DAWproBridgeProcessor::~DAWproBridgeProcessor()
{
    stopTimer();
    // Stop in-flight polls before the members they touch are destroyed.
    cancelled.store(true, std::memory_order_relaxed);
    uploadPool.removeAllJobs(true, 5000);
    metadataPool.removeAllJobs(true, 2000);
}

void DAWproBridgeProcessor::prepareToPlay(double sampleRate, int)
{
    const int numChannels = getTotalNumInputChannels() > 0 ? getTotalNumInputChannels() : 2;
    captureBuffer.prepare(sampleRate, numChannels);
    liveAnalyser.prepare(sampleRate);
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

    // Silent, continuous capture - never modifies the signal.
    captureBuffer.push(buffer);
    liveAnalyser.push(buffer);

    float peak = 0.0f;
    for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
        peak = juce::jmax(peak, buffer.getMagnitude(channel, 0, buffer.getNumSamples()));
    captureLevel.store(peak, std::memory_order_relaxed);

    if (auto* currentPlayHead = getPlayHead())
    {
        if (const auto position = currentPlayHead->getPosition())
        {
            if (const auto bpm = position->getBpm())
                currentBpm.store(*bpm, std::memory_order_relaxed);

            // Transport edges. Ableton keeps calling processBlock while stopped,
            // so "is the host playing" is the only way to know which part of the
            // rolling buffer is the take the user just performed.
            const bool playing = position->getIsPlaying();
            const bool previouslyPlaying = wasPlaying.exchange(playing, std::memory_order_relaxed);
            const auto writeHead = captureBuffer.getTotalSamplesWritten();

            if (playing && ! previouslyPlaying)
                playStartSamples.store(writeHead, std::memory_order_relaxed);

            if (previouslyPlaying && ! playing)
            {
                playEndSamples.store(writeHead, std::memory_order_relaxed);
                stopFired.store(true, std::memory_order_release);
            }

            int numerator = 4;
            if (const auto ts = position->getTimeSignature())
            {
                numerator = ts->numerator;
                currentTimeSigNumerator.store(ts->numerator, std::memory_order_relaxed);
                currentTimeSigDenominator.store(ts->denominator, std::memory_order_relaxed);
            }

            // Bar detection has to happen here: the exact downbeat is only
            // knowable from the playhead, on the audio thread.
            if (const auto ppq = position->getPpqPosition())
            {
                const double previous = lastPpq.exchange(*ppq, std::memory_order_relaxed);
                const double beatsPerBar = juce::jmax(1, numerator);
                const bool crossedBar =
                    std::floor(previous / beatsPerBar) < std::floor(*ppq / beatsPerBar);

                if (crossedBar && armPending.load(std::memory_order_relaxed))
                {
                    armPending.store(false, std::memory_order_relaxed);
                    armFired.store(true, std::memory_order_release);
                }
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

// --- Settings ---------------------------------------------------------------

DAWproBridgeProcessor::Settings DAWproBridgeProcessor::getSettings() const
{
    const juce::ScopedLock lock(stateLock);
    return settings;
}

void DAWproBridgeProcessor::setSettings(const Settings& newSettings)
{
    {
        const juce::ScopedLock lock(stateLock);
        settings = newSettings;
    }
    updateHostDisplay(); // marks the host session dirty
}

// --- Persistence ------------------------------------------------------------

void DAWproBridgeProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    const auto current = getSettings();

    juce::ValueTree tree(stateTag);
    tree.setProperty("backendUrl", current.backendUrl, nullptr);
    tree.setProperty("sessionId", current.sessionId, nullptr);
    tree.setProperty("personaId", current.personaId, nullptr);
    tree.setProperty("sonicIntention", current.sonicIntention, nullptr);
    tree.setProperty("genre", current.genre, nullptr);
    tree.setProperty("captureBars", current.captureBars, nullptr);
    tree.setProperty("armToBar", current.armToBar, nullptr);
    tree.setProperty("analyzeOnStop", current.analyzeOnStop, nullptr);

    juce::MemoryOutputStream stream(destData, false);
    tree.writeToStream(stream);
}

void DAWproBridgeProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    if (data == nullptr || sizeInBytes <= 0)
        return;

    const auto tree = juce::ValueTree::readFromData(data, (size_t) sizeInBytes);
    if (! tree.hasType(stateTag))
        return;

    Settings restored;
    const auto url = tree.getProperty("backendUrl").toString();
    if (url.isNotEmpty())
        restored.backendUrl = url;
    restored.sessionId = tree.getProperty("sessionId").toString();
    restored.personaId = tree.getProperty("personaId").toString();
    restored.sonicIntention = tree.getProperty("sonicIntention").toString();
    restored.genre = tree.getProperty("genre").toString();
    restored.captureBars = (int) tree.getProperty("captureBars", 16);
    restored.armToBar = (bool) tree.getProperty("armToBar", false);
    restored.analyzeOnStop = (bool) tree.getProperty("analyzeOnStop", false);

    {
        const juce::ScopedLock lock(stateLock);
        settings = restored;
    }
    sendChangeMessage();
    refreshBackend();
}

// --- Status -----------------------------------------------------------------

DAWproBridgeProcessor::Status DAWproBridgeProcessor::getStatus() const
{
    const juce::ScopedLock lock(stateLock);
    return status;
}

DAWproBridgeProcessor::Connection DAWproBridgeProcessor::getConnection() const
{
    const juce::ScopedLock lock(stateLock);
    return connection;
}

juce::String DAWproBridgeProcessor::getReferenceSpectrumJson() const
{
    const juce::ScopedLock lock(stateLock);
    return referenceSpectrumJson;
}

void DAWproBridgeProcessor::setStatus(Phase phase, const juce::String& message, float progress,
                                       const juce::String& resultJson)
{
    {
        const juce::ScopedLock lock(stateLock);
        status.phase = phase;
        status.message = message;
        status.progress = progress;
        status.activeJobs = jobsInFlight.load(std::memory_order_relaxed);
        status.armed = armPending.load(std::memory_order_relaxed);
        if (resultJson.isNotEmpty())
            status.resultJson = resultJson;
    }
    sendChangeMessage();
}

// --- Backend metadata -------------------------------------------------------

void DAWproBridgeProcessor::refreshBackend()
{
    const auto current = getSettings();
    const auto base = current.backendUrl.trimCharactersAtEnd("/");
    if (base.isEmpty())
        return;

    metadataPool.addJob([this, base, sessionId = current.sessionId]()
    {
        bool healthOk = false;
        fetchJson(base + "/health", healthOk);

        bool sessionsOk = false;
        const auto sessions = healthOk ? fetchJson(base + "/sessions", sessionsOk) : juce::String();

        bool historyOk = false;
        const auto history = (healthOk && sessionId.isNotEmpty())
                                 ? fetchJson(base + "/sessions/" + sessionId + "/analyses", historyOk)
                                 : juce::String();

        {
            const juce::ScopedLock lock(stateLock);
            connection.reachable = healthOk;
            connection.checked = true;
            if (sessionsOk)
                connection.sessionsJson = sessions;
            if (historyOk)
                connection.historyJson = history;
        }
        sendChangeMessage();
    });
}

// --- Analysis ---------------------------------------------------------------

int DAWproBridgeProcessor::captureWindowSamples() const
{
    const auto current = getSettings();
    if (current.captureBars <= 0)
        return 0; // whole buffer

    const double bpm = juce::jmax(1.0, currentBpm.load(std::memory_order_relaxed));
    const double beatsPerBar = juce::jmax(1, currentTimeSigNumerator.load(std::memory_order_relaxed));
    const double seconds = current.captureBars * beatsPerBar * 60.0 / bpm;
    return (int) (seconds * captureBuffer.getSampleRate());
}

void DAWproBridgeProcessor::triggerAnalysis()
{
    const auto current = getSettings();

    if (current.sessionId.isEmpty() || current.personaId.isEmpty())
    {
        setStatus(Phase::Failed, "Pick a session first.", 0.0f);
        return;
    }

    if (current.armToBar)
    {
        // Hand off to the audio thread, which fires on the next downbeat.
        armFired.store(false, std::memory_order_relaxed);
        armPending.store(true, std::memory_order_release);
        setStatus(Phase::Idle, "Armed - capturing on the next bar.", 0.0f);
        return;
    }

    submit(captureBuffer.snapshot(captureWindowSamples()), captureBuffer.getSampleRate());
}

void DAWproBridgeProcessor::submit(juce::AudioBuffer<float> audio, double sampleRate)
{
    if (audio.getNumSamples() == 0)
    {
        setStatus(Phase::Failed, "Nothing captured yet - play some audio first.", 0.0f);
        return;
    }

    const auto current = getSettings();

    UploadClient::AnalyzeParams params;
    params.backendUrl = current.backendUrl;
    params.sessionId = current.sessionId;
    params.personaId = current.personaId;
    params.sonicIntention = current.sonicIntention;
    params.genre = current.genre;
    params.bpm = currentBpm.load(std::memory_order_relaxed);
    params.timeSignature = juce::String(currentTimeSigNumerator.load(std::memory_order_relaxed))
                            + "/"
                            + juce::String(currentTimeSigDenominator.load(std::memory_order_relaxed));

    jobsInFlight.fetch_add(1, std::memory_order_relaxed);
    setStatus(Phase::Working, "Uploading...", 0.0f);

    uploadPool.addJob([this, audio = std::move(audio), sampleRate, params]() mutable
    {
        const auto response = UploadClient::analyzeAndAwait(
            audio, sampleRate, params,
            [this](const juce::String& stage, float progress)
            {
                setStatus(Phase::Working, stage + "...", progress);
            },
            cancelled);

        jobsInFlight.fetch_sub(1, std::memory_order_relaxed);

        if (response.ok)
            cacheReferenceSpectrum(response.resultJson);

        setStatus(response.ok ? Phase::Done : Phase::Failed,
                   response.message,
                   response.ok ? 1.0f : 0.0f,
                   response.resultJson);

        refreshBackend(); // the new analysis belongs in the history list
    });
}

void DAWproBridgeProcessor::cacheReferenceSpectrum(const juce::String& resultJson)
{
    // Kept so the live curve has something to be compared against between
    // analyses - without this the overlay would vanish the moment the plugin
    // window reopened.
    const auto parsed = juce::JSON::parse(resultJson);
    const auto reference = parsed.getProperty("measurements", {})
                                 .getProperty("spectrum", {})
                                 .getProperty("reference", {});

    const juce::ScopedLock lock(stateLock);
    referenceSpectrumJson = reference.isArray() ? juce::JSON::toString(reference) : juce::String("[]");
}

// This creates instances of the plugin - required JUCE entry point.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new DAWproBridgeProcessor();
}

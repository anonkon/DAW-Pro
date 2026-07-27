#include "PluginEditor.h"
#include "BinaryData.h"

namespace
{
    // The spectrum is the only thing that still needs a clock: it follows
    // continuous audio rather than a discrete state change. Everything else
    // arrives through changeListenerCallback.
    constexpr int liveHz = 24;
    constexpr int backendRefreshMs = 5000;

    const char* mimeFor(const juce::String& path)
    {
        if (path.endsWithIgnoreCase(".html")) return "text/html";
        if (path.endsWithIgnoreCase(".css")) return "text/css";
        if (path.endsWithIgnoreCase(".js")) return "application/javascript";
        return "application/octet-stream";
    }

    juce::var settingsToVar(const DAWproBridgeProcessor::Settings& s)
    {
        auto* object = new juce::DynamicObject();
        object->setProperty("backendUrl", s.backendUrl);
        object->setProperty("sessionId", s.sessionId);
        object->setProperty("personaId", s.personaId);
        object->setProperty("sonicIntention", s.sonicIntention);
        object->setProperty("genre", s.genre);
        object->setProperty("captureBars", s.captureBars);
        object->setProperty("armToBar", s.armToBar);
        return { object };
    }

    const char* phaseName(DAWproBridgeProcessor::Phase phase)
    {
        switch (phase)
        {
            case DAWproBridgeProcessor::Phase::Working: return "Working";
            case DAWproBridgeProcessor::Phase::Done:    return "Done";
            case DAWproBridgeProcessor::Phase::Failed:  return "Failed";
            case DAWproBridgeProcessor::Phase::Idle:
            default:                                    return "Idle";
        }
    }
}

DAWproBridgeEditor::DAWproBridgeEditor(DAWproBridgeProcessor& p)
    : juce::AudioProcessorEditor(&p),
      processorRef(p),
      webView(juce::WebBrowserComponent::Options{}
                  .withBackend(juce::WebBrowserComponent::Options::Backend::defaultBackend)
                  .withNativeIntegrationEnabled()
                  .withResourceProvider(&DAWproBridgeEditor::provideResource)
                  .withInitialisationData("settings", settingsJson())
                  .withInitialisationData("status", statusJson())
                  .withInitialisationData("connection", connectionJson())
                  .withInitialisationData("reference", processorRef.getReferenceSpectrumJson())
                  .withNativeFunction("setSettings",
                      [this](const juce::Array<juce::var>& args, auto complete)
                      {
                          if (args.size() > 0)
                          {
                              if (auto* object = args[0].getDynamicObject())
                              {
                                  auto updated = processorRef.getSettings();
                                  const auto str = [object](const char* key, juce::String fallback)
                                  {
                                      return object->hasProperty(key)
                                                 ? object->getProperty(key).toString()
                                                 : fallback;
                                  };
                                  updated.backendUrl = str("backendUrl", updated.backendUrl);
                                  updated.sessionId = str("sessionId", updated.sessionId);
                                  updated.personaId = str("personaId", updated.personaId);
                                  updated.sonicIntention = str("sonicIntention", updated.sonicIntention);
                                  updated.genre = str("genre", updated.genre);
                                  if (object->hasProperty("captureBars"))
                                      updated.captureBars = (int) object->getProperty("captureBars");
                                  if (object->hasProperty("armToBar"))
                                      updated.armToBar = (bool) object->getProperty("armToBar");
                                  processorRef.setSettings(updated);
                              }
                          }
                          complete({});
                      })
                  .withNativeFunction("analyze",
                      [this](const juce::Array<juce::var>&, auto complete)
                      {
                          processorRef.triggerAnalysis();
                          complete({});
                      })
                  .withNativeFunction("refresh",
                      [this](const juce::Array<juce::var>&, auto complete)
                      {
                          processorRef.refreshBackend();
                          complete({});
                      })
                  .withNativeFunction("openDashboard",
                      [this](const juce::Array<juce::var>&, auto complete)
                      {
                          const auto s = processorRef.getSettings();
                          // The dashboard is the Next app, not the API - assume
                          // the conventional local port rather than inventing a
                          // second URL field for the user to fill in.
                          auto base = s.backendUrl.replace(":8000", ":3000").trimCharactersAtEnd("/");
                          const auto url = s.sessionId.isNotEmpty()
                                               ? base + "/session/" + s.sessionId
                                               : base + "/dashboard";
                          juce::URL(url).launchInDefaultBrowser();
                          complete({});
                      }))
{
    addAndMakeVisible(webView);
    webView.goToURL(juce::WebBrowserComponent::getResourceProviderRoot() + "index.html");

    processorRef.addChangeListener(this);
    processorRef.refreshBackend();

    setResizable(true, true);
    setResizeLimits(340, 460, 900, 1400);
    setSize(420, 720);

    startTimerHz(liveHz);
    lastBackendRefresh = juce::Time::getMillisecondCounter();
}

DAWproBridgeEditor::~DAWproBridgeEditor()
{
    processorRef.removeChangeListener(this);
    stopTimer();
}

void DAWproBridgeEditor::paint(juce::Graphics& g)
{
    // Only visible for the instant before the page paints, so match its
    // background rather than flashing a different colour.
    g.fillAll(juce::Colour(0xff0a0a0c));
}

void DAWproBridgeEditor::resized()
{
    webView.setBounds(getLocalBounds());
}

void DAWproBridgeEditor::changeListenerCallback(juce::ChangeBroadcaster*)
{
    webView.emitEventIfBrowserIsVisible("status", juce::JSON::parse(statusJson()));
    webView.emitEventIfBrowserIsVisible("settings", juce::JSON::parse(settingsJson()));
    webView.emitEventIfBrowserIsVisible("connection", juce::JSON::parse(connectionJson()));
    webView.emitEventIfBrowserIsVisible("reference",
        juce::JSON::parse(processorRef.getReferenceSpectrumJson()));
}

void DAWproBridgeEditor::timerCallback()
{
    const auto frame = processorRef.computeLiveFrame();

    auto* object = new juce::DynamicObject();
    object->setProperty("level", processorRef.getCaptureLevel());
    object->setProperty("valid", frame.valid);
    object->setProperty("correlation", frame.correlation);
    object->setProperty("stereo", frame.stereo);

    if (frame.valid)
    {
        juce::Array<juce::var> db;
        db.ensureStorageAllocated((int) frame.db.size());
        for (float v : frame.db)
            db.add(juce::var(v));
        object->setProperty("db", db);
    }

    webView.emitEventIfBrowserIsVisible("live", juce::var(object));

    // Cheap enough to fold into this timer rather than run a second one.
    const auto now = juce::Time::getMillisecondCounter();
    if (now - lastBackendRefresh > (juce::uint32) backendRefreshMs)
    {
        lastBackendRefresh = now;
        processorRef.refreshBackend();
    }
}

juce::String DAWproBridgeEditor::settingsJson() const
{
    return juce::JSON::toString(settingsToVar(processorRef.getSettings()));
}

juce::String DAWproBridgeEditor::statusJson() const
{
    const auto status = processorRef.getStatus();

    auto* object = new juce::DynamicObject();
    object->setProperty("phase", phaseName(status.phase));
    object->setProperty("message", status.message);
    object->setProperty("progress", status.progress);
    object->setProperty("resultJson", status.resultJson);
    object->setProperty("activeJobs", status.activeJobs);
    object->setProperty("armed", status.armed);
    object->setProperty("bpm", processorRef.getCurrentBpm());
    return juce::JSON::toString(juce::var(object));
}

juce::String DAWproBridgeEditor::connectionJson() const
{
    const auto connection = processorRef.getConnection();

    auto* object = new juce::DynamicObject();
    object->setProperty("reachable", connection.reachable);
    object->setProperty("checked", connection.checked);
    object->setProperty("sessions", juce::JSON::parse(connection.sessionsJson));
    object->setProperty("history", juce::JSON::parse(connection.historyJson));
    return juce::JSON::toString(juce::var(object));
}

std::optional<juce::WebBrowserComponent::Resource>
DAWproBridgeEditor::provideResource(const juce::String& url)
{
    // The bundle is compiled in, so the plugin has no runtime file or network
    // dependency for its own UI.
    //
    // Match on the last path segment: juce_index.js imports a sibling by
    // relative path, and BinaryData keys are bare filenames either way.
    const auto path = url == "/" ? juce::String("index.html")
                                 : url.fromLastOccurrenceOf("/", false, false);

    int size = 0;
    if (const char* data = BinaryData::getNamedResource(
            juce::String(path).replaceCharacter('.', '_').toRawUTF8(), size))
    {
        std::vector<std::byte> bytes((size_t) size);
        std::memcpy(bytes.data(), data, (size_t) size);
        return juce::WebBrowserComponent::Resource { std::move(bytes), mimeFor(path) };
    }

    return std::nullopt;
}

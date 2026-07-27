#pragma once

#include <juce_gui_extra/juce_gui_extra.h>
#include "PluginProcessor.h"

/** The editor is a WebBrowserComponent hosting web/index.html.
 *
 *  It shares tokens.css with the dashboard verbatim (CMake copies the file in),
 *  so the plugin and the web app cannot drift apart visually. The alternative -
 *  a JUCE LookAndFeel - would mean maintaining the same palette in two places
 *  and hand-drawing the spectrum in juce::Graphics.
 */
class DAWproBridgeEditor : public juce::AudioProcessorEditor,
                            private juce::ChangeListener,
                            private juce::Timer
{
public:
    explicit DAWproBridgeEditor(DAWproBridgeProcessor&);
    ~DAWproBridgeEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void changeListenerCallback(juce::ChangeBroadcaster*) override;
    void timerCallback() override;

    juce::String settingsJson() const;
    juce::String statusJson() const;
    juce::String connectionJson() const;

    static std::optional<juce::WebBrowserComponent::Resource> provideResource(const juce::String& url);

    DAWproBridgeProcessor& processorRef;
    juce::WebBrowserComponent webView;
    juce::uint32 lastBackendRefresh = 0;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DAWproBridgeEditor)
};

#pragma once

#include <juce_audio_utils/juce_audio_utils.h>
#include "PluginProcessor.h"

class DAWproBridgeEditor : public juce::AudioProcessorEditor, private juce::Timer
{
public:
    explicit DAWproBridgeEditor(DAWproBridgeProcessor&);
    ~DAWproBridgeEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    void timerCallback() override;
    void analyzeButtonClicked();

    DAWproBridgeProcessor& processorRef;

    juce::Label titleLabel;
    juce::TextEditor backendUrlEditor;
    juce::TextEditor sessionIdEditor;
    juce::TextEditor personaIdEditor;
    juce::TextEditor sonicIntentionEditor;
    juce::TextEditor genreEditor;
    juce::TextButton analyzeButton { "Analyze" };
    juce::Label statusLabel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DAWproBridgeEditor)
};

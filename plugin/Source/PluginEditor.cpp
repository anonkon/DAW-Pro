#include "PluginEditor.h"

namespace
{
    void setupField(juce::TextEditor& editor, const juce::String& placeholder)
    {
        editor.setTextToShowWhenEmpty(placeholder, juce::Colours::grey);
        editor.setFont(juce::Font(14.0f));
    }
}

DAWproBridgeEditor::DAWproBridgeEditor(DAWproBridgeProcessor& p)
    : juce::AudioProcessorEditor(&p), processorRef(p)
{
    titleLabel.setText("DAWpro Bridge", juce::dontSendNotification);
    titleLabel.setFont(juce::Font(18.0f, juce::Font::bold));
    addAndMakeVisible(titleLabel);

    setupField(backendUrlEditor, "Backend URL");
    backendUrlEditor.setText("http://localhost:8000", juce::dontSendNotification);
    addAndMakeVisible(backendUrlEditor);

    setupField(sessionIdEditor, "Session ID (from the dashboard)");
    addAndMakeVisible(sessionIdEditor);

    setupField(personaIdEditor, "Persona ID (from the dashboard)");
    addAndMakeVisible(personaIdEditor);

    setupField(sonicIntentionEditor, "Sonic intention, e.g. modern trap beat, wide low end");
    addAndMakeVisible(sonicIntentionEditor);

    setupField(genreEditor, "Genre (optional)");
    addAndMakeVisible(genreEditor);

    analyzeButton.onClick = [this] { analyzeButtonClicked(); };
    addAndMakeVisible(analyzeButton);

    statusLabel.setText(processorRef.getStatusMessage(), juce::dontSendNotification);
    statusLabel.setFont(juce::Font(13.0f));
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::lightgrey);
    addAndMakeVisible(statusLabel);

    setSize(420, 320);
    startTimerHz(2);
}

DAWproBridgeEditor::~DAWproBridgeEditor()
{
    stopTimer();
}

void DAWproBridgeEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff1a1a1e));
}

void DAWproBridgeEditor::resized()
{
    auto area = getLocalBounds().reduced(16);

    titleLabel.setBounds(area.removeFromTop(28));
    area.removeFromTop(12);

    backendUrlEditor.setBounds(area.removeFromTop(28));
    area.removeFromTop(8);
    sessionIdEditor.setBounds(area.removeFromTop(28));
    area.removeFromTop(8);
    personaIdEditor.setBounds(area.removeFromTop(28));
    area.removeFromTop(8);
    sonicIntentionEditor.setBounds(area.removeFromTop(28));
    area.removeFromTop(8);
    genreEditor.setBounds(area.removeFromTop(28));
    area.removeFromTop(12);

    analyzeButton.setBounds(area.removeFromTop(32).withSizeKeepingCentre(120, 32));
    area.removeFromTop(12);

    statusLabel.setBounds(area);
}

void DAWproBridgeEditor::timerCallback()
{
    statusLabel.setText(processorRef.getStatusMessage(), juce::dontSendNotification);
}

void DAWproBridgeEditor::analyzeButtonClicked()
{
    processorRef.triggerAnalysis(backendUrlEditor.getText(),
                                  sessionIdEditor.getText(),
                                  personaIdEditor.getText(),
                                  sonicIntentionEditor.getText(),
                                  genreEditor.getText());
}

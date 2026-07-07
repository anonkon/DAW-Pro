cmake_minimum_required(VERSION 3.22)
project(DAWproBridge VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Point this at the unzipped JUCE folder, e.g.:
#   cmake -B build -DJUCE_DIR=C:/Tools/JUCE
set(JUCE_DIR "" CACHE PATH "Path to the unzipped JUCE folder")
if(NOT JUCE_DIR)
    message(FATAL_ERROR "Set -DJUCE_DIR=<path to unzipped JUCE>, e.g. -DJUCE_DIR=C:/Tools/JUCE")
endif()
add_subdirectory(${JUCE_DIR} JUCE)

juce_add_plugin(DAWproBridge
    COMPANY_NAME "DAWpro"
    PLUGIN_MANUFACTURER_CODE Dwpr
    PLUGIN_CODE Brdg
    FORMATS VST3
    PRODUCT_NAME "DAWpro Bridge"
    VST3_CATEGORIES "Analyzer"
    IS_SYNTH FALSE
    NEEDS_MIDI_INPUT FALSE
    NEEDS_MIDI_OUTPUT FALSE
    IS_MIDI_EFFECT FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS FALSE
)

target_sources(DAWproBridge PRIVATE
    Source/PluginProcessor.cpp
    Source/PluginEditor.cpp
    Source/CaptureBuffer.cpp
    Source/UploadClient.cpp
)

# VST3-only build (no VST2 target) - tells JUCE's VST3 wrapper it doesn't need
# to guard against VST2/VST3 parameter-automation ID collisions.
target_compile_definitions(DAWproBridge PUBLIC
    JUCE_VST3_CAN_REPLACE_VST2=0
)

target_link_libraries(DAWproBridge
    PRIVATE
        juce::juce_audio_utils
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)

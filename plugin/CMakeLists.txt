cmake_minimum_required(VERSION 3.22)

# macOS build settings must be set before project() so they take effect for the
# whole tree (including JUCE). Ignored on Windows/Linux.
#   - Deployment target: oldest macOS the plugin will load on.
#   - Architectures: build a universal binary so it runs on both Apple Silicon
#     and Intel hosts / DAWs.
if(APPLE)
    set(CMAKE_OSX_DEPLOYMENT_TARGET "10.13" CACHE STRING "Minimum macOS version")
    set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "Universal binary architectures")
endif()

project(DAWproBridge VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Point this at the unzipped JUCE folder:
#   macOS/Linux:  cmake -B build -DJUCE_DIR=~/JUCE
#   Windows:      cmake -B build -DJUCE_DIR=C:/Tools/JUCE
set(JUCE_DIR "" CACHE PATH "Path to the unzipped JUCE folder")
if(NOT JUCE_DIR)
    message(FATAL_ERROR "Set -DJUCE_DIR=<path to unzipped JUCE>, e.g. -DJUCE_DIR=~/JUCE (macOS) or -DJUCE_DIR=C:/Tools/JUCE (Windows)")
endif()
add_subdirectory(${JUCE_DIR} JUCE)

# Formats per platform: VST3 works everywhere; AU (Audio Unit) is the native
# macOS format that Logic Pro, GarageBand and other Apple-hosted DAWs require -
# they will not load a VST3. So macOS builds both.
if(APPLE)
    set(DAWPRO_FORMATS AU VST3)
else()
    set(DAWPRO_FORMATS VST3)
endif()

juce_add_plugin(DAWproBridge
    COMPANY_NAME "DAWpro"
    BUNDLE_ID com.dawpro.bridge
    PLUGIN_MANUFACTURER_CODE Dwpr
    PLUGIN_CODE Brdg
    FORMATS ${DAWPRO_FORMATS}
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
    Source/LiveAnalyser.cpp
)

# --- Web UI bundle ----------------------------------------------------------
# The editor is a WebBrowserComponent serving these files out of BinaryData, so
# the plugin has no runtime file or network dependency.
#
# tokens.css is copied from the dashboard rather than duplicated: it is the one
# source of truth for the palette, and a copy here would drift. configure_file
# registers a dependency, so editing the dashboard's copy re-runs CMake.
set(DAWPRO_TOKENS_SRC "${CMAKE_CURRENT_SOURCE_DIR}/../dashboard/app/tokens.css")
if(NOT EXISTS "${DAWPRO_TOKENS_SRC}")
    message(FATAL_ERROR "Design tokens not found at ${DAWPRO_TOKENS_SRC} - the plugin UI shares them with the dashboard.")
endif()
configure_file("${DAWPRO_TOKENS_SRC}" "${CMAKE_CURRENT_BINARY_DIR}/web/tokens.css" COPYONLY)

# JUCE's WebView frontend library. Only window.__JUCE__.backend (events) is
# injected natively; getNativeFunction lives in this ES module, so without it
# every JS -> C++ call throws and the UI silently stops responding while still
# receiving updates. It imports ./check_native_interop.js relatively, so both
# files are served from the same flat root.
set(DAWPRO_JUCE_JS "${JUCE_DIR}/modules/juce_gui_extra/native/javascript")
if(NOT EXISTS "${DAWPRO_JUCE_JS}/index.js")
    message(FATAL_ERROR "JUCE WebView frontend library not found at ${DAWPRO_JUCE_JS}")
endif()
configure_file("${DAWPRO_JUCE_JS}/index.js" "${CMAKE_CURRENT_BINARY_DIR}/web/juce_index.js" COPYONLY)
configure_file("${DAWPRO_JUCE_JS}/check_native_interop.js"
               "${CMAKE_CURRENT_BINARY_DIR}/web/check_native_interop.js" COPYONLY)

juce_add_binary_data(DAWproWebAssets
    HEADER_NAME BinaryData.h
    NAMESPACE BinaryData
    SOURCES
        "${CMAKE_CURRENT_SOURCE_DIR}/web/index.html"
        "${CMAKE_CURRENT_BINARY_DIR}/web/tokens.css"
        "${CMAKE_CURRENT_BINARY_DIR}/web/juce_index.js"
        "${CMAKE_CURRENT_BINARY_DIR}/web/check_native_interop.js"
)

# Binary data is linked into a shared-code target, so it needs PIC.
set_target_properties(DAWproWebAssets PROPERTIES POSITION_INDEPENDENT_CODE TRUE)

# VST3-only build (no VST2 target) - tells JUCE's VST3 wrapper it doesn't need
# to guard against VST2/VST3 parameter-automation ID collisions.
target_compile_definitions(DAWproBridge PUBLIC
    JUCE_VST3_CAN_REPLACE_VST2=0
    # Required for WebBrowserComponent's native integration (JUCE 8+).
    JUCE_WEB_BROWSER=1
    JUCE_USE_WIN_WEBVIEW2_WITH_STATIC_LINKING=1
)

target_link_libraries(DAWproBridge
    PRIVATE
        DAWproWebAssets
        juce::juce_audio_utils
        juce::juce_gui_extra
        juce::juce_dsp
    PUBLIC
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)

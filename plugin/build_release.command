#!/usr/bin/env bash
#
# macOS release build for the DAWpro Bridge plugin (VST3 + AU).
# Counterpart to build_release.bat (Windows). Double-clickable in Finder,
# or run from a terminal:  ./build_release.command
#
# Requirements:
#   - Xcode Command Line Tools:  xcode-select --install
#   - CMake:                     brew install cmake   (or https://cmake.org)
#   - JUCE unzipped somewhere, e.g. ~/JUCE
#
# Point it at JUCE via the JUCE_DIR env var or the first argument:
#   JUCE_DIR=~/JUCE ./build_release.command
#   ./build_release.command ~/JUCE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# JUCE location: env var, then first arg, then a few common install spots.
JUCE_DIR="${JUCE_DIR:-${1:-}}"
if [ -z "$JUCE_DIR" ]; then
    for candidate in "$HOME/JUCE" "$HOME/Tools/JUCE" "$HOME/Developer/JUCE" "/Applications/JUCE" "/usr/local/JUCE"; do
        if [ -f "$candidate/CMakeLists.txt" ]; then
            JUCE_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$JUCE_DIR" ] || [ ! -f "$JUCE_DIR/CMakeLists.txt" ]; then
    echo "error: could not find JUCE." >&2
    echo "Download it from https://juce.com/get-juce, unzip it, then run:" >&2
    echo "  JUCE_DIR=/path/to/JUCE ./build_release.command" >&2
    exit 1
fi

echo "Using JUCE at: $JUCE_DIR"

CORES="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"

cmake -B build-release -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DJUCE_DIR="$JUCE_DIR"

cmake --build build-release --target DAWproBridge_VST3 -j "$CORES"
cmake --build build-release --target DAWproBridge_AU   -j "$CORES"

ARTEFACTS="$SCRIPT_DIR/build-release/DAWproBridge_artefacts/Release"

echo
echo "Build complete. Built plugins:"
echo "  VST3: $ARTEFACTS/VST3/DAWpro Bridge.vst3"
echo "  AU:   $ARTEFACTS/AU/DAWpro Bridge.component"
echo
echo "To install for your DAW, copy them into your user plugin folders:"
echo "  cp -R \"$ARTEFACTS/VST3/DAWpro Bridge.vst3\" ~/Library/Audio/Plug-Ins/VST3/"
echo "  cp -R \"$ARTEFACTS/AU/DAWpro Bridge.component\" ~/Library/Audio/Plug-Ins/Components/"

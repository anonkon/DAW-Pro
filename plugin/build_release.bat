call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
"C:\Program Files\CMake\bin\cmake.exe" -G Ninja -B build-release -DCMAKE_BUILD_TYPE=Release -DJUCE_DIR=C:/Tools/juce-8.0.14-windows/JUCE
"C:\Program Files\CMake\bin\cmake.exe" --build build-release --target DAWproBridge_VST3

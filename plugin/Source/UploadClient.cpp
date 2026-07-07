#include "UploadClient.h"

namespace
{
    juce::MemoryBlock encodeAsWav(const juce::AudioBuffer<float>& audio, double sampleRate)
    {
        juce::MemoryBlock wavData;

        // WavAudioFormat::createWriterFor takes ownership of the stream it's
        // given and deletes it when the writer is destroyed - so this must be
        // a heap pointer, not the address of a stack object.
        auto* memoryStream = new juce::MemoryOutputStream(wavData, false);
        juce::WavAudioFormat wavFormat;
        std::unique_ptr<juce::AudioFormatWriter> writer(
            wavFormat.createWriterFor(memoryStream, sampleRate,
                                       (unsigned int) audio.getNumChannels(),
                                       16, {}, 0));

        if (writer == nullptr)
        {
            delete memoryStream;
            return {};
        }

        writer->writeFromAudioSampleBuffer(audio, 0, audio.getNumSamples());
        // Destroying `writer` here flushes the WAV header/data into wavData.

        return wavData;
    }

    void appendFormField(juce::MemoryOutputStream& out, const juce::String& boundary,
                          const juce::String& name, const juce::String& value)
    {
        out << "--" << boundary << "\r\n";
        out << "Content-Disposition: form-data; name=\"" << name << "\"\r\n\r\n";
        out << value << "\r\n";
    }
}

juce::String UploadClient::sendCapturedAudio(const juce::AudioBuffer<float>& audio,
                                              double sampleRate,
                                              const AnalyzeParams& params)
{
    if (audio.getNumSamples() == 0)
        return "Nothing captured yet";

    const juce::MemoryBlock wavData = encodeAsWav(audio, sampleRate);
    if (wavData.getSize() == 0)
        return "Failed to encode captured audio as WAV";

    const juce::String boundary =
        "DAWproBoundary" + juce::String(juce::Random::getSystemRandom().nextInt64());

    juce::MemoryBlock body;
    juce::MemoryOutputStream bodyStream(body, false);

    appendFormField(bodyStream, boundary, "session_id", params.sessionId);
    appendFormField(bodyStream, boundary, "persona_id", params.personaId);
    appendFormField(bodyStream, boundary, "sonic_intention", params.sonicIntention);
    appendFormField(bodyStream, boundary, "source", "plugin_capture");
    if (params.genre.isNotEmpty())
        appendFormField(bodyStream, boundary, "genre", params.genre);
    appendFormField(bodyStream, boundary, "bpm", juce::String(params.bpm));
    appendFormField(bodyStream, boundary, "time_signature", params.timeSignature);

    bodyStream << "--" << boundary << "\r\n";
    bodyStream << "Content-Disposition: form-data; name=\"file\"; filename=\"capture.wav\"\r\n";
    bodyStream << "Content-Type: audio/wav\r\n\r\n";
    bodyStream.write(wavData.getData(), wavData.getSize());
    bodyStream << "\r\n--" << boundary << "--\r\n";
    bodyStream.flush();

    juce::URL url(params.backendUrl.trimCharactersAtEnd("/") + "/analyze");
    url = url.withPOSTData(body);

    const juce::String contentTypeHeader = "Content-Type: multipart/form-data; boundary=" + boundary;
    int statusCode = 0;
    juce::StringPairArray responseHeaders;

    const auto options = juce::URL::InputStreamOptions(juce::URL::ParameterHandling::inPostData)
                              .withExtraHeaders(contentTypeHeader)
                              .withConnectionTimeoutMs(30000)
                              .withHttpRequestCmd("POST")
                              .withStatusCode(&statusCode)
                              .withResponseHeaders(&responseHeaders);

    std::unique_ptr<juce::InputStream> stream(url.createInputStream(options));

    if (stream == nullptr)
        return "Could not connect to backend at " + params.backendUrl;

    const auto responseBody = stream->readEntireStreamAsString();

    if (statusCode < 200 || statusCode >= 300)
        return "Backend returned " + juce::String(statusCode) + ": " + responseBody;

    return "Sent - analysis running, check the dashboard";
}

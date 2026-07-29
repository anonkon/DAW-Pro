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

        // The writer has to be destroyed *before* wavData is read. WavAudioFormat
        // only patches the RIFF and data chunk lengths in its destructor, by
        // seeking back to the top of the stream. Letting `writer` fall out of
        // scope at the end of the function is too late: the return value is
        // copied first, so the caller gets a header still claiming zero frames
        // and uploads megabytes of audio that every reader sees as empty.
        writer.reset();

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

namespace
{
    // How long to keep polling before giving up. Demucs stem separation is the
    // slow step and can run for minutes on a long capture.
    constexpr int pollTimeoutMs = 10 * 60 * 1000;
    constexpr int pollIntervalMs = 1000;

    juce::String friendlyStage(const juce::String& status)
    {
        if (status == "queued") return "Queued";
        if (status == "separating_stems") return "Separating stems";
        if (status == "extracting_features") return "Extracting features";
        if (status == "analyzing") return "Analyzing";
        return status;
    }
}

UploadClient::Response UploadClient::analyzeAndAwait(const juce::AudioBuffer<float>& audio,
                                                      double sampleRate,
                                                      const AnalyzeParams& params,
                                                      ProgressFn onProgress,
                                                      const std::atomic<bool>& cancelled)
{
    const auto report = [&onProgress](const juce::String& stage, float progress)
    {
        if (onProgress != nullptr)
            onProgress(stage, progress);
    };

    if (audio.getNumSamples() == 0)
        return { false, "Nothing captured yet", {} };

    const juce::MemoryBlock wavData = encodeAsWav(audio, sampleRate);
    if (wavData.getSize() == 0)
        return { false, "Failed to encode captured audio as WAV", {} };

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

    report("Uploading", 0.05f);
    std::unique_ptr<juce::InputStream> stream(url.createInputStream(options));

    if (stream == nullptr)
        return { false, "Could not connect to backend at " + params.backendUrl, {} };

    const auto responseBody = stream->readEntireStreamAsString();

    if (statusCode < 200 || statusCode >= 300)
        return { false, "Backend returned " + juce::String(statusCode) + ": " + responseBody, {} };

    const auto accepted = juce::JSON::parse(responseBody);
    const auto jobId = accepted.getProperty("job_id", {}).toString();
    if (jobId.isEmpty())
        return { false, "Backend did not return a job id", {} };

    // --- Poll until the job finishes -------------------------------------
    const juce::String jobUrl = params.backendUrl.trimCharactersAtEnd("/") + "/jobs/" + jobId;
    const auto deadline = juce::Time::getMillisecondCounter() + (juce::uint32) pollTimeoutMs;

    while (juce::Time::getMillisecondCounter() < deadline)
    {
        if (cancelled.load(std::memory_order_relaxed))
            return { false, "Cancelled - the analysis is still running, check the dashboard", {} };

        juce::Thread::sleep(pollIntervalMs);

        int jobStatusCode = 0;
        const auto jobOptions = juce::URL::InputStreamOptions(juce::URL::ParameterHandling::inAddress)
                                     .withConnectionTimeoutMs(15000)
                                     .withStatusCode(&jobStatusCode);

        std::unique_ptr<juce::InputStream> jobStream(juce::URL(jobUrl).createInputStream(jobOptions));
        if (jobStream == nullptr)
            continue; // a dropped poll is not fatal; the next one may succeed

        const auto jobBody = jobStream->readEntireStreamAsString();
        if (jobStatusCode < 200 || jobStatusCode >= 300)
            continue;

        const auto job = juce::JSON::parse(jobBody);
        const auto status = job.getProperty("status", {}).toString();
        const auto progress = (float) (double) job.getProperty("progress", 0.0);

        if (status == "done")
        {
            report("Done", 1.0f);
            const auto result = job.getProperty("result", {});
            return { true, "Analysis complete", juce::JSON::toString(result) };
        }

        if (status == "failed")
        {
            const auto error = job.getProperty("error", {}).toString();
            return { false, "Analysis failed: " + error, {} };
        }

        report(friendlyStage(status), progress);
    }

    return { false, "Timed out waiting for the backend - check the dashboard", {} };
}

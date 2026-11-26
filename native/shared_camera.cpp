// Windows Frame Server read-only camera. No driver or registry changes.
#define NOMINMAX
#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <mferror.h>
#include <wrl.h>
#include <condition_variable>
#include <mutex>
#include <memory>
#include <vector>
#include <chrono>
#include <cstring>

using Microsoft::WRL::ComPtr;
struct State {
    std::mutex mutex;
    std::condition_variable changed;
    ComPtr<IMFSourceReader> reader;
    std::vector<unsigned char> pixels;
    unsigned width = 0, height = 0;
    LONG stride = 0;
    unsigned long long sequence = 0;
    HRESULT error = S_OK;
    bool stopping = false, flushed = false;
};

class Callback final : public Microsoft::WRL::RuntimeClass<
    Microsoft::WRL::RuntimeClassFlags<Microsoft::WRL::ClassicCom>, IMFSourceReaderCallback> {
    std::shared_ptr<State> state;
public:
    explicit Callback(std::shared_ptr<State> s) : state(std::move(s)) {}
    STDMETHODIMP OnReadSample(HRESULT result, DWORD, DWORD flags, LONGLONG, IMFSample* sample) override try {
        auto s = state;
        std::lock_guard<std::mutex> lock(s->mutex);
        if (s->stopping) return S_OK;
        if (SUCCEEDED(result) && (flags & MF_SOURCE_READERF_ENDOFSTREAM)) result = MF_E_END_OF_STREAM;
        if (SUCCEEDED(result) && (flags & MF_SOURCE_READERF_CURRENTMEDIATYPECHANGED)) {
            s->pixels.clear(); // Old pixels no longer describe the new size.
            ComPtr<IMFMediaType> type;
            result = s->reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_VIDEO_STREAM, &type);
            if (SUCCEEDED(result)) result = MFGetAttributeSize(type.Get(), MF_MT_FRAME_SIZE, &s->width, &s->height);
            GUID subtype{};
            if (SUCCEEDED(result)) result = type->GetGUID(MF_MT_SUBTYPE, &subtype);
            if (SUCCEEDED(result) && subtype != MFVideoFormat_RGB32) result = MF_E_INVALIDMEDIATYPE;
            UINT32 stride = s->width * 4;
            if (type) type->GetUINT32(MF_MT_DEFAULT_STRIDE, &stride);
            s->stride = static_cast<LONG>(stride);
        }
        if (SUCCEEDED(result) && sample) {
            ComPtr<IMFMediaBuffer> buffer;
            result = sample->ConvertToContiguousBuffer(&buffer);
            if (SUCCEEDED(result)) {
                ComPtr<IMF2DBuffer> image;
                BYTE* bytes = nullptr;
                LONG pitch = s->stride;
                DWORD size = 0;
                bool twoD = SUCCEEDED(buffer.As(&image));
                result = twoD ? image->Lock2D(&bytes, &pitch) : buffer->Lock(&bytes, nullptr, &size);
                if (SUCCEEDED(result)) {
                    const size_t row = static_cast<size_t>(s->width) * 4;
                    const size_t required = static_cast<size_t>(s->height) * row;
                    if (!s->width || !s->height || required > 128 * 1024 * 1024 ||
                        static_cast<size_t>(std::abs(pitch)) < row ||
                        (!twoD && size < static_cast<size_t>(std::abs(pitch)) * s->height)) {
                        result = MF_E_BUFFERTOOSMALL;
                    } else {
                        s->pixels.resize(required);
                        if (!twoD && pitch < 0) bytes += static_cast<size_t>(-pitch) * (s->height - 1);
                        for (unsigned y = 0; y < s->height; ++y)
                            std::memcpy(s->pixels.data() + y * row, bytes + static_cast<ptrdiff_t>(y) * pitch, row);
                        ++s->sequence;
                    }
                    if (twoD) image->Unlock2D(); else buffer->Unlock();
                }
            }
        }
        if (SUCCEEDED(result)) result = s->reader->ReadSample(MF_SOURCE_READER_FIRST_VIDEO_STREAM, 0, nullptr, nullptr, nullptr, nullptr);
        if (FAILED(result)) s->error = result;
        s->changed.notify_all();
        return S_OK;
    } catch (...) {
        std::lock_guard<std::mutex> lock(state->mutex);
        state->error = E_OUTOFMEMORY;
        state->changed.notify_all();
        return S_OK;
    }
    STDMETHODIMP OnEvent(DWORD, IMFMediaEvent*) override { return S_OK; }
    STDMETHODIMP OnFlush(DWORD) override {
        std::lock_guard<std::mutex> lock(state->mutex);
        state->flushed = true;
        state->changed.notify_all();
        return S_OK;
    }
};

struct Session {
    std::shared_ptr<State> state = std::make_shared<State>();
    ComPtr<IMFMediaSource> source;
    bool com = false, mf = false;
    ~Session() {
        ComPtr<IMFSourceReader> reader;
        {
            std::lock_guard<std::mutex> lock(state->mutex);
            state->stopping = true;
            reader = state->reader;
        }
        if (reader) {
            HRESULT hr = reader->Flush(MF_SOURCE_READER_ALL_STREAMS);
            if (SUCCEEDED(hr)) {
                std::unique_lock<std::mutex> lock(state->mutex);
                state->changed.wait_for(lock, std::chrono::seconds(2), [&] { return state->flushed; });
            }
        }
        if (source) source->Shutdown();
        {
            std::lock_guard<std::mutex> lock(state->mutex);
            state->reader.Reset(); // Break callback -> state -> reader ownership.
        }
        reader.Reset();
        source.Reset();
        if (mf) MFShutdown();
        if (com) CoUninitialize();
    }
};

extern "C" __declspec(dllexport) HRESULT ac_open(int index, void** handle) {
    if (!handle || index < 0) return E_INVALIDARG;
    *handle = nullptr;
    try {
        auto session = std::make_unique<Session>();
        HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (FAILED(hr)) return hr;
        session->com = true;
        hr = MFStartup(MF_VERSION);
        if (FAILED(hr)) return hr;
        session->mf = true;
        ComPtr<IMFAttributes> attributes;
        hr = MFCreateAttributes(&attributes, 3);
        if (FAILED(hr)) return hr;
        hr = attributes->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE, MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID);
        if (FAILED(hr)) return hr;
        IMFActivate** devices = nullptr;
        UINT32 count = 0;
        hr = MFEnumDeviceSources(attributes.Get(), &devices, &count);
        if (FAILED(hr)) return hr;
        ComPtr<IMFActivate> chosen;
        if (static_cast<UINT32>(index) < count) chosen = devices[index];
        for (UINT32 i = 0; i < count; ++i) devices[i]->Release();
        CoTaskMemFree(devices);
        if (!chosen) return MF_E_NOT_FOUND;
        // Essential difference from OpenCV MSMF's default controlling mode.
        hr = chosen->SetUINT32(MF_DEVSOURCE_ATTRIBUTE_FRAMESERVER_SHARE_MODE, 1);
        if (FAILED(hr)) return hr;
        hr = chosen->ActivateObject(IID_PPV_ARGS(&session->source));
        if (FAILED(hr)) return hr;
        auto callback = Microsoft::WRL::Make<Callback>(session->state);
        attributes.Reset();
        hr = MFCreateAttributes(&attributes, 2);
        if (FAILED(hr)) return hr;
        hr = attributes->SetUnknown(MF_SOURCE_READER_ASYNC_CALLBACK, callback.Get());
        if (FAILED(hr)) return hr;
        hr = attributes->SetUINT32(MF_SOURCE_READER_ENABLE_VIDEO_PROCESSING, TRUE);
        if (FAILED(hr)) return hr;
        auto s = session->state;
        hr = MFCreateSourceReaderFromMediaSource(session->source.Get(), attributes.Get(), &s->reader);
        if (FAILED(hr)) return hr;
        hr = s->reader->SetStreamSelection(MF_SOURCE_READER_ALL_STREAMS, FALSE);
        if (FAILED(hr)) return hr;
        hr = s->reader->SetStreamSelection(MF_SOURCE_READER_FIRST_VIDEO_STREAM, TRUE);
        if (FAILED(hr)) return hr;
        ComPtr<IMFMediaType> type;
        hr = s->reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_VIDEO_STREAM, &type);
        if (FAILED(hr)) return hr;
        // Preserve the device's active size/rate. Convert the client output
        // only, never renegotiate the physical stream or change its controls.
        hr = type->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_RGB32);
        if (FAILED(hr)) return hr;
        type->DeleteItem(MF_MT_DEFAULT_STRIDE);
        hr = s->reader->SetCurrentMediaType(MF_SOURCE_READER_FIRST_VIDEO_STREAM, nullptr, type.Get());
        if (FAILED(hr)) return hr;
        type.Reset();
        hr = s->reader->GetCurrentMediaType(MF_SOURCE_READER_FIRST_VIDEO_STREAM, &type);
        if (FAILED(hr)) return hr;
        hr = MFGetAttributeSize(type.Get(), MF_MT_FRAME_SIZE, &s->width, &s->height);
        if (FAILED(hr)) return hr;
        UINT32 stride = s->width * 4;
        type->GetUINT32(MF_MT_DEFAULT_STRIDE, &stride);
        s->stride = static_cast<LONG>(stride);
        hr = s->reader->ReadSample(MF_SOURCE_READER_FIRST_VIDEO_STREAM, 0, nullptr, nullptr, nullptr, nullptr);
        if (FAILED(hr)) return hr;
        *handle = session.release();
        return S_OK;
    } catch (...) { return E_OUTOFMEMORY; }
}

// S_OK = copied, S_FALSE = timed out, 2 = caller needs larger buffer.
extern "C" __declspec(dllexport) HRESULT ac_frame(void* handle, unsigned long long after, unsigned timeout,
    unsigned char* output, unsigned capacity, unsigned* width, unsigned* height, unsigned long long* sequence) {
    if (!handle || !width || !height || !sequence) return E_INVALIDARG;
    auto s = static_cast<Session*>(handle)->state;
    std::unique_lock<std::mutex> lock(s->mutex);
    s->changed.wait_for(lock, std::chrono::milliseconds(timeout), [&] {
        return s->sequence > after || FAILED(s->error) || s->stopping;
    });
    if (FAILED(s->error)) return s->error;
    if (s->sequence <= after || s->pixels.empty()) return S_FALSE;
    *width = s->width; *height = s->height; *sequence = s->sequence;
    if (!output || capacity < s->pixels.size()) return 2;
    std::memcpy(output, s->pixels.data(), s->pixels.size());
    return S_OK;
}

extern "C" __declspec(dllexport) void ac_close(void* handle) {
    delete static_cast<Session*>(handle);
}

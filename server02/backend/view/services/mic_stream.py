# mic_stream.py
import sounddevice as sd
import numpy as np

class MicStreamer:
    """Captura audio del micrófono y envía PCM int16/16kHz al STT runtime."""
    def __init__(self, runtime, samplerate=16000, channels=1, block_ms=40):
        self.rt = runtime
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = int(samplerate * block_ms / 1000)
        self.stream: sd.InputStream | None = None
        self.active = False

    def _callback(self, indata, frames, time, status):
        if status:
            print("[mic]", status)
        if not self.active:
            return
        # indata ya está en int16 si así configuramos dtype
        data_bytes = indata.tobytes()
        self.rt.send_chunk(data_bytes)

    def start(self):
        if self.stream is None:
            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype='int16',
                blocksize=self.blocksize,
                callback=self._callback,
            )
        if not self.active:
            self.rt.start_session()
            self.stream.start()
            self.active = True
            print("[mic] grabando...")

    def stop(self):
        if self.active:
            self.active = False
            try:
                self.stream.stop()
            except Exception:
                pass
            self.rt.stop_session()
            print("[mic] detenido")

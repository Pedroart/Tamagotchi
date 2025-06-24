if __name__ == '__main__':
    print("Starting...")
    from RealtimeSTT import AudioToTextRecorder

    def text_detected(text):
        print(f"\n>> FINAL: {text}")

    def on_realtime_transcription_update(partial_text):
        print(f"\r>> EN VIVO: {partial_text}", end='', flush=True)

    with AudioToTextRecorder(
        spinner=False,
        model="tiny",                          # Modelo principal
        language="es",                         # Español
        device="cuda",                         # Usar GPU
        gpu_device_index=0,                    # GPU index
        enable_realtime_transcription=True,    # Transcripción en tiempo real
        use_main_model_for_realtime=True,      # Usar el mismo modelo para todo
        realtime_processing_pause=0.2,         # Frecuencia de actualización
        on_realtime_transcription_update=on_realtime_transcription_update,
    ) as recorder:
        while True:
            recorder.text(text_detected)

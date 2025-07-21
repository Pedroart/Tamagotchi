if __name__ == '__main__':
    print("Starting...")
    from RealtimeSTT import AudioToTextRecorder

    def text_detected(text):
        print(f"\n>> {text}")

    def on_realtime_transcription_update(partial_text):
        print(f"\r>> {partial_text}", end='', flush=True)

    with AudioToTextRecorder(
        spinner=False,
        model="tiny",
        language="es",
        #wakeword_backend="none",
        #openwakeword_model_paths="suh_man_tuh.onnx,suh_mahn_thuh.onnx",
        #enable_realtime_transcription=True,
        #use_main_model_for_realtime=True,
        #realtime_model_type="tiny",
        #realtime_processing_pause=0.1,
        #on_realtime_transcription_update=on_realtime_transcription_update,
        
    ) as recorder:
        while True:
            recorder.text(text_detected)

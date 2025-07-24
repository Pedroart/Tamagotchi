import asyncio
import websockets
import sounddevice as sd
import numpy as np
from pynput import keyboard as kb  # sin root

SERVER_URI = "ws://localhost:55000"
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)

mic_active = False  # ✅ ahora es un estado toggle
stream = None
main_loop = None  # referencia global del loop principal

async def websocket_client():
    global mic_active, stream, main_loop
    main_loop = asyncio.get_running_loop()  # ✅ guardamos el loop principal

    async with websockets.connect(SERVER_URI, max_size=50 * 1024 * 1024) as ws:
        print("✅ Conectado al servidor WebSocket")

        # Receptor paralelo para mensajes del servidor
        async def receiver():
            try:
                async for msg in ws:
                    if msg.startswith("(parcial)"):
                        print(f"📝 Parcial: {msg}")
                    else:
                        print(f"✅ Final recibido: {msg}")
            except websockets.ConnectionClosed:
                print("❌ Conexión cerrada")

        recv_task = asyncio.create_task(receiver())

        # ✅ Callback del micrófono → enviar chunk al WS usando el loop guardado
        def mic_callback(indata, frames, time, status):
            if status:
                print(f"⚠️ Estado del micrófono: {status}")
            pcm_chunk = (indata[:, 0] * 32767).astype(np.int16).tobytes()
            if main_loop and ws:
                asyncio.run_coroutine_threadsafe(ws.send(pcm_chunk), main_loop)

        async def start_mic():
            global stream, mic_active
            if stream is None:
                await ws.send("__START__")
                print("🎙️ Micrófono ACTIVADO")
                mic_active = True
                stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=CHUNK_SIZE,
                    callback=mic_callback
                )
                stream.start()

        async def stop_mic():
            global stream, mic_active
            if stream is not None:
                stream.stop()
                stream.close()
                stream = None
                mic_active = False
                await ws.send("__END__")
                print("🔇 Micrófono DESACTIVADO")

        # Escucha del teclado → toggle con espacio
        def on_press(key):
            nonlocal ws
            if key == kb.Key.space:
                # Alternar estado
                asyncio.run_coroutine_threadsafe(toggle_mic(), main_loop)
            elif key == kb.Key.esc:
                print("🛑 Saliendo...")
                return False  # detiene el listener

        async def toggle_mic():
            if mic_active:
                await stop_mic()
            else:
                await start_mic()

        listener = kb.Listener(on_press=on_press)
        listener.start()

        print("✅ Pulsa ESPACIO para alternar micrófono ON/OFF (ESC para salir)")

        try:
            while listener.running:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Programa terminado")

        # Si estaba activo, lo detenemos
        if stream is not None:
            await stop_mic()

        await recv_task

if __name__ == "__main__":
    asyncio.run(websocket_client())

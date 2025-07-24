import asyncio
import websockets
import json
import time

# URL del servidor TTS WebSocket
URI = "ws://localhost:8765"

# Frases con diferentes longitudes para probar
frases = [
    {
        "text": (
            "Hoy desperté con una enorme sonrisa. "
            "El sol brillaba con fuerza y sentí que todo era posible. "
            "Preparé mi desayuno favorito y puse mi canción preferida a todo volumen, bailando sin preocupaciones."
        ),
        "emotion": "alegre",
    },
    {
        "text": (
            "Después de un rato, me detuve a mirar por la ventana. "
            "Me di cuenta de que, aunque era un buen día, había muchas cosas que aún no entendía de la vida. "
            "Recordé que a veces el destino nos lleva por caminos inesperados, y eso me hizo reflexionar en silencio."
        ),
        "emotion": "neutral",
    },
    {
        "text": (
            "Entonces llegó a mi mente aquel momento doloroso. "
            "Hace un año, perdí a alguien que amaba profundamente, y desde entonces hay un vacío que nada puede llenar. "
            "Una tristeza silenciosa me envolvió, como una sombra que no se va."
        ),
        "emotion": "triste",
    },
    {
        "text": (
            "Pero justo en ese instante, sonó mi teléfono. "
            "Era un amigo que no veía hace años y me invitó a salir. "
            "De pronto mi corazón volvió a llenarse de alegría, como si el universo me regalara un pequeño milagro."
        ),
        "emotion": "alegre",
    },
    {
        "text": (
            "Mientras caminaba hacia el encuentro, pensé en todo lo que había pasado en este tiempo. "
            "La vida es un equilibrio extraño entre momentos de luz y de sombra. "
            "Respiré hondo, sintiéndome en paz, aunque consciente de que nada es permanente."
        ),
        "emotion": "neutral",
    },
    {
        "text": (
            "Al llegar al lugar, vi una foto en la pared que me recordó de nuevo esa pérdida. "
            "Fue como un golpe suave pero inevitable. "
            "Sentí una lágrima caer y comprendí que la tristeza siempre encuentra un camino para volver, aunque sepamos que debemos seguir adelante."
            "a.a"
            "a,a"
        ),
        "emotion": "triste",
    }
]


async def benchmark():
    async with websockets.connect(URI) as ws:
        # Esperar mensaje inicial del servidor
        ready = await ws.recv()
        print("✅ Servidor respondió:", ready)

        for idx, item in enumerate(frases, 1):
            texto = item["text"]
            emocion = item["emotion"]

            # Pausa para no saturar el servidor entre pruebas
            #print("\n⏳ Esperando 5 segundos antes de la siguiente prueba...")
            #await asyncio.sleep(5)

            print(f"\n▶️ Prueba {idx}: {len(texto.split())} palabras | Emoción: {emocion}")
            print(f"📝 Texto: {texto}")

            # Enviar mensaje al servidor con texto + emoción
            await ws.send(
                json.dumps(
                    {
                        "cmd": "say",
                        "text": texto,
                        "emotion": emocion  # Si el servidor no usa emociones, lo ignora
                    }
                )
            )

            start_send = time.time()
            t_hablando = None
            t_parado = None

            # Escuchar estados hasta que termine
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                estado = data.get("estado")

                if estado == "hablando":
                    t_hablando = time.time()
                    print(f"🎙️ Servidor empezó a hablar a los {t_hablando - start_send:.2f}s")

                elif estado == "parado":
                    t_parado = time.time()
                    print(f"⏹ Servidor terminó a los {t_parado - start_send:.2f}s")
                    break

            # Análisis del rendimiento
            if t_hablando and t_parado:
                synthesis_latency = t_hablando - start_send
                playback_time = t_parado - t_hablando
                total_time = t_parado - start_send

                print(f"⏱ Latencia de síntesis (envío→hablando): {synthesis_latency:.2f}s")
                print(f"🎧 Duración aproximada del audio (hablando→parado): {playback_time:.2f}s")
                print(f"🌐 Tiempo total percibido (envío→parado): {total_time:.2f}s")

        print("\n✅ Benchmark finalizado.")

# Ejecutar benchmark
asyncio.run(benchmark())

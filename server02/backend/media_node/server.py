from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

app = FastAPI()

# Middleware CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

relay = MediaRelay()  # <-- relay para reutilizar tracks

class Offer(BaseModel):
    sdp: str
    type: str

@app.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection()
    print("📡 Nueva conexión WebRTC")

    @pc.on("track")
    def on_track(track):
        print(f"🎥 Track recibido: {track.kind}")

        # ECO: reenviar el mismo track
        pc.addTrack(relay.subscribe(track))

        @track.on("ended")
        async def on_ended():
            print(f"⛔ Track terminado: {track.kind}")

    # Recibimos la oferta
    await pc.setRemoteDescription(RTCSessionDescription(offer.sdp, offer.type))
    
    # Creamos la respuesta
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

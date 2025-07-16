"use client"
import { Camera, CameraOff, Volume2 } from "lucide-react"

type Props = {
  isCameraActive: boolean
  isCapturing: boolean
  isAudioPlaying: boolean
}

export default function CameraPreview({ isCameraActive, isCapturing, isAudioPlaying }: Props) {
  return (
    <div className="relative">
      <div className="relative w-64 h-64 rounded-full overflow-hidden border-4 border-gray-600/50 bg-gray-800">
        {isCameraActive ? (
          <div className="w-full h-full bg-gradient-to-br from-blue-900 via-purple-900 to-pink-900 flex items-center justify-center">
            <div className="text-white/60 text-center">
              <Camera className="w-12 h-12 mx-auto mb-2" />
              <p className="text-sm">Vista previa de cámara</p>
            </div>
          </div>
        ) : (
          <div className="w-full h-full bg-gray-900 flex items-center justify-center">
            <div className="text-gray-500 text-center">
              <CameraOff className="w-12 h-12 mx-auto mb-2" />
              <p className="text-sm">Cámara desactivada</p>
            </div>
          </div>
        )}
        {isCapturing && <div className="absolute inset-0 bg-white animate-ping opacity-80 rounded-full" />}
      </div>

      {isAudioPlaying && (
        <>
          <div className="absolute inset-0 w-64 h-64 rounded-full border-2 border-purple-500/40 animate-ping" style={{ animationDuration: "1.5s" }} />
          <div className="absolute inset-4 w-56 h-56 rounded-full border-2 border-pink-500/50 animate-ping" style={{ animationDuration: "1.2s", animationDelay: "0.2s" }} />
          <div className="absolute inset-8 w-48 h-48 rounded-full border-2 border-blue-400/60 animate-ping" style={{ animationDuration: "1s", animationDelay: "0.4s" }} />
        </>
      )}

      {isAudioPlaying && (
        <div className="absolute -top-4 -right-4 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center animate-pulse">
          <Volume2 className="w-4 h-4 text-white" />
        </div>
      )}
    </div>
  )
}

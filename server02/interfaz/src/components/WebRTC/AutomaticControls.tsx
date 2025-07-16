"use client"
import { Mic, MicOff, Camera, CameraOff } from "lucide-react"

type Props = {
  isMicActive: boolean
  isCameraActive: boolean
  toggleMic: () => void
  toggleCamera: () => void
}

export default function AutomaticControls({
  isMicActive,
  isCameraActive,
  toggleMic,
  toggleCamera,
}: Props) {
  return (
    <div className="flex items-center justify-center space-x-8">
      {/* Micrófono */}
      <button
        onClick={toggleMic}
        className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200 ${
          isMicActive
            ? "bg-green-600/80 hover:bg-green-500/80 shadow-lg shadow-green-500/30"
            : "bg-red-600/80 hover:bg-red-500/80 shadow-lg shadow-red-500/30"
        }`}
      >
        {isMicActive ? (
          <Mic className="w-6 h-6 text-white" />
        ) : (
          <MicOff className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Cámara */}
      <button
        onClick={toggleCamera}
        className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200 ${
          isCameraActive
            ? "bg-blue-600/80 hover:bg-blue-500/80 shadow-lg shadow-blue-500/30"
            : "bg-gray-600/80 hover:bg-gray-500/80 shadow-lg shadow-gray-500/30"
        }`}
      >
        {isCameraActive ? (
          <Camera className="w-6 h-6 text-white" />
        ) : (
          <CameraOff className="w-6 h-6 text-white" />
        )}
      </button>
    </div>
  )
}

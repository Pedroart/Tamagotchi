"use client"
import { Camera, CameraOff, Mic, MicOff } from "lucide-react"

type Props = {
  isCameraActive: boolean
  isMicActive: boolean
  mode: "manual" | "automatic"
  isPushToTalk: boolean
}

export default function StatusIndicators({
  isCameraActive,
  isMicActive,
  mode,
  isPushToTalk,
}: Props) {
  const micEnabled = isMicActive && (mode === "automatic" || isPushToTalk)

  return (
    <div className="flex items-center space-x-6">
      {/* Indicador de cámara */}
      <div
        className={`flex items-center space-x-2 px-3 py-1 rounded-full ${
          isCameraActive
            ? "bg-green-900/30 border border-green-500/30"
            : "bg-red-900/30 border border-red-500/30"
        }`}
      >
        {isCameraActive ? (
          <Camera className="w-4 h-4 text-green-400" />
        ) : (
          <CameraOff className="w-4 h-4 text-red-400" />
        )}
        <span
          className={`text-xs ${
            isCameraActive ? "text-green-400" : "text-red-400"
          }`}
        >
          Cámara
        </span>
      </div>

      {/* Indicador de micrófono */}
      <div
        className={`flex items-center space-x-2 px-3 py-1 rounded-full ${
          micEnabled
            ? "bg-green-900/30 border border-green-500/30"
            : "bg-red-900/30 border border-red-500/30"
        }`}
      >
        {micEnabled ? (
          <Mic className="w-4 h-4 text-green-400" />
        ) : (
          <MicOff className="w-4 h-4 text-red-400" />
        )}
        <span
          className={`text-xs ${
            micEnabled ? "text-green-400" : "text-red-400"
          }`}
        >
          Micrófono
        </span>
      </div>
    </div>
  )
}

"use client"
import { Mic, Circle } from "lucide-react"

type Props = {
  isPushToTalk: boolean
  handlePushToTalk: (pressed: boolean) => void
  handleTakePhoto: () => void
  isCameraActive: boolean
}

export default function ManualControls({
  isPushToTalk,
  handlePushToTalk,
  handleTakePhoto,
  isCameraActive,
}: Props) {
  return (
    <div className="flex items-center justify-center space-x-8">
      {/* Botón Push to Talk */}
      <button
        onMouseDown={() => handlePushToTalk(true)}
        onMouseUp={() => handlePushToTalk(false)}
        onTouchStart={() => handlePushToTalk(true)}
        onTouchEnd={() => handlePushToTalk(false)}
        className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-200 ${
          isPushToTalk
            ? "bg-gradient-to-r from-green-600 via-green-500 to-green-400 shadow-lg shadow-green-500/30 scale-110"
            : "bg-gray-800/60 backdrop-blur-sm border border-gray-600/30 hover:bg-gray-700/60"
        }`}
      >
        <Mic
          className={`w-8 h-8 ${
            isPushToTalk ? "text-white" : "text-gray-300"
          }`}
        />
      </button>

      {/* Botón para tomar foto */}
      <button
        onClick={handleTakePhoto}
        disabled={!isCameraActive}
        className={`w-16 h-16 rounded-full flex items-center justify-center transition-all duration-200 ${
          isCameraActive
            ? "bg-gradient-to-r from-blue-600 via-purple-500 to-pink-500 hover:scale-105 shadow-lg shadow-purple-500/30"
            : "bg-gray-800/40 border border-gray-700/30"
        }`}
      >
        <Circle
          className={`w-6 h-6 ${
            isCameraActive ? "text-white" : "text-gray-600"
          }`}
        />
      </button>
    </div>
  )
}

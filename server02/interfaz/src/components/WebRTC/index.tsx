"use client"
import { useState } from "react"
import { useAudioSimulation } from "./useAudioSimulation"
import ModeSelector from "./ModeSelector"
import CameraPreview from "./CameraPreview"
import StatusIndicators from "./StatusIndicators"
import ManualControls from "./ManualControls"
import AutomaticControls from "./AutomaticControls"

export default function VoiceCameraSystem() {
  const [mode, setMode] = useState<"manual" | "automatic">("manual")
  const [isCameraActive, setIsCameraActive] = useState(true)
  const [isMicActive, setIsMicActive] = useState(true)
  const [isPushToTalk, setIsPushToTalk] = useState(false)
  const [isCapturing, setIsCapturing] = useState(false)

  const isAudioPlaying = useAudioSimulation()

  const handlePushToTalk = (pressed: boolean) => setIsPushToTalk(pressed)

  const handleTakePhoto = () => {
    setIsCapturing(true)
    setTimeout(() => setIsCapturing(false), 300)
  }

  const toggleCamera = () => setIsCameraActive(!isCameraActive)
  const toggleMic = () => setIsMicActive(!isMicActive)

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex flex-col items-center justify-center px-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-b from-purple-900/10 via-transparent to-blue-900/10" />

      <ModeSelector mode={mode} setMode={setMode} />

      <div className="flex flex-col items-center justify-center flex-1 space-y-12 z-10">
        <CameraPreview isCameraActive={isCameraActive} isCapturing={isCapturing} isAudioPlaying={isAudioPlaying} />
        <StatusIndicators
          isCameraActive={isCameraActive}
          isMicActive={isMicActive}
          mode={mode}
          isPushToTalk={isPushToTalk}
        />
      </div>

      <div className="pb-12 z-10">
        {mode === "manual" ? (
          <ManualControls
            isPushToTalk={isPushToTalk}
            handlePushToTalk={handlePushToTalk}
            handleTakePhoto={handleTakePhoto}
            isCameraActive={isCameraActive}
          />
        ) : (
          <AutomaticControls
            isMicActive={isMicActive}
            isCameraActive={isCameraActive}
            toggleMic={toggleMic}
            toggleCamera={toggleCamera}
          />
        )}

        <div className="mt-6 text-center">
          <p className="text-gray-400 text-sm">
            {mode === "manual"
              ? "Mantén presionado para hablar • Toca el círculo para capturar"
              : "Controles independientes de micrófono y cámara"}
          </p>
        </div>
      </div>
    </div>
  )
}

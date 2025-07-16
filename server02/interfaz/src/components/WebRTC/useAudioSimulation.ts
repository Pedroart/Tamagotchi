"use client"
import { useEffect, useState } from "react"

export function useAudioSimulation() {
  const [isAudioPlaying, setIsAudioPlaying] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      if (Math.random() > 0.7) {
        setIsAudioPlaying(true)
        setTimeout(() => setIsAudioPlaying(false), 2000)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [])

  return isAudioPlaying
}

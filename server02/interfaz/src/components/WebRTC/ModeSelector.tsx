"use client"

type Props = {
  mode: "manual" | "automatic"
  setMode: (mode: "manual" | "automatic") => void
}

export default function ModeSelector({ mode, setMode }: Props) {
  return (
    <div className="absolute top-12 left-1/2 transform -translate-x-1/2 z-20">
      <div className="flex bg-gray-800/60 backdrop-blur-sm rounded-full p-1 border border-gray-600/30">
        <button
          onClick={() => setMode("manual")}
          className={`px-6 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
            mode === "manual"
              ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Manual
        </button>
        <button
          onClick={() => setMode("automatic")}
          className={`px-6 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
            mode === "automatic"
              ? "bg-purple-600 text-white shadow-lg shadow-purple-500/30"
              : "text-gray-400 hover:text-white"
          }`}
        >
          Automático
        </button>
      </div>
    </div>
  )
}

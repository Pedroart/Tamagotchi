// src/Live2DCanvas.tsx
import React, { useEffect, useRef, useState } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display-lipsyncpatch'
import { Ticker } from 'pixi.js'

// Exponer PIXI global (requerido por el plugin)
declare global { interface Window { PIXI: typeof PIXI } }
window.PIXI = PIXI

// Ajusta a tu modelo
const MODEL_JSON_PATH = '/models/Natori/Natori.model3.json'

// Utils
const basename = (p?: string) => (p ? p.split('/').pop()?.replace(/\.(exp3|json)$/i, '') ?? '' : '')
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

// —— Tipos de acciones que el server envía por WS ——
type QueueAction =
  | { type: 'expression'; index?: number; name?: string }
  | { type: 'motion'; group: string; index?: number; priority?: number }
  | { type: 'audio'; src: string; crossOrigin?: string; waitEnd?: boolean }
  | { type: 'stopAll' }
  | { type: 'clearQueue' }
  | { type: 'ping' }
  | { type: 'sequence'; items: QueueAction[] }
  | { type: 'view.set'; x?: number; y?: number; scale?: number; rotation?: number; anchorX?: number; anchorY?: number }
  | { type: 'view.panBy'; dx?: number; dy?: number }
  | { type: 'view.zoomBy'; factor: number }
  | { type: 'view.center' }
  | { type: 'view.fit'; mode: 'contain' | 'cover' | 'width' | 'height' }

const isQueueAction = (a: any): a is QueueAction => a && typeof a.type === 'string'

// —— Cola FIFO ——
class ActionQueue {
  private q: QueueAction[] = []
  private running = false
  constructor(private exec: (a: QueueAction) => Promise<void>) {}
  enqueue(a: QueueAction | QueueAction[]) { Array.isArray(a) ? this.q.push(...a) : this.q.push(a); this.kick() }
  clear() { this.q = [] }
  private async kick() {
    if (this.running) return
    this.running = true
    try { while (this.q.length) await this.exec(this.q.shift()!) }
    finally { this.running = false }
  }
}

export default function Live2DCanvas() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const appRef = useRef<PIXI.Application | null>(null)
  const modelRef = useRef<any>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const [awaiting, setAwaiting] = useState(false)
  const awaitingRef = useRef(false)
  useEffect(() => { awaitingRef.current = awaiting }, [awaiting])

  const [listening, setListening] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [wsState, setWsState] = useState<'disconnected'|'connecting'|'connected'>('disconnected')

  // ⭐ Nuevo: panel flotante ocultable
  const [panelOpen, setPanelOpen] = useState(true)

  // --- UI de expresiones & motions
  const [expressions, setExpressions] = useState<{ index: number; label: string }[]>([])
  const [currentExprIndex, setCurrentExprIndex] = useState<number>(0)
  const [motions, setMotions] = useState<Record<string, any[]>>({})
  const [priority, setPriority] = useState<number>(3) // 0..3

  const expressionsRef = useRef<{ index: number; label: string }[]>([])
  useEffect(() => { expressionsRef.current = expressions }, [expressions])

  // Init PIXI + modelo
  useEffect(() => {
    if (!containerRef.current) return

    // ⭐ El canvas ocupa todo el contenedor (que será full-viewport)
    const app = new PIXI.Application({ resizeTo: containerRef.current, backgroundAlpha: 0, antialias: true })
    appRef.current = app
    containerRef.current.appendChild(app.view as HTMLCanvasElement)

    let disposed = false

    ;(async () => {
      try {
        Live2DModel.registerTicker?.(Ticker)
        const model = await Live2DModel.from(MODEL_JSON_PATH, { autoHitTest: true, autoFocus: true, ticker: Ticker.shared })
        if (disposed) return
        modelRef.current = model
        app.stage.addChild(model)
        centerAndScale(app, model) // ⭐ centrado inicial

        // Expresiones
        const settings: any = model.internalModel?.settings
        const rawExpr: any[] = settings?.expressions || settings?.FileReferences?.Expressions || []
        const mappedExpr = rawExpr.map((ex: any, i: number) => ({
          index: i,
          label: ex?.name || ex?.Name || basename(ex?.File || ex?.Path) || `expr_${i}`,
        }))
        setExpressions(mappedExpr)
        if (mappedExpr.length > 0) setCurrentExprIndex(mappedExpr[0].index)

        // Motions
        const motionDefs = model.internalModel?.motionManager?.definitions || {}
        setMotions(motionDefs)

        setLoading(false)
      } catch (e: any) {
        console.error(e)
        setError(String(e?.message || e))
        setLoading(false)
      }
    })()

    // ⭐ Resize robusto: se centra y escala ante cambios del contenedor
    const onResize = () => { if (!appRef.current || !modelRef.current) return; centerAndScale(appRef.current, modelRef.current) }
    window.addEventListener('resize', onResize)

    // ⭐ ResizeObserver por si el contenedor cambia de tamaño por CSS/layout
    const ro = new ResizeObserver(() => onResize())
    if (containerRef.current) ro.observe(containerRef.current)

    return () => {
      window.removeEventListener('resize', onResize)
      ro.disconnect()
      disposed = true
      try { appRef.current?.destroy(true, { children: true }) } catch {}
      appRef.current = null
      modelRef.current = null
    }
  }, [])

  // Ejecutores usan refs por cierre (no globals)
  const executeAction = async (a: QueueAction) => {
    switch (a.type) {
      case 'expression': return doExpression(modelRef.current, a, expressionsRef.current)
      case 'motion': return doMotion(modelRef.current, a)
      case 'audio': return doAudio(modelRef.current, a)
      case 'ping': return sleep(50)
      case 'sequence': for (const it of a.items) await executeAction(it); return
      case 'view.set': return doViewSet(modelRef.current, appRef.current, a)
      case 'view.panBy': return doViewPanBy(modelRef.current, a)
      case 'view.zoomBy': return doViewZoomBy(modelRef.current, appRef.current, a)
      case 'view.center': return doViewCenter(modelRef.current, appRef.current)
      case 'view.fit': return doViewFit(modelRef.current, appRef.current, a)
      case 'stopAll':
      case 'clearQueue':
        // manejados desde onmessage
        return
    }
  }

  const queueRef = useRef<ActionQueue>()
  if (!queueRef.current) queueRef.current = new ActionQueue(executeAction)

  // WebSocket + cola
  useEffect(() => {
    let ws: WebSocket | null = null
    let disposed = false
    let t: any = null
    const url = `ws://localhost:${import.meta.env.VITE_WS_PORT ?? 8080}`

    const connect = () => {
      if (disposed) return
      setWsState('connecting')
      try { ws = new WebSocket(url) } catch { schedule(); return }

      wsRef.current = ws

      ws.onopen = () => {
        setWsState('connected')
        ws?.send(JSON.stringify({ kind: 'hello', from: 'live2d-client' }))
      }

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(String(ev.data))
          if (msg?.kind === 'action' && isQueueAction(msg.payload)) {
            if (awaitingRef.current) {
              setAwaiting(false)
              awaitingRef.current = false
            }
            const a = msg.payload as QueueAction
            if (a.type === 'clearQueue') return queueRef.current?.clear()
            queueRef.current?.enqueue(a.type === 'sequence' ? a.items : a)
          }
        } catch {}
      }

      const onCloseErr = () => {
        setWsState('disconnected')
        if (wsRef.current === ws) wsRef.current = null
        schedule()
      }
      ws.onclose = onCloseErr
      ws.onerror = onCloseErr
    }

    const schedule = () => { if (disposed || t) return; t = setTimeout(() => { t = null; connect() }, 1000) }

    connect()
    return () => {
      disposed = true
      try { ws?.close() } catch {}
      if (wsRef.current === ws) wsRef.current = null
      if (t) clearTimeout(t)
    }
  }, [])

  useEffect(() => {
    const isEditable = (el: Element | null) => {
      if (!el) return false
      const tag = (el as HTMLElement).tagName
      const ce  = (el as HTMLElement).getAttribute?.('contenteditable')
      return tag === 'INPUT' || tag === 'TEXTAREA' || ce === '' || ce === 'true'
    }

    const stopAllNow = () => {
      queueRef.current?.clear()
      try { modelRef.current?.stopSpeaking?.() } catch {}
      try { modelRef.current?.stopMotions?.() } catch {}
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.code === 'Space' || e.key === ' ') && !e.repeat && !isEditable(e.target as Element)) {
        e.preventDefault()
        const ws = wsRef.current
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send('flag')
          stopAllNow()
          setAwaiting(true)
          setListening(v => !v)
        }
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // --- Handlers UI locales
  const applyExpression = () => {
    const idx = currentExprIndex
    if (typeof idx === 'number') {
      queueRef.current?.enqueue({ type: 'expression', index: idx })
    }
  }

  const playMotion = (group: string, index = 0) => {
    queueRef.current?.enqueue({ type: 'motion', group, index, priority })
  }

  // ⭐ Layout: contenedor 100% viewport, panel flotante, botón toggle
  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        inset: 0,
        background: listening ? '#0b5cff' : '#111',
        overflow: 'hidden'
      }}
    >
      {/* Botón para mostrar/ocultar panel */}
      <button
        onClick={() => setPanelOpen(v => !v)}
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          zIndex: 20,
          background: '#1e1e1e',
          color: '#eee',
          border: '1px solid #444',
          borderRadius: 8,
          padding: '8px 10px',
          cursor: 'pointer',
          opacity: 0.95
        }}
        title={panelOpen ? 'Ocultar panel' : 'Mostrar panel'}
      >
        {panelOpen ? '☰ Panel' : '☰ Panel'}
      </button>

      {/* Panel flotante */}
      {panelOpen && (
        <aside
          style={{
            position: 'absolute',
            top: 56,
            left: 12,
            width: 320,
            maxHeight: 'calc(100vh - 68px)',
            padding: 12,
            border: '1px solid #333',
            borderRadius: 12,
            background: 'rgba(20,20,20,0.95)',
            color: '#ddd',
            overflow: 'auto',
            zIndex: 15,
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            backdropFilter: 'blur(3px)'
          }}
        >
          <h3 style={{ marginTop: 0 }}>Live2D WS</h3>
          {loading && <p>Cargando modelo…</p>}
          {error && <p style={{ color: 'tomato' }}>Error: {error}</p>}
          <p>WS: <b style={{ color: wsState === 'connected' ? '#6f6' : '#fc6' }}>{wsState}</b></p>

          {/* Expresiones */}
          <section style={{ marginTop: 12 }}>
            <h4 style={{ margin: '8px 0' }}>Expresiones</h4>
            {expressions.length === 0 ? (
              <div style={{ fontSize: 12, color: '#aaa' }}>
                No se detectaron expresiones. Verifica que existan *.exp3.json* y que estén referenciadas en el <code>.model3.json</code>.
              </div>
            ) : (
              <>
                <select
                  style={{ width: '100%' }}
                  value={currentExprIndex}
                  onChange={(e) => setCurrentExprIndex(parseInt(e.target.value))}
                >
                  {expressions.map((ex) => (
                    <option key={`expr-${ex.index}`} value={ex.index}>
                      {ex.label}
                    </option>
                  ))}
                </select>
                <button style={{ marginTop: 6 }} onClick={applyExpression}>Aplicar</button>
              </>
            )}
          </section>

          {/* Motions */}
          <section style={{ marginTop: 16 }}>
            <h4 style={{ margin: '8px 0' }}>Motions</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <label>Prioridad: {priority}</label>
              <input
                type="range"
                min={0}
                max={3}
                step={1}
                value={priority}
                onChange={(e) => setPriority(parseInt(e.target.value))}
              />
            </div>

            <div style={{ maxHeight: 320, overflow: 'auto', border: '1px solid #444', padding: 8, marginTop: 8 }}>
              {Object.keys(motions).length === 0 && <p style={{ color: '#aaa' }}>Sin motions detectados.</p>}
              {Object.entries(motions).map(([group, list]) => (
                <div key={`group-${group}`} style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>{group}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {list.map((m, i) => (
                      <button key={`btn-${group}-${i}`} onClick={() => playMotion(group, i)}>
                        {basename(m?.File || '') || i}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <small style={{ color: '#aaa', display: 'block', marginTop: 12 }}>
            También puedes disparar acciones por WebSocket (expresión, motion, audio y vista).
          </small>
        </aside>
      )}
    </div>
  )
}

// —— Ejecutores ——
async function doExpression(
  model: any,
  { index, name }: { index?: number; name?: string },
  exprList: { index: number; label: string }[] = []
) {
  if (!model) return
  try {
    let i = -1
    if (name != null) {
      i = exprList.findIndex((e) => e.label.toLowerCase() === String(name).toLowerCase())
    } else if (typeof index === 'number') {
      i = index
    }
    if (i >= 0) model.expression(i)
  } catch (e) {
    console.warn('expression', e)
  }
  await sleep(120)
}

async function doMotion(model: any, { group, index = 0, priority = 3 }: { group: string; index?: number; priority?: number }) {
  if (!model) return
  try {
    const defs = model.internalModel?.motionManager?.definitions || {}
    const def = Array.isArray(defs[group]) ? defs[group][index] : null
    let ms = 2000
    const d = Number(def?.Duration)
    if (!Number.isNaN(d) && d > 0) ms = Math.round(d * 1000)
    model.motion(group, index, priority)
    await sleep(ms)
  } catch (e) { console.warn('motion', e) }
}

async function doAudio(model: any, {
  src, volume = 1, expression, resetExpression = true,
  crossOrigin = 'anonymous', waitEnd = true,
}: {
  src: string; volume?: number; expression?: number|string;
  resetExpression?: boolean; crossOrigin?: string; waitEnd?: boolean;
}) {
  if (!model || !src) return
  const opts: any = { volume, crossOrigin }
  if (expression !== undefined) opts.expression = expression
  if (resetExpression !== undefined) opts.resetExpression = resetExpression

  let done: Promise<void> | null = null
  if (waitEnd) {
    done = new Promise<void>(res => {
      opts.onFinish = () => res()
      opts.onError  = () => res()
    })
  }
  model.speak(src, opts)
  if (done) await done
}

// —— Control de vista ——
async function doViewSet(model: any, app: PIXI.Application | null, a: { x?: number; y?: number; scale?: number; rotation?: number; anchorX?: number; anchorY?: number }) {
  if (!model) return
  if (typeof a.anchorX === 'number' || typeof a.anchorY === 'number') model.anchor?.set?.(a.anchorX ?? model.anchor.x, a.anchorY ?? model.anchor.y)
  if (typeof a.x === 'number' || typeof a.y === 'number') model.position?.set?.(a.x ?? model.x, a.y ?? model.y)
  if (typeof a.scale === 'number') model.scale?.set?.(a.scale)
  if (typeof a.rotation === 'number') model.rotation = a.rotation
  await sleep(10)
}

async function doViewPanBy(model: any, { dx = 0, dy = 0 }: { dx?: number; dy?: number }) {
  if (!model) return
  model.position?.set?.(model.x + dx, model.y + dy)
  await sleep(10)
}

async function doViewZoomBy(model: any, app: PIXI.Application | null, { factor }: { factor: number }) {
  if (!model) return
  const next = Math.max(0.01, (model.scale?.x ?? 1) * factor)
  model.scale?.set?.(next)
  await sleep(10)
}

async function doViewCenter(model: any, app: PIXI.Application | null) {
  if (!model || !app) return
  // ⭐ Centrado exacto
  model.anchor?.set?.(0.5, 0.5)
  model.position?.set?.(app.renderer.width * 0.5, app.renderer.height * 0.5)
  await sleep(10)
}

async function doViewFit(model: any, app: PIXI.Application | null, { mode }: { mode: 'contain' | 'cover' | 'width' | 'height' }) {
  if (!model || !app) return
  const W = app.renderer.width, H = app.renderer.height
  // ⭐ Ajuste simple pero responsivo, prioriza contener
  const k = 0.35 // “tamaño” relativo del personaje; súbelo/bájalo a gusto
  let s = (mode === 'cover' ? Math.max(W, H) : Math.min(W, H)) / 1000 * k
  if (mode === 'width')  s = (W / 1000) * k
  if (mode === 'height') s = (H / 1000) * k
  model.anchor?.set?.(0.5, 0.5)
  model.position?.set?.(W * 0.5, H * 0.5)
  model.scale?.set?.(s)
  await sleep(10)
}

// —— Posición/escala inicial ——
function centerAndScale(app: PIXI.Application, model: any) {
  // ⭐ Siempre centrado
  model.anchor?.set?.(0.5, 0.5)
  model.position?.set?.(app.renderer.width * 0.5, app.renderer.height * 0.5)

  // ⭐ Escala responsiva basada en el lado menor (estilo "contain")
  // Ajusta k si quieres el modelo más grande/pequeño por defecto.
  const k = 0.1
  const base = Math.min(app.renderer.width, app.renderer.height) / 1000
  model.scale?.set?.(base * k)
}

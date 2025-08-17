from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional
import math, random

# ====================== Utilidades ======================
def clamp(x, lo=-1.0, hi=1.0): 
    return max(lo, min(hi, x))

def cosine_sim(u, v):
    up = math.sqrt(sum(x*x for x in u))
    vp = math.sqrt(sum(x*x for x in v))
    if up == 0 or vp == 0: 
        return 0.0
    return sum(ux*vx for ux, vx in zip(u, v)) / (up * vp)

def mix_vecs(vecs: List[Tuple[float,float,float]], weights: List[float]):
    """Media ponderada de vectores PAD (para multicanal)."""
    s = sum(weights) if weights else 0.0
    if s == 0: 
        return (0.0, 0.0, 0.0)
    px = sum(v[0]*w for v,w in zip(vecs, weights)) / s
    ax = sum(v[1]*w for v,w in zip(vecs, weights)) / s
    dx = sum(v[2]*w for v,w in zip(vecs, weights)) / s
    return (clamp(px), clamp(ax), clamp(dx))

# ====================== Prototipos ======================
EMOTION_PROTOTYPES: Dict[str, Tuple[float, float, float]] = {
    "alegría":      ( 0.80,  0.60,  0.30),
    "entusiasmo":   ( 0.85,  0.80,  0.40),
    "serenidad":    ( 0.50, -0.20,  0.10),
    "orgullo":      ( 0.60,  0.40,  0.60),
    "ira":          (-0.70,  0.80,  0.50),
    "miedo":        (-0.75,  0.85, -0.60),
    "tristeza":     (-0.70, -0.50, -0.40),
    "asco":         (-0.60,  0.20,  0.10),
    "sorpresa":     ( 0.10,  0.90,  0.00),
    "culpa":        (-0.60,  0.30, -0.50),
    "vergüenza":    (-0.55,  0.40, -0.70),
    "confianza":    ( 0.60,  0.10,  0.20),
}

def label_from_pad(e: Tuple[float,float,float]) -> Tuple[str, float]:
    best_label, best_sim = None, -1.0
    for name, proto in EMOTION_PROTOTYPES.items():
        sim = cosine_sim(e, proto)
        if sim > best_sim:
            best_label, best_sim = name, sim
    return best_label, best_sim

# ====================== Configuración ======================
@dataclass
class PADConfig:
    alpha: float = 0.4        # reacción al estímulo
    decay: float = 0.05       # decaimiento hacia neutro por tick
    ema: float = 0.2          # suavizado temporal (EMA) post-actualización (0=sin suavizado, 1=solo nuevo)
    noise_std: float = 0.03   # desviación estándar del ruido gaussiano
    noise_enabled: bool = True
    # Límites contextuales (por rol/escena). None = sin límite específico.
    min_P: Optional[float] = None
    max_P: Optional[float] = None
    min_A: Optional[float] = None
    max_A: Optional[float] = None
    min_D: Optional[float] = None
    max_D: Optional[float] = None

# ====================== Normalización / Baseline ======================
@dataclass
class Baseline:
    """Baseline individual del usuario/NPC: estado 'en reposo' y ganancia por eje."""
    P0: float = 0.0
    A0: float = 0.0
    D0: float = 0.0
    gain_P: float = 1.0  # escala la contribución del estímulo
    gain_A: float = 1.0
    gain_D: float = 1.0

    def apply(self, vec: Tuple[float,float,float]) -> Tuple[float,float,float]:
        p,a,d = vec
        p = self.P0 + self.gain_P * p
        a = self.A0 + self.gain_A * a
        d = self.D0 + self.gain_D * d
        return (clamp(p), clamp(a), clamp(d))

# ====================== Estado PAD con extensiones ======================
@dataclass
class PADState:
    P: float = 0.0
    A: float = 0.0
    D: float = 0.0
    cfg: PADConfig = field(default_factory=PADConfig)
    baseline: Baseline = field(default_factory=Baseline)

    def as_tuple(self): 
        return (self.P, self.A, self.D)

    def _apply_context_limits(self, p,a,d):
        c = self.cfg
        if c.min_P is not None: p = max(p, c.min_P)
        if c.max_P is not None: p = min(p, c.max_P)
        if c.min_A is not None: a = max(a, c.min_A)
        if c.max_A is not None: a = min(a, c.max_A)
        if c.min_D is not None: d = max(d, c.min_D)
        if c.max_D is not None: d = min(d, c.max_D)
        return p,a,d

    def _add_noise(self, p,a,d):
        if not self.cfg.noise_enabled or self.cfg.noise_std <= 0:
            return p,a,d
        n = self.cfg.noise_std
        p = clamp(p + random.gauss(0, n))
        a = clamp(a + random.gauss(0, n))
        d = clamp(d + random.gauss(0, n))
        return p,a,d

    def update_from_stimulus(self, stimulus_vec: Tuple[float,float,float], intensity: float):
        """Actualiza desde UN estímulo (con baseline, mezcla, decay, suavizado, ruido y límites)."""
        # 1) aplicar intensidad
        sp, sa, sd = (stimulus_vec[0]*intensity, stimulus_vec[1]*intensity, stimulus_vec[2]*intensity)
        # 2) baseline (recalibra contribución)
        sp, sa, sd = self.baseline.apply((sp, sa, sd))
        # 3) reacción
        c = self.cfg
        p = clamp((1 - c.alpha) * self.P + c.alpha * sp)
        a = clamp((1 - c.alpha) * self.A + c.alpha * sa)
        d = clamp((1 - c.alpha) * self.D + c.alpha * sd)
        # 4) decaimiento
        p = clamp((1 - c.decay) * p)
        a = clamp((1 - c.decay) * a)
        d = clamp((1 - c.decay) * d)
        # 5) suavizado temporal (EMA con estado previo)
        p = clamp((1 - c.ema) * self.P + c.ema * p)
        a = clamp((1 - c.ema) * self.A + c.ema * a)
        d = clamp((1 - c.ema) * self.D + c.ema * d)
        # 6) ruido + límites contextuales
        p,a,d = self._add_noise(p,a,d)
        p,a,d = self._apply_context_limits(p,a,d)
        # 7) asignar
        self.P, self.A, self.D = p, a, d
        return self.as_tuple()

    def update_from_multichannel(self, channel_vecs: List[Tuple[float,float,float]], 
                                 confidences: List[float], intensity: float = 1.0):
        """Fusión multicanal: combina primero, luego una sola actualización."""
        fused = mix_vecs(channel_vecs, confidences)
        return self.update_from_stimulus(fused, intensity)

# ====================== Mapeos de ejemplo ======================
STIMULI: Dict[str, Tuple[float, float, float]] = {
    "elogio":      ( 0.7,  0.3,  0.2),
    "ofensa":      (-0.6, 0.6,  0.3),
    "pérdida":     (-0.7,-0.4, -0.5),
    "logro":       ( 0.8,  0.5,  0.4),
    "amenaza":     (-0.8, 0.8, -0.6),
    "sorpresa":    ( 0.1,  0.9,  0.0),
}

def sentiment_to_pad(polarity: float, arousal_hint: float = 0.6) -> Tuple[float, float, float]:
    p = clamp(polarity)
    a = clamp(abs(polarity) * arousal_hint)
    d = clamp(0.3 * polarity)
    return (p, a, d)

# ====================== Política de acciones (ejemplo) ======================
def action_policy(e: Tuple[float,float,float]) -> str:
    P,A,D = e
    # Zonas simples a modo de demo:
    if P > 0.6 and A > 0.6:
        return "acción_expansiva"       # tono enérgico, proactividad
    if P < -0.4 and A > 0.5:
        return "acción_calmante"        # bajar ritmo, empatía
    if P < -0.5 and A < -0.2:
        return "acción_soporte"         # apoyo, contención
    if D > 0.5 and A > 0.4:
        return "acción_firme"           # asumir liderazgo
    return "acción_neutra"

# ====================== Ejemplo de uso ======================
if __name__ == "__main__":
    random.seed(7)  # para reproducibilidad del ruido

    # Configura contexto: agente "asistente servicial" (limitar Dominance y Arousal)
    cfg = PADConfig(
        alpha=0.45, decay=0.04, ema=0.25,
        noise_std=0.025, noise_enabled=True,
        min_D=-0.2, max_D=0.5,   # evita dominancia extrema
        min_A=-0.3, max_A=0.8    # acota activación
    )
    # Baseline individual ligeramente positivo y calmado
    base = Baseline(P0=0.1, A0=-0.05, D0=0.0, gain_P=1.0, gain_A=0.9, gain_D=0.8)
    estado = PADState(cfg=cfg, baseline=base)

    print("Estado inicial:", estado.as_tuple(), "→", label_from_pad(estado.as_tuple()))

    # 1) Llega un elogio (texto) y una sonrisa (visión) con confianzas distintas
    ch_text = STIMULI["elogio"]                # del clasificador de texto
    ch_vision = (0.6, 0.4, 0.1)                # detector facial → PAD aproximado
    e1 = estado.update_from_multichannel([ch_text, ch_vision], confidences=[0.8, 0.6], intensity=0.7)
    print("Tras evento social positivo:", e1, "→", label_from_pad(e1), "|", action_policy(e1))

    # 2) Luego una amenaza (voz alterada + palabras)
    voz = (-0.7, 0.9, -0.5)
    texto = STIMULI["ofensa"]
    e2 = estado.update_from_multichannel([voz, texto], confidences=[0.7, 0.9], intensity=0.9)
    print("Tras amenaza:", e2, "→", label_from_pad(e2), "|", action_policy(e2))

    # 3) Solo sentimiento global muy negativo
    vec = sentiment_to_pad(-0.8)
    e3 = estado.update_from_stimulus(vec, intensity=1.0)
    print("Tras sentimiento -0.8:", e3, "→", label_from_pad(e3), "|", action_policy(e3))

from pathlib import Path

def resolve_assets():
    base = Path(__file__).resolve().parent
    candidates = [
        base / "assets",
        base.parent / "assets",
        base.parent.parent / "assets",
    ]
    for d in candidates:
        if (d / "hero.png").exists() and (d / "hero_index.csv").exists():
            return d
    # si no están ambos, igual devuelve la primera carpeta existente
    for d in candidates:
        if d.exists():
            return d
    d = base / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d

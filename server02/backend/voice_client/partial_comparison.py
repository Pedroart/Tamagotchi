
import re
import difflib
import json

# --- Opcional: solo si usas un LLM ---
try:
    from langchain_openai import ChatOpenAI
    llm_comparador = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    USE_LLM = True
except ImportError:
    llm_comparador = None
    USE_LLM = False


# =========================================================
# 1. Normalización y similitud básica (backup)
# =========================================================

def normalizar(texto: str) -> str:
    """
    Normaliza el texto: minúsculas y elimina caracteres no alfanuméricos básicos
    """
    return re.sub(r'[^a-z0-9áéíóúüñ ]+', '', texto.lower()).strip()

def similitud(p1: str, p2: str) -> float:
    """
    Similaridad basada en SequenceMatcher (difflib)
    Devuelve valor entre 0.0 y 1.0
    """
    return difflib.SequenceMatcher(None, p1, p2).ratio()

def comparar_parciales_difflib(anterior: str, actual: str):
    """
    Compara parcial anterior y actual usando solo difflib.
    Devuelve lista [(palabra_anterior, mejor_match_actual, similitud)].
    """
    anterior_tokens = normalizar(anterior).split()
    actual_tokens   = normalizar(actual).split()

    resultados = []
    for palabra_prev in anterior_tokens:
        mejor_sim = 0.0
        mejor_match = "-"
        for palabra_actual in actual_tokens:
            sim = similitud(palabra_prev, palabra_actual)
            if sim > mejor_sim:
                mejor_sim = sim
                mejor_match = palabra_actual
        resultados.append((palabra_prev, mejor_match, mejor_sim))
    return resultados


# =========================================================
# 2. Comparación semántica usando LLM (si disponible)
# =========================================================

async def comparar_parciales_llm(anterior: str, actual: str) -> dict:
    """
    Usa un LLM para comparar parciales.
    Devuelve un dict con:
      - estables: lista de fragmentos confirmados
      - cambios: lista con pares {"de": "...", "a": "..."}
      - consolidado: mejor versión limpia
    """
    # Si no hay LLM, usamos difflib como fallback
    if not USE_LLM or llm_comparador is None:
        resultados_simple = comparar_parciales_difflib(anterior, actual)
        consolidado_simple = actual if actual else anterior
        return {
            "estables": [p for p, _, sim in resultados_simple if sim > 0.9],
            "cambios": [
                {"de": p, "a": m} for p, m, sim in resultados_simple if sim < 0.9
            ],
            "consolidado": consolidado_simple
        }

    # Si hay LLM disponible → comparación semántica
    prompt = f"""
        Estás procesando parciales de STT (speech-to-text).
        Analiza el cambio entre estos dos parciales:

        Parcial anterior:
        ```
        {anterior}
        ```

        Parcial nuevo:
        ```
        {actual}
        ```

        Tarea:
        1. Lista qué palabras o frases se mantienen estables.
        2. Lista qué se corrigió o cambió (pares de 'de' → 'a').
        3. Devuelve la mejor versión consolidada (corrigiendo errores).

        Responde SOLO en JSON con esta estructura:
        {{
        "estables": ["...","..."],
        "cambios": [{{"de":"...","a":"..."}}],
        "consolidado": "frase consolidada"
        }}
        """
    resp = await llm_comparador.ainvoke(prompt)

    try:
        data = json.loads(resp.content)
    except Exception:
        # Si no se puede parsear, devolvemos un mínimo
        data = {
            "estables": [],
            "cambios": [],
            "consolidado": actual if actual else anterior
        }
    return data


# =========================================================
# 3. Helpers para imprimir resultados
# =========================================================

def imprimir_resultados_difflib(resultados):
    """
    Imprime comparación simple tipo tabla
    """
    print("📊 Evolución vs parcial anterior:")
    for prev_word, new_match, sim in resultados:
        print(f"  {prev_word:<12} → {new_match:<12} ({sim*100:.1f}%)")

def imprimir_resultados_llm(data: dict):
    """
    Imprime de forma legible el JSON del LLM
    """
    print("📊 Evolución semántica (LLM):")
    if data.get("estables"):
        print("✔ Estables:", ", ".join(data.get("estables", [])))
    if data.get("cambios"):
        print("✏️ Cambios detectados:")
        for cambio in data["cambios"]:
            print(f"   {cambio['de']} → {cambio['a']}")
    print("✅ Consolidado:", data.get("consolidado", ""))


# =========================================================
# Ejemplo de uso directo
# =========================================================

if __name__ == "__main__":
    anterior = "Obrigado, quería saber cuánto estaba la poliera que me iba a saber"
    actual   = "Obrigado, quería saber cuánto estaba la pollera que me iba a llevar"

    # Comparación simple
    simple = comparar_parciales_difflib(anterior, actual)
    imprimir_resultados_difflib(simple)

    # Comparación semántica con LLM (si está disponible)
    if USE_LLM:
        import asyncio
        async def test_llm():
            data = await comparar_parciales_llm(anterior, actual)
            imprimir_resultados_llm(data)
        asyncio.run(test_llm())
    else:
        print("ℹ️ LLM no disponible, usando comparación simple.")
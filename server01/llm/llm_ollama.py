import requests
import sys

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

def chat_con_respuesta_corta(pregunta):
    payload = {
        "model": MODEL,
        "system": "Eres un asistente conciso que responde en espaÃ±ol con mÃ¡ximo 2 frases.",
        "messages": [
            {"role": "user", "content": pregunta}
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 32
    }

    response = requests.post(OLLAMA_API_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        contenido = data["choices"][0]["message"]["content"]
        print(f"ðŸ’¬ {contenido.strip()}")
    else:
        print("âŒ Error al contactar con Ollama:")
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python chat_corto.py \"Tu pregunta aquÃ­\"")
    else:
        pregunta = " ".join(sys.argv[1:])
        chat_con_respuesta_corta(pregunta)
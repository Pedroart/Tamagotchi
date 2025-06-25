import requests
import sys

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

def chat_con_respuesta_corta(pregunta):
    payload = {
        "model": MODEL,
        "system": "responde en estaño, en una sola oracion",
        "messages": [
            {"role": "user", "content": pregunta}
        ],
        "temperature": 0.5,
        "top_p": 0.5,
        "max_tokens": 20
    }

    response = requests.post(OLLAMA_API_URL, json=payload)
    if response.status_code == 200:
        data = response.json()
        contenido = data["choices"][0]["message"]["content"]
        print(f"{contenido.strip()}")
    else:
        print("Error al contactar con Ollama:")
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python chat_corto.py \"Tu pregunta aqui"")
    else:
        pregunta = " ".join(sys.argv[1:])
        chat_con_respuesta_corta(pregunta)
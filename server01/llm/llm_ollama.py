import requests
import sys
import json

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"

def chat_con_respuesta_corta(pregunta):
    payload = {
        "model": MODEL,
        "system": "Responde en espaÃ±ol de forma clara y muy breve, en una sola oracion.",
        "messages": [
            {"role": "user", "content": pregunta}
        ],
        "temperature": 0.5,
        "top_p": 0.7,
        "max_tokens": 20,
        "stream": True  # La clave para manejar la respuesta lÃ­nea por lÃ­nea
    }

    with requests.post(OLLAMA_API_URL, json=payload, stream=True) as response:
        if response.status_code == 200:
            print(" ", end="", flush=True)
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8"))
                        content = data.get("message", {}).get("content")
                        if content:
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        continue
            print()  # nueva lÃ­nea final
        else:
            print("Error al contactar con Ollama:")
            print(response.text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python llm_ollama.py Tu pregunta aqui")
    else:
        pregunta = " ".join(sys.argv[1:])
        chat_con_respuesta_corta(pregunta)



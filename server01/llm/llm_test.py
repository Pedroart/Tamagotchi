from llama_cpp import Llama

# Inicializa el modelo
llm = Llama(model_path="models/tinyllama.gguf", n_ctx=256, chat_format="chatml")

# Consulta
response = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "Eres un asistente útil en español."},
        {"role": "user", "content": "¿Qué es la inteligencia artificial?"}
    ],
    max_tokens=100,
    temperature=0.7,
    top_p=0.9
)

print(response["choices"][0]["message"]["content"].strip())
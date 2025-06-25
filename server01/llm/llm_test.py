from llama_cpp import Llama

# Inicializa el modelo
llm = Llama(model_path="models/tinyllama.gguf", n_ctx=256)

# Consulta
res = llm.create_chat_completion(
    messages=[
        {"role": "user", "content": "¿Qué es la inteligencia artificial?"}
    ],
    max_tokens=100
)
print(res['choices'][0]['message']['content'].strip())

from llama_cpp import Llama

# Inicializa el modelo
llm = Llama(model_path="models/tinyllama.gguf", n_ctx=512)

# Consulta
respuesta = llm("¿Qué es la inteligencia artificial?", max_tokens=100)

# Mostrar respuesta
print(respuesta['choices'][0]['text'].strip())

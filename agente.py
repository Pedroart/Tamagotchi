class Agente:
    def procesar(self, texto, imagen):
        if "foto" in texto:
            return "analizar_imagen"
        elif "caminar" in texto:
            return "mover"
        return "esperar"
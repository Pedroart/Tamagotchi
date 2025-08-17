import logging

# Configuración básica con módulo y función
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d → %(message)s",
)

# Crea un logger con el nombre del módulo
logger = logging.getLogger(__name__)

'''
logging.debug("Esto es DEBUG (no se mostrará por defecto)")
logging.info("Inicio del programa")
logging.warning("Ojo, algo podría estar mal")
logging.error("Error encontrado")
logging.critical("Fallo crítico")
'''
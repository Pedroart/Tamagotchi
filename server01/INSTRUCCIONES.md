# RealtimeSTT en CPU — Entorno Virtual e Instalación 🚀

## 1. Crear y activar entorno virtual

Desde la carpeta raíz del proyecto:

```bash
python3 -m venv .venv
```


En Windows (PowerShell/CMD):

```bash
.\.venv\Scripts\activate
```
En Linux/macOS:

```bash
source .venv/bin/activate
```

## 2. Instalar dependencias

Actualiza pip para descargar los componentes

```bash
python -m pip install --upgrade pip
```

# Exportar dependencias

```bash
pip freeze > requirements.txt
```

# Reiniciar Servicio de GIT
```bash
pkill -f serviceStt.py
pkill -f serviceTTS_piper.py
pkill -f test.py

sudo git fetch origin
sudo git reset --hard origin/main
```



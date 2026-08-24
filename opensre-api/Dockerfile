FROM python:3.12-slim

# Instalar dependencias del sistema y Git
RUN apt-get update && apt-get install -y git build-essential && rm -rf /var/lib/apt/lists/*

# Inyectar el binario de uv directamente
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Clonar el repositorio oficial de OpenSRE
RUN git clone https://github.com/Tracer-Cloud/opensre.git

# Instalar las librerías de OpenSRE + FastAPI usando uv (ultra rápido)
RUN uv pip install --system fastapi uvicorn pydantic ./opensre

# Copiar nuestro servidor
COPY main.py .

EXPOSE 8000

CMD ["python", "main.py"]
FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Agregar dependencias para producción escalable
RUN pip install --no-cache-dir \
    redis \
    rq \
    prometheus-client \
    gunicorn \
    pdfplumber \
    pymupdf

# Copiar código fuente
COPY . .

# Crear directorios para datos y logs
RUN mkdir -p /app/data /app/logs

# Variables de entorno por defecto
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV DATABASE_URL=/app/data/empresa.db

# Exponer puerto
EXPOSE 8000

# Comando por defecto (puede ser sobrescrito en docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

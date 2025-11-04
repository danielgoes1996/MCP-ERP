# ============================================
# STAGE 1: Builder - Instala dependencias
# ============================================
FROM python:3.11-slim as builder

# Establecer variables de entorno para optimizar pip
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema necesarias para compilar
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de requirements
COPY requirements-prod.txt .

# Instalar dependencias en un directorio separado
RUN pip install --user --no-cache-dir -r requirements-prod.txt

# ============================================
# STAGE 2: Runtime - Imagen final optimizada
# ============================================
FROM python:3.11-slim

# Crear usuario no-root para seguridad
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instalar solo las dependencias de runtime necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH=/home/appuser/.local/bin:$PATH

# Establecer directorio de trabajo
WORKDIR /app

# Copiar dependencias instaladas desde el builder
COPY --from=builder /root/.local /home/appuser/.local

# Copiar código fuente
COPY --chown=appuser:appuser . .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/uploads /app/data && \
    chown -R appuser:appuser /app

# Cambiar a usuario no-root
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Exponer puerto
EXPOSE 8000

# Comando por defecto usando uvicorn con workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--log-level", "info"]

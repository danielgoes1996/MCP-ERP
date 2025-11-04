# 🐳 Docker Setup - MCP Server

## 📋 Índice

1. [Descripción General](#descripción-general)
2. [Requisitos Previos](#requisitos-previos)
3. [Inicio Rápido](#inicio-rápido)
4. [Arquitectura de Contenedores](#arquitectura-de-contenedores)
5. [Configuración](#configuración)
6. [Comandos Útiles](#comandos-útiles)
7. [Troubleshooting](#troubleshooting)
8. [Migración desde SQLite](#migración-desde-sqlite)
9. [Producción](#producción)

---

## 🎯 Descripción General

Este setup Docker proporciona un entorno completamente aislado y reproducible para el MCP Server, incluyendo:

- ✅ **FastAPI Application** - Backend con multi-stage build optimizado
- ✅ **PostgreSQL 16** - Base de datos productiva y escalable
- ✅ **Redis 7** - Cache y task queue
- ✅ **PgAdmin 4** - Interfaz web para gestión de PostgreSQL

### 🏗️ Características Principales

- **Multi-stage Build**: Imagen Docker optimizada (~200MB vs ~1GB)
- **Health Checks**: Monitoreo automático de servicios
- **Non-root User**: Seguridad mejorada en contenedores
- **Volume Persistence**: Datos preservados entre reinicios
- **Auto-restart**: Servicios se reinician automáticamente
- **Network Isolation**: Red Docker privada para comunicación entre servicios

---

## 📦 Requisitos Previos

### Instalar Docker

```bash
# macOS
brew install docker docker-compose

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Verificar instalación
docker --version
docker-compose --version
```

### Recursos Mínimos Recomendados

- **RAM**: 4GB (8GB recomendado)
- **Disk**: 10GB libres
- **CPU**: 2 cores (4 cores recomendado)

---

## 🚀 Inicio Rápido

### Opción 1: Script Automático (Recomendado)

```bash
# 1. Clonar/navegar al proyecto
cd mcp-server

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 3. Iniciar todo el stack
./docker-start.sh
```

### Opción 2: Manual

```bash
# 1. Configurar .env
cp .env.example .env
nano .env  # Editar configuración

# 2. Construir y iniciar servicios
docker-compose up -d

# 3. Ver logs
docker-compose logs -f
```

### ✅ Verificar que todo funciona

```bash
# Health check de todos los servicios
docker-compose ps

# Debería mostrar:
# mcp-postgres  ... Up (healthy)
# mcp-api       ... Up (healthy)
# mcp-redis     ... Up (healthy)
# mcp-pgadmin   ... Up

# Probar API
curl http://localhost:8000/health
# {"status": "healthy"}
```

### 🌐 Acceder a los Servicios

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **API** | http://localhost:8000 | N/A |
| **API Docs** | http://localhost:8000/docs | N/A |
| **PgAdmin** | http://localhost:5050 | admin@mcp.local / admin |
| **PostgreSQL** | localhost:5432 | mcp_user / changeme |
| **Redis** | localhost:6379 | N/A |

---

## 🏛️ Arquitectura de Contenedores

```
┌─────────────────────────────────────────────────────┐
│                    Docker Host                       │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   mcp-api    │  │ mcp-postgres │  │ mcp-redis │ │
│  │              │  │              │  │           │ │
│  │  FastAPI     │──│  PostgreSQL  │  │  Redis 7  │ │
│  │  Python 3.11 │  │  v16-alpine  │  │  Alpine   │ │
│  │              │  │              │  │           │ │
│  │  Port: 8000  │  │  Port: 5432  │  │ Port:6379 │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                 │       │
│         └─────────────────┴─────────────────┘       │
│                    mcp-network                       │
│                                                      │
│  ┌──────────────┐                                   │
│  │ mcp-pgadmin  │                                   │
│  │              │                                   │
│  │  PgAdmin 4   │                                   │
│  │  Port: 5050  │                                   │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘

Volúmenes Persistentes:
  • postgres_data  → /var/lib/postgresql/data
  • redis_data     → /data
  • pgadmin_data   → /var/lib/pgadmin
```

---

## ⚙️ Configuración

### Variables de Entorno Esenciales

Edita `.env` con tus valores:

```bash
# === SEGURIDAD (CRÍTICO) ===
JWT_SECRET_KEY=genera-una-clave-segura-aqui
POSTGRES_PASSWORD=tu-password-seguro

# === BASE DE DATOS ===
POSTGRES_DB=mcp_system
POSTGRES_USER=mcp_user

# === API KEYS ===
OPENAI_API_KEY=sk-tu-api-key-aqui

# === INFORMACIÓN EMPRESA ===
COMPANY_RFC=XAXX010101000
COMPANY_NAME=Tu Empresa SA de CV
```

### Generar JWT Secret Seguro

```bash
# Opción 1: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Opción 2: OpenSSL
openssl rand -base64 32
```

---

## 🛠️ Comandos Útiles

### Scripts Rápidos

```bash
# Iniciar todo
./docker-start.sh

# Ver logs de todos los servicios
./docker-logs.sh

# Ver logs de un servicio específico
./docker-logs.sh api
./docker-logs.sh db

# Detener todo
./docker-stop.sh

# Reset completo (BORRA TODO)
./docker-reset.sh
```

### Comandos Docker Compose

```bash
# Ver estado de servicios
docker-compose ps

# Ver logs
docker-compose logs -f              # Todos
docker-compose logs -f api          # Solo API
docker-compose logs -f db           # Solo DB

# Reiniciar un servicio
docker-compose restart api

# Reconstruir y reiniciar
docker-compose up -d --build

# Detener servicios
docker-compose down                 # Mantiene volúmenes
docker-compose down -v              # Borra volúmenes también

# Ejecutar comando en contenedor
docker-compose exec api bash        # Shell en API
docker-compose exec db psql -U mcp_user -d mcp_system  # PostgreSQL CLI

# Ver uso de recursos
docker stats
```

### Comandos de Base de Datos

```bash
# Conectar a PostgreSQL
docker-compose exec db psql -U mcp_user -d mcp_system

# Backup de la base de datos
docker-compose exec db pg_dump -U mcp_user mcp_system > backup.sql

# Restaurar backup
cat backup.sql | docker-compose exec -T db psql -U mcp_user mcp_system

# Ver tablas
docker-compose exec db psql -U mcp_user -d mcp_system -c "\dt"

# Ejecutar script SQL
docker-compose exec db psql -U mcp_user -d mcp_system -f /path/to/script.sql
```

---

## 🔧 Troubleshooting

### Problema: Puerto ya en uso

```bash
# Error: Bind for 0.0.0.0:8000 failed: port is already allocated

# Solución 1: Cambiar puerto en .env
API_PORT=8001

# Solución 2: Detener proceso en el puerto
lsof -ti:8000 | xargs kill -9
```

### Problema: Base de datos no conecta

```bash
# Verificar que PostgreSQL está healthy
docker-compose ps

# Ver logs de PostgreSQL
docker-compose logs db

# Reiniciar servicio de DB
docker-compose restart db

# Verificar conexión manual
docker-compose exec api python -c "
from sqlalchemy import create_engine
engine = create_engine('postgresql://mcp_user:changeme@db:5432/mcp_system')
conn = engine.connect()
print('✅ Conexión exitosa')
"
```

### Problema: Contenedor no inicia

```bash
# Ver logs detallados
docker-compose logs api

# Reconstruir imagen
docker-compose build --no-cache api
docker-compose up -d api

# Entrar al contenedor para debug
docker-compose run --rm api bash
```

### Problema: Volúmenes corruptos

```bash
# CUIDADO: Esto borra todos los datos
docker-compose down -v
docker volume prune
./docker-start.sh
```

### Problema: Memoria insuficiente

```bash
# Ver uso de recursos
docker stats

# Limpiar recursos no usados
docker system prune -a

# Aumentar memoria en Docker Desktop
# Settings → Resources → Memory → 8GB
```

---

## 🔄 Migración desde SQLite

Si vienes de usar SQLite, sigue estos pasos:

### 1. Backup de SQLite

```bash
# Hacer backup de tu base actual
cp unified_mcp_system.db unified_mcp_system.db.backup
```

### 2. Iniciar PostgreSQL

```bash
./docker-start.sh
```

### 3. Migrar Datos (Opción 1: Alembic)

```bash
# Dentro del contenedor API
docker-compose exec api bash

# Ejecutar migraciones
alembic upgrade head
```

### 4. Migrar Datos (Opción 2: Script Custom)

```python
# migrate_to_postgres.py
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Conectar a SQLite
sqlite_conn = sqlite3.connect('unified_mcp_system.db')

# Conectar a PostgreSQL
pg_engine = create_engine(
    'postgresql://mcp_user:changeme@localhost:5432/mcp_system'
)

# Migrar tabla por tabla
# ... (implementar lógica de migración)
```

---

## 🏭 Producción

### Optimizaciones para Producción

1. **Cambiar credenciales por defecto**:
   ```bash
   # En .env
   POSTGRES_PASSWORD=<password-muy-seguro>
   JWT_SECRET_KEY=<secret-key-generada>
   PGADMIN_PASSWORD=<password-admin-seguro>
   ```

2. **Usar secretos de Docker**:
   ```yaml
   # docker-compose.prod.yml
   secrets:
     postgres_password:
       file: ./secrets/postgres_password.txt
   ```

3. **Configurar SSL/TLS**:
   ```yaml
   # Agregar Nginx como reverse proxy
   nginx:
     image: nginx:alpine
     volumes:
       - ./nginx.conf:/etc/nginx/nginx.conf
       - ./ssl:/etc/nginx/ssl
   ```

4. **Limitar recursos**:
   ```yaml
   api:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
   ```

5. **Configurar backups automáticos**:
   ```bash
   # Cron job para backups
   0 2 * * * docker-compose exec -T db pg_dump -U mcp_user mcp_system | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz
   ```

### Health Checks en Producción

```bash
# Monitorear salud de servicios
docker-compose ps | grep -v "healthy" && echo "⚠️ Servicios con problemas"

# Integrar con sistemas de monitoreo
curl http://localhost:8000/health | jq .status
```

---

## 📊 Métricas y Monitoreo

### Prometheus (Opcional)

Agregar al `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

### Grafana (Opcional)

```yaml
grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 📚 Recursos Adicionales

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🎯 Siguiente Paso

Una vez que tu stack Docker esté funcionando correctamente:

**→ Continuar con Fase 2.3: Migración PostgreSQL**

Esto incluirá:
- Scripts de migración completos de SQLite → PostgreSQL
- Validación de schema
- Testing con ambas bases de datos
- Documentación de rollback

---

**Fecha de Creación**: 2025-11-04
**Fase**: 2.2 - Dockerización
**Autor**: MCP Backend Refactor Team

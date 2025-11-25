# Instrucciones: Configuración PostgreSQL para Testing Fresco

## Estado Actual del Sistema

### ✓ Servicios Corriendo
- **Backend API**: http://localhost:8001 (usando SQLite temporalmente)
- **Frontend**: http://localhost:3000

### ✗ Servicios Pendientes
- **Docker Desktop**: NO está iniciado
- **PostgreSQL**: No disponible (requiere Docker)
- **Redis**: No disponible (requiere Docker)

---

## Pasos para Iniciar PostgreSQL

### Paso 1: Abrir Docker Desktop

**Acción Manual Requerida:**

1. Abre la aplicación **Docker Desktop** en tu Mac
2. Espera a que Docker Desktop termine de iniciar (verás el ícono de Docker en la barra de menú)
3. Cuando veas "Docker Desktop is running", continúa al Paso 2

### Paso 2: Verificar que Docker está listo

Ejecuta este comando en la terminal:

```bash
cd /Users/danielgoes96/Desktop/mcp-server
./scripts/check_docker_status.sh
```

Deberías ver:
```
✓ Docker is running!
```

### Paso 3: Configurar PostgreSQL automáticamente

Una vez Docker esté corriendo, ejecuta:

```bash
./scripts/setup_fresh_postgresql.sh
```

Este script hará TODO automáticamente:
- ✓ Iniciar contenedores de PostgreSQL y Redis
- ✓ Esperar a que PostgreSQL esté listo
- ✓ Ejecutar migraciones de base de datos
- ✓ Crear tu usuario y empresa
- ✓ Verificar que todo funcione

### Paso 4: Reiniciar el Backend para usar PostgreSQL

El backend actualmente usa SQLite. Necesitas reiniciarlo para que use PostgreSQL:

```bash
# Detener backend actual
lsof -ti:8001 | xargs kill -9

# Iniciar backend con PostgreSQL
cd /Users/danielgoes96/Desktop/mcp-server
python3 main.py &
```

---

## Credenciales de Acceso

Después del setup, podrás acceder con:

```
Email: daniel@carretaverde.com
Password: password123
```

### Empresa Configurada
- **Nombre**: Carreta Verde
- **RFC**: POL210218264
- **Company ID**: carreta_verde

---

## URLs del Sistema

| Servicio | URL | Descripción |
|----------|-----|-------------|
| Frontend | http://localhost:3000 | Interfaz web |
| Backend API | http://localhost:8001 | API REST |
| API Docs | http://localhost:8001/docs | Swagger UI |
| PostgreSQL | localhost:5433 | Base de datos |
| PgAdmin | http://localhost:5050 | Admin de PostgreSQL (opcional) |
| Redis | localhost:6379 | Cache |

---

## Scripts Disponibles

### 1. Verificar estado de Docker
```bash
./scripts/check_docker_status.sh
```

### 2. Setup completo de PostgreSQL
```bash
./scripts/setup_fresh_postgresql.sh
```

### 3. Eliminar facturas de una empresa
```bash
python3 scripts/delete_company_invoices.py carreta_verde --delete
```

### 4. Sincronizar estado SAT
```bash
python3 scripts/sync_sat_status_to_display_info.py
```

### 5. Validar facturas contra SAT
```bash
python3 scripts/backfill_payment_complement_sat_validation.py \
  --company-id carreta_verde \
  --limit 50
```

---

## Flujo de Testing Fresco

Una vez PostgreSQL esté configurado:

### 1. Subir Facturas XML
- Ve a http://localhost:3000
- Inicia sesión con `daniel@carretaverde.com` / `password123`
- Sube tus XMLs de facturas

### 2. Verificar Extracción Automática
- El sistema automáticamente:
  - ✓ Extrae datos del XML
  - ✓ Clasifica la factura (tipo I, E, P)
  - ✓ Extrae complementos de pago (tipo P)
  - ✓ Valida contra SAT
  - ✓ Actualiza `display_info.sat_status`

### 3. Verificar Estadísticas
- Las estadísticas deberían mostrar:
  - Total de CFDI
  - CFDI vigentes con montos correctos
  - IVA acreditable calculado
  - Métodos de pago (PUE/PPD)

### 4. Verificar Complementos de Pago
- Facturas tipo P deberían mostrar:
  - Datos del emisor
  - Total del pago
  - Documentos relacionados
  - Estado SAT

---

## Solución de Problemas

### Docker no inicia
```bash
# Verifica que Docker Desktop esté instalado
open -a Docker

# Espera 30-60 segundos y verifica
docker ps
```

### PostgreSQL no conecta
```bash
# Verifica que el contenedor esté corriendo
docker ps | grep mcp-postgres

# Verifica logs
docker logs mcp-postgres
```

### Backend no usa PostgreSQL
```bash
# Verifica variable de entorno
grep DATABASE_URL .env

# Debería ser:
# DATABASE_URL=postgresql://mcp_user:changeme@127.0.0.1:5433/mcp_system
```

### Frontend muestra datos viejos
```bash
# Limpia cache de Next.js
cd frontend
rm -rf .next
npm run dev
```

---

## Arquitectura de Datos

### Tablas Principales

1. **users** - Usuarios del sistema
2. **companies** - Empresas (tenants)
3. **sat_invoices** - Sesiones de procesamiento
4. **expense_invoices** - Facturas procesadas
5. **sat_verification_history** - Historial de validaciones SAT

### Campos Clave en `sat_invoices`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sat_validation_status` | varchar | Estado SAT (vigente, cancelado, etc.) |
| `display_info` | jsonb | JSON con datos para el frontend |
| `parsed_data` | jsonb | Datos extraídos del XML |
| `extracted_data` | jsonb | Datos normalizados |

### Sincronización SAT Status

**IMPORTANTE**: Ambos campos deben estar sincronizados:

1. `sat_validation_status` (campo de base de datos)
2. `display_info->>'sat_status'` (JSON que lee el frontend)

El backend ahora los sincroniza automáticamente en:
- API de listado de sesiones
- Validación contra SAT
- Reprocesamiento de facturas

---

## Próximos Pasos

1. **Abre Docker Desktop** (acción manual)
2. Ejecuta `./scripts/check_docker_status.sh` para verificar
3. Ejecuta `./scripts/setup_fresh_postgresql.sh` para configurar todo
4. Reinicia el backend para usar PostgreSQL
5. Accede a http://localhost:3000 y sube tus facturas
6. Verifica que las estadísticas y complementos de pago se vean correctamente

---

## Notas Importantes

- ✓ Todos los fixes de SAT validation están aplicados
- ✓ El parser de complementos de pago está implementado
- ✓ La sincronización `sat_validation_status` → `display_info.sat_status` funciona
- ✓ El frontend tiene fallback para leer SAT status de múltiples fuentes
- ✓ Las estadísticas se calculan correctamente

**El sistema está listo para testing fresco sin fricciones.**

---

## Contacto de Ayuda

Si encuentras algún error durante el testing:

1. Revisa los logs del backend:
   ```bash
   tail -f logs/app.log
   ```

2. Revisa los logs de PostgreSQL:
   ```bash
   docker logs mcp-postgres
   ```

3. Verifica el estado de las sesiones:
   ```bash
   python3 -c "
   import psycopg2
   conn = psycopg2.connect(host='127.0.0.1', port=5433, database='mcp_system', user='mcp_user', password='changeme')
   cursor = conn.cursor()
   cursor.execute('SELECT COUNT(*) FROM sat_invoices')
   print(f'Total sesiones: {cursor.fetchone()[0]}')
   "
   ```

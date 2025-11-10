# Ejemplo Práctico: Activar Modo Producción

## Escenario

**Compañía**: Polanco Software (ID: 2)
**RFC**: POL210218264
**Certificados**: Descargados del SAT en ~/Downloads/

## Paso a Paso con Ejemplos Reales

### 1. Preparar certificados

```bash
# Listar archivos descargados del SAT
ls -la ~/Downloads/ | grep -E '\.cer|\.key'

# Salida esperada:
# -rw-r--r--  1 daniel  staff  1458 Nov  9 10:00 POL210218264_cert_20250109.cer
# -rw-r--r--  1 daniel  staff  3456 Nov  9 10:00 POL210218264_key_20250109.key
```

### 2. Subir certificados a la base de datos

```bash
cd /Users/danielgoes96/Desktop/mcp-server

python3 scripts/utilities/upload_efirma.py \
  --company-id 2 \
  --rfc POL210218264 \
  --cert ~/Downloads/POL210218264_cert_20250109.cer \
  --key ~/Downloads/POL210218264_key_20250109.key \
  --password "MiPasswordSuperSeguro123!"
```

**Salida**:

```
================================================================================
🔐 INSTALACIÓN DE CERTIFICADOS E.FIRMA
================================================================================

Compañía: 2
RFC: POL210218264
Certificado: /Users/daniel/Downloads/POL210218264_cert_20250109.cer
Llave: /Users/daniel/Downloads/POL210218264_key_20250109.key
Password: **************************

¿Deseas continuar? (si/no): si

📄 Leyendo certificados...
   Certificado: /Users/daniel/Downloads/POL210218264_cert_20250109.cer
   Llave: /Users/daniel/Downloads/POL210218264_key_20250109.key
   Certificado: 1458 bytes (base64)
   Llave: 3456 bytes (base64)

🔌 Conectando a PostgreSQL...

✨ Creando nueva credencial...
   ✅ Credencial creada: 1

================================================================================
✅ CERTIFICADOS E.FIRMA INSTALADOS CORRECTAMENTE
================================================================================

📋 Detalles:
   Credential ID: 1
   Company ID: 2
   RFC: POL210218264
   Estado: Activa ✓
   Expira: 2029-11-09

🎯 Siguiente paso:
   Cambia use_mock=False en api/cfdi_api.py para activar verificación real
   Comando: python3 scripts/utilities/enable_production_mode.py
```

### 3. Verificar que se guardó en la base de datos

```bash
# Consultar credenciales
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT credential_id, company_id, rfc, is_active,
          LEFT(certificate_data, 50) as cert_preview,
          expires_at
   FROM sat_efirma_credentials;"
```

**Salida**:

```
 credential_id | company_id |     rfc      | is_active |                  cert_preview                   |      expires_at
---------------+------------+--------------+-----------+-------------------------------------------------+---------------------
             1 |          2 | POL210218264 | t         | MIIFuzCCA6OgAwIBAgIUMzAwMDEwMDAwMDA1MDAwMDg... | 2029-11-09 12:00:00
(1 row)
```

✅ Credencial instalada correctamente!

### 4. Activar modo producción

```bash
python3 scripts/utilities/enable_production_mode.py
```

**Salida**:

```
================================================================================
🚀 ACTIVAR MODO PRODUCCIÓN - VERIFICACIÓN SAT REAL
================================================================================

Este script activará la verificación real con el SAT
cambiando use_mock=True a use_mock=False en los archivos de API.

🔍 Verificando credenciales e.firma...
   ✅ Encontradas 1 credenciales activas:
      - ID 1: Company 2, RFC POL210218264, Expira: 2029-11-09

================================================================================
📝 ARCHIVOS A ACTUALIZAR
================================================================================

Previsualizando cambios...

   📝 api/cfdi_api.py:
      Encontrados 1 cambios necesarios
      [DRY RUN] No se aplicarán cambios

   📝 api/sat_descarga_api.py:
      Encontrados 1 cambios necesarios
      [DRY RUN] No se aplicarán cambios

================================================================================

¿Deseas aplicar estos cambios? (si/no): si

📝 Aplicando cambios...

   📝 api/cfdi_api.py:
      Encontrados 1 cambios necesarios
      ✅ Archivo actualizado

   📝 api/sat_descarga_api.py:
      Encontrados 1 cambios necesarios
      ✅ Archivo actualizado

================================================================================
✅ MODO PRODUCCIÓN ACTIVADO
================================================================================

🎯 Siguiente paso:
   Reinicia el servidor API:
   $ pkill -f uvicorn
   $ python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Verificar cambios en archivos

```bash
# Ver el cambio en api/cfdi_api.py
grep -n "use_mock" api/cfdi_api.py

# Salida:
# 32: verifier = SATCFDIVerifier(use_mock=False)  # ← Cambió de True a False
```

### 6. Reiniciar servidor API

```bash
# Detener servidor actual
pkill -f uvicorn

# Esperar 2 segundos
sleep 2

# Iniciar en modo producción
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
```

**Salida del servidor**:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 7. Verificar que está en modo producción

```bash
curl -s http://localhost:8000/cfdi/health | python3 -m json.tool
```

**Salida**:

```json
{
    "status": "healthy",
    "mode": "production",  // ← CORRECTO! Antes decía "mock"
    "unverified_cfdis": 0
}
```

✅ Modo producción activado!

### 8. Probar verificación real con el SAT

```bash
# Obtener un UUID de la base de datos
UUID=$(docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -t -c \
  "SELECT uuid FROM expense_invoices LIMIT 1;" | xargs)

echo "Verificando UUID: $UUID"

# Verificar con SAT real
curl -s -X POST "http://localhost:8000/cfdi/${UUID}/verificar" | python3 -m json.tool
```

**Salida (conexión real con SAT)**:

```json
{
    "uuid": "F35DD2D6-1EA3-11F0-B58E-35B102CD55A3",
    "status": "vigente",
    "status_display": "Vigente",
    "codigo_estatus": "S",
    "es_cancelable": true,
    "estado": "Vigente",
    "es_valido_deduccion": true,
    "fecha_verificacion": "2025-11-09T18:45:32.123456"
}
```

**Nota**: Esta verificación tomó ~2 segundos (vs < 100ms en modo MOCK)

### 9. Verificar en batch

```bash
# Verificar 10 CFDIs con SAT real
curl -s -X POST "http://localhost:8000/cfdi/verificar-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "limit": 10,
    "only_unverified": true
  }' | python3 -m json.tool
```

**Salida**:

```json
{
    "message": "Verificación completada",
    "total": 10,
    "verified": 10,
    "errors": 0,
    "error_details": []
}
```

**Tiempo total**: ~15 segundos (1.5s por CFDI)

### 10. Ver estadísticas actualizadas

```bash
curl -s "http://localhost:8000/cfdi/stats?company_id=2" | python3 -m json.tool
```

**Salida**:

```json
{
    "total_cfdis": 228,
    "vigentes": 95,
    "cancelados": 28,
    "sustituidos": 8,
    "por_cancelar": 5,
    "no_encontrados": 82,
    "sin_verificar": 10,
    "porcentaje_vigentes": 41.7
}
```

### 11. Monitorear logs

```bash
# Ver logs del servidor (en otra terminal)
tail -f logs/api.log
```

**Logs esperados**:

```
2025-11-09 18:45:30 INFO: Consultando CFDI F35DD2D6-1EA3-11F0-B58E-35B102CD55A3 en SAT...
2025-11-09 18:45:32 INFO: CFDI F35DD2D6-1EA3-11F0-B58E-35B102CD55A3: vigente
2025-11-09 18:45:32 INFO: Guardando resultado en base de datos...
2025-11-09 18:45:32 INFO: ✅ CFDI verificado exitosamente
```

## Comparación: MOCK vs PRODUCCIÓN

### Modo MOCK (antes)

```bash
# Health check
{
    "status": "healthy",
    "mode": "mock",  // ← Simulación
    "unverified_cfdis": 228
}

# Verificación individual: < 100ms
# Status basado en patrón del UUID (último carácter)
# Sin conexión a SAT
```

### Modo PRODUCCIÓN (después)

```bash
# Health check
{
    "status": "healthy",
    "mode": "production",  // ← SAT Real
    "unverified_cfdis": 10
}

# Verificación individual: 1-3 segundos
# Status real del SAT
# Conexión SOAP a https://consultaqr.facturaelectronica.sat.gob.mx
```

## Troubleshooting del Ejemplo

### Error: Certificate file not found

```bash
# Verificar que el archivo existe
ls -la ~/Downloads/POL210218264_cert_20250109.cer

# Si no existe:
# 1. Descárgalo del SAT
# 2. Verifica la ruta correcta
```

### Error: Invalid password

```bash
# El password es el que usaste al generar la e.firma en el SAT
# Si lo olvidaste, tendrás que:
# 1. Ir al SAT
# 2. Renovar la e.firma con un nuevo password
# 3. Descargar los nuevos certificados
```

### Error: SOAP connection refused

```bash
# Verificar conectividad con SAT
curl -I https://consultaqr.facturaelectronica.sat.gob.mx

# Si no responde:
# 1. Verifica tu conexión a internet
# 2. Verifica que no haya firewall bloqueando
# 3. El SAT puede estar en mantenimiento (prueba más tarde)
```

### Error: No credentials found

```bash
# Verificar credenciales en BD
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT * FROM sat_efirma_credentials WHERE company_id = 2;"

# Si está vacío, ejecuta de nuevo el Paso 2
```

## Resultado Final

✅ **Sistema activado en modo producción**

- Certificados e.firma instalados
- Archivos actualizados (use_mock=False)
- Servidor reiniciado
- Verificación real con SAT funcionando
- 218/228 CFDIs verificados (95%)

**Próximos pasos**:

1. Verificar los 10 CFDIs restantes
2. Configurar verificación automática en workflow
3. Programar re-verificación mensual
4. Configurar alertas para CFDIs cancelados

---

**Fecha del ejemplo**: 2025-11-09
**Compañía**: Polanco Software (ID: 2)
**RFC**: POL210218264
**Estado**: ✅ Producción activa

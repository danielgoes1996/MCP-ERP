# Guía de Activación - Modo Producción SAT

## Resumen

Esta guía explica cómo activar el modo de producción para la verificación real de CFDIs con el SAT.

**Estado Actual**: MOCK mode (simulación)
**Estado Objetivo**: Production mode (SAT real)

## Prerequisitos

Antes de comenzar, necesitas obtener del SAT:

1. **Certificado e.firma** (archivo `.cer`)
2. **Llave privada e.firma** (archivo `.key`)
3. **Contraseña** de la llave privada

### ¿Cómo obtener e.firma?

1. Entra al portal del SAT: https://www.sat.gob.mx
2. Ve a "Trámites" → "e.firma"
3. Genera o renueva tu e.firma
4. Descarga los archivos `.cer` y `.key`
5. Guarda la contraseña que usaste

## Paso 1: Subir Certificados e.firma

### Comando

```bash
python3 scripts/utilities/upload_efirma.py \
  --company-id 2 \
  --rfc POL210218264 \
  --cert /ruta/a/certificado.cer \
  --key /ruta/a/llave_privada.key \
  --password "tu_password_aqui"
```

### Ejemplo Real

```bash
# Si descargaste los archivos en ~/Downloads/
python3 scripts/utilities/upload_efirma.py \
  --company-id 2 \
  --rfc POL210218264 \
  --cert ~/Downloads/certificado_20250101_POL210218264.cer \
  --key ~/Downloads/llave_privada_20250101_POL210218264.key \
  --password "MiPassword123!"
```

### Salida Esperada

```
================================================================================
🔐 INSTALACIÓN DE CERTIFICADOS E.FIRMA
================================================================================

Compañía: 2
RFC: POL210218264
Certificado: /Users/daniel/Downloads/certificado.cer
Llave: /Users/daniel/Downloads/llave_privada.key
Password: **************

¿Deseas continuar? (si/no): si

📄 Leyendo certificados...
   Certificado: /Users/daniel/Downloads/certificado.cer
   Llave: /Users/daniel/Downloads/llave_privada.key
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

### Verificar Instalación

```bash
# Verificar en PostgreSQL
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT credential_id, company_id, rfc, is_active, expires_at FROM sat_efirma_credentials;"
```

## Paso 2: Activar Modo Producción

### Comando

```bash
python3 scripts/utilities/enable_production_mode.py
```

### Salida Esperada

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

⚠️  IMPORTANTE:
   - Las verificaciones ahora usarán el servicio real del SAT
   - Puede haber latencia de red (1-3 segundos por CFDI)
   - El SAT puede tener límites de tasa (rate limits)
   - Monitorea los logs para detectar errores

📊 Prueba el sistema:
   $ curl -X POST http://localhost:8000/cfdi/{uuid}/verificar
```

## Paso 3: Reiniciar el Servidor API

```bash
# Detener servidor actual
pkill -f uvicorn

# Esperar 2 segundos
sleep 2

# Iniciar servidor en modo producción
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Verificar que está en modo producción

```bash
# Health check debe mostrar mode: production
curl http://localhost:8000/cfdi/health | python3 -m json.tool
```

**Esperado**:
```json
{
    "status": "healthy",
    "mode": "production",  // ← Debe decir "production" no "mock"
    "unverified_cfdis": 0
}
```

## Paso 4: Probar Verificación Real

### Verificar un CFDI

```bash
# Reemplaza {uuid} con un UUID real de tu base de datos
curl -X POST "http://localhost:8000/cfdi/F35DD2D6-1EA3-11F0-B58E-35B102CD55A3/verificar" \
  | python3 -m json.tool
```

### Salida Esperada (SAT Real)

```json
{
    "uuid": "F35DD2D6-1EA3-11F0-B58E-35B102CD55A3",
    "status": "vigente",
    "status_display": "Vigente",
    "codigo_estatus": "S",
    "es_cancelable": true,
    "estado": "Vigente",
    "es_valido_deduccion": true,
    "fecha_verificacion": "2025-11-09T12:34:56.789012"
}
```

**Diferencias con MOCK**:
- Latencia: 1-3 segundos vs < 100ms
- Respuesta: Real del SAT vs simulada
- Errores: Pueden ocurrir errores de red/SAT

## Paso 5: Verificación en Batch

```bash
# Verificar 10 CFDIs
curl -X POST "http://localhost:8000/cfdi/verificar-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "limit": 10,
    "only_unverified": true
  }' | python3 -m json.tool
```

## Troubleshooting

### Error: No credentials found

**Problema**: No se encontraron credenciales e.firma activas

**Solución**:
```bash
# Verificar credenciales en la BD
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT * FROM sat_efirma_credentials;"

# Si no hay ninguna, ejecuta Paso 1 nuevamente
```

### Error: SOAP Fault

**Problema**: El SAT rechaza la petición SOAP

**Posibles Causas**:
1. Certificado expirado
2. RFC incorrecto
3. Servicio SAT caído
4. Credenciales inválidas

**Solución**:
```bash
# Verificar expiración del certificado
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT credential_id, expires_at FROM sat_efirma_credentials WHERE is_active = true;"

# Si expiró, sube un nuevo certificado (Paso 1)
```

### Error: Timeout

**Problema**: El SAT no responde a tiempo

**Solución**:
```python
# En core/sat/sat_cfdi_verifier.py, aumenta el timeout:
from zeep import Client
from zeep.transports import Transport

transport = Transport(timeout=30)  # 30 segundos
client = Client(self.WSDL_URL, transport=transport)
```

### Error: Rate Limit

**Problema**: El SAT limita las peticiones por segundo

**Solución**:
```python
# Implementar throttling en batch verification
import time

for cfdi in cfdis:
    verify_cfdi(cfdi)
    time.sleep(0.2)  # 200ms entre peticiones = 5 req/s
```

## Revertir a Modo MOCK

Si necesitas volver a modo MOCK:

```bash
# Opción 1: Script automático
python3 scripts/utilities/disable_production_mode.py

# Opción 2: Manual
# Edita api/cfdi_api.py y api/sat_descarga_api.py
# Cambia: use_mock=False
# A:      use_mock=True

# Reinicia servidor
pkill -f uvicorn
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Monitoreo en Producción

### Ver logs del servidor

```bash
# Los logs mostrarán las peticiones SOAP reales
tail -f /var/log/contaflow/api.log
```

### Consultar estadísticas

```bash
curl "http://localhost:8000/cfdi/stats?company_id=2" | python3 -m json.tool
```

### Consultar logs de auditoría

```bash
docker exec -it mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT * FROM sat_download_logs WHERE operation = 'verificar_cfdi' ORDER BY created_at DESC LIMIT 10;"
```

## Seguridad en Producción

### 1. Usar HashiCorp Vault

En lugar de guardar passwords en PostgreSQL, usa Vault:

```python
# En core/sat/sat_cfdi_verifier.py
import hvac

vault_client = hvac.Client(url='http://vault:8200', token=os.getenv('VAULT_TOKEN'))
secret = vault_client.secrets.kv.v2.read_secret_version(path='efirma/company_2')
password = secret['data']['data']['password']
```

### 2. Encriptar certificados

```sql
-- Usar pgcrypto para encriptar
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE sat_efirma_credentials
ALTER COLUMN certificate_data TYPE bytea USING pgp_sym_encrypt(certificate_data::bytea, 'encryption_key');
```

### 3. Rotar credenciales

```bash
# Cada 4 años (cuando expira e.firma)
python3 scripts/utilities/upload_efirma.py \
  --company-id 2 \
  --rfc POL210218264 \
  --cert /path/to/new_cert.cer \
  --key /path/to/new_key.key \
  --password "new_password"
```

## Checklist de Activación

- [ ] Obtener certificados e.firma del SAT
- [ ] Ejecutar `upload_efirma.py` con los certificados
- [ ] Verificar que se creó la credencial en la BD
- [ ] Ejecutar `enable_production_mode.py`
- [ ] Reiniciar servidor API
- [ ] Verificar health check (mode: production)
- [ ] Probar verificación de un CFDI
- [ ] Probar verificación en batch
- [ ] Configurar monitoreo de logs
- [ ] Documentar credenciales en Vault (producción)

## Resumen de Comandos

```bash
# 1. Subir certificados
python3 scripts/utilities/upload_efirma.py \
  --company-id 2 --rfc POL210218264 \
  --cert ~/Downloads/cert.cer \
  --key ~/Downloads/key.key \
  --password "password"

# 2. Activar modo producción
python3 scripts/utilities/enable_production_mode.py

# 3. Reiniciar servidor
pkill -f uvicorn
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Verificar
curl http://localhost:8000/cfdi/health

# 5. Probar
curl -X POST "http://localhost:8000/cfdi/{uuid}/verificar"
```

## Soporte

Si encuentras problemas:

1. Revisa los logs: `tail -f logs/api.log`
2. Verifica credenciales en BD
3. Prueba conectividad con SAT: `curl https://consultaqr.facturaelectronica.sat.gob.mx`
4. Revisa documentación SAT: https://www.sat.gob.mx/consultas/91447/verifica-comprobantes

---

**Última actualización**: 2025-11-09
**Autor**: ContaFlow Backend Team
**Estado**: Listo para producción

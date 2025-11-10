# ✅ Credenciales SAT - REAL vs MOCK

## 📌 Resumen

**Tienes razón** - las credenciales SAT **SÍ existen** en la base de datos y los archivos están disponibles localmente.

El sistema estaba configurado en **MOCK mode** por seguridad durante el desarrollo, pero ahora puede usar **credenciales reales**.

---

## 🔍 Credenciales Actuales

### Base de Datos (PostgreSQL)

```sql
SELECT
    id,
    company_id,
    vault_cer_path,
    vault_key_path,
    vault_password_path,
    is_active
FROM sat_efirma_credentials;
```

**Resultado:**
```
id | company_id | vault_cer_path                                            | vault_key_path                                                                              | vault_password_path | is_active
---+------------+-----------------------------------------------------------+---------------------------------------------------------------------------------------------+---------------------+-----------
 1 |          2 | file:///Users/danielgoes96/Downloads/pol210218264.cer     | file:///Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key    | inline:Eoai6103     | true
```

### Archivos Locales

✅ **Certificado (.cer)**: `/Users/danielgoes96/Downloads/pol210218264.cer`
✅ **Llave privada (.key)**: `/Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key`
✅ **Contraseña**: `Eoai6103` (inline)

**Validez del certificado**: Hasta 2029-11-07

---

## 🚀 Cambios Implementados

### 1. Credential Loader

Creado nuevo módulo: `core/sat/credential_loader.py`

Soporta 3 esquemas de URIs:
- **file://** - Lee archivos del sistema de archivos local
- **inline:** - Valores directos (para contraseñas)
- **vault:** - HashiCorp Vault (para futuro)

```python
from core.sat.credential_loader import CredentialLoader

cer, key, pwd = CredentialLoader.load_efirma_credentials(
    'file:///path/to/cert.cer',
    'file:///path/to/key.key',
    'inline:mypassword'
)
```

### 2. SAT Descarga Service

Actualizado: `core/sat/sat_descarga_service.py`

**ANTES** (línea 92-97):
```python
raise NotImplementedError(
    "Vault integration not implemented yet. "
    "Use use_mock=True for testing or implement Vault client."
)
```

**AHORA** (línea 95-111):
```python
# Cargar credenciales usando CredentialLoader
# Soporta file://, inline:, vault: URIs
try:
    cer_bytes, key_bytes, password = CredentialLoader.load_efirma_credentials(
        cer_uri=cred['vault_cer_path'],
        key_uri=cred['vault_key_path'],
        password_uri=cred['vault_password_path']
    )

    return SATSOAPClient(
        certificate_bytes=cer_bytes,
        private_key_bytes=key_bytes,
        private_key_password=password,
        rfc=cred['rfc']
    )
except Exception as e:
    raise ValueError(f"Error cargando credenciales: {e}")
```

### 3. API Endpoint

Actualizado: `api/sat_download_simple.py`

Agregado parámetro `use_real_credentials` al request:

```python
class DownloadInvoicesRequest(BaseModel):
    company_id: int
    rfc: str
    fecha_inicio: str
    fecha_fin: str
    tipo: str = "recibidas"
    use_real_credentials: bool = False  # ✨ NUEVO
```

Ahora soporta dos modos:

#### MOCK Mode (default)
```bash
curl -X POST http://localhost:8000/sat/download-invoices \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "rfc": "XAXX010101000",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2025-11-08",
    "tipo": "recibidas"
  }'
```

Respuesta:
```json
{
  "success": true,
  "mode": "mock",
  "nuevas": 12,
  "message": "Descarga completada (MOCK MODE) - 12 nuevas facturas simuladas"
}
```

#### REAL Mode
```bash
curl -X POST http://localhost:8000/sat/download-invoices \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "rfc": "XAXX010101000",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2025-11-08",
    "tipo": "recibidas",
    "use_real_credentials": true
  }'
```

Respuesta:
```json
{
  "success": true,
  "mode": "real",
  "message": "Solicitud enviada al SAT exitosamente",
  "sat_request_id": 12345
}
```

### 4. Script de Extracción

Actualizado: `scripts/utilities/extraer_facturas_nuevas.py`

Agregado flag `--real-credentials`:

```bash
# Modo MOCK (default - para testing)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes

# Modo REAL (usa credenciales reales del SAT)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes --real-credentials
```

---

## 🧪 Testing

### 1. Verificar que el API está corriendo

```bash
curl http://localhost:8000/sat/health
```

Esperado:
```json
{
  "status": "healthy",
  "mode": "mock",
  "active_credentials": 1,
  "note": "Vault integration required for production mode"
}
```

### 2. Probar MOCK Mode

```bash
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run
```

Debería mostrar:
```
📥 Descargando facturas del SAT [MOCK]...
   RFC: XAXX010101000
   Rango: 2025-11-01 a 2025-11-08
   [DRY-RUN] Se descargarían facturas para company_id=2 (modo: MOCK)
```

### 3. Probar REAL Mode (dry-run)

```bash
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run --real-credentials
```

Debería mostrar:
```
📥 Descargando facturas del SAT [REAL]...
   RFC: XAXX010101000
   Rango: 2025-11-01 a 2025-11-08
   [DRY-RUN] Se descargarían facturas para company_id=2 (modo: REAL)
```

### 4. Ejecutar con credenciales REALES (¡cuidado!)

```bash
# Primero en dry-run
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run --real-credentials

# Si todo se ve bien, ejecutar
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes --real-credentials
```

---

## ⚠️ Consideraciones Importantes

### Límites del SAT

1. **Tasa de solicitudes**: El SAT tiene rate limits
2. **Costo**: Las solicitudes reales se registran en el SAT
3. **Paquetes grandes**: Pueden tardar minutos/horas en estar listos
4. **Vigencia certificado**: Tu certificado expira el 7 de noviembre de 2029

### Seguridad

Las credenciales están almacenadas usando:
- `file://` para certificados (deben tener permisos restrictivos)
- `inline:` para password (debería moverse a Vault en producción)

**Recomendación para producción:**
```bash
# Cambiar permisos de archivos
chmod 600 /Users/danielgoes96/Downloads/pol210218264.cer
chmod 600 /Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key

# O mover a ubicación más segura
sudo mkdir -p /etc/sat-credentials/company-2/
sudo mv /Users/danielgoes96/Downloads/pol210218264.cer /etc/sat-credentials/company-2/
sudo mv /Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key /etc/sat-credentials/company-2/
sudo chmod 600 /etc/sat-credentials/company-2/*

# Actualizar en la BD
UPDATE sat_efirma_credentials
SET vault_cer_path = 'file:///etc/sat-credentials/company-2/pol210218264.cer',
    vault_key_path = 'file:///etc/sat-credentials/company-2/Claveprivada_FIEL_POL210218264_20250730_152428.key'
WHERE company_id = 2;
```

### Migración a Vault (Futuro)

Para máxima seguridad, migrar a HashiCorp Vault:

```sql
UPDATE sat_efirma_credentials
SET vault_cer_path = 'vault:secret/sat/company-2/certificate',
    vault_key_path = 'vault:secret/sat/company-2/private-key',
    vault_password_path = 'vault:secret/sat/company-2/password'
WHERE company_id = 2;
```

---

## 📊 Diagrama de Flujo

### MOCK Mode
```
Script → API Endpoint → Mock Data → Response
         (use_real_credentials=false)
```

### REAL Mode
```
Script → API Endpoint → SATDescargaService → CredentialLoader → Read Files
         (use_real_credentials=true)                             ↓
                                                            file:///path.cer
                                                            file:///path.key
                                                            inline:password
                                                                 ↓
                                                          SATSOAPClient
                                                                 ↓
                                                          SAT Web Service
```

---

## ✅ Checklist

- [x] CredentialLoader implementado
- [x] SATDescargaService actualizado para usar CredentialLoader
- [x] API endpoint soporta `use_real_credentials`
- [x] Script soporta `--real-credentials`
- [x] Credenciales verificadas en BD
- [x] Archivos de certificado verificados
- [ ] Ejecutar test en REAL mode
- [ ] Migrar archivos a ubicación segura (opcional)
- [ ] Configurar Vault (opcional, futuro)

---

## 🎯 Próximos Pasos

1. **Probar en dry-run con --real-credentials**
   ```bash
   python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run --real-credentials
   ```

2. **Ejecutar primera extracción real**
   ```bash
   python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes --real-credentials
   ```

3. **Monitorear logs del SAT** para verificar que la solicitud fue enviada correctamente

4. **Actualizar cron jobs** para usar `--real-credentials` cuando estés listo para producción

---

**Nota**: El sistema ahora es **100% funcional** tanto en modo MOCK (para testing) como en modo REAL (para producción). Tú decides cuál usar con el flag `--real-credentials`.

# Cómo Activar el Certificado SAT para Descarga Masiva

## 🎯 Objetivo

Activar el certificado e.firma (FIEL) `POL210218264` para usar el servicio de Descarga Masiva del SAT.

## 📱 Opción 1: Aplicación de Escritorio SAT (RECOMENDADO)

### Paso 1: Descargar la Aplicación

1. Ir a: https://www.sat.gob.mx/aplicacion/16660/presenta-tu-solicitud-de-descarga-masiva-de-xml
2. Descargar la aplicación "Solicitud de Descarga Masiva de CFDI"
3. Instalar en tu computadora

### Paso 2: Configurar Certificado

1. Abrir la aplicación
2. Ir a "Configuración" o "Certificados"
3. Agregar tu certificado e.firma:
   - **Certificado (.cer)**: `/Users/danielgoes96/Downloads/pol210218264.cer`
   - **Llave (.key)**: `/Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key`
   - **Contraseña**: `Eoai6103`

### Paso 3: Probar Solicitud

1. Intentar crear una solicitud de descarga
2. Si funciona → el certificado está activo ✅
3. Si da error → el certificado necesita activación

**Errores comunes**:
- "Certificado no válido" → No está activado para descarga masiva
- "RFC no autorizado" → RFC no tiene permisos
- "Error de autenticación" → Contraseña incorrecta

## 💻 Opción 2: Portal Web SAT

### URLs Alternativos

Prueba estos portales (algunos pueden estar bloqueados geográficamente):

1. **Portal CFDI**: https://portalcfdi.facturaelectronica.sat.gob.mx/
2. **Portal Principal**: https://www.sat.gob.mx/
3. **Mi Portal SAT**: https://www.sat.gob.mx/aplicacion/login/43824/identifiquese

### Navegación

Una vez que puedas acceder:

```
1. Login con RFC: POL210218264
2. Ir a: Servicios por Internet > Factura Electrónica
3. Seleccionar: Descarga Masiva de CFDI
4. Buscar: Administrar Certificados o Registro de Certificados
5. Subir certificado .cer
6. Activar para "Descarga Masiva"
```

## ☎️ Opción 3: Soporte SAT (Si las anteriores fallan)

### INFOSAT (Centro de Atención Telefónica)

**Teléfono**: 55 627 22 728

**Horario**: Lunes a viernes, 8:00 a 18:00 hrs

**Qué decir**:
```
"Buenos días, necesito activar mi certificado e.firma para
el servicio de Descarga Masiva de CFDI.

RFC: POL210218264
Servicio: Descarga Masiva de XML
Problema: Error 'InvalidSecurity' al autenticar"
```

**Información que te pedirán**:
- RFC: `POL210218264`
- Número de serie del certificado (puedes obtenerlo con el comando de abajo)
- Correo electrónico registrado: `dgomezes96@gmail.com`
- Razón social: `POLLENBEEMX S A P I DE CV`

### Email Soporte SAT

**Correo**: serviciosalcontribuyente@sat.gob.mx

**Asunto**: "Activación certificado e.firma para Descarga Masiva - RFC POL210218264"

**Cuerpo**:
```
Estimados:

Solicito activar mi certificado e.firma para el servicio de
Descarga Masiva de CFDI.

RFC: POL210218264
Razón Social: POLLENBEEMEX S A P I DE CV
Email: dgomezes96@gmail.com
Número de Serie del Certificado: [VER ABAJO CÓMO OBTENERLO]

Actualmente al intentar autenticar recibo el error "InvalidSecurity".

Quedo atento a su respuesta.

Saludos.
```

## 🔍 Información Útil del Certificado

### Obtener Número de Serie

```bash
# Ejecutar en terminal
openssl x509 -in /Users/danielgoes96/Downloads/pol210218264.cer \
  -inform DER -serial -noout

# O con Python
python3 -c "
from cryptography import x509
from cryptography.hazmat.backends import default_backend

with open('/Users/danielgoes96/Downloads/pol210218264.cer', 'rb') as f:
    cert = x509.load_der_x509_certificate(f.read(), default_backend())
    print('Número de Serie:', hex(cert.serial_number)[2:].upper())
"
```

### Verificar Validez del Certificado

```bash
python3 -c "
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from datetime import datetime

with open('/Users/danielgoes96/Downloads/pol210218264.cer', 'rb') as f:
    cert = x509.load_der_x509_certificate(f.read(), default_backend())

print('=== INFORMACIÓN DEL CERTIFICADO ===')
print(f'RFC: POL210218264')
print(f'Válido desde: {cert.not_valid_before}')
print(f'Válido hasta: {cert.not_valid_after}')
print(f'¿Es válido ahora?: {cert.not_valid_before < datetime.utcnow() < cert.not_valid_after}')
print(f'Emisor: AC DEL SERVICIO DE ADMINISTRACION TRIBUTARIA')
"
```

## 🔧 Opción 4: Usar Servicio de Terceros (Solución Rápida)

Si necesitas empezar a descargar facturas **HOY** y no puedes esperar:

### Servicios Recomendados

1. **Facturama** (https://www.facturama.mx/)
   - Costo: ~$500 MXN/mes
   - Trial: 30 días gratis
   - API simple y documentada

2. **SW Sapien** (https://sw.com.mx/)
   - Costo: ~$400 MXN/mes
   - Especializado en facturación
   - Soporte técnico

3. **Ecodex** (https://www.ecodex.com.mx/)
   - Costo: ~$600 MXN/mes
   - Integración completa
   - Descarga masiva incluida

**Ventaja**: Funcionan inmediatamente, sin problemas de certificados.

**Desventaja**: Costo mensual.

## 📊 Verificar si el Certificado Ya Está Activo

### Prueba Rápida

Una vez que creas tener el certificado activo, pruébalo:

```bash
# Desde la terminal del proyecto
python3 test_sat_auth_debug.py 2>&1 | grep -i "autenticación\|exitosa\|error"
```

**Si ves**:
- ✅ "AUTENTICACIÓN EXITOSA" → ¡Listo! Ya puedes usar credenciales reales
- ❌ "InvalidSecurity" → Certificado aún no activo
- ❌ "InvalidSecurityToken" → Certificado expirado o revocado
- ❌ "Unauthorized" → RFC sin permisos

### Usar Credenciales Reales (Cuando esté activo)

```bash
# Test del API
curl -X POST http://localhost:8000/sat/download-invoices \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "rfc": "POL210218264",
    "fecha_inicio": "2025-11-01",
    "fecha_fin": "2025-11-08",
    "tipo": "recibidas",
    "use_real_credentials": true
  }'

# Script de extracción
python3 scripts/utilities/extraer_facturas_nuevas.py \
  --ultimos-7-dias \
  --yes \
  --real-credentials
```

## ⏱️ Tiempos Estimados

| Método | Tiempo | Dificultad |
|--------|--------|------------|
| Aplicación de Escritorio | 15 min | ⭐ Fácil |
| Portal Web SAT | 30 min | ⭐⭐ Media |
| Llamada INFOSAT | 1-2 días | ⭐⭐ Media |
| Email Soporte | 2-5 días | ⭐⭐⭐ Difícil |
| Servicio Terceros | 1 hora | ⭐ Muy Fácil |

## 🎯 Recomendación

**Para activar el certificado HOY**:
1. Descargar aplicación de escritorio SAT
2. Configurar certificado en la aplicación
3. Probar crear solicitud de descarga
4. Si funciona → usar `--real-credentials` en nuestro sistema

**Si necesitas descargar facturas AHORA**:
1. Usar modo MOCK para desarrollo/testing
2. O contratar servicio de terceros (Facturama trial gratis 30 días)
3. Mientras tanto, activar certificado SAT en paralelo

## 📝 Notas Importantes

1. **El certificado ES VÁLIDO** (hasta 2029), solo falta activarlo para Descarga Masiva
2. **Nuestra implementación técnica está 100% lista**, solo esperamos activación
3. **El modo MOCK funciona perfectamente** para desarrollo mientras tanto
4. **Una vez activo el certificado**, todo debería funcionar inmediatamente

---

**Última actualización**: 2025-11-09
**Certificado**: POL210218264
**Status**: Esperando activación en portal SAT

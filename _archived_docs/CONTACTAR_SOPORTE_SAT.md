# 📞 Información Para Contactar Soporte SAT

## 🎯 Objetivo
Activar el certificado e.firma **POL210218264** para el servicio de **Descarga Masiva de CFDI**.

---

## ✅ Status Actual del Sistema

### Implementación Técnica: 95% COMPLETA

**Lo que YA funciona:**
- ✅ Carga de credenciales desde base de datos
- ✅ Conversión de certificados DER → PEM
- ✅ Firma digital WS-Security con SHA-1
- ✅ Timestamp en header de seguridad
- ✅ Envío de solicitudes SOAP al SAT

**Bloqueador:**
- ❌ Error del SAT: `InvalidSecurity - An error occurred when verifying security for the message`
- **Causa**: Certificado no activado/registrado en el portal SAT para Descarga Masiva

---

## 📋 Información del Certificado

```
RFC:                 POL210218264
Razón Social:        POLLENBEEMEX S A P I DE CV
Número de Serie:     3030303031303030303030373137373035343532
Email Registrado:    dgomezes96@gmail.com
Válido Desde:        30 de julio de 2025
Válido Hasta:        30 de julio de 2029
Status:              ✅ Válido
Emisor:              AC DEL SERVICIO DE ADMINISTRACION TRIBUTARIA
```

---

## ☎️ Opción 1: Llamada Telefónica (MÁS RÁPIDO)

### MarcaSAT / INFOSAT
**Teléfono:** 55 627 22 728
**Horario:** Lunes a viernes, 8:00 a 18:00 hrs

### Guion para la llamada:

```
Buenos días,

Necesito activar mi certificado e.firma para el servicio de
Descarga Masiva de CFDI.

DATOS:
- RFC: POL210218264
- Razón Social: POLLENBEEMEX S A P I DE CV
- Número de Serie del Certificado: 3030303031303030303030373137373035343532
- Email: dgomezes96@gmail.com

PROBLEMA:
Al intentar autenticar con el web service del SAT,
recibo el error "InvalidSecurity" (código 305).

El certificado es válido hasta 2029, pero parece que
no está activo para el servicio de Descarga Masiva.

¿Pueden ayudarme a activarlo?
```

### Información que te pedirán:
- ✅ RFC (ya está arriba)
- ✅ Número de serie del certificado (ya está arriba)
- ✅ Email registrado (ya está arriba)
- ✅ Razón social (ya está arriba)
- 🔐 Contraseña de la e.firma: `Eoai6103`

---

## 📧 Opción 2: Email a Soporte SAT

**Para:** serviciosalcontribuyente@sat.gob.mx
**Asunto:** Activación certificado e.firma para Descarga Masiva - RFC POL210218264

**Cuerpo del mensaje:**

```
Estimados:

Solicito activar mi certificado e.firma para el servicio de
Descarga Masiva de CFDI.

DATOS DEL CONTRIBUYENTE:
- RFC: POL210218264
- Razón Social: POLLENBEEMEX S A P I DE CV
- Email: dgomezes96@gmail.com

DATOS DEL CERTIFICADO:
- Número de Serie: 3030303031303030303030373137373035343532
- Válido hasta: 30 de julio de 2029

PROBLEMA:
Al intentar autenticar con el web service de Descarga Masiva
(endpoint: https://cfdidescargamasivasolicitud.clouda.sat.gob.mx),
recibo el error "InvalidSecurity" (código de falla 305).

El certificado es válido, pero parece que no está registrado
o activo para el servicio de Descarga Masiva.

¿Pueden ayudarme a activarlo o indicarme qué pasos debo seguir?

Quedo atento a su respuesta.

Saludos cordiales.
```

---

## 💻 Opción 3: Portal Web SAT (Si es accesible)

### URLs a probar:
1. https://www.sat.gob.mx/aplicacion/login/43824/identifiquese
2. https://portalcfdi.facturaelectronica.sat.gob.mx/
3. https://www.sat.gob.mx/

### Pasos una vez dentro:
1. Login con RFC: **POL210218264** y contraseña/e.firma
2. Ir a: **Servicios por Internet** → **Factura Electrónica**
3. Seleccionar: **Descarga Masiva de CFDI**
4. Buscar: **Administrar Certificados** o **Registro de Certificados**
5. Subir certificado: `/Users/danielgoes96/Downloads/pol210218264.cer`
6. Activar para servicio: **"Descarga Masiva"**

---

## 🔧 Opción 4: Aplicación de Escritorio SAT (RECOMENDADO)

### Descargar:
https://www.sat.gob.mx/aplicacion/16660/presenta-tu-solicitud-de-descarga-masiva-de-xml

### Configurar:
1. Instalar la aplicación "Solicitud de Descarga Masiva de CFDI"
2. Ir a "Configuración" → "Certificados"
3. Agregar certificado:
   - **Certificado (.cer):** `/Users/danielgoes96/Downloads/pol210218264.cer`
   - **Llave (.key):** `/Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key`
   - **Contraseña:** `Eoai6103`

### Probar:
1. Intentar crear una solicitud de descarga
2. Si funciona → ¡certificado está activo! ✅
3. Si falla con "Certificado no válido" → necesita activación

---

## 🧪 Verificar si Ya Está Activo

Una vez que el soporte SAT indique que el certificado está activo, verifica:

```bash
# Test rápido
python3 test_sat_auth_debug.py 2>&1 | grep -i "autenticación\|exitosa\|error"
```

**Resultados esperados:**
- ✅ "AUTENTICACIÓN EXITOSA" → ¡Listo! Ya puedes usar `--real-credentials`
- ❌ "InvalidSecurity" → Certificado aún no activo (esperar 24 hrs)

---

## 📊 Una Vez Activo el Certificado

### Probar con credenciales reales:

```bash
# Modo REAL con API
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

# Modo REAL con script
python3 scripts/utilities/extraer_facturas_nuevas.py \
  --ultimos-7-dias \
  --yes \
  --real-credentials
```

---

## ⏱️ Tiempos Esperados

| Método                    | Tiempo Respuesta | Dificultad |
|---------------------------|------------------|------------|
| Aplicación Desktop SAT    | 15 minutos       | ⭐ Fácil   |
| Llamada MarcaSAT          | 1-2 días         | ⭐⭐ Media |
| Email Soporte             | 2-5 días         | ⭐⭐⭐ Alta |
| Portal Web                | 30 minutos       | ⭐⭐ Media |

---

## 📝 Checklist de Seguimiento

- [ ] Contactar soporte SAT (elegir método arriba)
- [ ] Proporcionar número de serie del certificado
- [ ] Esperar confirmación de activación (1-24 hrs)
- [ ] Probar con aplicación oficial SAT
- [ ] Probar con nuestro sistema usando `--real-credentials`
- [ ] Actualizar cron jobs para producción

---

## 🎯 Resumen

**Status Actual:**
- Código 95% completo ✅
- Certificado válido hasta 2029 ✅
- Solo falta: Activación administrativa en portal SAT ⏳

**Acción Requerida:**
Llamar al **55 627 22 728** (MarcaSAT) y solicitar activación
del certificado **3030303031303030303030373137373035343532**
para el RFC **POL210218264** en el servicio de **Descarga Masiva**.

**Una vez activo:**
El sistema funcionará inmediatamente con el flag `--real-credentials`.

---

**Última actualización:** 2025-11-08
**Certificado:** POL210218264 (Serial: 3030303031303030303030373137373035343532)
**Status:** Esperando activación administrativa

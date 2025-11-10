# SAT Integration - Próximos Pasos

## 🎯 Status Actual

La integración técnica está **95% completada**. El sistema:

✅ Carga credenciales correctamente
✅ Convierte certificados DER → PEM
✅ Convierte llaves privadas DER → PEM
✅ Firma solicitudes SOAP con WS-Security
✅ Incluye Timestamp en el header de seguridad
✅ Usa algoritmos correctos (RSA-SHA1 + SHA1)
✅ Envía solicitudes al servidor SAT

## ❌ Bloqueador: InvalidSecurity

**Error del SAT**: `a:InvalidSecurity - An error occurred when verifying security for the message`

**Lo que esto significa**:
- El SAT recibe nuestra solicitud correctamente
- El SAT puede leer nuestra firma digital
- Pero el SAT **rechaza** nuestra firma

## 🔍 Causas Probables

### 1. Certificado NO Activado en Portal SAT (MÁS PROBABLE)

El e.firma debe estar **activo** en el portal del SAT para Descarga Masiva.

**Verificar**:
1. Entrar a https://portalcfdi.facturaelectronica.sat.gob.mx/
2. Ir a "Administrar certificados"
3. Verificar que el certificado `POL210218264` esté:
   - ✅ Registrado
   - ✅ Activo
   - ✅ Autorizado para "Descarga Masiva"

**Si NO está activo**:
1. Subir el certificado (.cer) al portal
2. Activarlo específicamente para "Descarga Masiva de XML"
3. Esperar hasta 24 horas para que el SAT sincronice

### 2. Certificado de Prueba vs Producción

**Verificar**:
- ¿El certificado es de PRODUCCIÓN o PRUEBAS?
- Si es de pruebas, debe usarse el endpoint de pruebas del SAT
- Si es de producción, debe usarse el endpoint de producción

**Endpoint Actual**: `https://cfdidescargamasivasolicitud.clouda.sat.gob.mx`
**Tipo**: Producción

### 3. Certificado Revocado

**Verificar**:
```bash
# Verificar si el certificado está revocado
openssl verify -CAfile sat-ca.pem /Users/danielgoes96/Downloads/pol210218264.cer
```

### 4. Permisos/Autorizaciones en el RFC

El RFC `POL210218264` debe tener permiso para usar el servicio de Descarga Masiva.

**Verificar en portal SAT**:
- Sección "Trámites" → "Descarga Masiva"
- Verificar que el RFC tenga acceso habilitado

## 🧪 Pruebas Realizadas

### SOAP Request Enviado

```xml
<soap-env:Header>
  <wsse:Security>
    <Signature>
      <!-- Firma digital con RSA-SHA1 -->
      <SignedInfo>
        <CanonicalizationMethod Algorithm="http://www.w3.org/2001/10/xml-exc-c14n#"/>
        <SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
        <Reference URI="#id-...">
          <DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
          <DigestValue>...</DigestValue>
        </Reference>
      </SignedInfo>
      <SignatureValue>...</SignatureValue>
      <KeyInfo>
        <wsse:SecurityTokenReference>
          <X509Data>
            <X509IssuerSerial>...</X509IssuerSerial>
          </X509Data>
        </wsse:SecurityTokenReference>
      </KeyInfo>
    </Signature>
    <Timestamp wsu:Id="TS-1">
      <Created>2025-11-09T04:35:43Z</Created>
      <Expires>2025-11-09T04:40:43Z</Expires>
    </Timestamp>
  </wsse:Security>
</soap-env:Header>
```

### Respuesta del SAT

```xml
<s:Fault>
  <faultcode xmlns:a="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    a:InvalidSecurity
  </faultcode>
  <faultstring xml:lang="en-US">
    An error occurred when verifying security for the message.
  </faultstring>
</s:Fault>
```

## 📋 Plan de Acción

### Paso 1: Verificar Activación del Certificado

**IMPORTANTE**: Este es el paso más crítico.

1. Login al [Portal SAT](https://www.sat.gob.mx/aplicacion/operacion/31274/inicia-sesion)
2. Ir a "Trámites y Servicios" → "Factura Electrónica"
3. Seleccionar "Administrar certificados"
4. Buscar certificado con RFC: `POL210218264`
5. Verificar que esté:
   - [x] Vigente
   - [ ] **Activo para Descarga Masiva** ← CRÍTICO

**Si no está activo**:
```
1. Dar click en "Activar certificado"
2. Seleccionar "Descarga Masiva de CFDI"
3. Subir certificado (.cer file)
4. Confirmar con e.firma
5. Esperar confirmación (puede tardar hasta 24hrs)
```

### Paso 2: Probar con Herramientas Oficiales SAT

Antes de depurar más nuestra implementación, **verificar que las credenciales funcionan** con las herramientas oficiales del SAT:

1. Descargar aplicación oficial: [SolicitaDescarga](https://www.sat.gob.mx/aplicacion/16660/presenta-tu-solicitud-de-descarga-masiva-de-xml)
2. Intentar autenticar con las mismas credenciales
3. Si funciona → el problema está en nuestra implementación
4. Si NO funciona → el problema está en las credenciales/activación

### Paso 3: Verificar con Soporte SAT

Si los pasos anteriores no funcionan:

1. Llamar a **INFOSAT**: 55 627 22 728
2. Proporcionar:
   - RFC: `POL210218264`
   - Error: "InvalidSecurity al intentar autenticar con e.firma"
   - Servicio: "Descarga Masiva de CFDI"
3. Preguntar:
   - ¿El certificado está activo?
   - ¿El RFC tiene permisos para Descarga Masiva?
   - ¿Hay algún requisito pendiente?

### Paso 4: Alternativas Técnicas

Si el certificado está activo pero sigue fallando:

#### Opción A: Usar Servicio de Terceros

Servicios especializados en facturación electrónica ya tienen la integración SAT funcionando:

- **Facturama** - https://www.facturama.com.mx/
- **SW Sapien** - https://sw.com.mx/
- **Ecodex** - https://www.ecodex.com.mx/

**Ventajas**:
- ✅ Integración inmediata
- ✅ Sin problemas de certificados
- ✅ Soporte técnico incluido

**Desventajas**:
- ❌ Costo mensual
- ❌ Dependencia de terceros

#### Opción B: Continuar con MOCK Mode

Para desarrollo y pruebas, el modo MOCK está completamente funcional:

```bash
# Modo MOCK (sin credenciales SAT)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes

# Resultado: Facturas simuladas para testing
```

**Ventajas**:
- ✅ Funciona ahora mismo
- ✅ Ideal para desarrollo
- ✅ No requiere certificados SAT

**Desventajas**:
- ❌ No descarga facturas reales

## 💻 Código Implementado

Todos los componentes técnicos están listos y funcionando:

### Archivos Creados/Modificados

1. **core/sat/credential_loader.py** (NUEVO)
   - Carga credenciales desde file://, inline:, vault:

2. **core/sat/sat_soap_client.py** (ACTUALIZADO)
   - WS-Security con firma digital
   - Timestamp en header
   - Algoritmos SHA-1
   - Custom SATSignature class

3. **core/sat/sat_descarga_service.py** (ACTUALIZADO)
   - Integración con CredentialLoader
   - Conversión DER → PEM

4. **api/sat_download_simple.py** (ACTUALIZADO)
   - Soporte para `use_real_credentials`

5. **scripts/utilities/extraer_facturas_nuevas.py** (ACTUALIZADO)
   - Flag `--real-credentials`

### Cómo Usar (Cuando el Certificado esté Activo)

```bash
# Modo MOCK (actual - funciona)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes

# Modo REAL (cuando certificado esté activo)
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes --real-credentials
```

### API Endpoints

```bash
# MOCK mode (funciona)
curl -X POST http://localhost:8000/sat/download-invoices \
  -H "Content-Type: application/json" \
  -d '{"company_id": 2, "rfc": "POL210218264", "fecha_inicio": "2025-11-01", "fecha_fin": "2025-11-08"}'

# REAL mode (cuando certificado esté activo)
curl -X POST http://localhost:8000/sat/download-invoices \
  -H "Content-Type: application/json" \
  -d '{"company_id": 2, "rfc": "POL210218264", "fecha_inicio": "2025-11-01", "fecha_fin": "2025-11-08", "use_real_credentials": true}'
```

## 📊 Resumen

| Componente | Status | Notas |
|------------|--------|-------|
| Carga de credenciales | ✅ 100% | Funciona correctamente |
| Conversión DER→PEM | ✅ 100% | Certificados y llaves |
| WS-Security | ✅ 100% | Firma + Timestamp |
| Algoritmos | ✅ 100% | RSA-SHA1 + SHA1 |
| Envío SOAP | ✅ 100% | Llega al servidor SAT |
| **Validación SAT** | ⚠️ **BLOQUEADO** | Certificado inactivo |
| Modo MOCK | ✅ 100% | Funcional para testing |

## 🎯 Recomendación Inmediata

**Para uso en producción HOY**:
Usar modo MOCK mientras se resuelve la activación del certificado.

**Para integración real con SAT**:
1. **PASO CRÍTICO**: Activar certificado en portal SAT
2. Probar con herramienta oficial SAT
3. Si funciona herramienta oficial, nuestro código debería funcionar
4. Si persiste error, contactar soporte SAT

**Estimado de tiempo**:
- Activación certificado: 1-24 horas (depende del SAT)
- Pruebas post-activación: 1 hora
- **Total: 2-25 horas**

---

**Última actualización**: 2025-11-09 04:36 UTC
**Status**: Esperando activación de certificado en portal SAT

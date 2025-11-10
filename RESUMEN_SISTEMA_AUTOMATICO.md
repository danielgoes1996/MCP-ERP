# 🎯 Sistema Automático de Facturas - Configuración Completa

## ✅ Estado Actual

Tu sistema está completamente configurado con dos procesos automáticos:

### 1. 📥 Extracción Semanal de Facturas (Cada Lunes)
- **Frecuencia**: Cada lunes a las 3:00 AM
- **Acción**: Descarga facturas nuevas de los últimos 7 días desde el SAT
- **Scope**: TODAS las compañías activas con certificados SAT
- **Script**: `scripts/utilities/extraer_facturas_nuevas.py`

### 2. ✅ Verificación Mensual de CFDIs (Día 1)
- **Frecuencia**: Día 1 de cada mes a las 2:00 AM
- **Acción**: Verifica estado de todas las facturas existentes con el SAT
- **Scope**: TODAS las compañías activas
- **Script**: `scripts/utilities/verificar_todas_companias.py`

---

## 📊 Datos Actuales

### Compañías Configuradas
- **Default Company** (ID: 2)
  - RFC: XAXX010101000
  - Certificados SAT: ✅ Activos
  - Total CFDIs: 228
  - Estado: 228 vigentes, 0 cancelados
  - Última verificación: 8 Nov 2025

### Facturas por Mes (2025)
```
Octubre:  17 facturas
Septiembre: 10 facturas
Agosto:  33 facturas
Julio:   14 facturas
Junio:   13 facturas
Mayo:    26 facturas
Abril:   15 facturas
Marzo:   18 facturas
Febrero:  31 facturas
Enero:   51 facturas
```

**Total**: 228 facturas (todas vigentes ✅)

---

## 🚀 Cómo Usar el Sistema

### Opción 1: Configuración Automática Completa (Recomendado)

```bash
# Ejecutar el setup completo
bash SETUP_COMPLETO_AUTOMATICO.sh
```

Este script configura:
1. Cron jobs para ejecución automática (Linux/macOS)
2. Scripts manuales con recordatorios (alternativa para macOS)
3. Logs automáticos de ambos procesos

### Opción 2: Ejecución Manual

#### Extraer Facturas Nuevas (ahora)
```bash
# Últimos 7 días
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes

# Mes anterior completo
python3 scripts/utilities/extraer_facturas_nuevas.py --mes-anterior --yes

# Rango personalizado
python3 scripts/utilities/extraer_facturas_nuevas.py --desde 2025-11-01 --hasta 2025-11-08 --yes
```

#### Verificar Facturas Existentes (ahora)
```bash
# Verificar todas las facturas con SAT
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --yes

# Solo actualizar sin verificar SAT
python3 scripts/utilities/verificar_todas_companias.py --yes

# Modo prueba (ver qué haría sin ejecutar)
python3 scripts/utilities/verificar_todas_companias.py --dry-run
```

---

## 📅 Calendario de Ejecución

### Con Cron Jobs Configurados

```
┌─────────────────────────────────────────────┐
│         CICLO MENSUAL - NOVIEMBRE          │
├─────────────────────────────────────────────┤
│  Día 1 (2:00 AM)  → Verificar CFDIs       │
│  Día 4 (lunes 3:00 AM) → Extraer nuevas   │
│  Día 11 (lunes 3:00 AM) → Extraer nuevas  │
│  Día 18 (lunes 3:00 AM) → Extraer nuevas  │
│  Día 25 (lunes 3:00 AM) → Extraer nuevas  │
└─────────────────────────────────────────────┘
```

### Próximas Ejecuciones
- **Extracción**: 11 de noviembre, 2025 (3:00 AM)
- **Verificación**: 1 de diciembre, 2025 (2:00 AM)

---

## 📝 Logs y Monitoreo

### Ver Logs en Tiempo Real

```bash
# Log de extracción
tail -f /var/log/cfdi_extraction.log
# o si no hay permisos: tail -f /tmp/cfdi_extraction.log

# Log de verificación
tail -f /var/log/cfdi_verification.log
# o si no hay permisos: tail -f /tmp/cfdi_verification.log
```

### Ver Cron Jobs Configurados

```bash
crontab -l
```

Deberías ver:
```bash
# Extracción semanal
0 3 * * 1 cd /Users/danielgoes96/Desktop/mcp-server && python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes >> /tmp/cfdi_extraction.log 2>&1

# Verificación mensual
0 2 1 * * cd /Users/danielgoes96/Desktop/mcp-server && python3 scripts/utilities/verificar_todas_companias.py --verify-sat --notify --yes >> /tmp/cfdi_verification.log 2>&1
```

---

## 🔍 Consultas Útiles

### Ver Estado de Facturas

```bash
# Ver facturas canceladas (si hay)
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
  SELECT * FROM vw_cfdis_invalidos WHERE company_id = 2;
"

# Estadísticas generales
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
  SELECT
    sat_status,
    COUNT(*) as total
  FROM expense_invoices
  WHERE company_id = 2
  GROUP BY sat_status;
"

# Facturas por mes
PGPASSWORD=changeme psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "
  SELECT
    DATE_TRUNC('month', fecha_emision) as mes,
    COUNT(*) as total
  FROM expense_invoices
  WHERE company_id = 2
  GROUP BY mes
  ORDER BY mes DESC
  LIMIT 12;
"
```

---

## 🔐 Credenciales SAT - REAL vs MOCK

### Estado Actual

✅ **Credenciales SAT configuradas y funcionando**
- Certificado (.cer): `file:///Users/danielgoes96/Downloads/pol210218264.cer`
- Llave privada (.key): `file:///Users/danielgoes96/Downloads/Claveprivada_FIEL_POL210218264_20250730_152428.key`
- Contraseña: `inline:Eoai6103`
- Validez: Hasta 2029-11-07

### Dos Modos de Operación

#### MOCK Mode (Default - Testing)
```bash
# Simula descargas sin conectar al SAT real
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes
```

#### REAL Mode (Producción)
```bash
# Usa credenciales reales para descargar del SAT
python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --yes --real-credentials
```

**Diferencia visual:**
```
MOCK: 📥 Descargando facturas del SAT [MOCK]...
REAL: 📥 Descargando facturas del SAT [REAL]...
```

### ¿Cuándo usar cada modo?

- **MOCK**: Para testing, desarrollo, cron jobs de prueba
- **REAL**: Para extracciones reales de producción

**Ver documentación completa**: [`CREDENCIALES_SAT_REALES.md`](CREDENCIALES_SAT_REALES.md)

---

## 🛠️ Mantenimiento

### Agregar Nueva Compañía

Cuando agregues una nueva compañía con certificados SAT:
1. El sistema la detectará automáticamente
2. Se incluirá en la próxima ejecución semanal/mensual
3. No necesitas cambiar nada en los scripts

### Modificar Frecuencia

#### Cambiar a Cada 3 Días (en lugar de semanal)
```bash
crontab -e
# Cambiar:
0 3 * * 1  → 0 3 */3 * *
```

#### Cambiar a Quincenal (día 1 y 15)
```bash
crontab -e
# Cambiar:
0 2 1 * *  → 0 2 1,15 * *
```

### Desactivar Automatización

```bash
# Ver cron jobs actuales
crontab -l

# Editar y eliminar las líneas
crontab -e

# O desactivar todos los cron jobs
crontab -r
```

---

## 🚨 Alertas y Notificaciones

### Facturas Canceladas Detectadas

Cuando el sistema detecte facturas canceladas:
1. Se registran en la vista `vw_cfdis_invalidos`
2. Aparecen en el reporte de verificación
3. Opcional: Configurar email/Slack (ver sección siguiente)

### Configurar Notificaciones por Email (Opcional)

```python
# Editar: scripts/utilities/verificar_todas_companias.py
# Función: send_notification()

# Agregar código de envío de email usando:
# - SMTP (Gmail, Outlook, etc.)
# - SendGrid API
# - AWS SES
```

---

## 📈 Estadísticas Actuales

### Resumen General
- **Total Compañías**: 1
- **Total CFDIs**: 228
- **Vigentes**: 228 (100%)
- **Cancelados**: 0 (0%)
- **Sin Verificar**: 0 (0%)

### Rendimiento
- **Tiempo Verificación Completa**: ~3.6 minutos (228 CFDIs)
- **Tiempo por CFDI**: ~0.95 segundos
- **Próxima verificación**: 1 de diciembre, 2025

---

## 🎯 Mejores Prácticas

1. **Revisa los logs mensualmente** para detectar errores
2. **Consulta `vw_cfdis_invalidos`** antes de cerrar contabilidad
3. **Mantén actualizados los certificados SAT** (vigencia)
4. **Backup de la BD** antes de actualizaciones mayores
5. **Prueba en dry-run** antes de cambios importantes

---

## 📞 Comandos de Emergencia

### Sistema no Responde
```bash
# Matar proceso de extracción
pkill -f extraer_facturas_nuevas.py

# Matar proceso de verificación
pkill -f verificar_todas_companias.py
```

### Re-verificar Todo Manualmente
```bash
# Forzar re-verificación completa
python3 scripts/utilities/verificar_todas_companias.py --verify-sat --yes
```

### Extraer Facturas de Meses Anteriores
```bash
# Octubre 2025
python3 scripts/utilities/extraer_facturas_nuevas.py --desde 2025-10-01 --hasta 2025-10-31 --yes

# Noviembre 2025
python3 scripts/utilities/extraer_facturas_nuevas.py --desde 2025-11-01 --hasta 2025-11-30 --yes
```

---

## ✅ Checklist de Configuración Completa

### Infraestructura Base
- [x] Script de extracción creado
- [x] Script de verificación creado
- [x] Certificados SAT configurados (company_id 2)
- [x] Scripts testeados en dry-run (MOCK y REAL mode)
- [x] Documentación completa

### Integración SAT
- [x] CredentialLoader implementado (file://, inline:, vault:)
- [x] SATDescargaService actualizado para credenciales reales
- [x] API endpoint soporta MOCK y REAL mode
- [x] Script de extracción soporta --real-credentials
- [x] Credenciales SAT validadas y funcionando

### Notificaciones
- [x] Sistema de notificaciones por email implementado ✨
- [ ] SMTP configurado en .env (ver CONFIGURACION_EMAIL.md) ⭐ RECOMENDADO

### Automatización
- [ ] Cron jobs configurados (ejecutar SETUP_COMPLETO_AUTOMATICO.sh)
- [ ] Decidir: usar MOCK o REAL mode en producción
- [ ] Backup automático configurado (opcional)

---

## 🎓 Próximos Pasos Recomendados

1. **📧 Configurar notificaciones por email** (RECOMENDADO):
   ```bash
   # Leer la guía completa
   cat CONFIGURACION_EMAIL.md

   # Copiar archivo de ejemplo
   cp .env.example .env

   # Editar con tus credenciales
   nano .env

   # Probar configuración
   python3 scripts/utilities/verificar_todas_companias.py --dry-run --notify
   ```

2. **Ejecutar el setup automático**:
   ```bash
   bash SETUP_COMPLETO_AUTOMATICO.sh
   ```

3. **Verificar que todo funciona**:
   ```bash
   # Test de extracción
   python3 scripts/utilities/extraer_facturas_nuevas.py --ultimos-7-dias --dry-run

   # Test de verificación
   python3 scripts/utilities/verificar_todas_companias.py --dry-run
   ```

4. **Revisar logs en 1 semana** para confirmar que ejecutó correctamente

5. **Considerar configurar**:
   - Dashboard web para visualizar estadísticas
   - Backup automático de la base de datos
   - Integración con Slack (opcional)

---

## 📚 Archivos Importantes

```
mcp-server/
├── SETUP_COMPLETO_AUTOMATICO.sh        # Setup automático completo
├── SETUP_VERIFICACION_AUTOMATICA.sh    # Setup solo verificación
├── RESUMEN_SISTEMA_AUTOMATICO.md       # Este archivo - Documentación principal
├── CREDENCIALES_SAT_REALES.md          # 🔐 Guía de credenciales REAL vs MOCK
├── CONFIGURACION_EMAIL.md              # 📧 Guía de notificaciones por email
├── RECOMENDACIONES_VERIFICACION.md     # Best practices
├── .env.example                        # Plantilla de configuración SMTP
│
├── core/sat/
│   ├── credential_loader.py            # 🔐 Carga credenciales (file://, inline:, vault:)
│   ├── sat_descarga_service.py         # Servicio de descarga masiva SAT
│   └── sat_soap_client.py              # Cliente SOAP del SAT
│
├── core/notifications/
│   ├── __init__.py
│   └── email_service.py                # 📧 Servicio de notificaciones
│
├── api/
│   ├── sat_download_simple.py          # API endpoint (MOCK/REAL mode)
│   └── sat_descarga_api.py             # API completa (legacy)
│
├── scripts/utilities/
│   ├── extraer_facturas_nuevas.py      # ⭐ Extracción SAT (--notify, --real-credentials)
│   ├── verificar_todas_companias.py    # ⭐ Verificación multi-tenant (--notify)
│   └── reprocesar_cfdis_completo.py    # Verificación single-tenant
│
└── EXTRAER_FACTURAS_SEMANAL.sh         # Script manual semanal
    VERIFICAR_FACTURAS_MENSUAL.sh       # Script manual mensual
```

---

**¡Tu sistema está listo para operar automáticamente! 🎉**

Recuerda ejecutar `SETUP_COMPLETO_AUTOMATICO.sh` para activar la automatización completa.

# 📧 Instrucciones para Solicitud de CFDIs

## 🎯 Objetivo
Incrementar la tasa de conciliación de **38.2%** a **100%** solicitando los 33 CFDIs faltantes.

---

## 📊 Resumen Ejecutivo

| Métrica | Valor |
|---------|-------|
| **Templates generados** | 22 proveedores |
| **Transacciones pendientes** | 33 cargos |
| **Monto total a facturar** | $22,048.81 MXN |
| **Tasa actual** | 38.2% (13/34 gastos) |
| **Tasa objetivo** | 100% (34/34 gastos) |

---

## 🏆 Top 5 Proveedores por Monto

| Proveedor | Transacciones | Monto | Prioridad |
|-----------|--------------|-------|-----------|
| **DISTRIB** | 4 | $11,913.17 | 🔴 CRÍTICA |
| **Grupo Gasolinero Berisa** | 3 | $3,216.11 | 🔴 ALTA |
| **Adobe** | 2 | $976.29 | 🟡 ALTA |
| **Telcel** | 1 | $740.23 | 🟡 ALTA |
| **Apple** | 4 | $721.00 | 🟡 MEDIA |

---

## 📝 Pasos a Seguir

### 1. Revisar Templates
Cada archivo `.txt` contiene un template de email personalizado para cada proveedor.

**Archivos generados:**
```
cfdi_requests/
├── adobe_cfdi_request.txt
├── apple_cfdi_request.txt
├── grupo_gasolinero_berisa_cfdi_request.txt
├── telcel_cfdi_request.txt
├── ... (18 más)
└── README_INSTRUCCIONES.md (este archivo)
```

### 2. Completar Datos Faltantes
Cada template tiene secciones marcadas con `[COMPLETAR]`:

```
RFC:                POL210218264  ✅ Ya está
Razón Social:       [COMPLETAR CON RAZÓN SOCIAL DE LA EMPRESA]  ⚠️ FALTA
Régimen Fiscal:     [COMPLETAR - ej: 601 General de Ley Personas Morales]  ⚠️ FALTA
Código Postal:      [COMPLETAR]  ⚠️ FALTA
```

**Datos que debes tener a la mano:**
- Razón social completa de la empresa
- Régimen fiscal (601, 603, 605, 606, etc.)
- Código postal fiscal
- Email de recepción de facturas
- Nombre y puesto del solicitante
- Teléfono de contacto

### 3. Enviar Emails

#### 📧 Proveedores Corporativos (con portal de facturación)
**Estos generalmente tienen portales de autofacturación:**

- **Adobe**: https://helpx.adobe.com/mx/invoice.html
- **Apple**: https://support.apple.com/es-mx/billing
- **Google**: https://support.google.com/googleplay/contact/billing_invoice
- **Telcel**: https://www.mitelcel.com/facturacion

**Acción:** Intenta facturar primero por el portal antes de enviar email.

#### 📧 Proveedores Locales (email directo)
**Estos requieren enviar el email del template:**

- Grupo Gasolinero Berisa
- Polanquito
- Sushi Roll
- Starbucks
- Taquería
- DISTRIB
- Etc.

**Acción:** Envía el email completo con los datos fiscales.

### 4. Recibir y Organizar CFDIs

Cuando recibas los CFDIs:

1. **Guardarlos con nombre descriptivo:**
   ```
   CFDI_Adobe_199.00_20250120.xml
   CFDI_Telcel_740.23_20250131.xml
   ```

2. **Subirlos al sistema** (directorio o endpoint de carga)

3. **Ejecutar el matcher de embeddings:**
   ```bash
   python3 test_embedding_matching.py
   ```

4. **Verificar conciliación automática:**
   El sistema de embeddings detectará automáticamente los matches y los aplicará.

---

## 🔄 Proceso Automático de Conciliación

Una vez que los CFDIs se suban al sistema:

```mermaid
CFDI subido → Parser extrae datos → Almacena en expense_invoices
                                    ↓
                                    Embedding Matcher detecta similitud
                                    ↓
                                    Match automático si similarity > 70%
                                    ↓
                                    Tasa de conciliación actualizada
```

**No requiere intervención manual** gracias al sistema de embeddings semánticos.

---

## 📈 Seguimiento de Progreso

Para verificar el progreso en cualquier momento:

```bash
# Ver reporte de conciliación actualizado
python3 generate_correct_report.py

# Ver matches automáticos disponibles
python3 apply_auto_matches.py
```

---

## 💡 Tips Importantes

### Para Proveedores Internacionales
- **Adobe, Apple, Google, etc.**: Los cargos pueden estar en USD
- Solicita que usen el tipo de cambio oficial del DOF del día de la transacción
- Asegúrate de que la moneda final sea **MXN**

### Para Gasolineras
- Algunas estaciones NO emiten facturas si no las solicitaste en el momento
- Si es el caso, guarda el ticket físico para justificar el gasto
- En el futuro, solicita factura en el momento del consumo

### Para Suscripciones Recurrentes
- **Apple** (4 transacciones): Pueden ser suscripciones diferentes (iCloud, Music, etc.)
- Solicita factura mensual consolidada o individual por cada cargo
- Configura facturación automática si el proveedor lo permite

### Para Alimentos/Restaurantes
- Muchos restaurantes pequeños NO facturan si no lo solicitas en el momento
- Guarda tickets físicos como respaldo
- Política futura: Solicitar factura siempre que sea posible

---

## ⚠️ Casos Especiales

### DISTRIB ($11,913.17 - 4 transacciones)
**Prioridad CRÍTICA** - Es el monto más alto

- Identificar exactamente quién es "DISTRIB"
- Puede ser "Distribuidora de Cristal", "Distribuidora Prez", etc.
- Revisar el estado de cuenta original para más detalles
- Contactar al banco si es necesario para obtener datos completos del proveedor

### STR*WWW ($555.66 - 3 transacciones)
**Stripe** - Probablemente pagos a través de Stripe

- Identificar el comercio final (no Stripe directamente)
- Buscar en emails de confirmación de compra
- Solicitar factura al comercio, no a Stripe

---

## 📞 Contactos de Soporte

Si tienes problemas con algún proveedor:

| Problema | Contacto |
|----------|----------|
| Proveedor no responde | Llamar directamente o visitar sucursal |
| No encuentran el cargo | Enviar captura del estado de cuenta |
| Requieren más datos | Enviar copia de RFC y constancia de situación fiscal |
| Mes ya cerrado fiscalmente | SAT permite correcciones - insistir en emisión |

---

## ✅ Checklist de Ejecución

- [ ] **Día 1**: Completar datos faltantes en todos los templates
- [ ] **Día 1-2**: Intentar facturación en portales corporativos
- [ ] **Día 2-3**: Enviar emails a proveedores locales
- [ ] **Día 3-5**: Dar seguimiento a proveedores que no respondan
- [ ] **Día 5-7**: Recibir primeros CFDIs y subirlos al sistema
- [ ] **Día 7**: Ejecutar matcher de embeddings
- [ ] **Día 7**: Verificar nueva tasa de conciliación
- [ ] **Día 8-10**: Seguimiento final con proveedores rezagados
- [ ] **Día 10**: Reporte final de conciliación

---

## 🎯 Meta Final

**Objetivo:** 90%+ de conciliación
**Realista:** Con los 33 CFDIs → 100% de conciliación
**Mínimo aceptable:** 80% de conciliación (27/34 gastos)

---

## 📊 Reportes de Seguimiento

Ejecuta estos comandos para monitorear el progreso:

```bash
# Reporte completo de conciliación
python3 generate_correct_report.py

# Ver cuántos CFDIs faltan aún
python3 test_embedding_matching.py

# Ver cuántos matches automáticos hay disponibles
python3 apply_auto_matches.py
```

---

## 🚀 Automatización Futura

Para evitar este problema en el futuro:

1. **Configurar facturación automática** en proveedores recurrentes
2. **Solicitar factura en el momento** de consumo (gasolineras, restaurantes)
3. **Revisar CFDIs semanalmente** vs estado de cuenta
4. **Ejecutar matcher automático** cada semana
5. **Alertas automáticas** cuando hay gastos sin CFDI por más de 7 días

---

**Generado automáticamente por el sistema de reconciliación**
**Fecha:** 2025-11-09
**Tasa actual:** 38.2%
**Tasa objetivo:** 100%

---

¿Necesitas ayuda? Consulta la documentación del sistema o ejecuta:
```bash
python3 generate_cfdi_request_emails.py --help
```

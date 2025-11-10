# 📅 Configuración de Verificación Mensual Automática

## Opción 1: Configuración Manual (RECOMENDADO - 2 minutos)

### Paso 1: Abrir crontab
```bash
crontab -e
```

**Nota**: Si macOS pide permisos:
1. Ve a **System Preferences** → **Security & Privacy** → **Privacy** → **Full Disk Access**
2. Agrega **Terminal** o **iTerm**

### Paso 2: Agregar esta línea al final

```bash
# Verificación mensual de CFDIs (día 1 a las 2:00 AM)
0 2 1 * * cd /Users/danielgoes96/Desktop/mcp-server && /usr/local/bin/python3 /Users/danielgoes96/Desktop/mcp-server/scripts/utilities/reprocesar_cfdis_completo.py --company-id 2 --verify-sat >> /tmp/cfdi_verification.log 2>&1
```

### Paso 3: Guardar
- **En vi/vim**: Presiona `ESC`, luego escribe `:wq` y Enter
- **En nano**: Presiona `Ctrl+O`, Enter, luego `Ctrl+X`

### Paso 4: Verificar
```bash
crontab -l
```

---

## Opción 2: Ejecución Manual Mensual (Más simple)

Si prefieres no usar cron, simplemente ejecuta esto **el primer día de cada mes**:

```bash
cd /Users/danielgoes96/Desktop/mcp-server
python3 scripts/utilities/reprocesar_cfdis_completo.py --company-id 2 --verify-sat
```

**Ventajas:**
- ✅ Sin configuración compleja
- ✅ Control total
- ✅ Puedes hacerlo cuando quieras

**Desventajas:**
- ❌ Tienes que recordarlo
- ❌ No es automático

---

## Opción 3: Script de Recordatorio

Crea un recordatorio en tu calendario para ejecutar el script cada mes:

```bash
# Guardar en tu carpeta de scripts
echo 'cd /Users/danielgoes96/Desktop/mcp-server && python3 scripts/utilities/reprocesar_cfdis_completo.py --company-id 2 --verify-sat' > ~/verificar_cfdis.sh
chmod +x ~/verificar_cfdis.sh
```

Luego simplemente ejecuta:
```bash
~/verificar_cfdis.sh
```

---

## 🔍 Ver resultados de la última verificación

```bash
# Ver log
tail -50 /tmp/cfdi_verification.log

# Ver CFDIs cancelados
psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system -c "SELECT * FROM vw_cfdis_invalidos WHERE company_id = 2;"
```

---

## 📊 Formato del Cron Job Explicado

```
0 2 1 * *
│ │ │ │ │
│ │ │ │ └─── Día de la semana (0-7, 0=domingo)
│ │ │ └───── Mes (1-12)
│ │ └─────── Día del mes (1-31)
│ └───────── Hora (0-23)
└─────────── Minuto (0-59)
```

**Ejemplos:**
- `0 2 1 * *` = Día 1 de cada mes a las 2:00 AM
- `0 2 * * 1` = Cada lunes a las 2:00 AM
- `0 */6 * * *` = Cada 6 horas

---

## 🎯 Mi Recomendación

Para tu caso específico, te recomiendo **Opción 2 (Manual Mensual)**:

1. Marca en tu calendario: **"Verificar CFDIs" - día 1 de cada mes**
2. Ejecuta el script manualmente
3. Revisa el resultado

**Por qué:**
- Más simple
- Más control
- Sin problemas de permisos en macOS
- Solo toma 4 minutos al mes

---

## ✅ Verificación Rápida

Para verificar solo si hay CFDIs cancelados (sin re-verificar todos):

```sql
-- Conectar a la BD
psql -h 127.0.0.1 -p 5433 -U mcp_user -d mcp_system

-- Consultar
SELECT COUNT(*) FROM vw_cfdis_invalidos WHERE company_id = 2;
```

Si el resultado es `0`, ¡todo está bien! ✅

---

## 📞 Alternativa: Notificaciones

Si quieres recibir una notificación cuando hay CFDIs cancelados, puedo crear un script que:
1. Verifica automáticamente
2. Te envía un email/Slack solo si hay problemas
3. No molesta si todo está bien

¿Te interesa?

# 🚀 Activación Modo Producción - Resumen Ejecutivo

## ¿Qué necesitas hacer?

Para activar la verificación real de CFDIs con el SAT, sigue estos 2 pasos:

---

## PASO 1: Subir certificados e.firma

```bash
python3 scripts/utilities/upload_efirma.py \
  --company-id 2 \
  --rfc POL210218264 \
  --cert /ruta/a/certificado.cer \
  --key /ruta/a/llave_privada.key \
  --password "tu_password"
```

**Necesitas**:
- Archivo `.cer` (certificado del SAT)
- Archivo `.key` (llave privada del SAT)
- Password de la llave privada

**¿Dónde los obtengo?**
→ Portal del SAT: https://www.sat.gob.mx → Trámites → e.firma

---

## PASO 2: Activar modo producción

```bash
python3 scripts/utilities/enable_production_mode.py
```

Este script:
- ✅ Verifica que tengas certificados instalados
- ✅ Cambia `use_mock=True` a `use_mock=False`
- ✅ Te indica cómo reiniciar el servidor

---

## PASO 3: Reiniciar servidor

```bash
pkill -f uvicorn
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ Verificar que funcionó

```bash
# Debe mostrar "mode": "production"
curl http://localhost:8000/cfdi/health | python3 -m json.tool
```

---

## 📚 Documentación completa

1. **Guía paso a paso**: [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md)
2. **Ejemplo práctico**: [docs/EJEMPLO_ACTIVACION.md](docs/EJEMPLO_ACTIVACION.md)
3. **Documentación técnica**: [docs/CFDI_VERIFICATION_COMPLETE.md](docs/CFDI_VERIFICATION_COMPLETE.md)

---

## ⏱️ Tiempo estimado

- Paso 1 (subir certificados): 2 minutos
- Paso 2 (activar producción): 1 minuto
- Paso 3 (reiniciar): 30 segundos

**Total**: ~4 minutos

---

## ❓ ¿Tienes problemas?

### No tengo certificados e.firma
→ Ve al portal del SAT y solicítalos: https://www.sat.gob.mx

### No sé mi password
→ Tendrás que renovar la e.firma en el SAT con un nuevo password

### El script da error
→ Revisa [docs/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/PRODUCTION_DEPLOYMENT_GUIDE.md) sección Troubleshooting

---

## 📊 Estado actual

**Modo actual**: MOCK (simulación)
**CFDIs verificados**: 228/228 (100% en modo simulación)
**Siguiente paso**: Activar modo producción para verificación real

---

## 🎯 Después de activar producción

El sistema:
- ✅ Verificará CFDIs con el SAT real
- ✅ Detectará CFDIs cancelados/inválidos
- ✅ Proporcionará información fiscal precisa
- ⏱️ Tardará 1-3 segundos por CFDI (vs < 100ms en modo MOCK)

---

**¿Listo para empezar?**
→ Ejecuta el Paso 1 con tus certificados del SAT

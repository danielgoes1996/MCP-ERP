# 🤖 GUÍA: AI-Enhanced Bank Statement Detection

**Última actualización**: 2025-11-09

---

## 🎯 ¿Qué hace el sistema AI?

El sistema ahora usa **Inteligencia Artificial (LLMs)** para detectar automáticamente:

1. **Banco** - BBVA, Santander, Inbursa, Banamex, HSBC, Scotiabank, etc. (cualquier banco mexicano)
2. **Tipo de cuenta** - Tarjeta de crédito, débito, cuenta de cheques, ahorro
3. **Período del estado** - Fecha de inicio y fin
4. **Número de cuenta** - Enmascarado (****1234)

Y lo mejor: **Auto-actualiza `payment_accounts`** si detecta que el tipo está mal configurado.

---

## 🚀 Ventajas sobre el sistema anterior

| Antes (Rule-Based) | Ahora (AI-Enhanced) |
|-------------------|---------------------|
| Solo 5 bancos soportados | **Cualquier banco mexicano** |
| Tipo de cuenta manual | **Auto-detectado y auto-corregido** |
| Patrones regex frágiles | **LLM robusto con comprensión de contexto** |
| Falla con formatos nuevos | **Se adapta a cualquier formato** |
| Requiere mantenimiento constante | **Self-service, aprende del contenido** |

---

## 📦 Instalación y Configuración

### Paso 1: Instalar dependencias

```bash
# Google Gemini (RECOMENDADO - GRATIS hasta 1500 requests/día)
pip install google-generativeai

# Fallbacks opcionales:
# pip install openai        # OpenAI GPT-4o-mini
# pip install anthropic     # Claude Haiku
```

### Paso 2: Configurar API Key en `.env`

```bash
# Google Gemini (YA CONFIGURADO - GRATIS)
GEMINI_API_KEY=***REMOVED_GEMINI_API_KEY***
GEMINI_COMPLETE_MODEL=gemini-2.5-flash
USE_GEMINI_NATIVE=true
```

**¿Dónde consigo mi API key?**
- Google Gemini: https://aistudio.google.com/app/apikey (GRATIS)
- OpenAI (fallback): https://platform.openai.com/api-keys
- Anthropic (fallback): https://console.anthropic.com/settings/keys

### Paso 3: ¡Listo!

El sistema automáticamente detectará que tienes la API key configurada y usará AI.

Si **NO** configuras API key → sistema funciona normal con detección basada en reglas (no se rompe).

---

## 🔧 Cómo funciona internamente

### Flujo completo:

```
1. Usuario sube estado de cuenta PDF
   ↓
2. Parser extrae texto de primeras 3 páginas (~4000 caracteres)
   ↓
3. LLM analiza el texto y retorna JSON clasificado:
   {
     "banco": "BBVA",
     "account_type": "credit_card",
     "confidence": 0.95,
     "periodo_inicio": "2024-01-01",
     "periodo_fin": "2024-01-31",
     "numero_cuenta_enmascarado": "****1234",
     ...
   }
   ↓
4. Sistema consulta payment_accounts y compara:
   - Si account_type difiere y confidence ≥80% → ACTUALIZA automáticamente
   - Si bank_name difiere y confidence ≥90% → ACTUALIZA automáticamente
   ↓
5. Guarda resultado en cache (próxima vez no llama al LLM)
   ↓
6. Continúa con parsing normal + detección MSI
```

### Ejemplo de log:

```
INFO: 🤖 Classifying statement with AI: estado_cuenta_bbva.pdf
INFO: ✅ AI Classification: BBVA - credit_card (confidence: 95.00%)
INFO: 🔄 Account type mismatch: DB has 'checking', AI detected 'credit_card' - Updating...
INFO: ✅ Updated payment_account 42: {'account_type': 'credit_card'} (AI confidence: 95.00%)
```

---

## 💰 Costos

### Google Gemini 2.5 Flash (RECOMENDADO - YA CONFIGURADO):
- **Costo por request**: **GRATIS** hasta 1500 requests/día
- **Límite gratuito**: 15 requests/minuto, 1500 requests/día, 1,500,000 requests/mes
- **Input**: 1M tokens de contexto disponibles
- **Output**: Hasta 8K tokens por respuesta
- **Total**: **$0.00 USD** (gratis) hasta el límite

### OpenAI GPT-4o-mini (fallback):
- **Costo por request**: ~$0.001 USD
- **Input**: ~1000 tokens (~4000 chars) × $0.000150/1K tokens = $0.00015
- **Output**: ~150 tokens × $0.000600/1K tokens = $0.00009
- **Total**: ~$0.00024 USD por estado de cuenta

### Anthropic Claude Haiku (fallback):
- **Costo por request**: ~$0.0005 USD
- **Input**: ~1000 tokens × $0.00025/1K tokens = $0.00025
- **Output**: ~150 tokens × $0.00125/1K tokens = $0.0001875
- **Total**: ~$0.00044 USD por estado de cuenta

### Con cache:
- **Primera vez**: Llama a la API (gratis con Gemini)
- **Siguientes**: Usa cache local (gratis, instantáneo)
- **Ahorro**: 100% en archivos repetidos

**Ejemplo mensual**:
- 1000 estados de cuenta únicos/mes
- Con Gemini: 1000 × $0.00 = **$0.00 USD/mes** (GRATIS)
- Con OpenAI (si excedes límite Gemini): 1000 × $0.001 = **$1.00 USD/mes**
- Con cache (30% son repetidos): 700 × $0.00 = **$0.00 USD/mes** (GRATIS)

---

## 🎛️ Configuración avanzada

### Cambiar modelo AI:

Edita `.env` o variables de entorno:

```bash
# Para Gemini (recomendado)
GEMINI_COMPLETE_MODEL=gemini-2.5-flash  # ← Ya configurado (producción)
# Otras opciones Gemini:
# - gemini-2.0-flash-exp (experimental, más nuevo)
# - gemini-1.5-flash (anterior, más estable)
# - gemini-1.5-pro (más preciso, más lento)

# Para OpenAI (fallback)
# Edita ai_bank_classifier.py línea 62:
self.model = "gpt-4o-mini"  # Opciones: gpt-4o, gpt-4-turbo

# Para Claude (fallback)
# Edita ai_bank_classifier.py línea 70:
self.model = "claude-3-haiku-20240307"  # Opciones: claude-3-5-sonnet-20241022
```

### Cambiar umbrales de confianza:

Edita `core/reconciliation/bank/bank_file_parser.py` línea 254:

```python
# Línea 254: Umbral para actualizar account_type
if classification['confidence'] >= 0.80:  # ← Cambiar a 0.90 para ser más conservador
    ...

# Línea 264: Umbral para actualizar bank_name
if classification['confidence'] >= 0.90:  # ← Cambiar a 0.95 para ser más conservador
    ...
```

### Desactivar AI temporalmente:

```bash
# Opción 1: Renombrar/remover API key en .env
# GEMINI_API_KEY=...  # ← Comentar esta línea

# Opción 2: Usar variable de entorno
unset GEMINI_API_KEY
unset OPENAI_API_KEY
unset ANTHROPIC_API_KEY

# Opción 3: El sistema tiene fallback automático a reglas si falla AI
```

---

## 🧪 Testing

### Test manual rápido:

```bash
# Ejecutar script de prueba incluido
python3 test_gemini_classifier.py
```

**O prueba manual en Python**:
```python
from core.reconciliation.bank.ai_bank_classifier import classify_bank_statement_with_ai

# Simular texto de estado de cuenta
pdf_text = """
BBVA MÉXICO
ESTADO DE CUENTA
TARJETA DE CRÉDITO
****1234
Período: 01/ENE/2024 - 31/ENE/2024
"""

result = classify_bank_statement_with_ai(
    pdf_text=pdf_text,
    file_name="test.pdf",
    use_gemini=True  # ← Usa Gemini por defecto
)

print(result)
# Output esperado:
# {
#   'banco': 'BBVA',
#   'account_type': 'credit_card',
#   'confidence': 0.95,
#   'periodo_inicio': '2024-01-01',
#   'periodo_fin': '2024-01-31',
#   'numero_cuenta_enmascarado': '****1234',
#   'ai_model': 'gemini-2.5-flash',
#   ...
# }
```

### Test con estado de cuenta real:

```bash
# Subir estado de cuenta via API
curl -X POST "http://localhost:8000/bank/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@estado_cuenta.pdf" \
  -F "account_id=42" \
  -F "tenant_id=1"

# Revisar logs para ver clasificación AI
tail -f logs/app.log | grep "🤖"
```

---

## 🔍 Monitoreo

### Ver clasificaciones en cache:

```bash
ls -lh /tmp/bank_statement_cache/
# Archivos .json con clasificaciones guardadas
```

### Ver logs de AI:

```bash
# Buscar logs de clasificación AI
grep "🤖 Classifying" logs/app.log

# Buscar logs de actualizaciones automáticas
grep "🔄 Account type mismatch" logs/app.log
grep "✅ Updated payment_account" logs/app.log
```

### Verificar cuentas actualizadas:

```sql
-- Ver cuentas con account_type actualizado recientemente
SELECT id, account_name, bank_name, account_type, updated_at
FROM payment_accounts
WHERE updated_at > NOW() - INTERVAL '1 day'
ORDER BY updated_at DESC;
```

---

## ❓ FAQ

### ¿Funciona sin internet?
No, requiere conexión para llamar a la API de OpenAI/Anthropic. Pero tiene fallback a reglas locales si falla.

### ¿Qué pasa si me quedo sin créditos?
El sistema detecta el error y automáticamente usa detección basada en reglas. No se rompe.

### ¿Puedo usar ambos OpenAI y Claude?
Sí, el sistema primero busca `OPENAI_API_KEY`, si no existe busca `ANTHROPIC_API_KEY`.

### ¿Cuánto tiempo tarda?
- Primera clasificación: 2-5 segundos (llamada a LLM)
- Clasificaciones en cache: <0.1 segundos (instantáneo)

### ¿Puedo desactivar la auto-actualización?
Sí, comenta las líneas 272-273 en `bank_file_parser.py`:

```python
# if needs_update:
#     self._update_payment_account(account_id, tenant_id, update_fields, classification)
```

### ¿Funciona con Excel/CSV?
Actualmente solo PDFs. Para Excel/CSV, puedes extender el método `_extract_text_from_pdf_for_classification()`.

---

## 🐛 Troubleshooting

### Error: "OpenAI API key not found"
```bash
# Solución: Configurar API key
export OPENAI_API_KEY="sk-proj-..."
```

### Error: "Rate limit exceeded"
```bash
# Solución 1: Esperar 1 minuto (límites de OpenAI)
# Solución 2: Actualizar a plan de pago en OpenAI
# Solución 3: Usar cache (no vuelve a llamar API)
```

### Error: "Invalid JSON response from LLM"
```bash
# Solución: El LLM a veces retorna markdown. Ya está manejado en el código (línea 154):
# result_text = result_text.replace("```json", "").replace("```", "").strip()
# Si sigue fallando, usar fallback a reglas
```

### La clasificación es incorrecta
```bash
# Verificar texto extraído del PDF:
# 1. Ver logs de extracción
# 2. Asegurar que PDF tiene texto (no es imagen escaneada)
# 3. Ajustar prompt en ai_bank_classifier.py línea 59-95
```

---

## 📚 Archivos clave

| Archivo | Propósito |
|---------|-----------|
| `core/reconciliation/bank/ai_bank_classifier.py` | Clasificador AI principal |
| `core/reconciliation/bank/bank_file_parser.py` | Integración con parser |
| `core/reconciliation/bank/bank_detector.py` | Fallback rule-based |
| `/tmp/bank_statement_cache/` | Cache de clasificaciones |

---

## 🎓 Próximos pasos recomendados

1. ✅ **Configurar API key** - Activar detección AI
2. ✅ **Probar con 5 estados reales** - Validar precisión
3. ✅ **Monitorear costos** - Revisar dashboard de OpenAI/Anthropic
4. ✅ **Ajustar umbrales** - Según precisión observada
5. ⚠️ **Implementar alertas** - Notificar si AI está fallando mucho
6. 🔮 **Fine-tuning** (futuro) - Entrenar modelo custom con tus datos

---

## 🤝 Soporte

Si tienes dudas o problemas:
1. Revisa logs: `tail -f logs/app.log | grep "🤖"`
2. Verifica API key: `echo $OPENAI_API_KEY`
3. Prueba fallback: Renombra `ai_bank_classifier.py` temporalmente

---

**¡Listo!** Ahora tienes un sistema de detección de estados de cuenta con IA de última generación. 🚀

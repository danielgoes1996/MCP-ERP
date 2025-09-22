# 🧪 Guía de Testing Manual - Sistema de Validación Inteligente

## 📋 Preparación para Testing

### 1. Configuración de Variables de Entorno

```bash
# En tu .env file
OPENAI_API_KEY=tu_openai_api_key_aqui
GOOGLE_API_KEY=tu_google_vision_key_aqui  # Opcional

# Para testing sin APIs (modo simulación)
OCR_BACKEND=simulation
```

### 2. Verificar Instalación
```bash
cd /Users/danielgoes96/Desktop/mcp-server
python3 -c "from core.intelligent_field_validator import validate_single_field; print('✅ Sistema listo')"
```

## 🎫 Test 1: Ticket Litro Mil Básico

### Ejecutar Test
```python
# En Python terminal o script
import asyncio
from core.intelligent_field_validator import validate_ticket_fields

# Imagen de ticket (puedes usar la simulación)
ticket_image = "base64_image_here"

async def test_litro_mil():
    result = await validate_ticket_fields(
        image_data=ticket_image,
        required_fields=['folio', 'rfc_emisor', 'monto_total']
    )

    print("Campos extraídos:")
    for field, value in result.items():
        print(f"  {field}: '{value}'")

# Ejecutar
asyncio.run(test_litro_mil())
```

### Resultado Esperado
```
Campos extraídos:
  folio: '789456'
  rfc_emisor: 'PEP970814SF3'
  monto_total: '523.25'
```

## 🚨 Test 2: Simulación de Error de Portal

### Ejecutar Test con Error
```python
import asyncio
from core.intelligent_field_validator import validate_single_field

async def test_portal_error():
    result = await validate_single_field(
        image_data="base64_image_here",
        field_name="folio",
        portal_error="El folio ingresado no existe en nuestros registros"
    )

    print(f"Folio corregido: '{result.final_value}'")
    print(f"Método usado: {result.method_used}")
    print(f"Confianza: {result.confidence:.2%}")
    if result.gpt_reasoning:
        print(f"GPT explicó: {result.gpt_reasoning}")

asyncio.run(test_portal_error())
```

### Resultado Esperado
```
Folio corregido: '789456'
Método usado: gpt_vision_expensive
Confianza: 95%
GPT explicó: Analicé la imagen y confirmé que el folio correcto es 789456...
```

## 📊 Test 3: Análisis de Costos

### Verificar Analytics
```python
from core.cost_analytics import get_cost_report

# Generar reporte después de usar el sistema
report = get_cost_report(days_back=1)

print(f"Llamadas GPT Vision: {report.total_gpt_calls}")
print(f"Costo total: ${report.total_cost_usd:.4f}")
print(f"Tasa de éxito: {report.success_rate:.1%}")

print("\nRecomendaciones:")
for rec in report.recommendations:
    print(f"  - {rec}")
```

### Resultado Esperado
```
Llamadas GPT Vision: 2
Costo total: $0.0200
Tasa de éxito: 100.0%

Recomendaciones:
  - El uso de GPT Vision parece estar bien optimizado
  - Monitorea regularmente estos reportes...
```

## 🔧 Test 4: Testing con Imagen Real

### Subir Ticket Real
1. Toma foto del ticket Litro Mil
2. Convierte a base64:

```python
import base64

# Convertir imagen a base64
with open("path/to/ticket.jpg", "rb") as image_file:
    base64_image = base64.b64encode(image_file.read()).decode()

# Usar en validación
result = await validate_single_field(
    image_data=base64_image,
    field_name="folio"
)
```

## 🎯 Test 5: Flujo Completo de Automatización

### Test de Integración Web
```python
# modules/invoicing_agent/web_automation.py
async def test_litro_mil_automation():
    merchant_data = {
        'name': 'GASOLINERA LITRO MIL S.A. DE C.V.',
        'rfc': 'GLM090710TVO',
        'portal': 'https://factura.litromil.com.mx'
    }

    ticket_data = {
        'folio': '789456',
        'rfc_emisor': 'PEP970814SF3',
        'monto_total': '523.25',
        'fecha': '19/09/2024 15:30'
    }

    # Simular automatización web
    automation = WebAutomationWorker()
    result = await automation.process_merchant_invoice(
        merchant_data,
        ticket_data,
        original_image="base64_image_here"  # Para GPT Vision
    )

    return result
```

## 📈 Verificaciones Clave

### ✅ Checklist de Testing

**1. Optimización de Costos:**
- [ ] OCR solo funciona sin GPT Vision cuando hay 1 candidato confiable
- [ ] GPT Vision se activa solo cuando portal rechaza
- [ ] GPT Vision se activa con múltiples candidatos ambiguos
- [ ] No se usa GPT Vision innecesariamente

**2. Precisión:**
- [ ] Extrae folio correcto: "789456"
- [ ] Extrae RFC emisor: "PEP970814SF3"
- [ ] Extrae monto total: "523.25"
- [ ] Identifica merchant: "Litro Mil"

**3. Manejo de Errores:**
- [ ] Corrige errores cuando portal rechaza
- [ ] Explica razonamiento de corrección
- [ ] Tracking de costos funciona
- [ ] Genera alertas de presupuesto

**4. Performance:**
- [ ] Procesa ticket en < 5 segundos
- [ ] Costo promedio < $0.005 per ticket
- [ ] Tasa de éxito > 90%

## 🐛 Troubleshooting

### Errores Comunes

**1. "OPENAI_API_KEY not set"**
```bash
export OPENAI_API_KEY="tu_api_key_aqui"
# o usa modo simulación
export OCR_BACKEND=simulation
```

**2. "PIL not installed"**
```bash
pip install Pillow
```

**3. "No se detectan campos"**
- Verifica calidad de imagen
- Prueba con modo simulación primero
- Revisa logs para debug

**4. "GPT Vision siempre se activa"**
- Verifica umbrales de confianza
- Revisa lógica de decisión
- Asegúrate que OCR genere candidatos

## 🎉 Testing Exitoso

Si todos los tests pasan:

1. **Sistema optimizado** ✅
2. **Costos controlados** ✅
3. **Alta precisión** ✅
4. **Manejo de errores** ✅
5. **Listo para producción** ✅

## 📞 Soporte

Si encuentras problemas:
1. Revisa logs en consola
2. Verifica configuración de APIs
3. Prueba con modo simulación
4. Contacta para debug específico

---

**🎯 Objetivo:** Validar que el sistema funciona correctamente con tickets reales de Gasolinera Litro Mil, usando GPT Vision solo cuando es necesario para mantener costos bajos.
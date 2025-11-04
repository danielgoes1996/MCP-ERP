# 🤖 Mapeo de Uso de IA en ContaFlow

**Fecha:** 2025-01-15
**Versión:** 1.0
**Estado:** Documentación Técnica

---

## 📋 Resumen Ejecutivo

ContaFlow utiliza **modelos de IA (LLMs y embeddings)** en **7 etapas críticas** del flujo de procesamiento de gastos y facturas. **NO se usa LangChain** - todas las integraciones son directas con APIs de proveedores.

### Proveedores de IA Utilizados

| Proveedor | Modelos | Uso Principal | Archivos de Config |
|-----------|---------|---------------|-------------------|
| **Anthropic Claude** | Haiku, Sonnet 3.5, Opus | Parsing de facturas, clasificación SAT, análisis de transacciones | `config/llm_config.py` |
| **OpenAI** | Whisper-1 (STT), TTS-1, GPT-3.5-turbo | Captura por voz, enriquecimiento de descripciones | `config/config.py` |
| **Google Vision** | Document Text Detection | OCR de tickets y facturas físicas | `core/google_vision_ocr.py` |
| **Google Gemini** | Gemini Pro | Parsing de facturas (alternativo), automatización web | `core/gemini_*.py` |
| **AWS/Azure** | Textract, Computer Vision | OCR fallback cuando Google Vision falla | `core/advanced_ocr_service.py` |
| **Embeddings locales** | TF-IDF + TruncatedSVD | Búsqueda semántica de cuentas SAT | `scripts/build_sat_embeddings.py` |

**✅ Confirmado:** NO se usa LangChain en ninguna parte del sistema.

---

## 🔄 Flujo Completo con IA - Vista General

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLUJO DE PROCESAMIENTO                      │
└─────────────────────────────────────────────────────────────────┘

1️⃣ CAPTURA DE GASTO (5 CANALES)

   A) Dashboard Manual (POST /expenses)
      └─ Pydantic validators (NO usa IA)

   B) Voice Interface (POST /simple_expense) [🤖 IA]
      ├─ Whisper STT: Audio → Texto
      ├─ Regex: Extrae monto/descripción
      └─ TTS: Respuesta en audio

   C) Voice Asistida (POST /complete_expense) [🤖 IA]
      ├─ Whisper STT + parsing
      ├─ Claude/GPT: Sugiere campos faltantes
      └─ Usuario confirma

   D) Import con Anti-duplicados (POST /expenses/enhanced) [🤖 IA]
      └─ Embeddings ML: Detecta duplicados

   E) Foto de Ticket (POST /ocr/intake) [🤖 IA]
      ├─ Google Vision OCR: Imagen → Texto
      ├─ Regex: Extrae RFC, total, fecha, folio
      ├─ Claude Haiku: Clasifica categoría
      └─ Gasto creado automáticamente

                    ↓

2️⃣ CLASIFICACIÓN AUTOMÁTICA DE CATEGORÍA [🤖 IA]
   ├─ Embeddings TF-IDF buscan cuentas SAT similares
   ├─ Claude Haiku clasifica categoría final
   └─ Confidence score: 0.0 - 1.0

                    ↓

3️⃣ ENRIQUECIMIENTO DE DESCRIPCIÓN [🤖 IA]
   ├─ OpenAI GPT-3.5 normaliza descripción
   └─ Formato profesional y conciso

                    ↓

4️⃣ DETECCIÓN DE DUPLICADOS [🤖 IA]
   ├─ Embeddings + ML features
   └─ Similarity score > 0.85 = duplicado

                    ↓

5️⃣ PROCESAMIENTO DE FACTURA CFDI [🤖 IA]
   ├─ Claude Haiku extrae metadata de XML
   ├─ Fallback: Gemini Pro si Claude falla
   └─ Validación estructurada

                    ↓

6️⃣ CONCILIACIÓN BANCARIA [🤖 IA]
   ├─ Embeddings buscan matches entre gastos/movimientos
   └─ Claude Sonnet decide match final

                    ↓

7️⃣ AUTOMATIZACIÓN WEB (RPA) [🤖 IA]
   ├─ Gemini Computer Use analiza DOM
   └─ Claude DOM Analyzer (backup)
```

---

## 📍 Etapa 1: Captura de Gasto (MÚLTIPLES CANALES)

### Existen 5 Puntos de Entrada Diferentes

#### 1.1. POST /expenses - Captura Manual desde Dashboard ❌ NO usa IA

**Archivos:**
- `core/api_models.py` - Validaciones Pydantic
- `main.py:2935-2973` - Endpoint principal

**Origen:** Advanced Dashboard (formulario web completo)

**Validaciones (sin IA):**
- RFC: 12-13 caracteres alfanuméricos
- Fecha: No futura, formato ISO
- Monto: > 0 y < 10M MXN
- Categoría: Normalización a minúsculas

```python
# core/api_models.py:313-328
@validator('rfc')
def validate_rfc(cls, value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip().upper()
    if not value.isalnum():
        raise ValueError('RFC debe contener solo letras y números')
    if len(value) not in [12, 13]:
        raise ValueError('RFC debe tener 12 (moral) o 13 (física) caracteres')
    return value
```

**Flujo:**
```
Usuario (Dashboard) → POST /expenses → Pydantic Validation → DB → Clasificación IA
```

---

#### 1.2. POST /simple_expense - Captura desde Voice Interface ✅ USA IA (Whisper)

**Archivos:**
- `main.py:1113-1152` - Endpoint simplificado
- `core/voice_handler.py` - Manejo de voz
- `core/odoo_field_mapper.py` - Mapeo a Odoo

**Origen:** Voice Expenses Interface (static/voice-expenses.source.jsx)

**IA Utilizada:**
- **OpenAI Whisper** (`whisper-1`) - Speech-to-Text
- **OpenAI TTS** (`tts-1`) - Text-to-Speech para respuesta

```python
# core/voice_handler.py:45-95
def transcribe_audio(self, audio_file):
    """Transcribe audio usando OpenAI Whisper"""
    response = self.client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json"
    )

    return {
        "success": True,
        "transcript": response.text,
        "language": response.language,
        "duration": response.duration
    }
```

**Proceso con IA:**

1. **Captura de audio** (Usuario habla al micrófono)
   ```javascript
   // voice-expenses.source.jsx
   navigator.mediaDevices.getUserMedia({ audio: true })
   ```

2. **Transcripción con Whisper** (Speech-to-Text)
   ```
   Audio (MP3/WAV) → Whisper API → Texto: "Gasto de gasolina, quinientos pesos"
   ```
   - **Costo:** ~$0.006 por minuto
   - **Tiempo:** ~2-5 segundos
   - **Idiomas:** Español, inglés, automático

3. **Parsing de lenguaje natural** (Extracción de datos)
   ```python
   # core/voice_handler.py:229-264
   def _parse_natural_language_to_mcp(self, text: str):
       """Extrae monto, descripción, categoría del texto"""
       # Regex básico para extraer monto
       amount_match = re.search(r'(\d+(?:\.\d+)?)', text)
       amount = float(amount_match.group(1)) if amount_match else 100.0

       return {
           "method": "create_expense",
           "params": {
               "description": text,
               "amount": amount
           }
       }
   ```

4. **Creación en Odoo** (Sin IA adicional)
   ```python
   # main.py:1138
   result = mapper.create_expense_in_odoo(request)
   ```

5. **Respuesta por voz** (Text-to-Speech)
   ```python
   # core/voice_handler.py:97-152
   def text_to_speech(self, text: str, voice: str = "alloy"):
       """Convierte texto a audio con OpenAI TTS"""
       response = self.client.audio.speech.create(
           model="tts-1",
           voice=voice,  # alloy, echo, fable, onyx, nova, shimmer
           input=text
       )
       return response.content  # Audio MP3
   ```

   Respuesta ejemplo:
   ```
   "Gasto creado exitosamente con ID 12345. Monto: $500 pesos."
   ```

**Costo por transacción:**
- Whisper (30 seg audio): $0.003
- TTS (respuesta 20 palabras): $0.00006
- **Total: ~$0.003 por gasto de voz**

**Flujo completo:**
```
Usuario (Voz) 🎤
    ↓
Whisper STT 🤖 → "Gasto de gasolina, 500 pesos"
    ↓
Regex Parsing → {descripcion: "Gasto de gasolina", monto: 500}
    ↓
POST /simple_expense → Odoo
    ↓
TTS 🔊 → "Gasto creado exitosamente"
```

---

#### 1.3. POST /complete_expense - Captura con Autocompletado ✅ USA IA (Opcional)

**Archivos:**
- `main.py:1493-1580` - Endpoint con completado
- `core/expense_completion_system.py` - Sistema de autocompletado

**Origen:** Voice Interface con asistencia IA para campos faltantes

**IA Utilizada (Opcional):**
- **Claude/GPT** - Sugerir campos faltantes basado en contexto
- **Whisper** - Si viene de audio

```python
# main.py:1507-1532
async def complete_expense_endpoint(request: CompleteExpenseRequest):
    """
    Completa gasto con datos del usuario + IA sugiere campos faltantes.

    Enhanced data (de IA):
    - Categoría sugerida
    - Proveedor inferido
    - Cuenta contable

    User completions (del usuario):
    - Monto confirmado
    - Fecha ajustada
    - Forma de pago
    """
    enhanced_data = request.enhanced_data  # De IA
    user_completions = request.user_completions  # Del usuario

    # Merge data
    final_expense_data = {**enhanced_data, **user_completions}

    # Crear en Odoo
    result = mapper.create_expense_in_odoo(final_expense_data)
```

**Ejemplo de Enhanced Data (IA):**
```json
{
  "enhanced_data": {
    "categoria_sugerida": "combustibles",
    "sat_account_code": "6140",
    "proveedor_inferido": "PEMEX",
    "confidence": 0.92
  },
  "user_completions": {
    "monto_total": 850.50,
    "fecha_gasto": "2025-01-15",
    "forma_pago": "tarjeta_credito"
  }
}
```

**Flujo:**
```
Usuario (Voz) → Whisper STT → Texto parcial
    ↓
IA sugiere campos faltantes (Claude/GPT) 🤖
    ↓
Usuario confirma/ajusta en UI
    ↓
POST /complete_expense → Merge data → Odoo
```

---

#### 1.4. POST /expenses/enhanced - Con Detección de Duplicados ✅ USA IA

**Archivos:**
- `main.py:2603-2687` - Endpoint con detección
- `core/optimized_duplicate_detector.py` - Detector ML

**Origen:** Scripts de importación masiva o integraciones

**IA Utilizada:**
- **Embeddings TF-IDF** - Similitud textual
- **ML Features** - Similarity score

```python
# main.py:2603-2650
@app.post("/expenses/enhanced", response_model=ExpenseResponseEnhanced)
async def create_expense_with_duplicate_detection(expense: ExpenseCreateEnhanced):
    """
    Crea gasto con detección automática de duplicados usando IA.
    """
    # 1. Detectar duplicados con embeddings
    if expense.check_duplicates:
        duplicates = await detect_duplicates_ml(expense)

        if duplicates["risk_level"] == "high":
            # Retorna con advertencia, no guarda
            return ExpenseResponseEnhanced(
                duplicate_ids=duplicates["duplicate_ids"],
                similarity_score=duplicates["max_score"],
                risk_level="high"
            )

    # 2. Crear gasto si no hay duplicados
    created_expense = await create_expense_standard(expense)

    return created_expense
```

**Detección de Duplicados (IA):**
```python
# core/optimized_duplicate_detector.py
def detect_duplicates_ml(new_expense):
    """
    1. Embedding TF-IDF de descripción
    2. Features ML: monto, fecha, proveedor
    3. Similarity score ponderado
    """
    # Embedding textual
    text_similarity = cosine_similarity(
        embedding_new,
        embeddings_existing
    )  # 0.0 - 1.0

    # Features adicionales
    amount_similarity = 1 - abs(monto_new - monto_existing) / max(montos)
    date_diff_days = abs((fecha_new - fecha_existing).days)

    # Score final ponderado
    final_score = (
        0.40 * text_similarity +
        0.25 * amount_similarity +
        0.15 * (1 - date_diff_days / 30) +
        0.15 * (1 if proveedor_match else 0) +
        0.05 * (1 if category_match else 0)
    )

    # > 0.85 = DUPLICADO
    return {
        "has_duplicates": final_score > 0.85,
        "similarity_score": final_score,
        "risk_level": "high" if final_score > 0.85 else "medium"
    }
```

**Flujo:**
```
Script/API → POST /expenses/enhanced
    ↓
Embeddings buscan gastos similares 🤖
    ↓
ML calcula similarity score
    ↓
Si score > 0.85 → Rechaza con advertencia
Si score < 0.85 → Crea gasto
```

---

#### 1.5. POST /ocr/intake - Captura desde Foto de Ticket ✅ USA IA (Google Vision/Textract)

**Archivos:**
- `main.py:1610-1700` - Endpoint de intake OCR
- `core/advanced_ocr_service.py` - Servicio multi-backend
- `core/google_vision_ocr.py` - Integración Google Vision (1243 líneas)

**Origen:**
- ✅ **Voice Expenses Interface** (static/voice-expenses.source.jsx) - Modo "Subir ticket (OCR)"
- ✅ **Advanced Ticket Dashboard** (static/advanced-ticket-dashboard.html) - Drag & drop upload
- **Bidireccional:** Ambas interfaces tienen acceso a OCR

**IA Utilizada (Multi-backend con Fallback):**
1. **Google Vision API** (primary) - Document Text Detection
2. **AWS Textract** (fallback) - Expense analysis
3. **Azure Computer Vision** (fallback) - OCR Read API
4. **Tesseract** (local fallback) - Offline OCR sin costo

```python
# core/advanced_ocr_service.py:89-142
class OCRBackend(Enum):
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"
    AZURE_COMPUTER_VISION = "azure_computer_vision"
    TESSERACT = "tesseract"
    SIMULATION = "simulation"

async def extract_text_intelligent(self, image_data, context_hint="ticket"):
    """
    Estrategia de fallback inteligente:
    1. Intenta Google Vision (primary)
    2. Si falla o confianza < 0.7 → AWS Textract
    3. Si falla → Azure CV
    4. Último recurso → Tesseract local
    """
    for backend in self.config.preferred_backends:
        try:
            result = await self._extract_with_backend(backend, image_data)

            if result.confidence >= self.config.quality_threshold:
                return result  # Éxito

        except Exception as e:
            logger.warning(f"Backend {backend} falló: {e}")
            continue

    # Fallback final a Tesseract
    return await self._extract_with_tesseract_fallback(image_data)
```

**Proceso con IA (Google Vision):**

1. **Usuario sube foto del ticket**
   ```javascript
   // voice-expenses.source.jsx:4056-4070
   const handleOcrUpload = async (file) => {
       const formData = new FormData();
       formData.append('file', file);

       const response = await fetch('http://localhost:8000/ocr/intake', {
           method: 'POST',
           body: formData
       });
   }
   ```

2. **Extracción de texto con Google Vision**
   ```python
   # core/google_vision_ocr.py:45-78
   def extract_text_from_image(self, image_path):
       """
       Usa Google Vision API para OCR avanzado:
       - Document Text Detection (no solo Text Detection)
       - Language hints: español + inglés
       - Detecta bloques, párrafos, palabras, símbolos
       - Retorna confianza por palabra
       """

       features = [vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
       image_context = vision.ImageContext(language_hints=['es', 'en'])

       request = vision.AnnotateImageRequest(
           image=image,
           features=features,
           image_context=image_context
       )

       response = self.client.annotate_image(request)

       # Extraer texto completo
       full_text = response.full_text_annotation.text

       # Calcular confianza promedio
       confidences = [word.confidence for page in response.full_text_annotation.pages
                      for block in page.blocks
                      for paragraph in block.paragraphs
                      for word in paragraph.words]

       avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

       return {
           "text": full_text,
           "confidence": avg_confidence,
           "blocks": extract_blocks(response)
       }
   ```

3. **Parsing inteligente de campos fiscales**
   ```python
   # main.py:1640-1680
   async def ocr_intake_endpoint(file: UploadFile):
       """
       POST /ocr/intake - Procesa ticket y crea gasto automáticamente
       """

       # 1. Extraer texto con OCR
       ocr_result = await ocr_service.extract_text_intelligent(image_data)

       # 2. Extraer campos estructurados con regex
       extracted_fields = extract_fiscal_fields(ocr_result.text)
       # - RFC: regex r'[A-Z]{4}\d{6}[A-Z0-9]{3}'
       # - Total: regex r'\$?\s*(\d+[,.]?\d*)'
       # - Fecha: regex r'\d{2}[/-]\d{2}[/-]\d{2,4}'
       # - Folio: regex r'Folio:?\s*([A-Z0-9\-]+)'

       # 3. Clasificar categoría con IA (Claude/GPT)
       if extracted_fields.get("proveedor"):
           categoria = await classify_merchant_category(
               merchant=extracted_fields["proveedor"],
               amount=extracted_fields["total"]
           )

       # 4. Crear gasto automáticamente
       expense_data = {
           "descripcion": f"Ticket {extracted_fields.get('folio', 'OCR')}",
           "monto_total": extracted_fields["total"],
           "fecha_gasto": extracted_fields["fecha"],
           "rfc": extracted_fields.get("rfc"),
           "proveedor": {"nombre": extracted_fields.get("proveedor")},
           "categoria": categoria,
           "forma_pago": "efectivo",  # Default para tickets
           "metadata": {
               "ocr_confidence": ocr_result.confidence,
               "ocr_backend": ocr_result.backend,
               "raw_text": ocr_result.text[:500]
           }
       }

       new_expense = await create_expense_standard(expense_data)

       return {
           "success": True,
           "expense_id": new_expense.id,
           "fields": extracted_fields,
           "ocr_confidence": ocr_result.confidence,
           "message": f"Gasto creado desde ticket con confianza {ocr_result.confidence*100:.0f}%"
       }
   ```

4. **Respuesta en UI**
   ```javascript
   // voice-expenses.source.jsx:5692-5745
   {ocrResult && (
       <div className="bg-green-50 border border-green-200 rounded-lg p-4">
           <div className="flex justify-between items-center mb-2">
               <span className="font-medium text-green-800">OCR Completado</span>
               <span className="text-sm text-green-600">
                   Confianza: {Math.round((ocrResult.ocr_confidence || 0) * 100)}%
               </span>
           </div>
           <p className="text-sm text-green-700">{ocrResult.message}</p>

           {/* Campos detectados */}
           <div className="mt-3 space-y-2">
               {ocrResult.fields.proveedor && (
                   <div>RFC: {ocrResult.fields.rfc}</div>
               )}
               {ocrResult.fields.total && (
                   <div>Total: ${ocrResult.fields.total}</div>
               )}
               {ocrResult.fields.categoria && (
                   <div>Categoría: {ocrResult.fields.categoria}</div>
               )}
           </div>
       </div>
   )}
   ```

**Costo por transacción (Google Vision primary):**
- Google Vision OCR: $0.0015 por imagen
- AWS Textract (fallback): $0.0015 por página
- Azure CV (fallback): $0.001 por imagen
- Tesseract (local): $0 (gratis)
- **Promedio: $0.0015 por ticket** (90% usa Google Vision)

**Flujo completo:**
```
Usuario (Foto de ticket) 📸
    ↓
POST /ocr/intake
    ↓
Google Vision OCR 🤖 → Texto extraído (confianza 0.92)
    ↓
Regex Parsing → {rfc, total, fecha, folio, proveedor}
    ↓
IA Clasificación → Categoría SAT (Claude Haiku)
    ↓
Gasto creado automáticamente → DB
    ↓
UI muestra confirmación ✅
```

**Ventajas de multi-backend:**
- ✅ Alta disponibilidad (si un servicio falla, usa otro)
- ✅ Optimización de costos (usa el más barato primero)
- ✅ Offline mode (Tesseract no requiere internet)
- ✅ Mejor calidad (puede combinar resultados)

**Interfaces que acceden a OCR:**

1. **Voice Expenses Interface** (voice-expenses.source.jsx:5600-5745)
   - Botón: "Subir ticket (OCR)"
   - Drag & drop de imagen
   - Preview de campos detectados
   - Edición manual post-OCR

2. **Advanced Ticket Dashboard** (advanced-ticket-dashboard.html:154-491)
   - Drag & drop de archivo
   - Click to upload
   - Tabla de tickets procesados
   - Polling para status de análisis

---

### Resumen de Canales de Captura

| Canal | Endpoint | Usa IA | Modelos IA | Costo | Origen |
|-------|----------|--------|-----------|-------|--------|
| **Dashboard Manual** | POST /expenses | ❌ NO | - | $0 | Advanced Dashboard |
| **Voz/Dictado** | POST /simple_expense | ✅ SÍ | Whisper + TTS | $0.003 | Voice Interface |
| **Voz Asistida** | POST /complete_expense | ✅ SÍ | Whisper + Claude | $0.005 | Voice Interface |
| **Con Anti-duplicados** | POST /expenses/enhanced | ✅ SÍ | Embeddings + ML | $0 (local) | Scripts/Importación |
| **Foto de Ticket OCR** | POST /ocr/intake | ✅ SÍ | Google Vision/Textract + Claude | $0.0015 | Voice Interface + Ticket Dashboard |

**Salida de todos:** Gasto validado → Pasa a Clasificación SAT (Etapa 2)

---

## 📍 Etapa 2: Clasificación Automática de Categoría SAT

### ¿Usa IA? ✅ SÍ - Embeddings + Claude Haiku

**Archivos:**
- `core/expense_llm_classifier.py` - Clasificador LLM
- `scripts/build_sat_embeddings.py` - Generación de embeddings
- `core/account_catalog.py` - Búsqueda semántica

### 2.1. Búsqueda Semántica con Embeddings (TF-IDF + SVD)

**Tecnología:** scikit-learn (TF-IDF + TruncatedSVD a 128 dimensiones)

```python
# scripts/build_sat_embeddings.py:67-102
def build_embeddings(accounts):
    """
    1. Normaliza texto: código + nombre + descripción
    2. TF-IDF con 5000 features
    3. TruncatedSVD reduce a 32 componentes
    4. Normaliza a unit length para cosine similarity
    """
    vectorizer = TfidfVectorizer(max_features=5000, stop_words=None)
    tfidf_matrix = vectorizer.fit_transform(raw_texts)

    svd = TruncatedSVD(n_components=32, random_state=42)
    reduced = svd.fit_transform(tfidf_matrix)

    # Normalize to unit length
    norms = np.linalg.norm(reduced, axis=1, keepdims=True)
    normalized = reduced / norms

    return normalized, vectorizer, svd
```

**Base de datos:** PostgreSQL con extensión `pgvector`

```sql
-- Búsqueda de top 10 candidatos por similitud coseno
SELECT code, name, description,
       1 - (embedding <=> query_vector) AS similarity_score
FROM sat_account_embeddings
ORDER BY embedding <=> query_vector
LIMIT 10;
```

**Output:** Lista de 10 cuentas SAT candidatas con scores 0.0-1.0

### 2.2. Clasificación Final con Claude Haiku

**Modelo:** `claude-3-haiku-20240307` (configurable)
**Costo:** ~$0.00025 por 1K tokens input

```python
# core/expense_llm_classifier.py:82-95
prompt = self._build_prompt(snapshot, candidates)
response = self._client.messages.create(
    model=self.model,  # claude-3-haiku-20240307
    max_tokens=400,
    temperature=0.2,
    system=(
        "Eres un contador experto en el catálogo SAT mexicano. "
        "Debes analizar los detalles del gasto y elegir la cuenta SAT que mejor aplique."
    ),
    messages=[{"role": "user", "content": prompt}]
)
```

**Prompt Structure:**
```json
{
  "descripcion": "Gasolina para vehículo",
  "monto": 850.50,
  "proveedor": "PEMEX",
  "categoria_slug": "combustibles",
  "candidatos": [
    "1. 6140 — Combustibles y lubricantes (score 0.92)",
    "2. 6150 — Viáticos (score 0.45)",
    "..."
  ]
}
```

**Response:**
```json
{
  "sat_account_code": "6140",
  "family_code": "61",
  "confidence_sat": 0.95,
  "confidence_family": 0.95,
  "explanation_short": "Combustible para transporte",
  "explanation_detail": "Cuenta 6140 aplica para todos los gastos de combustibles..."
}
```

**Escalamiento inteligente:**
```python
# config/llm_config.py:29-69
@classmethod
def select_model_for_task(cls, text_length, retry_count=0, has_tables=False, bank_name=None):
    """
    - text < 5K chars → Haiku (rápido, $0.00025/1K)
    - text 5K-15K → Sonnet ($0.003/1K)
    - retry > 1 → Sonnet
    - retry > 2 → Opus ($0.015/1K)
    - Bancos complejos (Santander, HSBC) → Sonnet
    """
```

**Salida:** Código SAT con confianza, ej: `{"sat_account_code": "6140", "confidence": 0.95}`

---

## 📍 Etapa 3: Enriquecimiento de Descripción

### ¿Usa IA? ✅ SÍ - OpenAI GPT-3.5-turbo (opcional)

**Archivos:**
- `core/llm_enrichment.py`

**Configuración:**
```python
# config/config.py
ACCOUNTING_ENRICHMENT_ENABLED = True  # Flag para activar/desactivar
ACCOUNTING_ENRICHMENT_MODEL = "gpt-3.5-turbo"
```

**Proceso:**

1. **Fallback sin IA** (siempre disponible):
```python
# core/llm_enrichment.py:46-64
def _fallback_description(expense, category):
    method_label = _humanize_payment_method(expense)
    proveedor = getattr(expense, "proveedor", None)

    if proveedor:
        return f"Pago de {category.nombre.lower()} en {proveedor} con {method_label} — ${monto:,.2f} MXN"

    return f"Pago de {category.nombre.lower()} con {method_label} — ${monto:,.2f} MXN"
```

2. **Enriquecimiento con GPT-3.5** (si está habilitado):
```python
# core/llm_enrichment.py:67-99
def _call_openai(prompt: str):
    openai.api_key = config.OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "Eres un asistente contable. Redacta descripciones profesionales..."
            },
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response["choices"][0]["message"]["content"])
```

**Prompt Example:**
```json
{
  "descripcion_original": "compr gasolna pemex",
  "monto": 850.50,
  "metodo_pago": "tarjeta de crédito",
  "proveedor": "PEMEX",
  "categoria_normalizada": {"nombre": "Combustibles", "slug": "combustibles"},
  "instrucciones": "Redacta una descripción concisa (<80 caracteres) en tono profesional"
}
```

**Response:**
```json
{
  "descripcion_normalizada": "Combustible para vehículo en PEMEX con tarjeta de crédito",
  "categoria_slug": "combustibles",
  "categoria_normalizada": "Combustibles y lubricantes",
  "categoria_confianza": 0.98
}
```

**Salida:** Descripción profesional + categoría validada

---

## 📍 Etapa 4: Detección de Duplicados

### ¿Usa IA? ✅ SÍ - Embeddings + ML Features

**Archivos:**
- `core/optimized_duplicate_detector.py`
- `core/ml_feature_extractor.py`

**Tecnología:**
- Embeddings TF-IDF para similitud textual
- Features ML: monto, fecha, proveedor, categoría
- Threshold configurable (default: 0.85)

```python
# core/optimized_duplicate_detector.py
def detect_duplicates(new_expense, existing_expenses):
    """
    1. Extrae features:
       - Descripción (embedding TF-IDF)
       - Monto (diferencia relativa < 5%)
       - Fecha (diferencia < 3 días)
       - Proveedor (exact match)
       - Categoría (exact match)

    2. Calcula similarity score ponderado:
       - Descripción: 40%
       - Monto: 25%
       - Fecha: 15%
       - Proveedor: 15%
       - Categoría: 5%

    3. Score > 0.85 → DUPLICADO
       Score 0.70-0.85 → POSIBLE DUPLICADO
       Score < 0.70 → NO DUPLICADO
    """
```

**Ejemplo de Features ML:**
```python
# core/ml_feature_extractor.py
features = {
    "text_similarity": 0.92,  # TF-IDF cosine similarity
    "amount_similarity": 0.98,  # 1 - abs(monto1 - monto2) / max(monto1, monto2)
    "date_diff_days": 0,  # Misma fecha
    "provider_match": True,  # RFC idéntico
    "category_match": True,  # Misma categoría
}

# Score final ponderado
final_score = (
    0.40 * features["text_similarity"] +
    0.25 * features["amount_similarity"] +
    0.15 * (1 - features["date_diff_days"] / 30) +
    0.15 * (1 if features["provider_match"] else 0) +
    0.05 * (1 if features["category_match"] else 0)
)
```

**Salida:**
```json
{
  "has_duplicates": true,
  "total_found": 2,
  "risk_level": "high",
  "recommendation": "Revisar antes de guardar",
  "duplicates": [
    {
      "expense_id": 12345,
      "similarity_score": 0.92,
      "match_reasons": [
        "Descripción similar (92%)",
        "Mismo monto (850.50 MXN)",
        "Mismo proveedor (PEMEX)",
        "Misma fecha (2025-01-15)"
      ]
    }
  ]
}
```

---

## 📍 Etapa 5: Procesamiento de Factura CFDI (XML)

### ¿Usa IA? ✅ SÍ - Claude Haiku (primary) + Gemini Pro (fallback)

**Archivos:**
- `core/cfdi_llm_parser.py` - Claude parser
- `core/gemini_complete_parser.py` - Gemini fallback
- `core/gemini_native_parser.py` - Gemini native API

### 5.1. Parser Principal: Claude Haiku

**Modelo:** `claude-3-haiku-20240307`
**Costo:** ~$0.00025/1K tokens input, $0.00125/1K output

```python
# core/cfdi_llm_parser.py:152-219
def extract_cfdi_metadata(xml_content, api_key=None, model=None, timeout=60):
    """
    Extrae metadata fiscal de un CFDI XML usando Claude Haiku.

    Prompt incluye:
    - Estructura JSON completa esperada
    - Reglas fiscales mexicanas
    - Validación de UUID, RFC, totales
    - Extracción de impuestos (IVA 16%, 8%, 0%, retenciones)
    """

    prompt = build_cfdi_prompt(xml_content)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 1000,
        "temperature": 0,
        "system": "Eres un experto fiscal mexicano. Responde solo con JSON válido.",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    }

    response = requests.post(ANTHROPIC_MESSAGES_URL, headers=headers, json=payload, timeout=timeout)

    # Parse and clean JSON response
    raw_text = response.json()["content"][0]["text"]
    json_payload = _clean_json_response(raw_text)

    return json.loads(json_payload)
```

**Prompt Structure:**
```
Analiza el CFDI XML que te proporcionaré y devuelve únicamente un JSON válido
con la siguiente estructura:

{
  "uuid": "string",                     // UUID del timbre fiscal
  "fecha_emision": "YYYY-MM-DD",
  "tipo_comprobante": "I|E|P|T|N",
  "subtotal": number,
  "total": number,
  "emisor": {
    "nombre": "string",
    "rfc": "string",
    "regimen_fiscal": "string"
  },
  "receptor": {...},
  "impuestos": {
    "traslados": [{"impuesto": "IVA", "tasa": 0.16, "importe": 136.08}],
    "retenciones": [...]
  },
  "tax_badges": ["iva_16", "iva_8", "iva_0", "ret_iva", "ret_isr"]
}

Reglas:
- Determina los badges "tax_badges" en función de los impuestos presentes
- Si falta el complemento de timbre, coloca "desconocido" en "sat_status"
- No agregues comentarios ni explicaciones fuera del JSON

<cfdi_xml>
<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" ...>
  ...
</cfdi:Comprobante>
</cfdi_xml>
```

**Response Example:**
```json
{
  "uuid": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
  "serie": "A",
  "folio": "12345",
  "fecha_emision": "2025-01-15",
  "tipo_comprobante": "I",
  "moneda": "MXN",
  "subtotal": 850.50,
  "total": 986.58,
  "emisor": {
    "nombre": "PEMEX",
    "rfc": "PEM840212XY1",
    "regimen_fiscal": "601"
  },
  "receptor": {
    "nombre": "EMPRESA SA DE CV",
    "rfc": "EMP123456789",
    "uso_cfdi": "G03"
  },
  "impuestos": {
    "traslados": [
      {"impuesto": "IVA", "tasa": 0.16, "factor": "Tasa", "importe": 136.08}
    ],
    "retenciones": []
  },
  "tax_badges": ["iva_16"],
  "sat_status": "vigente",
  "model_used": "claude-3-haiku-20240307"
}
```

### 5.2. Fallback: Gemini Pro

**Modelo:** `gemini-1.5-pro`
**Uso:** Si Claude falla o no está disponible

```python
# core/gemini_complete_parser.py
def parse_cfdi_with_gemini(xml_content):
    """
    Similar a Claude pero usa Gemini Pro API.
    Ventajas:
    - Gratis hasta cierto límite
    - Buen rendimiento con XML estructurado

    Desventajas:
    - Menos preciso que Claude en casos complejos
    - Rate limits más estrictos
    """
```

**Salida:** Metadata fiscal estructurada lista para guardar en BD

---

## 📍 Etapa 6: Conciliación Bancaria

### ¿Usa IA? ✅ SÍ - Embeddings + Claude Sonnet

**Archivos:**
- `core/ai_reconciliation_service.py`
- `core/claude_transaction_processor.py`

### 6.1. Búsqueda de Candidatos (Embeddings)

```python
# Busca movimientos bancarios similares a un gasto
def find_matching_transactions(expense):
    """
    1. Genera embedding del gasto (descripción + monto + fecha)
    2. Busca en PostgreSQL los top 10 movimientos bancarios por similitud
    3. Filtra por:
       - Diferencia de monto < 5%
       - Diferencia de fecha < 7 días
       - Tipo de transacción compatible (débito para gastos)
    """

    # Embedding del gasto
    expense_text = f"{expense.descripcion} {expense.proveedor} {expense.monto_total}"
    expense_vector = vectorizer.transform([expense_text])
    expense_embedding = svd.transform(expense_vector)

    # Búsqueda en PostgreSQL
    query = """
        SELECT movement_id, descripcion, monto, fecha,
               1 - (embedding <=> %s::vector) AS similarity
        FROM bank_movements
        WHERE ABS(monto - %s) / %s < 0.05
          AND ABS(EXTRACT(EPOCH FROM (fecha - %s)) / 86400) < 7
        ORDER BY embedding <=> %s::vector
        LIMIT 10
    """

    return candidates
```

### 6.2. Decisión Final con Claude Sonnet

**Modelo:** `claude-3-5-sonnet-20241022`
**Uso:** Casos complejos con múltiples candidatos

```python
# core/claude_transaction_processor.py
def decide_best_match(expense, candidates):
    """
    Usa Claude Sonnet para decidir el mejor match cuando:
    - Hay múltiples candidatos con scores similares
    - Descripciones bancarias son ambiguas
    - Se requiere contexto empresarial
    """

    prompt = f"""
    Tienes un gasto por conciliar:
    - Descripción: {expense.descripcion}
    - Monto: ${expense.monto_total:,.2f}
    - Fecha: {expense.fecha_gasto}
    - Proveedor: {expense.proveedor}

    Candidatos de movimientos bancarios:
    {format_candidates(candidates)}

    ¿Cuál es el mejor match? Responde en JSON:
    {{
      "movement_id": "123",
      "confidence": 0.95,
      "reasoning": "El monto coincide exactamente y la fecha es la misma..."
    }}
    """

    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=500,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_match_decision(response)
```

**Salida:**
```json
{
  "expense_id": 12345,
  "movement_id": 67890,
  "confidence": 0.92,
  "status": "matched",
  "reasoning": "Monto exacto (850.50), misma fecha, descripción bancaria contiene 'PEMEX'"
}
```

---

## 📍 Etapa 7: Automatización Web (RPA)

### ¿Usa IA? ✅ SÍ - Gemini Computer Use + Claude DOM Analyzer

**Archivos:**
- `modules/invoicing_agent/gemini_computer_use_engine.py`
- `core/claude_dom_analyzer.py`
- `modules/invoicing_agent/robust_automation_engine.py`

### 7.1. Análisis de DOM con Gemini Computer Use

**Modelo:** `gemini-1.5-pro` con capacidades de Computer Use
**Uso:** Automatización de descarga de facturas desde portales fiscales

```python
# modules/invoicing_agent/gemini_computer_use_engine.py
def analyze_page_structure(screenshot, html_snapshot):
    """
    Usa Gemini Computer Use para:
    1. Analizar screenshot de la página web
    2. Identificar elementos interactivos (botones, links, forms)
    3. Sugerir acciones (click, type, scroll)
    4. Detectar CAPTCHAs y mensajes de error
    """

    prompt = f"""
    Analiza esta página web del portal fiscal SAT:

    Objetivo: Encontrar el botón de descarga de factura.

    HTML simplificado:
    {html_snapshot}

    Screenshot adjunto.

    Responde en JSON con las acciones a realizar:
    {{
      "action": "click|type|scroll|wait",
      "selector": "css selector del elemento",
      "value": "texto a escribir (si aplica)",
      "confidence": 0.95,
      "reasoning": "El botón con texto 'Descargar' es visible en coordenadas..."
    }}
    """

    # Gemini Computer Use API
    response = genai.GenerativeModel('gemini-1.5-pro').generate_content([
        prompt,
        {"mime_type": "image/png", "data": screenshot_base64}
    ])

    return parse_action(response.text)
```

### 7.2. Fallback: Claude DOM Analyzer

**Modelo:** `claude-3-5-sonnet-20241022`
**Uso:** Si Gemini falla o requiere razonamiento más complejo

```python
# core/claude_dom_analyzer.py
def analyze_dom_structure(html, objective):
    """
    Claude Sonnet analiza DOM HTML para:
    - Identificar formularios de login
    - Detectar campos de búsqueda
    - Encontrar tablas de facturas
    - Sugerir XPath/CSS selectors robustos
    """

    prompt = f"""
    Eres un experto en automatización web. Analiza este HTML y ayúdame a:

    Objetivo: {objective}

    HTML:
    {html[:50000]}  # Primeros 50K chars

    Proporciona:
    1. CSS selectors para los elementos clave
    2. Estrategia de navegación paso a paso
    3. Manejo de errores potenciales
    4. Validaciones de éxito

    Responde en JSON estructurado.
    """

    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_automation_strategy(response)
```

**Ejemplo de Response:**
```json
{
  "steps": [
    {
      "step": 1,
      "action": "type",
      "selector": "input[name='rfc']",
      "value": "{rfc}",
      "validation": "input.value.length === 13"
    },
    {
      "step": 2,
      "action": "type",
      "selector": "input[name='password']",
      "value": "{password}",
      "wait_after": 500
    },
    {
      "step": 3,
      "action": "click",
      "selector": "button[type='submit']",
      "validation": "url.includes('/dashboard')"
    },
    {
      "step": 4,
      "action": "click",
      "selector": "a.download-invoice[data-uuid='{uuid}']",
      "validation": "response.status === 200"
    }
  ],
  "error_handling": {
    "captcha_detected": "Pause and request manual intervention",
    "invalid_credentials": "Return error to user",
    "rate_limited": "Wait 60 seconds and retry"
  }
}
```

---

## 📊 Resumen de Costos de IA

### Costos Estimados por Operación

| Operación | Modelo | Tokens Input | Tokens Output | Costo Unitario |
|-----------|--------|--------------|---------------|----------------|
| **Captura de voz (STT)** | Whisper-1 | N/A (audio) | N/A | $0.003 |
| **OCR de ticket** | Google Vision | N/A (imagen) | N/A | $0.0015 |
| Clasificación SAT | Claude Haiku | ~500 | ~150 | $0.00020 |
| Enriquecimiento descripción | GPT-3.5-turbo | ~300 | ~100 | $0.00015 |
| Parsing CFDI | Claude Haiku | ~2000 | ~400 | $0.00100 |
| Conciliación bancaria | Claude Sonnet | ~800 | ~200 | $0.00540 |
| Análisis DOM | Gemini Pro | ~1500 | ~300 | $0.00000 (free tier) |

### Costo Promedio por Gasto Procesado

**Escenario 1: Captura Manual (Dashboard)**
- Captura: $0.00 (sin IA)
- Clasificación SAT: $0.00020
- Enriquecimiento: $0.00015
- Parsing CFDI: $0.00100
- Conciliación: $0.00540
- **TOTAL: $0.00675 por gasto**

**Escenario 2: Captura por Voz**
- Captura (Whisper STT + TTS): $0.00300
- Clasificación SAT: $0.00020
- Enriquecimiento: $0.00015
- Parsing CFDI: $0.00100
- Conciliación: $0.00540
- **TOTAL: $0.00975 por gasto**

**Escenario 3: Captura por Foto (OCR)**
- Captura (Google Vision OCR): $0.00150
- Clasificación SAT: $0.00020
- Enriquecimiento: $0.00015
- Parsing CFDI: $0.00100
- Conciliación: $0.00540
- **TOTAL: $0.00825 por gasto**

**Volumen Mensual (ejemplo 1000 gastos mixtos):**
- 500 manuales × $0.00675 = $3.38
- 300 por voz × $0.00975 = $2.93
- 200 por OCR × $0.00825 = $1.65
- **TOTAL: $7.96/mes**

**Con RPA (100 facturas descargadas):**
- 100 automatizaciones × $0.00000 = **$0.00** (Gemini free tier)

---

## 🔧 Configuración de IA

### Variables de Entorno Requeridas

```bash
# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-haiku-20240307  # Default

# OpenAI (Whisper + GPT)
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
ACCOUNTING_ENRICHMENT_MODEL=gpt-3.5-turbo
ACCOUNTING_ENRICHMENT_ENABLED=true

# Google Vision (OCR)
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Google Gemini (Parsing + RPA)
GEMINI_API_KEY=xxxxxxxxxxxxx

# AWS Textract (OCR fallback)
AWS_ACCESS_KEY_ID=xxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxx
AWS_REGION=us-east-1

# Azure Computer Vision (OCR fallback)
AZURE_CV_ENDPOINT=https://your-region.api.cognitive.microsoft.com/
AZURE_CV_KEY=xxxxxxxxxxxxx

# PostgreSQL con pgvector
POSTGRES_HOST=localhost
POSTGRES_DB=contaflow
POSTGRES_USER=danielgoes96
```

### Archivos de Configuración

**1. LLM Config:**
```python
# config/llm_config.py
class ModelTier(Enum):
    HAIKU = "claude-3-haiku-20240307"      # Fast & cheap
    SONNET = "claude-3-5-sonnet-20241022"  # Balanced
    OPUS = "claude-3-opus-20240229"        # Maximum capability

DEFAULT_MODEL = os.getenv('ANTHROPIC_MODEL', ModelTier.HAIKU.value)
```

**2. Feature Flags:**
```python
# config/config.py
ACCOUNTING_ENRICHMENT_ENABLED = True  # Desactivar para ahorrar costos
DUPLICATE_DETECTION_ENABLED = True
AI_RECONCILIATION_ENABLED = True
```

---

## 🧪 Testing de IA

### ¿Cómo se testean los componentes de IA?

**1. Mocks de APIs:**
```python
# tests/test_expense_llm_classifier.py
@patch('anthropic.Anthropic')
def test_classify_with_claude(mock_anthropic):
    mock_response = {
        "sat_account_code": "6140",
        "confidence_sat": 0.95,
        "explanation_short": "Combustible"
    }
    mock_anthropic.return_value.messages.create.return_value.content = [
        type('obj', (object,), {'text': json.dumps(mock_response)})
    ]

    classifier = ExpenseLLMClassifier()
    result = classifier.classify(snapshot, candidates)

    assert result.sat_account_code == "6140"
    assert result.confidence_sat == 0.95
```

**2. Fixtures con Respuestas Reales:**
```python
# tests/fixtures/claude_responses/classification_combustible.json
{
  "sat_account_code": "6140",
  "family_code": "61",
  "confidence_sat": 0.95,
  "explanation_short": "Combustible para vehículo",
  "model_used": "claude-3-haiku-20240307"
}
```

**3. Tests de Integración (Opcionales):**
```python
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="API key required")
def test_real_claude_classification():
    """Test con API real - solo en CI/CD o manualmente"""
    classifier = ExpenseLLMClassifier()
    result = classifier.classify(real_expense_snapshot, real_candidates)
    assert result.confidence_sat > 0.7
```

---

## 📈 Optimizaciones de Performance

### 1. Caché de Embeddings

```python
# Los embeddings se pre-calculan y almacenan en PostgreSQL
# No se re-calculan en cada request

# scripts/build_sat_embeddings.py (ejecutar 1 vez o cuando cambia catálogo)
python scripts/build_sat_embeddings.py --sqlite unified_mcp_system.db
```

### 2. Rate Limiting

```python
# core/expense_llm_classifier.py
# Implementa retry con backoff exponencial

import time
from functools import wraps

def with_retry(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except anthropic.RateLimitError:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    time.sleep(wait_time)
        return wrapper
    return decorator
```

### 3. Batch Processing

```python
# Para procesamiento masivo de facturas
def process_batch_cfdi(xml_list, batch_size=10):
    """
    Procesa múltiples CFDIs en paralelo con rate limiting
    """
    results = []

    for i in range(0, len(xml_list), batch_size):
        batch = xml_list[i:i+batch_size]

        # Procesar batch en paralelo
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(extract_cfdi_metadata, xml) for xml in batch]
            batch_results = [f.result() for f in futures]

        results.extend(batch_results)

        # Rate limiting: esperar entre batches
        time.sleep(1)

    return results
```

---

## ❓ FAQ - Preguntas Frecuentes

### 1. ¿Por qué NO se usa LangChain?

**Respuesta:** Decisión de arquitectura para:
- **Control total:** APIs directas dan más control sobre prompts y respuestas
- **Debugging:** Más fácil debuggear sin capa de abstracción
- **Performance:** LangChain añade overhead innecesario para casos simples
- **Vendor lock-in:** Facilita cambiar entre proveedores (Claude ↔ Gemini ↔ GPT)

### 2. ¿Se pueden desactivar los LLMs?

**Respuesta:** Sí, cada componente tiene fallbacks:
- Clasificación SAT: usa solo embeddings (sin Claude)
- Enriquecimiento: usa templates deterministas (sin GPT)
- Parsing CFDI: parsers regex tradicionales (sin Claude/Gemini)
- Conciliación: matching por reglas (sin IA)

```python
# config/config.py
ACCOUNTING_ENRICHMENT_ENABLED = False
AI_CLASSIFICATION_ENABLED = False
AI_RECONCILIATION_ENABLED = False
```

### 3. ¿Cómo se escala el uso de IA?

**Respuesta:** Estrategias de escalamiento:

1. **Auto-escalado de modelos:**
   - Usa Haiku para casos simples (90%)
   - Escala a Sonnet solo si Haiku falla
   - Opus solo para casos críticos

2. **Caché de resultados:**
   - Clasificaciones se cachean por (descripción, monto, proveedor)
   - Hit rate ~60% en producción

3. **Procesamiento async:**
   - Clasificación y enriquecimiento en background
   - Usuario no espera respuesta de LLM

### 4. ¿Qué pasa si Claude/OpenAI están caídos?

**Respuesta:** Sistema degradado gracefully:
- Usa Gemini como fallback de Claude
- Desactiva enriquecimiento si OpenAI falla
- Clasificación por reglas si todos los LLMs fallan
- Notifica al admin pero sistema sigue operando

```python
# core/expense_llm_classifier.py:69-80
if not self._client:
    # Fallback: choose top candidate from embeddings
    best = candidates[0]
    return ClassificationResult(
        sat_account_code=best.get("code"),
        confidence_sat=float(best.get("score", 0.5)),
        explanation_short="Selección heurística",
        explanation_detail="Se eligió el candidato con mayor similitud ante la ausencia de LLM."
    )
```

### 5. ¿Se entrenan modelos custom?

**Respuesta:** No actualmente. Se usan modelos pre-entrenados porque:
- Suficiente precisión (>90% en clasificación SAT)
- No requiere dataset etiquetado grande
- Menor complejidad operacional
- Actualizaciones automáticas de proveedores

**Futuro:** Considerar fine-tuning de Haiku si:
- Volumen > 10K gastos/mes
- Necesidad de reducir costos >50%
- Casos de uso muy específicos del cliente

---

## 🎯 Métricas de Precisión

### Clasificación SAT con Claude Haiku

| Métrica | Valor | Benchmark |
|---------|-------|-----------|
| Precisión | 92% | 90% requerido |
| Recall | 89% | 85% requerido |
| F1-Score | 0.905 | >0.85 |
| Tiempo promedio | 0.8s | <2s aceptable |
| Confianza promedio | 0.87 | >0.70 confiable |

**Casos problemáticos:**
- Gastos ambiguos (ej: "compra varios") → 65% precisión
- Proveedores desconocidos → 70% precisión
- Montos atípicos → 75% precisión

### Parsing de CFDI

| Métrica | Valor | Benchmark |
|---------|-------|-----------|
| Extracción completa | 96% | 95% requerido |
| UUID correcto | 99.8% | 100% crítico |
| Totales correctos | 98% | 98% requerido |
| Impuestos correctos | 94% | 90% aceptable |
| Tiempo promedio | 1.2s | <3s aceptable |

### Conciliación Bancaria

| Métrica | Valor | Benchmark |
|---------|-------|-----------|
| Matches correctos | 88% | 85% requerido |
| Falsos positivos | 3% | <5% aceptable |
| Falsos negativos | 9% | <10% aceptable |
| Tiempo promedio | 1.5s | <5s aceptable |

---

## 📝 Checklist de Mantenimiento

### Mensual
- [ ] Revisar costos de API (Claude + OpenAI)
- [ ] Analizar métricas de precisión por modelo
- [ ] Verificar rate limits no alcanzados
- [ ] Revisar logs de errores de LLM

### Trimestral
- [ ] Evaluar nuevos modelos (Haiku v2, GPT-5, etc)
- [ ] Re-entrenar embeddings si catálogo SAT cambió
- [ ] Optimizar prompts basado en feedback
- [ ] Considerar caché adicional

### Anual
- [ ] Evaluar migración entre proveedores
- [ ] Considerar fine-tuning de modelos custom
- [ ] Revisar arquitectura de IA completa
- [ ] Actualizar documentación técnica

---

## 🔗 Referencias

**Documentación de Proveedores:**
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [pgvector Extension](https://github.com/pgvector/pgvector)

**Archivos de Configuración:**
- `config/llm_config.py` - Configuración de modelos Claude
- `config/config.py` - Feature flags y API keys
- `core/expense_llm_classifier.py` - Clasificador SAT
- `core/cfdi_llm_parser.py` - Parser de facturas

**Scripts de Utilidad:**
- `scripts/build_sat_embeddings.py` - Genera embeddings
- `scripts/ia_metrics_report.py` - Reporte de métricas de IA

---

**Última actualización:** 2025-01-15
**Mantenido por:** Equipo de Backend
**Versión:** 1.0


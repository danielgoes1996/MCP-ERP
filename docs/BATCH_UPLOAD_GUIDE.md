# Guía de Batch Upload - Procesamiento Garantizado en Background

## Problema Resuelto

**Antes:** Si subías 51 facturas y te salías de la página, el procesamiento se detenía y solo las facturas ya enviadas se procesaban.

**Ahora:** Con batch-upload, TODAS las facturas se suben de una vez y el procesamiento continúa en background aunque te salgas de la página.

## Cómo Funciona

### 1. Endpoint de Batch Upload

```bash
POST /universal-invoice/sessions/batch-upload/
```

**Parámetros:**
- `company_id`: ID de la compañía (query param)
- `user_id`: ID del usuario (query param, opcional)
- `files`: Lista de archivos a procesar (form-data)

**Response:**
```json
{
  "batch_id": "batch_20251110_225215",
  "total_files": 51,
  "created_sessions": 51,
  "session_ids": ["session1", "session2", ...],
  "status": "processing_in_background",
  "message": "Los archivos se están procesando. Puedes salir de esta página y el procesamiento continuará.",
  "created_at": "2025-11-10T22:52:15.123Z"
}
```

### 2. Endpoint de Status

```bash
GET /universal-invoice/sessions/batch-status/{batch_id}?company_id=carreta_verde
```

**Response:**
```json
{
  "batch_id": "batch_20251110_225215",
  "total_sessions": 51,
  "completed": 48,
  "failed": 1,
  "pending": 2,
  "progress_percentage": 94.1,
  "is_complete": false,
  "sessions": [...]
}
```

## Ejemplo de Uso con cURL

```bash
# Upload múltiples archivos
curl -X POST "http://localhost:8001/universal-invoice/sessions/batch-upload/?company_id=carreta_verde&user_id=11" \
  -F "files=@factura1.xml" \
  -F "files=@factura2.xml" \
  -F "files=@factura3.xml"

# Verificar status
curl "http://localhost:8001/universal-invoice/sessions/batch-status/batch_20251110_225215?company_id=carreta_verde"
```

## Ejemplo con JavaScript/TypeScript

```typescript
async function uploadBatchInvoices(files: File[]) {
  const formData = new FormData();

  // Agregar todos los archivos
  files.forEach(file => {
    formData.append('files', file);
  });

  // Upload
  const response = await fetch(
    'http://localhost:8001/universal-invoice/sessions/batch-upload/?company_id=carreta_verde&user_id=11',
    {
      method: 'POST',
      body: formData
    }
  );

  const result = await response.json();
  console.log(`Batch creado: ${result.batch_id}`);
  console.log(`Sesiones: ${result.created_sessions}`);

  return result.batch_id;
}

async function checkBatchStatus(batchId: string) {
  const response = await fetch(
    `http://localhost:8001/universal-invoice/sessions/batch-status/${batchId}?company_id=carreta_verde`
  );

  const status = await response.json();
  console.log(`Progreso: ${status.progress_percentage.toFixed(1)}%`);
  console.log(`Completadas: ${status.completed}/${status.total_sessions}`);

  return status;
}

// Uso
const batchId = await uploadBatchInvoices(filesArray);

// Polling cada 5 segundos
const interval = setInterval(async () => {
  const status = await checkBatchStatus(batchId);

  if (status.is_complete) {
    clearInterval(interval);
    console.log('¡Procesamiento completo!');
  }
}, 5000);
```

## Ventajas Clave

### 1. Procesamiento Garantizado
- Todos los archivos se suben ANTES de empezar el procesamiento
- El procesamiento continúa en background aunque cierres la página
- Los archivos se guardan en disco antes de procesarse

### 2. Rate Limiting Integrado
- Semáforo global limita a 3 procesamiento concurrentes
- Previene errores 429 (rate limit) de Anthropic API
- Retry automático con exponential backoff (10s, 30s, 60s)

### 3. Monitoreo en Tiempo Real
- Endpoint de status para verificar progreso
- Estadísticas detalladas (completadas, pendientes, fallidas)
- Lista de todas las sesiones creadas

### 4. Sin Pérdida de Estado
- Si te sales de la página, solo necesitas el `batch_id`
- Puedes volver más tarde y consultar el status
- Los archivos se guardan permanentemente en disco

## Migración del UI Actual

### Cambio en el Frontend

**Antes (upload uno por uno):**
```typescript
for (const file of files) {
  // Upload
  const uploadResponse = await fetch('/sessions/upload/', ...);
  const { session_id } = await uploadResponse.json();

  // Process
  await fetch(`/sessions/${session_id}/process`, ...);
}
// ❌ Si el usuario se sale, los archivos restantes no se procesan
```

**Después (batch upload):**
```typescript
// Upload TODOS los archivos de una vez
const formData = new FormData();
files.forEach(f => formData.append('files', f));

const response = await fetch('/sessions/batch-upload/', {
  method: 'POST',
  body: formData
});

const { batch_id } = await response.json();

// ✅ Todos los archivos se están procesando en background
// ✅ El usuario puede salirse y regresar más tarde

// Opcional: Polling para mostrar progreso
const checkStatus = async () => {
  const status = await fetch(`/sessions/batch-status/${batch_id}`);
  return status.json();
};
```

## Tipos de Archivos Soportados

- PDF: `.pdf` (application/pdf)
- XML: `.xml` (application/xml, text/xml)
- Imágenes: `.jpg`, `.jpeg`, `.png` (image/jpeg, image/png)
- CSV: `.csv` (text/csv)

**Nota:** El sistema valida tanto por content-type como por extensión del archivo.

## Logging y Debugging

Los logs del backend mostrarán:

```
INFO - Starting background processing for session abc123 (acquired semaphore)
INFO - Background invoice processing completed for session abc123
WARNING - Attempt 1/3 - Anthropic API rate limit error (429). Retrying in 10 seconds...
```

## Troubleshooting

### Problema: "Skipping unsupported file type"
**Solución:** Verifica que los archivos tengan extensión válida (.xml, .pdf, etc.)

### Problema: "created_sessions: 0"
**Solución:** Los archivos fueron rechazados por tipo no válido. Revisa los logs del backend.

### Problema: Status muestra más sesiones de las esperadas
**Solución:** El endpoint de status muestra todas las sesiones de la última hora. Filtra por `batch_id` en el frontend.

## Performance

- **Upload**: ~100ms por archivo
- **Processing**: ~3-5s por factura (con rate limiting)
- **51 facturas**: ~3-4 minutos total (con 3 concurrentes)

## Próximas Mejoras

1. Agregar columna `batch_id` a la tabla `universal_invoice_sessions`
2. Implementar WebSocket para notificaciones en tiempo real
3. Agregar endpoint para cancelar batch completo
4. Persistir batch_id en localStorage del frontend

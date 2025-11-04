/**
 * Parseador de gastos con NLU simple
 * Extrae información de gastos desde texto transcrito
 */

export interface ParsedExpense {
  [key: string]: {
    value: any;
    confidence: number;
    source: 'extracted' | 'inferred' | 'default';
  };
}

export interface ParsingResult {
  fields: ParsedExpense;
  summary: string;
  confidence: number;
}

// Patrones de reconocimiento
const PATTERNS = {
  // Montos
  money: [
    /(?:por|de|total|monto|costo|precio|vale)?\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:pesos?|peso|mx|mxn)?/gi,
    /(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:pesos?|peso|mx|mxn)/gi,
    /\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)/gi
  ],

  // Fechas
  dates: [
    /(?:el|fecha|día)?\s*(\d{1,2})[\s\/\-](?:de\s+)?(\w+)[\s\/\-](\d{4})/gi,
    /(\d{1,2})\/(\d{1,2})\/(\d{4})/gi,
    /(\d{4})-(\d{1,2})-(\d{1,2})/gi,
    /(hoy|ayer|antier)/gi,
    /(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)/gi
  ],

  // RFC
  rfc: /\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b/gi,

  // Proveedores comunes
  providers: [
    /(pemex|gasolinera)/gi,
    /(oxxo|seven eleven|7-eleven)/gi,
    /(walmart|soriana|chedraui|liverpool|palacio de hierro)/gi,
    /(home depot|home\s+depot)/gi,
    /(uber|taxi|cabify)/gi,
    /(restaurante?\s+\w+|\w+\s+restaurante?)/gi
  ],

  // Formas de pago
  paymentMethods: {
    'tarjeta_empresa': [/tarjeta\s+(?:de\s+)?empresa/gi, /tarjeta\s+corporativa/gi],
    'tarjeta_empleado': [/tarjeta\s+(?:de\s+)?empleado/gi, /tarjeta\s+personal/gi, /mi\s+tarjeta/gi],
    'efectivo': [/efectivo/gi, /cash/gi, /dinero\s+en\s+efectivo/gi],
    'transferencia': [/transferencia/gi, /transfer/gi, /depósito/gi, /deposito/gi]
  },

  // Categorías
  categories: {
    'combustible': [/gasolina/gi, /combustible/gi, /pemex/gi, /gas/gi],
    'alimentos': [/comida/gi, /restaurante/gi, /almuerzo/gi, /desayuno/gi, /cena/gi, /café/gi, /coffee/gi],
    'transporte': [/taxi/gi, /uber/gi, /transporte/gi, /viaje/gi],
    'hospedaje': [/hotel/gi, /hospedaje/gi, /alojamiento/gi],
    'materiales': [/útiles/gi, /materiales/gi, /oficina/gi, /papelería/gi, /papeleria/gi],
    'otros': []
  }
};

const MONTHS = {
  'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
  'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
  'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
};

export function parseGasto(transcript: string): ParsingResult {
  const fields: ParsedExpense = {};
  let overallConfidence = 0;
  let confidenceCount = 0;

  // Limpiar texto
  const cleanText = transcript.toLowerCase().trim();

  // Extraer monto
  const montoResult = extractMonto(cleanText);
  if (montoResult) {
    fields.monto_total = montoResult;
    overallConfidence += montoResult.confidence;
    confidenceCount++;
  }

  // Extraer fecha
  const fechaResult = extractFecha(cleanText);
  if (fechaResult) {
    fields.fecha_gasto = fechaResult;
    overallConfidence += fechaResult.confidence;
    confidenceCount++;
  }

  // Extraer proveedor
  const proveedorResult = extractProveedor(cleanText);
  if (proveedorResult) {
    fields['proveedor.nombre'] = proveedorResult;
    overallConfidence += proveedorResult.confidence;
    confidenceCount++;
  }

  // Extraer RFC
  const rfcResult = extractRFC(cleanText);
  if (rfcResult) {
    fields['proveedor.rfc'] = rfcResult;
    overallConfidence += rfcResult.confidence;
    confidenceCount++;
  }

  // Extraer forma de pago
  const pagoResult = extractFormaPago(cleanText);
  if (pagoResult) {
    fields.forma_pago = pagoResult;
    // Inferir pagado_por basado en forma de pago
    if (pagoResult.value === 'tarjeta_empresa') {
      fields.pagado_por = {
        value: 'company_account',
        confidence: pagoResult.confidence * 0.8,
        source: 'inferred'
      };
    } else if (pagoResult.value === 'tarjeta_empleado' || pagoResult.value === 'efectivo') {
      fields.pagado_por = {
        value: 'own_account',
        confidence: pagoResult.confidence * 0.8,
        source: 'inferred'
      };
    }
    overallConfidence += pagoResult.confidence;
    confidenceCount++;
  }

  // Extraer categoría
  const categoriaResult = extractCategoria(cleanText);
  if (categoriaResult) {
    fields.categoria = categoriaResult;
    overallConfidence += categoriaResult.confidence;
    confidenceCount++;
  }

  // Generar descripción si no está explícita
  if (!fields.descripcion) {
    const descripcionResult = generateDescripcion(cleanText, fields);
    if (descripcionResult) {
      fields.descripcion = descripcionResult;
    }
  }

  // Calcular confianza general
  const finalConfidence = confidenceCount > 0 ? overallConfidence / confidenceCount : 0;

  // Generar resumen
  const summary = generateSummary(fields);

  return {
    fields,
    summary,
    confidence: finalConfidence
  };
}

function extractMonto(text: string): ParsedExpense[string] | null {
  for (const pattern of PATTERNS.money) {
    const match = pattern.exec(text);
    if (match) {
      const amount = parseFloat(match[1].replace(/,/g, ''));
      if (amount > 0) {
        return {
          value: amount,
          confidence: 0.9,
          source: 'extracted'
        };
      }
    }
  }
  return null;
}

function extractFecha(text: string): ParsedExpense[string] | null {
  // Buscar fecha específica
  for (const pattern of PATTERNS.dates) {
    const matches = [...text.matchAll(pattern)];
    if (matches.length > 0) {
      const match = matches[0];

      if (match[0].includes('hoy')) {
        return {
          value: new Date().toISOString().split('T')[0],
          confidence: 0.95,
          source: 'extracted'
        };
      }

      if (match[0].includes('ayer')) {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        return {
          value: yesterday.toISOString().split('T')[0],
          confidence: 0.95,
          source: 'extracted'
        };
      }

      // Formato DD/MM/YYYY o DD de MONTH YYYY
      if (match[1] && match[2] && match[3]) {
        let day = match[1];
        let month = match[2];
        let year = match[3];

        // Si el mes es texto, convertir
        if (isNaN(parseInt(month))) {
          month = MONTHS[month.toLowerCase()] || month;
        }

        // Si el formato es DD/MM/YYYY, convertir
        if (match[0].includes('/')) {
          if (parseInt(year) < 100) year = '20' + year;
          if (month.length === 1) month = '0' + month;
          if (day.length === 1) day = '0' + day;

          // Validar fecha
          const date = new Date(`${year}-${month}-${day}`);
          if (!isNaN(date.getTime())) {
            return {
              value: `${year}-${month}-${day}`,
              confidence: 0.85,
              source: 'extracted'
            };
          }
        }
      }
    }
  }

  return null;
}

function extractProveedor(text: string): ParsedExpense[string] | null {
  for (const pattern of PATTERNS.providers) {
    const match = pattern.exec(text);
    if (match) {
      let proveedorName = match[0].trim();

      // Normalizar nombres conocidos
      proveedorName = proveedorName.replace(/home\s+depot/gi, 'Home Depot');
      proveedorName = proveedorName.replace(/pemex/gi, 'PEMEX');
      proveedorName = proveedorName.replace(/oxxo/gi, 'OXXO');

      return {
        value: proveedorName,
        confidence: 0.8,
        source: 'extracted'
      };
    }
  }

  // Buscar patrón "en [lugar]"
  const enPattern = /\ben\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ\s]+)/gi;
  const enMatch = enPattern.exec(text);
  if (enMatch) {
    return {
      value: enMatch[1].trim(),
      confidence: 0.6,
      source: 'extracted'
    };
  }

  return null;
}

function extractRFC(text: string): ParsedExpense[string] | null {
  const match = PATTERNS.rfc.exec(text.toUpperCase());
  if (match) {
    return {
      value: match[1],
      confidence: 0.95,
      source: 'extracted'
    };
  }
  return null;
}

function extractFormaPago(text: string): ParsedExpense[string] | null {
  for (const [method, patterns] of Object.entries(PATTERNS.paymentMethods)) {
    for (const pattern of patterns) {
      if (pattern.test(text)) {
        return {
          value: method,
          confidence: 0.8,
          source: 'extracted'
        };
      }
    }
  }
  return null;
}

function extractCategoria(text: string): ParsedExpense[string] | null {
  for (const [category, patterns] of Object.entries(PATTERNS.categories)) {
    for (const pattern of patterns) {
      if (pattern.test(text)) {
        return {
          value: category,
          confidence: 0.7,
          source: 'extracted'
        };
      }
    }
  }
  return null;
}

function generateDescripcion(text: string, fields: ParsedExpense): ParsedExpense[string] | null {
  const categoria = fields.categoria?.value || 'Gasto';
  const proveedor = fields['proveedor.nombre']?.value || '';
  const monto = fields.monto_total?.value || '';

  let descripcion = `${categoria}`;
  if (proveedor) descripcion += ` en ${proveedor}`;
  if (monto) descripcion += ` por $${monto}`;

  return {
    value: descripcion,
    confidence: 0.6,
    source: 'inferred'
  };
}

function generateSummary(fields: ParsedExpense): string {
  const categoria = fields.categoria?.value || 'Gasto';
  const monto = fields.monto_total?.value;
  const proveedor = fields['proveedor.nombre']?.value;
  const fecha = fields.fecha_gasto?.value;

  let summary = `Detecté: **${categoria}**`;
  if (monto) summary += ` por **$${monto}**`;
  if (proveedor) summary += ` con **${proveedor}**`;
  if (fecha) summary += ` el **${fecha}**`;

  return summary;
}

export function mergeWithFormState(
  parsed: ParsedExpense,
  currentForm: Record<string, any>
): Record<string, any> {
  const merged = { ...currentForm };

  for (const [fieldPath, parsedValue] of Object.entries(parsed)) {
    const currentValue = getNestedValue(merged, fieldPath);

    // Solo autocompletar si el campo está vacío o el usuario no lo ha editado manualmente
    if (!currentValue || !merged._manualEdits?.[fieldPath]) {
      setNestedValue(merged, fieldPath, parsedValue.value);

      // Guardar metadatos de confianza
      if (!merged._confidence) merged._confidence = {};
      merged._confidence[fieldPath] = parsedValue.confidence;
    }
  }

  return merged;
}

function getNestedValue(obj: Record<string, any>, path: string): any {
  return path.split('.').reduce((current, key) => current?.[key], obj);
}

function setNestedValue(obj: Record<string, any>, path: string, value: any): void {
  const keys = path.split('.');
  const lastKey = keys.pop()!;
  const target = keys.reduce((current, key) => {
    if (!current[key]) current[key] = {};
    return current[key];
  }, obj);
  target[lastKey] = value;
}
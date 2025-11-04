"""
Procesador inteligente de tickets con extracción de información
Identifica automáticamente el tipo de merchant y call-to-action
"""

import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class TicketProcessor:
    """
    Procesador inteligente que extrae información estructurada de tickets
    y determina el call-to-action para facturación
    """

    def __init__(self):
        # Patrones de extracción mejorados
        self.patterns = {
            'rfc': r'RFC[:\s]*([A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3})',
            'folio': r'(?:Folio\s+No|NO\.\s*FOLIO|FOLIO|TICKET)[:\s]*([A-Z0-9\-]+)',
            'fecha': r'(?:Fecha|FECHA)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            'hora': r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)',
            'subtotal': r'(?:Subtotal|Sub|SUBTOTAL)[:\s]*\$?\s*([\d,]+\.?\d*)',
            'iva': r'(?:IVA|I\.V\.A\.?)[:\s]*\$?\s*([\d,]+\.?\d*)',
            'total': r'(?:Total|TOTAL)[:\s]*\$?\s*([\d,]+\.?\d*)',
            'codigo_verificacion': r'(?:Código|Code)[:\s]*([A-Z0-9]{6,})',
            'direccion': r'(?:Sucursal|Tienda|Store|ESTACIÓN)[:\s]*(.+?)(?:\n|$)',
            'telefono': r'Tel[:\s]*([\d\s\-\(\)]+)',
            'litros': r'(\d+\.?\d*)\s*(?:LTS|LITROS|L)',
            'precio_litro': r'\$?\s*([\d,]+\.?\d*)/L',
        }

        # Configuración de merchants con sus portales
        self.merchant_config = {
            'PEMEX': {
                'rfc': 'PEP970814SF3',
                'portal': 'https://factura.pemex.com',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['PEMEX', 'GASOLINERA PEMEX', 'ESTACIÓN DE SERVICIO', 'PETRÓLEOS MEXICANOS'],
            },
            'SHELL': {
                'rfc': 'SHE850912XY4',
                'portal': 'https://factura.shell.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['SHELL', 'SHELL ESTACIÓN', 'COMBUSTIBLES SHELL'],
            },
            'MOBIL': {
                'rfc': 'MOB930228AB1',
                'portal': 'https://factura.mobil.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['MOBIL', 'MOBIL GASOLINERA', 'SERVICIOS AUTOMOTRICES'],
            },
            'MEJOR_FUTURO': {
                'rfc': 'MFU761216I40',
                'portal': 'https://facturacion.inforest.com.mx',
                'portal_alternativo': 'https://facturacion.infocaja.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['MEJOR FUTURO', 'MEJOR FUTURO S.A. DE C.V.', 'MFU761216I40'],
            },
            'OXXO': {
                'rfc': 'OXX970814HS9',
                'portal': 'https://factura.oxxo.com',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['OXXO', 'CADENA COMERCIAL OXXO'],
            },
            'WALMART': {
                'rfc': 'WAL9709244W4',
                'portal': 'https://factura.walmart.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total', 'tienda'],
                'identificadores': ['WALMART', 'WAL-MART', 'SUPERCENTER'],
            },
            'COSTCO': {
                'rfc': 'COS050815PE4',
                'portal': 'https://facturaelectronica.costco.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total', 'almacen'],
                'identificadores': ['COSTCO', 'WHOLESALE'],
            },
            'HOME_DEPOT': {
                'rfc': 'HDM930228Q90',
                'portal': 'https://homedepot.com.mx/facturacion',
                'campos_requeridos': ['folio', 'fecha', 'total', 'tienda'],
                'identificadores': ['HOME DEPOT', 'THE HOME DEPOT'],
            },
            'SORIANA': {
                'rfc': 'SOR810511HN9',
                'portal': 'https://facturacion.soriana.com',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['SORIANA', 'HIPER SORIANA', 'MEGA SORIANA'],
            },
            'FARMACIA_DEL_AHORRO': {
                'rfc': 'FDA970304GH6',
                'portal': 'https://facturacion.fahorro.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['FARMACIA DEL AHORRO', 'FAHORRO'],
            },
            'CHEDRAUI': {
                'rfc': 'CCH850701TN7',
                'portal': 'https://factura.chedraui.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total', 'sucursal'],
                'identificadores': ['CHEDRAUI', 'SUPER CHE'],
            },
            '7_ELEVEN': {
                'rfc': 'SEL991209KE7',
                'portal': 'https://facturacion.7-eleven.com.mx',
                'campos_requeridos': ['folio', 'fecha', 'total'],
                'identificadores': ['7-ELEVEN', '7 ELEVEN', 'SEVEN ELEVEN'],
            },
        }

    async def process_ticket(self, ocr_text: str) -> Dict[str, Any]:
        """
        Procesa el texto OCR y extrae toda la información relevante

        Args:
            ocr_text: Texto extraído por OCR

        Returns:
            Dict con información estructurada y call-to-action
        """
        # Limpiar texto
        clean_text = self._clean_text(ocr_text)

        # Identificar merchant
        merchant_info = self._identify_merchant(clean_text)

        # Extraer campos
        extracted_data = self._extract_fields(clean_text)

        # Validar campos requeridos
        validation = self._validate_required_fields(merchant_info, extracted_data)

        # Generar call-to-action
        call_to_action = self._generate_call_to_action(merchant_info, extracted_data, validation)

        return {
            'merchant': merchant_info,
            'extracted_data': extracted_data,
            'validation': validation,
            'call_to_action': call_to_action,
            'raw_text': ocr_text,
            'confidence': self._calculate_confidence(extracted_data, validation)
        }

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza el texto OCR"""
        # Convertir a mayúsculas para búsqueda
        text = text.upper()
        # Normalizar espacios
        text = re.sub(r'\s+', ' ', text)
        # Remover caracteres especiales innecesarios
        text = re.sub(r'[^\w\s\.\,\:\-\/\$]', '', text)
        return text.strip()

    def _identify_merchant(self, text: str) -> Optional[Dict[str, Any]]:
        """Identifica el merchant del ticket"""
        for merchant_name, config in self.merchant_config.items():
            for identifier in config['identificadores']:
                if identifier in text:
                    logger.info(f"Merchant identificado: {merchant_name}")
                    return {
                        'name': merchant_name,
                        'rfc': config['rfc'],
                        'portal': config['portal'],
                        'campos_requeridos': config['campos_requeridos']
                    }

        # Intentar extraer RFC genérico
        rfc_match = re.search(self.patterns['rfc'], text)
        if rfc_match:
            logger.info(f"RFC encontrado pero merchant no identificado: {rfc_match.group(1)}")
            return {
                'name': 'DESCONOCIDO',
                'rfc': rfc_match.group(1),
                'portal': None,
                'campos_requeridos': ['folio', 'fecha', 'total']
            }

        return None

    def _extract_fields(self, text: str) -> Dict[str, Any]:
        """Extrae campos específicos del texto"""
        extracted = {}

        for field, pattern in self.patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Para folio, manejar múltiples grupos de captura
                if field == 'folio':
                    value = match.group(1) if match.group(1) else match.group(2)
                else:
                    value = match.group(1)

                if value:
                    value = value.strip()

                    # Limpiar valores monetarios
                    if field in ['subtotal', 'iva', 'total']:
                        value = value.replace(',', '').replace('$', '')
                        try:
                            value = float(value)
                        except:
                            pass

                    extracted[field] = value

        # Extraer elementos de lista (productos)
        extracted['items'] = self._extract_items(text)

        return extracted

    def _extract_items(self, text: str) -> List[Dict[str, Any]]:
        """Extrae lista de productos del ticket"""
        items = []

        # Patrón para líneas de productos (ejemplo: "PRODUCTO 1.00 $25.50")
        item_pattern = r'([A-Z\s]+)\s+(\d+\.?\d*)\s+\$?([\d,]+\.?\d*)'
        matches = re.findall(item_pattern, text)

        for match in matches[:10]:  # Limitar a 10 items
            try:
                items.append({
                    'descripcion': match[0].strip(),
                    'cantidad': float(match[1]),
                    'precio': float(match[2].replace(',', ''))
                })
            except:
                continue

        return items

    def _validate_required_fields(self, merchant_info: Dict, extracted_data: Dict) -> Dict[str, Any]:
        """Valida que se hayan extraído los campos requeridos"""
        if not merchant_info:
            return {
                'is_valid': False,
                'missing_fields': ['merchant'],
                'errors': ['No se pudo identificar el merchant']
            }

        missing_fields = []
        for field in merchant_info.get('campos_requeridos', []):
            if field not in extracted_data or not extracted_data[field]:
                missing_fields.append(field)

        return {
            'is_valid': len(missing_fields) == 0,
            'missing_fields': missing_fields,
            'errors': [f"Campo requerido faltante: {field}" for field in missing_fields]
        }

    def _generate_call_to_action(self, merchant_info: Dict, extracted_data: Dict, validation: Dict) -> Dict[str, Any]:
        """
        Genera el call-to-action basado en la información extraída
        """
        if not merchant_info:
            return {
                'action': 'MANUAL_REVIEW',
                'message': 'No se pudo identificar el merchant. Requiere revisión manual.',
                'can_auto_process': False
            }

        if not validation['is_valid']:
            return {
                'action': 'MISSING_DATA',
                'message': f"Faltan campos requeridos: {', '.join(validation['missing_fields'])}",
                'can_auto_process': False,
                'portal_url': merchant_info.get('portal'),
                'missing_fields': validation['missing_fields']
            }

        # Si tenemos toda la información
        if merchant_info.get('portal'):
            return {
                'action': 'AUTO_INVOICE',
                'message': f"Listo para facturar en {merchant_info['name']}",
                'can_auto_process': True,
                'portal_url': merchant_info['portal'],
                'merchant_name': merchant_info['name'],
                'data_to_submit': {
                    'rfc_receptor': None,  # Se llenará con datos fiscales del usuario
                    'folio': extracted_data.get('folio'),
                    'fecha': extracted_data.get('fecha'),
                    'total': extracted_data.get('total'),
                    'uso_cfdi': 'G03',  # Gastos en general
                    'forma_pago': '04',  # Tarjeta de crédito (default)
                    'metodo_pago': 'PUE'  # Pago en una sola exhibición
                }
            }
        else:
            return {
                'action': 'MANUAL_INVOICE',
                'message': f"Merchant {merchant_info['name']} requiere facturación manual",
                'can_auto_process': False,
                'merchant_rfc': merchant_info.get('rfc')
            }

    def _calculate_confidence(self, extracted_data: Dict, validation: Dict) -> float:
        """Calcula un score de confianza de la extracción"""
        base_score = 0.0

        # Puntos por campos extraídos
        important_fields = ['folio', 'fecha', 'total', 'rfc']
        for field in important_fields:
            if field in extracted_data and extracted_data[field]:
                base_score += 0.2

        # Puntos por validación
        if validation['is_valid']:
            base_score += 0.2

        return min(base_score, 1.0)


# Función helper para usar desde el worker
async def process_ticket_with_intelligence(ocr_text: str) -> Dict[str, Any]:
    """
    Procesa un ticket con extracción inteligente

    Args:
        ocr_text: Texto extraído por OCR

    Returns:
        Información estructurada y call-to-action
    """
    processor = TicketProcessor()
    return await processor.process_ticket(ocr_text)


if __name__ == "__main__":
    # Test del procesador
    import asyncio

    test_text = """
    OXXO TIENDA #4512
    RFC: OXX970814HS9
    AV. INSURGENTES 234
    COL. ROMA NORTE

    FECHA: 15/01/2024 14:35:22
    FOLIO: A-789456

    COCA COLA 600ML     1.00  $18.00
    SABRITAS ORIGINAL   2.00  $32.00
    GANSITO MARINELA    1.00  $15.00

    SUBTOTAL: $65.00
    IVA: $10.40
    TOTAL: $75.40

    GRACIAS POR SU COMPRA
    """

    async def test():
        result = await process_ticket_with_intelligence(test_text)
        print("Resultado del procesamiento:")
        print(f"Merchant: {result['merchant']}")
        print(f"Datos extraídos: {result['extracted_data']}")
        print(f"Call to Action: {result['call_to_action']}")
        print(f"Confianza: {result['confidence']}")

    asyncio.run(test())
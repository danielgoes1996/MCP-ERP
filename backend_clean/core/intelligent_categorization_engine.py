#!/usr/bin/env python3
"""
Motor de Categorización Inteligente Jerárquico
Versión Enterprise para clasificación automática avanzada
"""
import re
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass

@dataclass
class CategoryResult:
    """Resultado de categorización con metadatos"""
    category: str
    subcategory: str
    confidence: float
    transaction_subtype: str
    movement_kind: str  # Ingreso, Gasto, Transferencia
    display_type: str   # transaction, balance_inicial, transfer
    tax_deductible: bool = False
    requires_receipt: bool = True
    description_clean: str = ""

class IntelligentCategorizationEngine:
    def __init__(self):
        # 🎯 CAPA 1: PATTERNS ESPECÍFICOS (Alta confianza)
        self.specific_patterns = {
            # INGRESOS FINANCIEROS
            'Ingresos Financieros': {
                'subcategories': {
                    'Intereses Bancarios': [r'intereses\s+ganados', r'rendimiento', r'interest', r'ganancias'],
                    'Depósitos SPEI': [r'deposito\s+spei', r'spei.*deposito', r'transferencia.*recibida'],
                    'Depósitos TEF': [r'deposito\s+tef', r'tef.*deposito'],
                    'Depósitos Nómina': [r'deposito.*nomina', r'sueldo', r'salario', r'payroll']
                },
                'movement_kind': 'Ingreso',
                'tax_deductible': False,
                'requires_receipt': False
            },

            # TRANSPORTE
            'Transporte': {
                'subcategories': {
                    'Gasolina': [r'gasoliner[aoi]', r'pemex', r'shell', r'bp\s', r'mobil', r'g500', r'combustible'],
                    'Uber/Taxi': [r'uber', r'didi', r'taxi', r'cabify', r'beat'],
                    'Peajes': [r'peaje', r'cuota', r'autopista', r'carretera'],
                    'Estacionamiento': [r'estacionamiento', r'parking', r'pension']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': True,
                'requires_receipt': True
            },

            # TECNOLOGÍA Y SOFTWARE
            'Tecnología': {
                'subcategories': {
                    'Software': [r'google.*storage', r'microsoft', r'adobe', r'spotify', r'netflix', r'zoom'],
                    'Hardware': [r'amazon.*tech', r'best\s*buy', r'liverpool.*electronic'],
                    'Telecomunicaciones': [r'telcel', r'movistar', r'at&t', r'unefon', r'telmex', r'izzi']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': True,
                'requires_receipt': True
            },

            # PAPELERÍA Y OFICINA
            'Oficina': {
                'subcategories': {
                    'Papelería': [r'office\s*max', r'office\s*depot', r'staples', r'papeleria'],
                    'Suministros': [r'material.*oficina', r'toner', r'papel'],
                    'Muebles': [r'escritorio', r'silla', r'mueble.*oficina']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': True,
                'requires_receipt': True
            },

            # NÓMINA Y SERVICIOS GUBERNAMENTALES
            'Servicios Gubernamentales': {
                'subcategories': {
                    'Nómina': [r'gpdc.*ejercito', r'sedena', r'pago.*nomina', r'sueldo.*gobierno'],
                    'Impuestos': [r'isr.*retenido', r'impuesto', r'sat\s', r'hacienda'],
                    'Servicios Públicos': [r'cfe\s', r'luz\s', r'agua\s', r'predial']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': False,
                'requires_receipt': True
            },

            # COMPRAS ONLINE
            'Compras Online': {
                'subcategories': {
                    'Marketplace Internacional': [r'temu', r'amazon', r'aliexpress', r'wish'],
                    'Marketplace Nacional': [r'mercadolibre', r'mercado\s*libre', r'liverpool'],
                    'Pagos Digitales': [r'mercado\s*pago', r'paypal', r'stripe']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': False,
                'requires_receipt': True
            },

            # TRANSFERENCIAS (No son gastos)
            'Transferencias': {
                'subcategories': {
                    'Transferencias Propias': [r'traspaso\s+spei.*inbured', r'transferencia.*propia', r'movimiento.*cuentas'],
                    'Pagos a Terceros': [r'pago.*spei', r'transferencia.*pago'],
                    'Inversiones': [r'inversion', r'ahorro', r'plazo\s*fijo']
                },
                'movement_kind': 'Transferencia',
                'tax_deductible': False,
                'requires_receipt': False
            },

            # SUPERMERCADOS
            'Supermercados': {
                'subcategories': {
                    'Walmart': [r'walmart', r'wm\s+express', r'bodega\s*aurrera'],
                    'Soriana': [r'soriana', r'city\s*club'],
                    'Otros': [r'chedraui', r'costco', r'sams', r'comercial\s*mexicana']
                },
                'movement_kind': 'Gasto',
                'tax_deductible': False,
                'requires_receipt': True
            }
        }

        # 🎯 CAPA 2: KEYWORDS GENERALES (Confianza media)
        self.general_keywords = {
            'Restaurantes': [r'restaurant', r'rest\s', r'comida', r'pizza', r'burger', r'mcdonalds', r'kfc'],
            'Salud': [r'hospital', r'clinica', r'medic', r'farmacia', r'doctor', r'dental'],
            'Educación': [r'escuela', r'universidad', r'curso', r'capacitacion', r'book'],
            'Viajes': [r'hotel', r'vuelo', r'airline', r'booking', r'trivago'],
            'Entretenimiento': [r'cine', r'teatro', r'concierto', r'evento', r'diversión']
        }

        # 🔍 PATTERNS DE CORRECCIÓN DE SIGNOS
        self.sign_correction_patterns = {
            'force_income': [
                r'intereses\s+ganados', r'rendimiento', r'deposito.*spei', r'deposito.*tef',
                r'abono', r'transferencia.*recibida', r'pago.*recibido'
            ],
            'force_expense': [
                r'comision', r'anualidad', r'isr.*retenido', r'impuesto'
            ],
            'force_transfer': [
                r'traspaso', r'transferencia.*propia', r'movimiento.*cuentas'
            ]
        }

    def _determine_correct_transaction_type(self, description: str, amount: float) -> Tuple[str, str, str]:
        """
        Determina el tipo correcto de transacción basado en keywords y lógica de negocio
        Returns: (transaction_type, movement_kind, display_type)
        """
        desc_lower = description.lower().strip()

        # Balance inicial
        if re.search(r'balance\s+inicial', desc_lower):
            return "credit", "Transferencia", "balance_inicial"

        # Forzar como ingreso
        for pattern in self.sign_correction_patterns['force_income']:
            if re.search(pattern, desc_lower):
                return "credit", "Ingreso", "transaction"

        # Forzar como transferencia
        for pattern in self.sign_correction_patterns['force_transfer']:
            if re.search(pattern, desc_lower):
                return "credit" if amount > 0 else "debit", "Transferencia", "transaction"

        # Forzar como gasto
        for pattern in self.sign_correction_patterns['force_expense']:
            if re.search(pattern, desc_lower):
                return "debit", "Gasto", "transaction"

        # Lógica por defecto: usar el monto
        if amount > 0:
            # Monto positivo - probablemente ingreso
            return "credit", "Ingreso", "transaction"
        else:
            # Monto negativo - gasto
            return "debit", "Gasto", "transaction"

    def _clean_description(self, raw_description: str) -> str:
        """
        Limpia la descripción manteniendo lo esencial
        """
        if not raw_description:
            return ""

        # Remover fechas al inicio (MAR 01, etc.)
        cleaned = re.sub(r'^[A-Z]{3}\s+\d{1,2}\s+', '', raw_description)

        # Remover números de referencia largos
        cleaned = re.sub(r'\d{10,}', '', cleaned)

        # Remover montos al final
        cleaned = re.sub(r'\s+[\d,]+\.?\d*\s*$', '', cleaned)

        # Limpiar espacios múltiples
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Capitalizar apropiadamente
        words = cleaned.split()
        important_words = []
        for word in words:
            if len(word) > 2:
                important_words.append(word.capitalize())
            else:
                important_words.append(word.upper())

        return ' '.join(important_words)

    def categorize_advanced(self, description: str, amount: float, raw_description: str = None) -> CategoryResult:
        """
        Categorización avanzada jerárquica con corrección automática
        """
        if not description:
            return CategoryResult(
                category="Sin categoría",
                subcategory="Desconocido",
                confidence=0.0,
                transaction_subtype="unknown",
                movement_kind="Gasto",
                display_type="transaction"
            )

        desc_lower = description.lower().strip()
        raw_desc = raw_description or description
        clean_desc = self._clean_description(raw_desc)

        # Determinar tipo correcto de transacción
        transaction_type, movement_kind, display_type = self._determine_correct_transaction_type(
            description, amount
        )

        # CAPA 1: Búsqueda específica (alta confianza)
        for category, config in self.specific_patterns.items():
            for subcategory, patterns in config['subcategories'].items():
                for pattern in patterns:
                    if re.search(pattern, desc_lower):
                        # Sobrescribir movement_kind si está en la configuración
                        final_movement_kind = config.get('movement_kind', movement_kind)

                        return CategoryResult(
                            category=category,
                            subcategory=subcategory,
                            confidence=0.9,
                            transaction_subtype=subcategory.lower().replace(' ', '_'),
                            movement_kind=final_movement_kind,
                            display_type=display_type,
                            tax_deductible=config.get('tax_deductible', False),
                            requires_receipt=config.get('requires_receipt', True),
                            description_clean=clean_desc
                        )

        # CAPA 2: Keywords generales (confianza media)
        for category, patterns in self.general_keywords.items():
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    return CategoryResult(
                        category=category,
                        subcategory="General",
                        confidence=0.6,
                        transaction_subtype=category.lower().replace(' ', '_'),
                        movement_kind=movement_kind,
                        display_type=display_type,
                        description_clean=clean_desc
                    )

        # FALLBACK: Sin categoría pero con tipo correcto
        return CategoryResult(
            category="Sin categoría",
            subcategory="Desconocido",
            confidence=0.0,
            transaction_subtype="unknown",
            movement_kind=movement_kind,
            display_type=display_type,
            description_clean=clean_desc
        )

    def get_deductibility_info(self, category: str) -> Dict:
        """
        Retorna información fiscal de deducibilidad
        """
        for cat_name, config in self.specific_patterns.items():
            if cat_name == category:
                return {
                    'tax_deductible': config.get('tax_deductible', False),
                    'requires_receipt': config.get('requires_receipt', True),
                    'iva_rate': 0.16 if config.get('tax_deductible') else 0.0
                }

        return {
            'tax_deductible': False,
            'requires_receipt': True,
            'iva_rate': 0.0
        }

# Test del motor mejorado
if __name__ == "__main__":
    engine = IntelligentCategorizationEngine()

    test_cases = [
        ("DEPOSITO SPEI ANA LAURA RAMIREZ SANCHEZ CLAVE DE RASTREO", 2600.0),
        ("GPO GASOLINERO BERISA MX", -1152.74),
        ("TRASPASO SPEI INBURED", -440.80),
        ("INTERESES GANADOS", -121.89),  # Mal signo en el PDF
        ("OFFICE MAX MATERIAL OFICINA", -245.50),
        ("GOOGLE STORAGE CLOUD", -99.00),
        ("GPDC EJERCITO PAGO NOMINA", 15000.00),
        ("ISR RETENIDO MENSUAL", -2500.00),
        ("TEMU COM MX COMPRA ONLINE", -662.75)
    ]

    print("🧪 TESTING INTELLIGENT CATEGORIZATION ENGINE")
    print("=" * 80)

    for desc, amount in test_cases:
        result = engine.categorize_advanced(desc, amount)
        print(f"\n📝 {desc}")
        print(f"   💰 Amount: ${amount:,.2f} → Type: {result.movement_kind}")
        print(f"   🏷️ Category: {result.category} → {result.subcategory}")
        print(f"   📊 Confidence: {result.confidence:.1f}")
        print(f"   📄 Clean: {result.description_clean}")
        print(f"   💼 Tax Deductible: {'✅' if result.tax_deductible else '❌'}")
        print(f"   🧾 Requires Receipt: {'✅' if result.requires_receipt else '❌'}")
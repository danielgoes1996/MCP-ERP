#!/usr/bin/env python3
"""
Enhanced Categorization Engine for Bank Transactions
Implementa las mejoras identificadas para producción
"""
import re
from typing import Dict, Tuple
from dateutil import parser as date_parser

class EnhancedCategorizationEngine:
    def __init__(self):
        self.category_patterns = {
            # Transporte
            'Transporte': [
                r'gasoliner[aoi]', r'pemex', r'shell', r'bp\s', r'mobil',
                r'uber', r'didi', r'taxi', r'transporte', r'combust',
                r'gasolinero', r'g500'
            ],

            # Compras en línea
            'Compras Online': [
                r'temu', r'amazon', r'mercadolibre', r'mercado\s*libre',
                r'ebay', r'aliexpress', r'wish', r'shopify', r'paypal'
            ],

            # Supermercados y consumo
            'Supermercados': [
                r'walmart', r'wm\s+express', r'soriana', r'chedraui',
                r'costco', r'sams', r'comercial mexicana', r'oxxo',
                r'seven\s*eleven', r'7\s*eleven'
            ],

            # Restaurantes
            'Restaurantes': [
                r'restaurant', r'rest\s', r'comida', r'pizza', r'burger',
                r'mcdonalds', r'kfc', r'subway', r'starbucks', r'cafe'
            ],

            # Servicios financieros
            'Servicios Financieros': [
                r'banco', r'banamex', r'bbva', r'santander', r'hsbc',
                r'banorte', r'comision', r'intereses', r'anualidad'
            ],

            # Telecomunicaciones
            'Telecomunicaciones': [
                r'telcel', r'movistar', r'at&t', r'unefon', r'netflix',
                r'spotify', r'disney', r'amazon\s*prime', r'telmex'
            ],

            # Salud
            'Salud': [
                r'hospital', r'clinica', r'medic', r'farmacia', r'doctor',
                r'consultorio', r'laboratorio', r'rayos\s*x'
            ],

            # Ingresos SPEI
            'Ingresos SPEI': [
                r'deposito\s+spei', r'spei.*deposito', r'transferencia.*recibida',
                r'abono.*spei'
            ],

            # Ingresos TEF
            'Ingresos TEF': [
                r'deposito\s+tef', r'tef.*deposito', r'transferencia.*tef'
            ],

            # Fletes y logística
            'Fletes/Logística': [
                r'transport.*julian', r'flete', r'logistica', r'envio',
                r'paqueteria', r'mensajeria', r'dhl', r'fedex', r'ups'
            ]
        }

        self.transaction_subtypes = {
            'balance_inicial': [r'balance\s+inicial'],
            'deposito_spei': [r'deposito\s+spei'],
            'deposito_tef': [r'deposito\s+tef'],
            'gasto_gasolina': [r'gasoliner[aoi]', r'pemex', r'shell'],
            'gasto_supermercado': [r'walmart', r'wm\s+express', r'soriana'],
            'gasto_online': [r'temu', r'amazon', r'mercadolibre'],
            'transferencia_spei': [r'traspaso\s+spei', r'spei.*traspaso']
        }

    def normalize_date(self, date_str: str) -> str:
        """
        Normaliza fechas a formato ISO 2024-03-01
        Maneja formatos como: MAR 01, 1/3/2024, etc.
        """
        try:
            # Si ya está en formato ISO, retornarlo
            if re.match(r'\d{4}-\d{2}-\d{2}', str(date_str)):
                return str(date_str)

            # Manejar formato mexicano con meses en español
            month_map = {
                'ENE': 'JAN', 'FEB': 'FEB', 'MAR': 'MAR', 'ABR': 'APR',
                'MAY': 'MAY', 'JUN': 'JUN', 'JUL': 'JUL', 'AGO': 'AUG',
                'SEP': 'SEP', 'OCT': 'OCT', 'NOV': 'NOV', 'DIC': 'DEC'
            }

            date_normalized = str(date_str).upper()
            for es, en in month_map.items():
                date_normalized = date_normalized.replace(es, en)

            # Agregar año si no está presente
            if not re.search(r'\d{4}', date_normalized):
                date_normalized += ' 2024'

            # Parsear fecha
            parsed_date = date_parser.parse(date_normalized, dayfirst=False)
            return parsed_date.strftime('%Y-%m-%d')

        except Exception as e:
            print(f"⚠️ Error parsing date '{date_str}': {e}")
            return str(date_str)  # Fallback

    def categorize_transaction(self, description: str) -> Tuple[str, float, str]:
        """
        Categoriza una transacción y devuelve:
        (categoría, confianza, subtipo)
        """
        if not description:
            return "Sin categoría", 0.0, "unknown"

        desc_lower = description.lower().strip()

        # Buscar subtipo primero
        transaction_subtype = "transaction"
        for subtype, patterns in self.transaction_subtypes.items():
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    transaction_subtype = subtype
                    break
            if transaction_subtype != "transaction":
                break

        # Buscar categoría
        for category, patterns in self.category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    # Calcular confianza basada en qué tan específico es el match
                    confidence = 0.8 if len(pattern) > 5 else 0.6
                    return category, confidence, transaction_subtype

        return "Sin categoría", 0.0, transaction_subtype

    def determine_transaction_type(self, description: str, amount: float) -> Tuple[str, str, str]:
        """
        Determina transaction_type, movement_kind y display_type
        basado en descripción y monto
        """
        desc_lower = description.lower().strip()

        # Balance inicial
        if re.search(r'balance\s+inicial', desc_lower):
            return "credit", "Transferencia", "balance_inicial"

        # Ingresos (SPEI, TEF, depósitos)
        if re.search(r'deposito|abono|spei.*recib|tef.*recib', desc_lower):
            return "credit", "Ingreso", "transaction"

        # Todo lo demás son gastos
        return "debit", "Gasto", "transaction"

    def separate_cargo_abono(self, amount: float, transaction_type: str) -> Tuple[float, float]:
        """
        Separa monto en cargo_amount y abono_amount
        """
        if transaction_type == "credit":
            return 0.0, abs(amount)
        else:
            return abs(amount), 0.0

    def clean_description(self, raw_description: str) -> str:
        """
        Limpia la descripción manteniendo lo esencial
        """
        if not raw_description:
            return ""

        # Remover caracteres especiales excesivos
        cleaned = re.sub(r'[^\w\s\-\.]', ' ', raw_description)

        # Remover espacios múltiples
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Capitalizar primera letra de cada palabra importante
        words = cleaned.split()
        important_words = []

        for word in words:
            if len(word) > 2:  # Solo palabras importantes
                important_words.append(word.capitalize())
            else:
                important_words.append(word.upper())

        return ' '.join(important_words).strip()

    def process_transaction(self,
                          description: str,
                          amount: float,
                          date_str: str,
                          raw_description: str = None) -> Dict:
        """
        Procesa una transacción completa aplicando todas las mejoras
        """
        # 1. Normalizar fecha
        normalized_date = self.normalize_date(date_str)

        # 2. Limpiar descripción
        cleaned_desc = self.clean_description(description)
        raw_desc = raw_description or description

        # 3. Categorizar
        category, confidence, subtype = self.categorize_transaction(description)

        # 4. Determinar tipos
        transaction_type, movement_kind, display_type = self.determine_transaction_type(description, amount)

        # 5. Separar cargo/abono
        cargo_amount, abono_amount = self.separate_cargo_abono(amount, transaction_type)

        return {
            'date': normalized_date,
            'description': cleaned_desc,
            'description_raw': raw_desc,
            'amount': amount,
            'transaction_type': transaction_type,
            'movement_kind': movement_kind,
            'display_type': display_type,
            'transaction_subtype': subtype,
            'category_auto': category,
            'category_confidence': confidence,
            'cargo_amount': cargo_amount,
            'abono_amount': abono_amount
        }

# Test de la clase
if __name__ == "__main__":
    engine = EnhancedCategorizationEngine()

    # Test cases
    test_transactions = [
        ("BALANCE INICIAL", 0.0, "MAR 01"),
        ("DEPOSITO SPEI ANA LAURA RAMIREZ SANCHEZ CLAVE DE RASTREO", 2600.0, "MAR 04"),
        ("GPO GASOLINERO BERISA MX", 1152.74, "MAR 04"),
        ("WM EXPRESS PAB CAMPSTR MX", 322.02, "MAR 04"),
        ("TEMU COM MX", 662.75, "MAR 08")
    ]

    print("🧪 TESTING ENHANCED CATEGORIZATION ENGINE")
    print("=" * 60)

    for desc, amount, date in test_transactions:
        result = engine.process_transaction(desc, amount, date)
        print(f"\n📝 {desc}")
        print(f"   📅 Fecha: {result['date']}")
        print(f"   💰 Tipo: {result['transaction_type']} | {result['movement_kind']}")
        print(f"   🏷️ Categoría: {result['category_auto']} ({result['category_confidence']:.1f})")
        print(f"   🔍 Subtipo: {result['transaction_subtype']}")
        print(f"   💸 Cargo: ${result['cargo_amount']:.2f} | Abono: ${result['abono_amount']:.2f}")
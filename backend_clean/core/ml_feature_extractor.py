"""
ML Feature Extractor - Extrae características ML de gastos para detección de duplicados
"""

import json
import re
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MLFeatureExtractor:
    """
    Extractor de características ML para gastos
    """

    def __init__(self):
        # Patrones para categorización automática
        self.category_patterns = {
            'gasolina': [r'gas.*station', r'pemex', r'shell', r'bp', r'gasolina', r'combustible'],
            'restaurant': [r'restaurant', r'cafe', r'starbucks', r'mcdonalds', r'burger', r'pizza'],
            'grocery': [r'walmart', r'costco', r'supermarket', r'grocery', r'oxxo', r'seven', r'7-eleven'],
            'transport': [r'uber', r'taxi', r'metro', r'transporte', r'peaje', r'toll'],
            'office': [r'office', r'staples', r'papeleria', r'oficina', r'suministros'],
            'hotel': [r'hotel', r'motel', r'hostel', r'marriott', r'hilton', r'holiday'],
            'parking': [r'parking', r'estacionamiento', r'valet'],
            'pharmacy': [r'pharmacy', r'farmacia', r'cvs', r'walgreens', r'guadalajara']
        }

        # Patrones para proveedores comunes
        self.vendor_patterns = {
            'chain_store': [r'walmart', r'costco', r'home depot', r'best buy'],
            'gas_station': [r'pemex', r'shell', r'bp', r'mobil', r'chevron'],
            'restaurant_chain': [r'mcdonalds', r'burger king', r'subway', r'dominos'],
            'pharmacy_chain': [r'cvs', r'walgreens', r'rite aid'],
            'hotel_chain': [r'marriott', r'hilton', r'hyatt', r'holiday inn']
        }

        # Keywords para análisis de texto
        self.expense_keywords = [
            'meal', 'food', 'gas', 'fuel', 'hotel', 'lodging', 'transport', 'taxi',
            'office', 'supplies', 'parking', 'toll', 'conference', 'meeting'
        ]

    def extract_features(self, expense: Dict[str, Any], include_embeddings: bool = False) -> Dict[str, Any]:
        """
        Extrae características ML completas de un gasto
        """
        try:
            features = {}

            # Características básicas
            features.update(self._extract_basic_features(expense))

            # Características textuales
            features.update(self._extract_text_features(expense))

            # Características numéricas
            features.update(self._extract_numeric_features(expense))

            # Características temporales
            features.update(self._extract_temporal_features(expense))

            # Características de categorización
            features.update(self._extract_category_features(expense))

            # Características de proveedor
            features.update(self._extract_vendor_features(expense))

            # Hash único del gasto para comparaciones
            features['expense_hash'] = self._generate_expense_hash(expense)

            # Calidad de los datos
            features['data_quality_score'] = self._calculate_data_quality(expense)

            # Metadata de extracción
            features['extraction_timestamp'] = datetime.utcnow().isoformat()
            features['feature_version'] = '1.0'
            features['extraction_method'] = 'rule_based'

            return features

        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {'error': str(e)}

    def _extract_basic_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características básicas"""
        return {
            'has_description': bool(expense.get('description')),
            'has_amount': bool(expense.get('amount')),
            'has_date': bool(expense.get('date')),
            'has_merchant': bool(expense.get('merchant_name')),
            'has_category': bool(expense.get('category')),
            'description_length': len(str(expense.get('description', ''))),
            'amount_value': float(expense.get('amount', 0)),
            'currency': expense.get('currency', 'MXN')
        }

    def _extract_text_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características del texto de descripción"""
        description = str(expense.get('description', '')).lower()
        merchant = str(expense.get('merchant_name', '')).lower()

        # Análisis de descripción
        desc_features = {
            'desc_word_count': len(description.split()),
            'desc_char_count': len(description),
            'desc_has_numbers': bool(re.search(r'\d', description)),
            'desc_has_special_chars': bool(re.search(r'[^a-zA-Z0-9\s]', description)),
            'desc_all_caps_ratio': sum(1 for c in description if c.isupper()) / max(len(description), 1),
        }

        # Análisis de merchant
        merchant_features = {
            'merchant_word_count': len(merchant.split()),
            'merchant_char_count': len(merchant),
            'merchant_has_numbers': bool(re.search(r'\d', merchant)),
        }

        # Keywords matching
        keyword_features = {}
        for keyword in self.expense_keywords:
            desc_key = f'desc_contains_{keyword}'
            merchant_key = f'merchant_contains_{keyword}'
            desc_features[desc_key] = keyword in description
            merchant_features[merchant_key] = keyword in merchant

        return {**desc_features, **merchant_features}

    def _extract_numeric_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características numéricas"""
        amount = float(expense.get('amount', 0))

        return {
            'amount_rounded': round(amount),
            'amount_has_cents': (amount % 1) != 0,
            'amount_log': __import__('math').log10(amount + 1),  # +1 para evitar log(0)
            'amount_range': self._classify_amount_range(amount),
            'is_round_number': amount in [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000],
            'amount_digits': len(str(int(amount)))
        }

    def _extract_temporal_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características temporales"""
        date_str = expense.get('date')
        if not date_str:
            return {'has_valid_date': False}

        try:
            if isinstance(date_str, str):
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                date_obj = date_str

            return {
                'has_valid_date': True,
                'year': date_obj.year,
                'month': date_obj.month,
                'day': date_obj.day,
                'weekday': date_obj.weekday(),  # 0=Monday, 6=Sunday
                'is_weekend': date_obj.weekday() >= 5,
                'hour': date_obj.hour,
                'is_business_hours': 9 <= date_obj.hour <= 17,
                'quarter': ((date_obj.month - 1) // 3) + 1,
                'day_of_year': date_obj.timetuple().tm_yday,
                'is_month_start': date_obj.day <= 5,
                'is_month_end': date_obj.day >= 25
            }

        except Exception as e:
            logger.warning(f"Error parsing date {date_str}: {e}")
            return {'has_valid_date': False}

    def _extract_category_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características de categorización automática"""
        description = str(expense.get('description', '')).lower()
        merchant = str(expense.get('merchant_name', '')).lower()
        text_combined = f"{description} {merchant}"

        category_scores = {}
        matched_patterns = {}

        for category, patterns in self.category_patterns.items():
            score = 0
            matched = []

            for pattern in patterns:
                if re.search(pattern, text_combined, re.IGNORECASE):
                    score += 1
                    matched.append(pattern)

            category_scores[f'category_score_{category}'] = score
            matched_patterns[f'category_patterns_{category}'] = matched

        # Categoría con mayor score
        best_category = max(category_scores.items(), key=lambda x: x[1])
        predicted_category = best_category[0].replace('category_score_', '') if best_category[1] > 0 else 'unknown'

        return {
            **category_scores,
            'predicted_category': predicted_category,
            'category_confidence': best_category[1] / len(self.category_patterns) if best_category[1] > 0 else 0
        }

    def _extract_vendor_features(self, expense: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae características del proveedor"""
        merchant = str(expense.get('merchant_name', '')).lower()

        vendor_features = {
            'is_chain_vendor': False,
            'vendor_type': 'unknown',
            'vendor_confidence': 0
        }

        # Buscar patrones de cadenas conocidas
        for vendor_type, patterns in self.vendor_patterns.items():
            for pattern in patterns:
                if re.search(pattern, merchant, re.IGNORECASE):
                    vendor_features.update({
                        'is_chain_vendor': True,
                        'vendor_type': vendor_type,
                        'vendor_confidence': 1.0
                    })
                    break

            if vendor_features['is_chain_vendor']:
                break

        return vendor_features

    def _classify_amount_range(self, amount: float) -> str:
        """Clasifica el monto en rangos"""
        if amount <= 0:
            return 'invalid'
        elif amount <= 100:
            return 'small'
        elif amount <= 500:
            return 'medium'
        elif amount <= 2000:
            return 'large'
        elif amount <= 10000:
            return 'very_large'
        else:
            return 'extreme'

    def _generate_expense_hash(self, expense: Dict[str, Any]) -> str:
        """Genera hash único para el gasto"""
        # Crear string único combinando campos clave
        hash_string = f"{expense.get('description', '')}{expense.get('amount', 0)}{expense.get('date', '')}{expense.get('merchant_name', '')}"
        return hashlib.md5(hash_string.encode()).hexdigest()

    def _calculate_data_quality(self, expense: Dict[str, Any]) -> float:
        """Calcula score de calidad de datos (0.0 - 1.0)"""
        score = 0.0
        max_score = 5.0

        # Descripción presente y de calidad
        description = expense.get('description', '')
        if description:
            score += 1.0
            if len(description) > 5:
                score += 0.5

        # Monto válido
        amount = expense.get('amount', 0)
        if amount > 0:
            score += 1.0

        # Fecha presente
        if expense.get('date'):
            score += 1.0

        # Merchant presente
        if expense.get('merchant_name'):
            score += 1.0

        # Categoría presente
        if expense.get('category'):
            score += 0.5

        return min(score / max_score, 1.0)

    def extract_features_for_comparison(self, expense1: Dict[str, Any], expense2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae características específicas para comparación de duplicados
        """
        features1 = self.extract_features(expense1)
        features2 = self.extract_features(expense2)

        comparison_features = {
            'amount_diff_ratio': abs(features1['amount_value'] - features2['amount_value']) / max(features1['amount_value'], features2['amount_value'], 1),
            'description_length_diff': abs(features1['description_length'] - features2['description_length']),
            'same_predicted_category': features1['predicted_category'] == features2['predicted_category'],
            'same_vendor_type': features1['vendor_type'] == features2['vendor_type'],
            'same_amount_range': features1['amount_range'] == features2['amount_range'],
            'both_round_numbers': features1['is_round_number'] and features2['is_round_number'],
            'data_quality_diff': abs(features1['data_quality_score'] - features2['data_quality_score'])
        }

        # Características temporales de comparación
        if features1.get('has_valid_date') and features2.get('has_valid_date'):
            comparison_features.update({
                'same_day': features1['day'] == features2['day'],
                'same_month': features1['month'] == features2['month'],
                'same_weekday': features1['weekday'] == features2['weekday'],
                'both_weekend': features1['is_weekend'] and features2['is_weekend'],
                'both_business_hours': features1['is_business_hours'] and features2['is_business_hours']
            })

        return comparison_features


# Factory function
_ml_extractor = None

def get_ml_feature_extractor() -> MLFeatureExtractor:
    """Obtener instancia global del extractor ML"""
    global _ml_extractor
    if _ml_extractor is None:
        _ml_extractor = MLFeatureExtractor()
    return _ml_extractor


def extract_expense_features(expense: Dict[str, Any], include_embeddings: bool = False) -> Dict[str, Any]:
    """
    Función helper para extraer características ML de un gasto
    """
    extractor = get_ml_feature_extractor()
    return extractor.extract_features(expense, include_embeddings)


def extract_comparison_features(expense1: Dict[str, Any], expense2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función helper para extraer características de comparación entre dos gastos
    """
    extractor = get_ml_feature_extractor()
    return extractor.extract_features_for_comparison(expense1, expense2)
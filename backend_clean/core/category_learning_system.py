"""
Category Learning System - Sistema de aprendizaje automático para predicción de categorías
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class CategoryLearningSystem:
    """
    Sistema de aprendizaje que mejora las predicciones de categorías
    basándose en el feedback del usuario
    """

    def __init__(self):
        self.min_feedback_count = 5  # Mínimo feedback para actualizar patrones
        self.learning_rate = 0.1  # Qué tan rápido se adapta el sistema
        self.confidence_boost = 0.15  # Boost de confianza por feedback positivo

    def process_feedback(self, expense_id: int, feedback_data: Dict[str, Any],
                        tenant_id: int = 1) -> bool:
        """
        Procesa feedback del usuario y actualiza el sistema de aprendizaje
        """
        try:
            from core.unified_db_adapter import get_unified_adapter

            adapter = get_unified_adapter()
            with adapter.get_connection() as conn:
                cursor = conn.cursor()

                # 1. Obtener datos del gasto
                cursor.execute("""
                    SELECT description, amount, merchant_name, category,
                           categoria_sugerida, confianza
                    FROM expense_records
                    WHERE id = ? AND tenant_id = ?
                """, (expense_id, tenant_id))

                expense_data = cursor.fetchone()
                if not expense_data:
                    return False

                expense_dict = dict(expense_data)

                # 2. Actualizar métricas de aprendizaje
                self._update_learning_metrics(
                    expense_dict, feedback_data, tenant_id, cursor
                )

                # 3. Actualizar preferencias del usuario
                if feedback_data.get('user_id'):
                    self._update_user_preferences(
                        expense_dict, feedback_data, tenant_id, cursor
                    )

                # 4. Actualizar patrones globales
                self._update_global_patterns(
                    expense_dict, feedback_data, tenant_id, cursor
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return False

    def _update_learning_metrics(self, expense_data: Dict[str, Any],
                               feedback_data: Dict[str, Any],
                               tenant_id: int, cursor) -> None:
        """Actualiza métricas de aprendizaje por categoría"""

        predicted_category = expense_data.get('categoria_sugerida')
        actual_category = feedback_data.get('actual_category')
        feedback_type = feedback_data.get('feedback_type')

        if not predicted_category:
            return

        # Determinar si fue correcto
        is_correct = (
            feedback_type == 'accepted' or
            (feedback_type == 'corrected' and predicted_category == actual_category)
        )

        # Buscar métricas existentes
        cursor.execute("""
            SELECT * FROM category_learning_metrics
            WHERE tenant_id = ? AND category_name = ?
        """, (tenant_id, predicted_category))

        existing_metrics = cursor.fetchone()

        if existing_metrics:
            # Actualizar métricas existentes
            metrics = dict(existing_metrics)
            total_predictions = metrics['total_predictions'] + 1
            correct_predictions = metrics['correct_predictions'] + (1 if is_correct else 0)
            accuracy_rate = correct_predictions / total_predictions

            # Actualizar keywords y merchants comunes
            keywords = self._extract_keywords(expense_data.get('description', ''))
            merchant = expense_data.get('merchant_name', '')

            existing_keywords = json.loads(metrics.get('most_common_keywords') or '[]')
            existing_merchants = json.loads(metrics.get('most_common_merchants') or '[]')

            updated_keywords = self._update_frequency_list(existing_keywords, keywords)
            updated_merchants = self._update_frequency_list(existing_merchants, [merchant] if merchant else [])

            cursor.execute("""
                UPDATE category_learning_metrics
                SET total_predictions = ?, correct_predictions = ?, accuracy_rate = ?,
                    most_common_keywords = ?, most_common_merchants = ?,
                    last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                total_predictions, correct_predictions, accuracy_rate,
                json.dumps(updated_keywords), json.dumps(updated_merchants),
                metrics['id']
            ))
        else:
            # Crear nuevas métricas
            keywords = self._extract_keywords(expense_data.get('description', ''))
            merchant = expense_data.get('merchant_name', '')

            cursor.execute("""
                INSERT INTO category_learning_metrics (
                    tenant_id, category_name, total_predictions, correct_predictions,
                    accuracy_rate, most_common_keywords, most_common_merchants,
                    typical_amount_range
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tenant_id, predicted_category, 1, 1 if is_correct else 0,
                1.0 if is_correct else 0.0,
                json.dumps(keywords), json.dumps([merchant] if merchant else []),
                self._classify_amount_range(expense_data.get('amount', 0))
            ))

    def _update_user_preferences(self, expense_data: Dict[str, Any],
                               feedback_data: Dict[str, Any],
                               tenant_id: int, cursor) -> None:
        """Actualiza preferencias específicas del usuario"""

        user_id = feedback_data.get('user_id')
        if not user_id:
            return

        category_name = feedback_data.get('actual_category') or expense_data.get('categoria_sugerida')
        if not category_name:
            return

        # Buscar preferencias existentes
        cursor.execute("""
            SELECT * FROM user_category_preferences
            WHERE user_id = ? AND tenant_id = ? AND category_name = ?
        """, (user_id, tenant_id, category_name))

        existing_pref = cursor.fetchone()

        if existing_pref:
            # Actualizar preferencia existente
            pref = dict(existing_pref)
            new_frequency = pref['frequency'] + 1

            # Extraer keywords de la descripción
            keywords = self._extract_keywords(expense_data.get('description', ''))
            existing_keywords = json.loads(pref.get('keywords') or '[]')
            updated_keywords = self._update_frequency_list(existing_keywords, keywords)

            cursor.execute("""
                UPDATE user_category_preferences
                SET frequency = ?, last_used = CURRENT_TIMESTAMP,
                    keywords = ?, preference_score = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                new_frequency,
                json.dumps(updated_keywords),
                min(1.0, pref['preference_score'] + self.learning_rate),
                pref['id']
            ))
        else:
            # Crear nueva preferencia
            keywords = self._extract_keywords(expense_data.get('description', ''))

            cursor.execute("""
                INSERT INTO user_category_preferences (
                    user_id, tenant_id, category_name, frequency,
                    keywords, preference_score
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, tenant_id, category_name, 1,
                json.dumps(keywords), 0.8
            ))

    def _update_global_patterns(self, expense_data: Dict[str, Any],
                              feedback_data: Dict[str, Any],
                              tenant_id: int, cursor) -> None:
        """Actualiza patrones globales del tenant"""

        actual_category = feedback_data.get('actual_category')
        if not actual_category:
            return

        # Actualizar categoría personalizada si existe
        cursor.execute("""
            SELECT * FROM custom_categories
            WHERE tenant_id = ? AND category_name = ?
        """, (tenant_id, actual_category))

        custom_category = cursor.fetchone()

        if custom_category:
            category = dict(custom_category)

            # Extraer y actualizar keywords
            keywords = self._extract_keywords(expense_data.get('description', ''))
            merchant = expense_data.get('merchant_name', '')

            existing_keywords = json.loads(category.get('keywords') or '[]')
            existing_merchants = json.loads(category.get('merchant_patterns') or '[]')

            updated_keywords = self._update_frequency_list(existing_keywords, keywords)
            updated_merchants = self._update_frequency_list(
                existing_merchants, [merchant.lower()] if merchant else []
            )

            cursor.execute("""
                UPDATE custom_categories
                SET keywords = ?, merchant_patterns = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                json.dumps(updated_keywords),
                json.dumps(updated_merchants),
                category['id']
            ))

    def get_learned_improvements(self, tenant_id: int = 1) -> Dict[str, Any]:
        """
        Obtiene mejoras aprendidas para aplicar al predictor
        """
        try:
            from core.unified_db_adapter import get_unified_adapter

            adapter = get_unified_adapter()
            with adapter.get_connection() as conn:
                cursor = conn.cursor()

                # 1. Obtener categorías con mejor accuracy
                cursor.execute("""
                    SELECT category_name, accuracy_rate, most_common_keywords,
                           most_common_merchants, total_predictions
                    FROM category_learning_metrics
                    WHERE tenant_id = ? AND total_predictions >= ?
                    ORDER BY accuracy_rate DESC
                """, (tenant_id, self.min_feedback_count))

                high_accuracy_categories = [dict(row) for row in cursor.fetchall()]

                # 2. Obtener preferencias de usuarios más activos
                cursor.execute("""
                    SELECT category_name, keywords, AVG(preference_score) as avg_score,
                           SUM(frequency) as total_usage
                    FROM user_category_preferences
                    WHERE tenant_id = ? AND active = TRUE
                    GROUP BY category_name
                    HAVING total_usage >= ?
                    ORDER BY avg_score DESC
                """, (tenant_id, self.min_feedback_count))

                user_preferences = [dict(row) for row in cursor.fetchall()]

                # 3. Obtener patrones de custom categories actualizadas
                cursor.execute("""
                    SELECT category_name, keywords, merchant_patterns, color_hex
                    FROM custom_categories
                    WHERE tenant_id = ? AND is_active = TRUE
                    ORDER BY updated_at DESC
                """, (tenant_id,))

                custom_patterns = [dict(row) for row in cursor.fetchall()]

                return {
                    'high_accuracy_categories': high_accuracy_categories,
                    'user_preferences': user_preferences,
                    'custom_patterns': custom_patterns,
                    'learning_stats': {
                        'categories_with_feedback': len(high_accuracy_categories),
                        'active_user_preferences': len(user_preferences),
                        'custom_categories': len(custom_patterns)
                    }
                }

        except Exception as e:
            logger.error(f"Error getting learned improvements: {e}")
            return {'error': str(e)}

    def suggest_category_optimizations(self, tenant_id: int = 1) -> List[Dict[str, Any]]:
        """
        Sugiere optimizaciones basadas en el aprendizaje
        """
        improvements = self.get_learned_improvements(tenant_id)
        suggestions = []

        if improvements.get('error'):
            return [{'type': 'error', 'message': improvements['error']}]

        # Sugerir mejoras en categorías con baja accuracy
        high_accuracy = improvements.get('high_accuracy_categories', [])
        for category in high_accuracy:
            if category['accuracy_rate'] < 0.7 and category['total_predictions'] >= 10:
                suggestions.append({
                    'type': 'low_accuracy',
                    'category': category['category_name'],
                    'current_accuracy': category['accuracy_rate'],
                    'suggestion': 'Considerar revisar keywords y patrones de merchant',
                    'keywords': json.loads(category.get('most_common_keywords') or '[]')[:5]
                })

        # Sugerir nuevas categorías basadas en patrones
        user_prefs = improvements.get('user_preferences', [])
        existing_categories = {cat['category_name'] for cat in high_accuracy}

        for pref in user_prefs:
            if (pref['category_name'] not in existing_categories and
                pref['total_usage'] >= 15):
                suggestions.append({
                    'type': 'new_category_suggestion',
                    'category': pref['category_name'],
                    'usage_count': pref['total_usage'],
                    'suggestion': 'Considerar crear categoría personalizada',
                    'common_keywords': json.loads(pref.get('keywords') or '[]')[:3]
                })

        return suggestions

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrae keywords relevantes del texto"""
        if not text:
            return []

        import re

        # Limpiar y tokenizar
        text = text.lower().strip()
        words = re.findall(r'\b\w+\b', text)

        # Filtrar palabras cortas y comunes
        stop_words = {
            'de', 'la', 'el', 'en', 'y', 'a', 'que', 'es', 'se', 'no', 'te', 'lo',
            'le', 'da', 'su', 'por', 'son', 'con', 'las', 'mi', 'sus', 'un', 'para'
        }

        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        return keywords[:10]  # Top 10 keywords

    def _update_frequency_list(self, existing_list: List[str], new_items: List[str]) -> List[str]:
        """Actualiza lista de frecuencias combinando elementos existentes y nuevos"""
        if not new_items:
            return existing_list

        # Combinar y contar frecuencias
        all_items = existing_list + new_items
        counter = Counter(all_items)

        # Retornar top items ordenados por frecuencia
        return [item for item, count in counter.most_common(15)]

    def _classify_amount_range(self, amount: float) -> str:
        """Clasifica el monto en rangos"""
        if amount <= 0:
            return 'invalid'
        elif amount <= 100:
            return '0-100'
        elif amount <= 500:
            return '100-500'
        elif amount <= 1000:
            return '500-1000'
        elif amount <= 5000:
            return '1000-5000'
        else:
            return '5000+'

    def generate_learning_report(self, tenant_id: int = 1) -> Dict[str, Any]:
        """
        Genera reporte completo de aprendizaje del sistema
        """
        try:
            from core.unified_db_adapter import get_unified_adapter

            adapter = get_unified_adapter()
            with adapter.get_connection() as conn:
                cursor = conn.cursor()

                # Estadísticas generales
                cursor.execute("""
                    SELECT COUNT(*) as total_categories,
                           AVG(accuracy_rate) as avg_accuracy,
                           SUM(total_predictions) as total_predictions
                    FROM category_learning_metrics
                    WHERE tenant_id = ?
                """, (tenant_id,))

                general_stats = dict(cursor.fetchone() or {})

                # Top categorías por accuracy
                cursor.execute("""
                    SELECT category_name, accuracy_rate, total_predictions
                    FROM category_learning_metrics
                    WHERE tenant_id = ? AND total_predictions >= 3
                    ORDER BY accuracy_rate DESC LIMIT 5
                """, (tenant_id,))

                top_accuracy = [dict(row) for row in cursor.fetchall()]

                # Preferencias de usuarios más activos
                cursor.execute("""
                    SELECT COUNT(DISTINCT user_id) as active_users,
                           AVG(preference_score) as avg_preference,
                           SUM(frequency) as total_interactions
                    FROM user_category_preferences
                    WHERE tenant_id = ? AND active = TRUE
                """, (tenant_id,))

                user_stats = dict(cursor.fetchone() or {})

                # Sugerencias de optimización
                suggestions = self.suggest_category_optimizations(tenant_id)

                return {
                    'report_date': datetime.now().isoformat(),
                    'tenant_id': tenant_id,
                    'general_stats': general_stats,
                    'top_accuracy_categories': top_accuracy,
                    'user_engagement': user_stats,
                    'optimization_suggestions': suggestions,
                    'learning_health': {
                        'categories_learning': general_stats.get('total_categories', 0),
                        'avg_accuracy': round(general_stats.get('avg_accuracy', 0), 2),
                        'total_feedback': general_stats.get('total_predictions', 0),
                        'active_users': user_stats.get('active_users', 0)
                    }
                }

        except Exception as e:
            logger.error(f"Error generating learning report: {e}")
            return {'error': str(e)}


# Factory function
_learning_system = None

def get_learning_system() -> CategoryLearningSystem:
    """Obtener instancia global del sistema de aprendizaje"""
    global _learning_system
    if _learning_system is None:
        _learning_system = CategoryLearningSystem()
    return _learning_system


# Helper functions
def process_category_feedback(expense_id: int, feedback_data: Dict[str, Any],
                            tenant_id: int = 1) -> bool:
    """Procesa feedback y actualiza sistema de aprendizaje"""
    learning_system = get_learning_system()
    return learning_system.process_feedback(expense_id, feedback_data, tenant_id)


def get_category_learning_insights(tenant_id: int = 1) -> Dict[str, Any]:
    """Obtiene insights del aprendizaje automático"""
    learning_system = get_learning_system()
    return learning_system.generate_learning_report(tenant_id)


def optimize_category_predictor(tenant_id: int = 1) -> Dict[str, Any]:
    """Optimiza el predictor basándose en el aprendizaje"""
    learning_system = get_learning_system()
    improvements = learning_system.get_learned_improvements(tenant_id)

    # Aquí se podría integrar con el CategoryPredictor para aplicar las mejoras
    # Por ahora retornamos las mejoras sugeridas

    return {
        'optimizations_available': len(improvements.get('high_accuracy_categories', [])),
        'user_patterns_learned': len(improvements.get('user_preferences', [])),
        'custom_patterns_updated': len(improvements.get('custom_patterns', [])),
        'suggestions': learning_system.suggest_category_optimizations(tenant_id)
    }
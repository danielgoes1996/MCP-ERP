"""
Sistema de Completado Inteligente de Gastos
Punto 15: Completado de Gastos - Complete Implementation

Este módulo proporciona:
- Completado automático de campos basado en patrones
- Sistema de sugerencias inteligentes por contexto
- Aprendizaje automático de preferencias de usuario
- Validación de completeness con scoring
- Analytics de efectividad de completado
- Sistema de reglas configurables por empresa
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import json
import re

logger = logging.getLogger(__name__)


class CompletionType(Enum):
    """Tipos de completado"""
    AUTO = "auto"
    SUGGESTED = "suggested"
    MANUAL = "manual"
    BULK = "bulk"
    IMPORT = "import"
    API = "api"


class UserAction(Enum):
    """Acciones del usuario sobre sugerencias"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"
    IGNORED = "ignored"
    DELAYED = "delayed"


class PatternType(Enum):
    """Tipos de patrones de completado"""
    VENDOR_COMPLETION = "vendor_completion"
    CATEGORY_SUGGESTION = "category_suggestion"
    AMOUNT_PREDICTION = "amount_prediction"
    PROJECT_ASSIGNMENT = "project_assignment"
    APPROVAL_ROUTING = "approval_routing"
    TAX_CLASSIFICATION = "tax_classification"
    LOCATION_INFERENCE = "location_inference"
    DATE_NORMALIZATION = "date_normalization"
    CUSTOM_FIELD_COMPLETION = "custom_field_completion"


class FieldCategory(Enum):
    """Categorías de campos"""
    BASIC = "basic"
    FINANCIAL = "financial"
    TAX = "tax"
    APPROVAL = "approval"
    CATEGORIZATION = "categorization"
    VENDOR = "vendor"
    PROJECT = "project"
    LOCATION = "location"
    METADATA = "metadata"
    CUSTOM = "custom"


@dataclass
class CompletionSuggestion:
    """Sugerencia de completado"""
    field_name: str
    suggested_value: Any
    confidence_score: float
    suggestion_source: str
    pattern_id: Optional[int]
    reasoning: Optional[str]
    alternatives: List[Any] = None


@dataclass
class FieldPriority:
    """Prioridad de campo"""
    field_name: str
    field_category: FieldCategory
    base_priority: int
    calculated_priority: Optional[int]
    context_multipliers: Dict[str, float]
    auto_complete_when_confident: bool
    required_for_submission: bool


@dataclass
class CompletionRule:
    """Regla de completado"""
    id: Optional[int]
    company_id: str
    rule_name: str
    rule_code: str
    trigger_conditions: Dict[str, Any]
    completion_rules: Dict[str, Any]
    priority: int
    confidence_threshold: float
    is_active: bool
    success_rate: Optional[float]


@dataclass
class CompletionPattern:
    """Patrón de completado aprendido"""
    id: Optional[int]
    company_id: str
    user_id: Optional[int]
    pattern_hash: str
    pattern_type: PatternType
    trigger_values: Dict[str, Any]
    completion_values: Dict[str, Any]
    confidence_score: float
    usage_count: int
    is_validated: bool


@dataclass
class UserPreferences:
    """Preferencias de usuario para completado"""
    user_id: int
    company_id: str
    auto_completion_enabled: bool
    suggestion_aggressiveness: str  # low, medium, high
    confirmation_required: bool
    max_suggestions_per_field: int
    preferred_fields: List[str]
    ignored_fields: List[str]


class ExpenseCompletionSystem:
    """
    Sistema inteligente de completado de gastos con capacidades enterprise
    """

    def __init__(self):
        self.db = None
        self.ml_enabled = True
        self.learning_enabled = True
        self.cache_enabled = True
        self._suggestion_cache = {}
        self._pattern_cache = {}

    async def initialize(self, db_adapter):
        """Inicializar el sistema con adaptador de BD"""
        self.db = db_adapter
        await self._initialize_default_priorities()
        logger.info("ExpenseCompletionSystem initialized")

    async def suggest_completions(
        self,
        company_id: str,
        user_id: int,
        partial_expense_data: Dict[str, Any],
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[CompletionSuggestion]:
        """
        Generar sugerencias de completado para un gasto
        """
        try:
            suggestions = []
            context_data = context_data or {}

            # Get user preferences
            user_prefs = await self._get_user_preferences(user_id, company_id)
            if not user_prefs.auto_completion_enabled:
                return suggestions

            # Get field priorities for this company
            field_priorities = await self._get_field_priorities(company_id)

            # Determine which fields need completion
            missing_fields = await self._identify_missing_fields(
                partial_expense_data, field_priorities, user_prefs
            )

            # Generate suggestions for each missing field
            for field_name in missing_fields:
                field_suggestions = await self._generate_field_suggestions(
                    company_id, user_id, field_name,
                    partial_expense_data, context_data, user_prefs
                )
                suggestions.extend(field_suggestions)

            # Sort suggestions by priority and confidence
            suggestions.sort(key=lambda s: (
                self._get_field_priority_score(s.field_name, field_priorities),
                s.confidence_score
            ), reverse=True)

            # Limit suggestions based on user preferences
            max_total_suggestions = user_prefs.max_suggestions_per_field * 3
            suggestions = suggestions[:max_total_suggestions]

            logger.info(f"Generated {len(suggestions)} completion suggestions for user {user_id}")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating completion suggestions: {e}")
            return []

    async def _generate_field_suggestions(
        self,
        company_id: str,
        user_id: int,
        field_name: str,
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any],
        user_prefs: UserPreferences
    ) -> List[CompletionSuggestion]:
        """
        Generar sugerencias para un campo específico
        """
        try:
            suggestions = []

            # Get suggestions from patterns
            pattern_suggestions = await self._get_pattern_suggestions(
                company_id, user_id, field_name, partial_data, context_data
            )
            suggestions.extend(pattern_suggestions)

            # Get suggestions from rules
            rule_suggestions = await self._get_rule_suggestions(
                company_id, field_name, partial_data, context_data
            )
            suggestions.extend(rule_suggestions)

            # Get suggestions from historical data
            if self.learning_enabled:
                history_suggestions = await self._get_historical_suggestions(
                    company_id, user_id, field_name, partial_data
                )
                suggestions.extend(history_suggestions)

            # Deduplicate and limit suggestions
            unique_suggestions = self._deduplicate_suggestions(suggestions)
            limited_suggestions = unique_suggestions[:user_prefs.max_suggestions_per_field]

            return limited_suggestions

        except Exception as e:
            logger.error(f"Error generating field suggestions for {field_name}: {e}")
            return []

    async def _get_pattern_suggestions(
        self,
        company_id: str,
        user_id: int,
        field_name: str,
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> List[CompletionSuggestion]:
        """
        Obtener sugerencias basadas en patrones aprendidos
        """
        try:
            suggestions = []

            # Build pattern matching query
            query = """
            SELECT id, pattern_type, trigger_values, completion_values,
                   confidence_score, usage_count
            FROM expense_completion_patterns
            WHERE company_id = ?
            AND is_active = true
            AND completion_values ? ?
            AND (user_id IS NULL OR user_id = ?)
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT 10
            """

            patterns = await self.db.fetch_all(query, (company_id, field_name, user_id))

            for pattern in patterns:
                # Check if pattern triggers match current data
                if self._pattern_matches(pattern["trigger_values"], partial_data, context_data):
                    completion_values = json.loads(pattern["completion_values"])
                    suggested_value = completion_values.get(field_name)

                    if suggested_value:
                        suggestion = CompletionSuggestion(
                            field_name=field_name,
                            suggested_value=suggested_value,
                            confidence_score=float(pattern["confidence_score"]),
                            suggestion_source="pattern",
                            pattern_id=pattern["id"],
                            reasoning=f"Based on {pattern['usage_count']} similar expenses"
                        )
                        suggestions.append(suggestion)

            return suggestions

        except Exception as e:
            logger.error(f"Error getting pattern suggestions: {e}")
            return []

    async def _get_rule_suggestions(
        self,
        company_id: str,
        field_name: str,
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> List[CompletionSuggestion]:
        """
        Obtener sugerencias basadas en reglas configuradas
        """
        try:
            suggestions = []

            # Get active completion rules
            query = """
            SELECT id, rule_name, trigger_conditions, completion_rules,
                   confidence_threshold, priority
            FROM expense_completion_rules
            WHERE company_id = ? AND is_active = true
            ORDER BY priority ASC
            """

            rules = await self.db.fetch_all(query, (company_id,))

            for rule in rules:
                # Check if rule conditions are met
                if self._rule_applies(rule, partial_data, context_data):
                    completion_rules = json.loads(rule["completion_rules"])
                    field_rules = completion_rules.get(field_name)

                    if field_rules:
                        suggested_value = await self._apply_completion_rule(
                            field_rules, partial_data, context_data
                        )

                        if suggested_value:
                            suggestion = CompletionSuggestion(
                                field_name=field_name,
                                suggested_value=suggested_value,
                                confidence_score=float(rule["confidence_threshold"]),
                                suggestion_source="rule",
                                pattern_id=None,
                                reasoning=f"Applied rule: {rule['rule_name']}"
                            )
                            suggestions.append(suggestion)

            return suggestions

        except Exception as e:
            logger.error(f"Error getting rule suggestions: {e}")
            return []

    async def _get_historical_suggestions(
        self,
        company_id: str,
        user_id: int,
        field_name: str,
        partial_data: Dict[str, Any]
    ) -> List[CompletionSuggestion]:
        """
        Obtener sugerencias basadas en historial del usuario
        """
        try:
            suggestions = []

            # Get user's historical completions for similar contexts
            query = """
            SELECT final_value, COUNT(*) as frequency,
                   AVG(user_satisfaction) as avg_satisfaction
            FROM expense_completion_history
            WHERE company_id = ? AND user_id = ? AND field_name = ?
            AND user_action = 'accepted'
            AND completed_at >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY final_value
            HAVING COUNT(*) >= 2
            ORDER BY frequency DESC, avg_satisfaction DESC
            LIMIT 5
            """

            history = await self.db.fetch_all(query, (company_id, user_id, field_name))

            for record in history:
                confidence = min(0.9, 0.3 + (record["frequency"] * 0.1))
                if record["avg_satisfaction"]:
                    confidence *= (record["avg_satisfaction"] / 5.0)

                suggestion = CompletionSuggestion(
                    field_name=field_name,
                    suggested_value=record["final_value"],
                    confidence_score=confidence,
                    suggestion_source="history",
                    pattern_id=None,
                    reasoning=f"Used {record['frequency']} times recently"
                )
                suggestions.append(suggestion)

            return suggestions

        except Exception as e:
            logger.error(f"Error getting historical suggestions: {e}")
            return []

    def _pattern_matches(
        self,
        trigger_values: str,
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> bool:
        """
        Verificar si un patrón coincide con los datos actuales
        """
        try:
            triggers = json.loads(trigger_values) if isinstance(trigger_values, str) else trigger_values

            for trigger_field, expected_value in triggers.items():
                actual_value = partial_data.get(trigger_field) or context_data.get(trigger_field)

                if not actual_value:
                    continue

                # Handle different comparison types
                if isinstance(expected_value, dict):
                    if expected_value.get("type") == "regex":
                        if not re.match(expected_value["pattern"], str(actual_value)):
                            return False
                    elif expected_value.get("type") == "range":
                        if not (expected_value["min"] <= float(actual_value) <= expected_value["max"]):
                            return False
                else:
                    # Exact or fuzzy match
                    if str(actual_value).lower() != str(expected_value).lower():
                        # Try fuzzy matching for text fields
                        similarity = self._calculate_text_similarity(
                            str(actual_value).lower(), str(expected_value).lower()
                        )
                        if similarity < 0.8:
                            return False

            return True

        except Exception as e:
            logger.error(f"Error matching pattern: {e}")
            return False

    def _rule_applies(
        self,
        rule: Dict[str, Any],
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> bool:
        """
        Verificar si una regla aplica para los datos actuales
        """
        try:
            conditions = json.loads(rule["trigger_conditions"])

            # Check amount conditions
            if "amount_range" in conditions:
                amount = partial_data.get("monto_total") or partial_data.get("amount")
                if amount:
                    range_cond = conditions["amount_range"]
                    if not (range_cond.get("min", 0) <= amount <= range_cond.get("max", float('inf'))):
                        return False

            # Check category conditions
            if "categories" in conditions:
                category = partial_data.get("categoria") or partial_data.get("category")
                if category and category not in conditions["categories"]:
                    return False

            # Check vendor conditions
            if "vendors" in conditions:
                vendor = partial_data.get("proveedor") or partial_data.get("provider_name")
                if vendor and not any(v.lower() in vendor.lower() for v in conditions["vendors"]):
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking rule applicability: {e}")
            return False

    async def _apply_completion_rule(
        self,
        field_rules: Dict[str, Any],
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Aplicar regla de completado para obtener valor sugerido
        """
        try:
            rule_type = field_rules.get("type")

            if rule_type == "fixed_value":
                return field_rules["value"]

            elif rule_type == "conditional":
                conditions = field_rules["conditions"]
                for condition in conditions:
                    if self._condition_matches(condition, partial_data, context_data):
                        return condition["value"]

            elif rule_type == "lookup":
                lookup_field = field_rules["lookup_field"]
                lookup_value = partial_data.get(lookup_field) or context_data.get(lookup_field)
                if lookup_value:
                    mapping = field_rules["mapping"]
                    return mapping.get(str(lookup_value))

            elif rule_type == "calculation":
                return await self._calculate_field_value(field_rules, partial_data)

            return None

        except Exception as e:
            logger.error(f"Error applying completion rule: {e}")
            return None

    def _condition_matches(
        self,
        condition: Dict[str, Any],
        partial_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> bool:
        """
        Verificar si una condición específica se cumple
        """
        try:
            field_name = condition["field"]
            operator = condition["operator"]
            expected = condition["expected"]

            actual = partial_data.get(field_name) or context_data.get(field_name)

            if operator == "equals":
                return str(actual).lower() == str(expected).lower()
            elif operator == "contains":
                return str(expected).lower() in str(actual).lower()
            elif operator == "greater_than":
                return float(actual) > float(expected)
            elif operator == "less_than":
                return float(actual) < float(expected)
            elif operator == "in_list":
                return actual in expected

            return False

        except Exception as e:
            logger.error(f"Error checking condition: {e}")
            return False

    async def _calculate_field_value(
        self,
        calculation_rules: Dict[str, Any],
        partial_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Calcular valor de campo basado en otros campos
        """
        try:
            formula = calculation_rules.get("formula")

            if formula == "percentage":
                base_field = calculation_rules["base_field"]
                percentage = calculation_rules["percentage"]
                base_value = partial_data.get(base_field)

                if base_value:
                    return round(float(base_value) * percentage / 100, 2)

            elif formula == "tax_calculation":
                amount = partial_data.get("monto_total") or partial_data.get("amount")
                tax_rate = calculation_rules.get("tax_rate", 16)  # Default IVA 16%

                if amount:
                    return round(float(amount) * tax_rate / 116, 2)  # Extract IVA from total

            elif formula == "category_mapping":
                description = partial_data.get("descripcion") or partial_data.get("description")
                if description:
                    return await self._predict_category_from_description(description)

            return None

        except Exception as e:
            logger.error(f"Error calculating field value: {e}")
            return None

    async def record_completion_interaction(
        self,
        user_id: int,
        company_id: str,
        session_id: str,
        field_name: str,
        suggested_value: Any,
        final_value: Any,
        user_action: UserAction,
        confidence_score: float,
        pattern_id: Optional[int] = None,
        rule_id: Optional[int] = None,
        interaction_time_ms: Optional[int] = None,
        user_satisfaction: Optional[float] = None
    ):
        """
        Registrar interacción del usuario con el sistema de completado
        """
        try:
            # Record the interaction
            query = """
            INSERT INTO expense_completion_history (
                user_id, company_id, session_id, field_name,
                suggested_value, final_value, confidence_score,
                user_action, interaction_time_ms, user_satisfaction,
                pattern_used_id, rule_used_id, completion_source,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            await self.db.execute(query, (
                user_id, company_id, session_id, field_name,
                json.dumps(suggested_value) if isinstance(suggested_value, (dict, list)) else str(suggested_value),
                json.dumps(final_value) if isinstance(final_value, (dict, list)) else str(final_value),
                confidence_score, user_action.value, interaction_time_ms,
                user_satisfaction, pattern_id, rule_id,
                "pattern" if pattern_id else "rule" if rule_id else "manual",
                datetime.utcnow().isoformat()
            ))

            # Learn from the interaction if enabled
            if self.learning_enabled:
                await self._learn_from_interaction(
                    user_id, company_id, field_name, suggested_value,
                    final_value, user_action, confidence_score
                )

            logger.info(f"Recorded completion interaction: user={user_id}, field={field_name}, action={user_action.value}")

        except Exception as e:
            logger.error(f"Error recording completion interaction: {e}")

    async def _learn_from_interaction(
        self,
        user_id: int,
        company_id: str,
        field_name: str,
        suggested_value: Any,
        final_value: Any,
        user_action: UserAction,
        confidence_score: float
    ):
        """
        Aprender de la interacción del usuario para mejorar futuras sugerencias
        """
        try:
            if user_action == UserAction.ACCEPTED:
                # Reinforce the pattern that led to this suggestion
                await self._reinforce_successful_pattern(
                    company_id, user_id, field_name, final_value
                )

            elif user_action == UserAction.MODIFIED:
                # Create or update pattern based on user's modification
                await self._create_pattern_from_modification(
                    company_id, user_id, field_name, suggested_value, final_value
                )

            elif user_action == UserAction.REJECTED:
                # Lower confidence of the pattern that made this suggestion
                await self._penalize_rejected_pattern(
                    company_id, user_id, field_name, suggested_value
                )

        except Exception as e:
            logger.error(f"Error learning from interaction: {e}")

    async def _reinforce_successful_pattern(
        self,
        company_id: str,
        user_id: int,
        field_name: str,
        final_value: Any
    ):
        """
        Reforzar patrones que llevaron a sugerencias exitosas
        """
        try:
            # Find patterns that suggest similar values
            query = """
            SELECT id, confidence_score, usage_count
            FROM expense_completion_patterns
            WHERE company_id = ? AND completion_values ? ?
            AND (user_id IS NULL OR user_id = ?)
            """

            patterns = await self.db.fetch_all(query, (
                company_id, field_name, user_id
            ))

            for pattern in patterns:
                completion_values = await self.db.fetch_val(
                    "SELECT completion_values FROM expense_completion_patterns WHERE id = ?",
                    (pattern["id"],)
                )

                if completion_values:
                    values = json.loads(completion_values)
                    if values.get(field_name) == final_value:
                        # Boost confidence slightly
                        new_confidence = min(1.0, pattern["confidence_score"] + 0.05)
                        await self.db.execute(
                            "UPDATE expense_completion_patterns SET confidence_score = ? WHERE id = ?",
                            (new_confidence, pattern["id"])
                        )

        except Exception as e:
            logger.error(f"Error reinforcing successful pattern: {e}")

    async def get_completion_analytics(
        self,
        company_id: str,
        period_days: int = 30,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtener analytics del sistema de completado
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=period_days)

            # Base query conditions
            where_conditions = ["company_id = ?", "completed_at >= ?"]
            params = [company_id, start_date.isoformat()]

            if user_id:
                where_conditions.append("user_id = ?")
                params.append(user_id)

            where_clause = " AND ".join(where_conditions)

            # Overall metrics
            overall_query = f"""
            SELECT
                COUNT(*) as total_completions,
                COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted_count,
                COUNT(CASE WHEN user_action = 'rejected' THEN 1 END) as rejected_count,
                COUNT(CASE WHEN user_action = 'modified' THEN 1 END) as modified_count,
                AVG(confidence_score) as avg_confidence,
                AVG(user_satisfaction) as avg_satisfaction,
                AVG(interaction_time_ms) as avg_interaction_time
            FROM expense_completion_history
            WHERE {where_clause}
            """

            overall = await self.db.fetch_one(overall_query, params)

            # Field-specific metrics
            field_query = f"""
            SELECT
                field_name,
                COUNT(*) as completions,
                COUNT(CASE WHEN user_action = 'accepted' THEN 1 END) as accepted,
                AVG(confidence_score) as avg_confidence
            FROM expense_completion_history
            WHERE {where_clause}
            GROUP BY field_name
            ORDER BY completions DESC
            LIMIT 10
            """

            field_stats = await self.db.fetch_all(field_query, params)

            # Pattern effectiveness
            pattern_query = f"""
            SELECT
                p.pattern_type,
                COUNT(*) as usage_count,
                AVG(h.confidence_score) as avg_confidence,
                COUNT(CASE WHEN h.user_action = 'accepted' THEN 1 END) as accepted_count
            FROM expense_completion_history h
            JOIN expense_completion_patterns p ON h.pattern_used_id = p.id
            WHERE {where_clause} AND h.pattern_used_id IS NOT NULL
            GROUP BY p.pattern_type
            ORDER BY usage_count DESC
            """

            pattern_stats = await self.db.fetch_all(pattern_query, params)

            # Calculate metrics
            total = overall["total_completions"] or 0
            acceptance_rate = (overall["accepted_count"] / total * 100) if total > 0 else 0
            rejection_rate = (overall["rejected_count"] / total * 100) if total > 0 else 0

            return {
                "period_days": period_days,
                "total_completions": total,
                "acceptance_rate": round(acceptance_rate, 2),
                "rejection_rate": round(rejection_rate, 2),
                "modification_rate": round((overall["modified_count"] / total * 100) if total > 0 else 0, 2),
                "avg_confidence_score": round(float(overall["avg_confidence"]) if overall["avg_confidence"] else 0, 3),
                "avg_user_satisfaction": round(float(overall["avg_satisfaction"]) if overall["avg_satisfaction"] else 0, 2),
                "avg_interaction_time_ms": round(float(overall["avg_interaction_time"]) if overall["avg_interaction_time"] else 0, 0),
                "field_statistics": [
                    {
                        "field_name": record["field_name"],
                        "completions": record["completions"],
                        "acceptance_rate": round(record["accepted"] / record["completions"] * 100, 2),
                        "avg_confidence": round(float(record["avg_confidence"]), 3)
                    } for record in field_stats
                ],
                "pattern_effectiveness": [
                    {
                        "pattern_type": record["pattern_type"],
                        "usage_count": record["usage_count"],
                        "avg_confidence": round(float(record["avg_confidence"]), 3),
                        "success_rate": round(record["accepted_count"] / record["usage_count"] * 100, 2)
                    } for record in pattern_stats
                ]
            }

        except Exception as e:
            logger.error(f"Error getting completion analytics: {e}")
            return {"error": str(e)}

    # Helper methods
    async def _get_user_preferences(self, user_id: int, company_id: str) -> UserPreferences:
        """Obtener preferencias del usuario"""
        try:
            query = """
            SELECT * FROM user_completion_preferences
            WHERE user_id = ? AND company_id = ?
            """

            record = await self.db.fetch_one(query, (user_id, company_id))

            if record:
                return UserPreferences(
                    user_id=record["user_id"],
                    company_id=record["company_id"],
                    auto_completion_enabled=record["auto_completion_enabled"],
                    suggestion_aggressiveness=record["suggestion_aggressiveness"],
                    confirmation_required=record["confirmation_required"],
                    max_suggestions_per_field=record["max_suggestions_per_field"],
                    preferred_fields=json.loads(record["preferred_fields"]) if record["preferred_fields"] else [],
                    ignored_fields=json.loads(record["ignored_fields"]) if record["ignored_fields"] else []
                )
            else:
                # Return default preferences
                return UserPreferences(
                    user_id=user_id,
                    company_id=company_id,
                    auto_completion_enabled=True,
                    suggestion_aggressiveness="medium",
                    confirmation_required=False,
                    max_suggestions_per_field=5,
                    preferred_fields=[],
                    ignored_fields=[]
                )

        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return UserPreferences(
                user_id=user_id, company_id=company_id, auto_completion_enabled=True,
                suggestion_aggressiveness="medium", confirmation_required=False,
                max_suggestions_per_field=5, preferred_fields=[], ignored_fields=[]
            )

    async def _get_field_priorities(self, company_id: str) -> Dict[str, FieldPriority]:
        """Obtener prioridades de campos"""
        try:
            query = """
            SELECT * FROM expense_field_priorities WHERE company_id = ?
            """

            records = await self.db.fetch_all(query, (company_id,))
            priorities = {}

            for record in records:
                priorities[record["field_name"]] = FieldPriority(
                    field_name=record["field_name"],
                    field_category=FieldCategory(record["field_category"]),
                    base_priority=record["base_priority"],
                    calculated_priority=json.loads(record["field_priorities"]).get("calculated_priority") if record["field_priorities"] else None,
                    context_multipliers=json.loads(record["context_multipliers"]) if record["context_multipliers"] else {},
                    auto_complete_when_confident=record["auto_complete_when_confident"],
                    required_for_submission=record["required_for_submission"]
                )

            return priorities

        except Exception as e:
            logger.error(f"Error getting field priorities: {e}")
            return {}

    async def _identify_missing_fields(
        self,
        partial_data: Dict[str, Any],
        field_priorities: Dict[str, FieldPriority],
        user_prefs: UserPreferences
    ) -> List[str]:
        """Identificar campos faltantes que necesitan completado"""
        missing_fields = []

        for field_name, priority in field_priorities.items():
            # Skip ignored fields
            if field_name in user_prefs.ignored_fields:
                continue

            # Check if field is missing or empty
            if field_name not in partial_data or not partial_data[field_name]:
                missing_fields.append(field_name)

        # Sort by priority
        missing_fields.sort(
            key=lambda f: field_priorities[f].calculated_priority or field_priorities[f].base_priority,
            reverse=True
        )

        return missing_fields

    def _get_field_priority_score(self, field_name: str, field_priorities: Dict[str, FieldPriority]) -> int:
        """Obtener score de prioridad de un campo"""
        if field_name in field_priorities:
            priority = field_priorities[field_name]
            return priority.calculated_priority or priority.base_priority
        return 0

    def _deduplicate_suggestions(self, suggestions: List[CompletionSuggestion]) -> List[CompletionSuggestion]:
        """Eliminar sugerencias duplicadas"""
        seen = set()
        unique = []

        for suggestion in suggestions:
            key = f"{suggestion.field_name}:{suggestion.suggested_value}"
            if key not in seen:
                seen.add(key)
                unique.append(suggestion)

        return unique

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calcular similitud entre textos"""
        if not text1 or not text2:
            return 0.0

        # Simple Jaccard similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    async def _initialize_default_priorities(self):
        """Inicializar prioridades por defecto"""
        try:
            # Check if default priorities exist
            count = await self.db.fetch_val(
                "SELECT COUNT(*) FROM expense_field_priorities WHERE company_id = 'default'"
            )

            if count > 0:
                return  # Already initialized

            # Insert default field priorities
            default_fields = [
                ("descripcion", "basic", 90),
                ("monto_total", "financial", 95),
                ("categoria", "categorization", 85),
                ("proveedor", "vendor", 80),
                ("fecha_gasto", "basic", 88),
                ("centro_costo", "project", 70),
                ("proyecto", "project", 65),
                ("metodo_pago", "financial", 75),
                ("cfdi_uuid", "tax", 60),
                ("rfc_proveedor", "tax", 55),
                ("ubicacion", "location", 50),
                ("notas", "metadata", 30)
            ]

            for field_name, category, priority in default_fields:
                await self.db.execute("""
                    INSERT INTO expense_field_priorities (
                        company_id, field_name, field_category, base_priority
                    ) VALUES (?, ?, ?, ?)
                """, ("default", field_name, category, priority))

            logger.info("Initialized default field priorities")

        except Exception as e:
            logger.error(f"Error initializing default priorities: {e}")

    async def health_check(self) -> bool:
        """Health check del sistema"""
        try:
            if not self.db:
                return False

            # Test database connectivity
            await self.db.fetch_one("SELECT 1")
            return True
        except:
            return False


# Singleton instance
expense_completion_system = ExpenseCompletionSystem()
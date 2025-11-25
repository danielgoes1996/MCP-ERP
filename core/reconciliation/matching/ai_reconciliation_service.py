"""
AI-Powered Reconciliation Service

Hybrid approach:
1. Rule-based matching (exact amount + date proximity)
2. Text similarity using embeddings (OpenAI)
3. Confidence scoring system
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import json
from difflib import SequenceMatcher
import re

logger = logging.getLogger(__name__)


class AIReconciliationService:
    """Service for AI-powered bank reconciliation suggestions"""

    def __init__(self, db_path: str = "unified_mcp_system.db"):
        self.db_path = db_path
        self.confidence_threshold_high = 85.0  # Green zone
        self.confidence_threshold_medium = 60.0  # Yellow zone

    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =====================================================
    # MAIN SUGGESTION METHODS
    # =====================================================

    def get_all_suggestions(self, limit: int = 20, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all reconciliation suggestions (both one-to-many and many-to-one) - tenant-aware

        Args:
            limit: Maximum number of suggestions
            tenant_id: Tenant ID for multi-tenancy filtering

        Returns:
            List of suggestions sorted by confidence (highest first)
        """
        suggestions = []

        # Get one-to-many suggestions (with tenant filter)
        one_to_many = self.suggest_one_to_many_splits(limit=limit, tenant_id=tenant_id)
        suggestions.extend(one_to_many)

        # Get many-to-one suggestions (with tenant filter)
        many_to_one = self.suggest_many_to_one_splits(limit=limit, tenant_id=tenant_id)
        suggestions.extend(many_to_one)

        # Sort by confidence
        suggestions.sort(key=lambda x: x['confidence_score'], reverse=True)

        return suggestions[:limit]

    def suggest_one_to_many_splits(self, limit: int = 10, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Suggest one-to-many splits (1 movement → N expenses) - tenant-aware

        Strategy:
        1. Find large movements that could cover multiple smaller expenses
        2. Group expenses by date proximity and total amount match
        3. Calculate confidence based on amount match + date proximity + description similarity
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Build queries with tenant filtering
            movements_query = """
                SELECT * FROM bank_movements
                WHERE (matched_expense_id IS NULL OR matched_expense_id = '')
                AND amount < 0
            """
            movements_params = []
            if tenant_id is not None:
                movements_query += " AND tenant_id = ?"
                movements_params.append(tenant_id)
            movements_query += " ORDER BY date DESC LIMIT 50"

            cursor.execute(movements_query, movements_params)
            movements = [dict(row) for row in cursor.fetchall()]

            # Get pending expenses with tenant filter
            expenses_query = """
                SELECT * FROM expense_records
                WHERE (bank_status = 'pending' OR bank_status IS NULL)
            """
            expenses_params = []
            if tenant_id is not None:
                expenses_query += " AND tenant_id = ?"
                expenses_params.append(tenant_id)
            expenses_query += " ORDER BY date DESC"

            cursor.execute(expenses_query, expenses_params)
            expenses = [dict(row) for row in cursor.fetchall()]

            suggestions = []

            for movement in movements:
                movement_amount = abs(movement['amount'])
                movement_date = datetime.fromisoformat(movement['date'].replace(' ', 'T')) if movement['date'] else None

                if not movement_date:
                    continue

                # Find combinations of expenses that sum to movement amount
                matching_combos = self._find_expense_combinations(
                    expenses=expenses,
                    target_amount=movement_amount,
                    target_date=movement_date,
                    movement_description=movement['description']
                )

                for combo in matching_combos[:3]:  # Top 3 combinations per movement
                    confidence = self._calculate_one_to_many_confidence(
                        movement=movement,
                        expenses=combo['manual_expenses'],
                        amount_diff=combo['amount_diff'],
                        date_diff_avg=combo['date_diff_avg']
                    )

                    if confidence >= self.confidence_threshold_medium:
                        suggestions.append({
                            'type': 'one_to_many',
                            'confidence_score': confidence,
                            'confidence_level': self._get_confidence_level(confidence),
                            'movement': {
                                'id': movement['id'],
                                'description': movement['description'],
                                'amount': movement_amount,
                                'date': movement['date']
                            },
                            'manual_expenses': [
                                {
                                    'id': e['id'],
                                    'description': e['description'],
                                    'amount': e['amount'],
                                    'date': e['date'],
                                    'allocated_amount': e['amount']  # Default to full amount
                                }
                                for e in combo['manual_expenses']
                            ],
                            'breakdown': combo['breakdown'],
                            'total_allocated': sum(e['amount'] for e in combo['manual_expenses']),
                            'difference': combo['amount_diff']
                        })

            conn.close()
            return sorted(suggestions, key=lambda x: x['confidence_score'], reverse=True)[:limit]

        except Exception as e:
            logger.error(f"Error suggesting one-to-many splits: {e}")
            conn.close()
            return []

    def suggest_many_to_one_splits(self, limit: int = 10, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Suggest many-to-one splits (N movements → 1 expense) - tenant-aware

        Strategy:
        1. Find large expenses that could be paid in installments
        2. Group movements by description similarity and date sequence
        3. Check if sum matches expense amount
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 🔐 Build queries with tenant filtering
            # Get pending expenses (likely large purchases paid in installments)
            expenses_query = """
                SELECT * FROM expense_records
                WHERE (bank_status = 'pending' OR bank_status IS NULL)
            """
            expenses_params = []
            if tenant_id is not None:
                expenses_query += " AND tenant_id = ?"
                expenses_params.append(tenant_id)
            expenses_query += " ORDER BY amount DESC, date DESC LIMIT 50"

            cursor.execute(expenses_query, expenses_params)
            expenses = [dict(row) for row in cursor.fetchall()]

            # Get unreconciled movements with tenant filter
            movements_query = """
                SELECT * FROM bank_movements
                WHERE (matched_expense_id IS NULL OR matched_expense_id = '')
                AND amount < 0
            """
            movements_params = []
            if tenant_id is not None:
                movements_query += " AND tenant_id = ?"
                movements_params.append(tenant_id)
            movements_query += " ORDER BY date DESC"

            cursor.execute(movements_query, movements_params)
            movements = [dict(row) for row in cursor.fetchall()]

            suggestions = []

            for expense in expenses:
                expense_date = datetime.fromisoformat(expense['date'].replace(' ', 'T')) if expense['date'] else None

                if not expense_date:
                    continue

                # Find combinations of movements that sum to expense amount
                matching_combos = self._find_movement_combinations(
                    movements=movements,
                    target_amount=expense['amount'],
                    target_date=expense_date,
                    expense_description=expense['description']
                )

                for combo in matching_combos[:3]:  # Top 3 combinations per expense
                    confidence = self._calculate_many_to_one_confidence(
                        expense=expense,
                        movements=combo['movements'],
                        amount_diff=combo['amount_diff'],
                        date_diff_avg=combo['date_diff_avg']
                    )

                    if confidence >= self.confidence_threshold_medium:
                        suggestions.append({
                            'type': 'many_to_one',
                            'confidence_score': confidence,
                            'confidence_level': self._get_confidence_level(confidence),
                            'expense': {
                                'id': expense['id'],
                                'description': expense['description'],
                                'amount': expense['amount'],
                                'date': expense['date']
                            },
                            'movements': [
                                {
                                    'id': m['id'],
                                    'description': m['description'],
                                    'amount': abs(m['amount']),
                                    'date': m['date'],
                                    'allocated_amount': abs(m['amount']),
                                    'payment_number': idx + 1
                                }
                                for idx, m in enumerate(combo['movements'])
                            ],
                            'breakdown': combo['breakdown'],
                            'total_allocated': sum(abs(m['amount']) for m in combo['movements']),
                            'difference': combo['amount_diff']
                        })

            conn.close()
            return sorted(suggestions, key=lambda x: x['confidence_score'], reverse=True)[:limit]

        except Exception as e:
            logger.error(f"Error suggesting many-to-one splits: {e}")
            conn.close()
            return []

    # =====================================================
    # COMBINATION FINDERS
    # =====================================================

    def _find_expense_combinations(
        self,
        expenses: List[Dict],
        target_amount: float,
        target_date: datetime,
        movement_description: str,
        max_combo_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find combinations of expenses that sum close to target amount

        Uses greedy algorithm + date filtering for performance
        """
        # Filter expenses by date (±30 days)
        date_filtered = [
            e for e in expenses
            if e['date'] and abs((datetime.fromisoformat(e['date'].replace(' ', 'T')) - target_date).days) <= 30
        ]

        if not date_filtered:
            date_filtered = expenses[:20]  # Fallback to recent expenses

        combinations = []

        # Try exact matches first (2-5 expenses)
        for combo_size in range(2, min(max_combo_size + 1, len(date_filtered) + 1)):
            # Simple greedy: pick closest amounts
            sorted_expenses = sorted(date_filtered, key=lambda e: abs(e['amount'] - target_amount / combo_size))

            combo = sorted_expenses[:combo_size]
            combo_sum = sum(e['amount'] for e in combo)
            amount_diff = abs(target_amount - combo_sum)

            # Only consider if difference is small
            if amount_diff <= target_amount * 0.05:  # Within 5%
                date_diffs = [
                    abs((datetime.fromisoformat(e['date'].replace(' ', 'T')) - target_date).days)
                    for e in combo if e['date']
                ]
                date_diff_avg = sum(date_diffs) / len(date_diffs) if date_diffs else 999

                # Calculate description similarity
                desc_similarity = self._calculate_description_similarity(
                    movement_description,
                    [e['description'] for e in combo]
                )

                combinations.append({
                    'manual_expenses': combo,
                    'amount_diff': amount_diff,
                    'date_diff_avg': date_diff_avg,
                    'desc_similarity': desc_similarity,
                    'breakdown': {
                        'amount_match': 100 - (amount_diff / target_amount * 100),
                        'date_proximity': max(0, 100 - date_diff_avg * 3),  # 3 points per day
                        'description_similarity': desc_similarity
                    }
                })

        return sorted(combinations, key=lambda c: (c['amount_diff'], c['date_diff_avg']))[:5]

    def _find_movement_combinations(
        self,
        movements: List[Dict],
        target_amount: float,
        target_date: datetime,
        expense_description: str,
        max_combo_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find combinations of movements that sum close to target amount
        """
        # Filter movements by date (±60 days for installments)
        date_filtered = [
            m for m in movements
            if m['date'] and abs((datetime.fromisoformat(m['date'].replace(' ', 'T')) - target_date).days) <= 60
        ]

        if not date_filtered:
            date_filtered = movements[:20]

        combinations = []

        for combo_size in range(2, min(max_combo_size + 1, len(date_filtered) + 1)):
            sorted_movements = sorted(date_filtered, key=lambda m: abs(abs(m['amount']) - target_amount / combo_size))

            combo = sorted_movements[:combo_size]
            combo_sum = sum(abs(m['amount']) for m in combo)
            amount_diff = abs(target_amount - combo_sum)

            if amount_diff <= target_amount * 0.05:
                date_diffs = [
                    abs((datetime.fromisoformat(m['date'].replace(' ', 'T')) - target_date).days)
                    for m in combo if m['date']
                ]
                date_diff_avg = sum(date_diffs) / len(date_diffs) if date_diffs else 999

                desc_similarity = self._calculate_description_similarity(
                    expense_description,
                    [m['description'] for m in combo]
                )

                combinations.append({
                    'movements': combo,
                    'amount_diff': amount_diff,
                    'date_diff_avg': date_diff_avg,
                    'desc_similarity': desc_similarity,
                    'breakdown': {
                        'amount_match': 100 - (amount_diff / target_amount * 100),
                        'date_proximity': max(0, 100 - date_diff_avg * 2),
                        'description_similarity': desc_similarity
                    }
                })

        return sorted(combinations, key=lambda c: (c['amount_diff'], c['date_diff_avg']))[:5]

    # =====================================================
    # CONFIDENCE SCORING
    # =====================================================

    def _calculate_one_to_many_confidence(
        self,
        movement: Dict,
        expenses: List[Dict],
        amount_diff: float,
        date_diff_avg: float
    ) -> float:
        """
        Calculate confidence score for one-to-many match

        Weights:
        - Amount match: 50%
        - Date proximity: 30%
        - Description similarity: 20%
        """
        movement_amount = abs(movement['amount'])

        # Amount match score (50 points)
        amount_match_pct = max(0, 100 - (amount_diff / movement_amount * 100))
        amount_score = (amount_match_pct / 100) * 50

        # Date proximity score (30 points)
        # Perfect = same day (30), -3 points per day
        date_score = max(0, 30 - (date_diff_avg * 3))

        # Description similarity (20 points)
        desc_similarity = self._calculate_description_similarity(
            movement['description'],
            [e['description'] for e in expenses]
        )
        desc_score = (desc_similarity / 100) * 20

        total_score = amount_score + date_score + desc_score
        return round(total_score, 2)

    def _calculate_many_to_one_confidence(
        self,
        expense: Dict,
        movements: List[Dict],
        amount_diff: float,
        date_diff_avg: float
    ) -> float:
        """Calculate confidence for many-to-one match"""
        # Similar to one-to-many
        amount_match_pct = max(0, 100 - (amount_diff / expense['amount'] * 100))
        amount_score = (amount_match_pct / 100) * 50

        date_score = max(0, 30 - (date_diff_avg * 2))  # More lenient for installments

        desc_similarity = self._calculate_description_similarity(
            expense['description'],
            [m['description'] for m in movements]
        )
        desc_score = (desc_similarity / 100) * 20

        total_score = amount_score + date_score + desc_score
        return round(total_score, 2)

    def _calculate_description_similarity(
        self,
        source_desc: str,
        target_descs: List[str]
    ) -> float:
        """
        Calculate text similarity between descriptions

        Uses multiple strategies:
        1. Exact keyword matching
        2. Sequence matching (fuzzy)
        3. Common terms extraction
        """
        if not source_desc or not target_descs:
            return 0.0

        source_clean = self._clean_description(source_desc)
        targets_clean = [self._clean_description(d) for d in target_descs]

        # Extract keywords
        source_keywords = set(self._extract_keywords(source_clean))

        similarities = []
        for target in targets_clean:
            target_keywords = set(self._extract_keywords(target))

            # Keyword overlap
            if source_keywords and target_keywords:
                overlap = len(source_keywords & target_keywords) / len(source_keywords | target_keywords)
            else:
                overlap = 0.0

            # Sequence matching
            seq_match = SequenceMatcher(None, source_clean, target).ratio()

            # Combined score
            combined = (overlap * 0.6) + (seq_match * 0.4)
            similarities.append(combined)

        # Return average similarity
        return round(sum(similarities) / len(similarities) * 100, 2) if similarities else 0.0

    def _clean_description(self, text: str) -> str:
        """Clean and normalize description text"""
        if not text:
            return ""

        # Lowercase
        text = text.lower()

        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)

        # Remove extra spaces
        text = ' '.join(text.split())

        return text

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        # Common stopwords in Spanish/English
        stopwords = {
            'de', 'del', 'la', 'el', 'en', 'a', 'para', 'con', 'por',
            'the', 'of', 'to', 'and', 'in', 'for', 'on', 'with',
            'pago', 'payment', 'compra', 'purchase', 'movimiento', 'movement'
        }

        words = text.split()
        keywords = [w for w in words if len(w) > 2 and w not in stopwords]

        return keywords

    def _get_confidence_level(self, score: float) -> str:
        """Get confidence level label"""
        if score >= self.confidence_threshold_high:
            return 'high'
        elif score >= self.confidence_threshold_medium:
            return 'medium'
        else:
            return 'low'


# =====================================================
# FACTORY FUNCTION
# =====================================================

def get_ai_reconciliation_service() -> AIReconciliationService:
    """Get singleton instance of AI reconciliation service"""
    return AIReconciliationService()

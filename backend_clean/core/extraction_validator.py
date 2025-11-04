#!/usr/bin/env python3
"""
Production-ready extraction validation system
Ensures PDF processing quality for commercial clients
"""
import re
import logging
from typing import Dict, Any, List
from core.robust_pdf_parser import RobustPDFParser

logger = logging.getLogger(__name__)

class ExtractionValidator:
    """Validates PDF extraction completeness and quality for production use"""

    def __init__(self):
        self.parser = RobustPDFParser()

    def validate_extraction_completeness(self, extracted_count: int, pdf_path: str,
                                       extracted_transactions: List = None) -> Dict[str, Any]:
        """
        Validate extraction quality before saving to database
        CRITICAL for commercial deployment
        """
        try:
            # Count expected transactions from raw PDF text
            expected_count = self._count_transaction_patterns_in_pdf(pdf_path)

            completion_rate = extracted_count / expected_count if expected_count > 0 else 0

            # Detailed analysis
            missing_patterns = self._analyze_missing_patterns(pdf_path, extracted_transactions or [])

            validation_result = {
                "is_complete": completion_rate >= 0.95,  # 95% threshold for production
                "extracted_count": extracted_count,
                "expected_count": expected_count,
                "completion_rate": completion_rate,
                "missing_count": expected_count - extracted_count,
                "status": self._get_status_level(completion_rate),
                "missing_patterns": missing_patterns,
                "recommendations": self._get_recommendations(completion_rate, missing_patterns),
                "client_notification_required": completion_rate < 0.90  # Notify client if < 90%
            }

            # Log validation results
            if completion_rate < 0.95:
                logger.warning(f"⚠️ Extraction incomplete: {completion_rate:.1%} ({extracted_count}/{expected_count})")
                logger.warning(f"Missing patterns: {missing_patterns}")
            else:
                logger.info(f"✅ Extraction complete: {completion_rate:.1%} ({extracted_count}/{expected_count})")

            return validation_result

        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            return {
                "is_complete": False,
                "extracted_count": extracted_count,
                "expected_count": 0,
                "completion_rate": 0,
                "status": "ERROR",
                "error": str(e),
                "client_notification_required": True
            }

    def _count_transaction_patterns_in_pdf(self, pdf_path: str) -> int:
        """Count expected transactions by unique references - IMPROVED METHOD"""
        try:
            # Extract raw text
            text = self.parser.extract_text(pdf_path)
            lines = text.split('\n')

            unique_references = set()
            balance_inicials = 0

            for line in lines:
                line_clean = line.strip()

                # Count unique reference transactions
                match = re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s+\d{1,2}\s+(\d{8,12})\s+', line_clean)
                if match:
                    reference = match.group(2)
                    unique_references.add(reference)

                # Count Balance Inicial separately
                elif re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s+\d{1,2}\s+BALANCE\s+INICIAL', line_clean):
                    balance_inicials += 1

            expected_count = len(unique_references) + balance_inicials

            logger.info(f"🔍 Reference analysis: Unique refs={len(unique_references)}, Balance inicial={balance_inicials}")
            logger.info(f"📊 Expected transactions (by references): {expected_count}")

            return expected_count

        except Exception as e:
            logger.error(f"❌ Error counting references: {e}")
            return 0

    def _analyze_missing_patterns(self, pdf_path: str, extracted_transactions: List) -> Dict[str, int]:
        """Analyze what types of transactions are missing"""
        try:
            text = self.parser.extract_text(pdf_path)
            lines = text.split('\n')

            missing_patterns = {
                "balance_inicial": 0,
                "with_reference": 0,
                "without_reference": 0,
                "special_characters": 0,
                "complex_descriptions": 0
            }

            extracted_descriptions = {t.description.lower() for t in extracted_transactions} if extracted_transactions else set()

            for line in lines:
                line_clean = line.strip()

                # Check for Balance Inicial
                if re.search(r'BALANCE\s+INICIAL', line_clean, re.IGNORECASE):
                    if not any('balance inicial' in desc for desc in extracted_descriptions):
                        missing_patterns["balance_inicial"] += 1

                # Check for transactions with references
                if re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s+\d{1,2}\s+\d{10}', line_clean):
                    missing_patterns["with_reference"] += 1

                # Check for transactions without references
                elif re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.\s+\d{1,2}\s+[A-Z]', line_clean):
                    missing_patterns["without_reference"] += 1

                # Check for special characters (*, /, etc.)
                if re.search(r'[*\/]+', line_clean) and re.search(r'(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)', line_clean):
                    missing_patterns["special_characters"] += 1

            return missing_patterns

        except Exception as e:
            logger.error(f"❌ Error analyzing missing patterns: {e}")
            return {}

    def _get_status_level(self, completion_rate: float) -> str:
        """Get status level based on completion rate"""
        if completion_rate >= 0.95:
            return "EXCELLENT"
        elif completion_rate >= 0.90:
            return "GOOD"
        elif completion_rate >= 0.80:
            return "WARNING"
        elif completion_rate >= 0.60:
            return "CRITICAL"
        else:
            return "FAILED"

    def _get_recommendations(self, completion_rate: float, missing_patterns: Dict) -> List[str]:
        """Get recommendations for improving extraction"""
        recommendations = []

        if completion_rate < 0.95:
            recommendations.append("Consider using LLM parser with improved chunking")

        if missing_patterns.get("balance_inicial", 0) > 0:
            recommendations.append("Enable automatic Balance Inicial generation")

        if missing_patterns.get("special_characters", 0) > 0:
            recommendations.append("Improve regex patterns for special characters")

        if missing_patterns.get("with_reference", 0) > 0:
            recommendations.append("Enhance reference number detection patterns")

        if completion_rate < 0.80:
            recommendations.append("URGENT: Manual review required before client delivery")

        return recommendations

def validate_pdf_extraction(extracted_count: int, pdf_path: str, extracted_transactions: List = None) -> Dict[str, Any]:
    """
    Convenience function for validating PDF extraction
    Use this in production parsers
    """
    validator = ExtractionValidator()
    return validator.validate_extraction_completeness(extracted_count, pdf_path, extracted_transactions)
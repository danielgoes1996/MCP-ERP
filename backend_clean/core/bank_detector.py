#!/usr/bin/env python3
"""
Detector automático de banco basado en contenido del PDF
"""
import re
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class BankDetector:
    """Detecta automáticamente el banco basado en el contenido del PDF"""

    def __init__(self):
        # Patrones específicos por banco
        self.bank_patterns = {
            'BBVA': [
                r'BBVA\s+MÉXICO',
                r'BBVA\s+BANCOMER',
                r'www\.bbva\.mx',
                r'ESTADO\s+DE\s+CUENTA\s+BBVA',
                r'BBVA\s+CREDIT',
                r'BBVA\s+DEBIT'
            ],
            'Santander': [
                r'BANCO\s+SANTANDER',
                r'SANTANDER\s+MÉXICO',
                r'www\.santander\.com\.mx',
                r'ESTADO\s+DE\s+CUENTA\s+SANTANDER',
                r'SANTANDER\s+SERFIN'
            ],
            'Inbursa': [
                r'BANCO\s+INBURSA',
                r'INBURSA\s+GRUPO\s+FINANCIERO',
                r'www\.inbursa\.com',
                r'ESTADO\s+DE\s+CUENTA.*INBURSA',
                r'GRUPO\s+FINANCIERO\s+INBURSA',
                r'INBURSA\s+S\.A\.',
                r'INBURSA.*INSTITUCIÓN\s+DE\s+BANCA'
            ],
            'Banamex': [
                r'CITIBANAMEX',
                r'BANCO\s+NACIONAL\s+DE\s+MÉXICO',
                r'BANAMEX',
                r'www\.banamex\.com',
                r'CITIGROUP'
            ],
            'Banorte': [
                r'BANCO\s+MERCANTIL\s+DEL\s+NORTE',
                r'BANORTE',
                r'www\.banorte\.com',
                r'GRUPO\s+FINANCIERO\s+BANORTE'
            ]
        }

        # Patrones de formato específicos por banco - UNIVERSALES
        self.format_patterns = {
            'BBVA': [
                r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2}\s+\d{8,}',  # Formato universal BBVA
                r'BBVA.*\*\d{4}'  # Número de cuenta enmascarado BBVA
            ],
            'Inbursa': [
                r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2}\s+\d{8,}',  # Formato universal Inbursa
                r'INBURSA.*\d{4,}',
                r'TRASPASO\s+SPEI\s+INBURSA',  # Transferencias específicas Inbursa
                r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2}\s+\d{10}\s+[A-Z]',  # Patrón específico Inbursa con ref larga
            ],
            'Santander': [
                r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\.?\s+\d{1,2}\s+\d{6,}',  # Formato universal Santander
                r'SANTANDER.*\d{4,}'
            ]
        }

    def detect_bank_from_text(self, text: str) -> Optional[str]:
        """
        Detecta el banco basado en el contenido del texto

        Args:
            text: Texto extraído del PDF

        Returns:
            Nombre del banco detectado o None si no se puede determinar
        """
        text_upper = text.upper()

        # Puntuación por banco
        bank_scores = {}

        # Verificar patrones de nombre/marca del banco
        for bank, patterns in self.bank_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_upper))
                score += matches * 10  # Peso alto para nombres de banco

            bank_scores[bank] = score

        # Verificar patrones de formato específicos
        for bank, patterns in self.format_patterns.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_upper))
                bank_scores[bank] = bank_scores.get(bank, 0) + matches * 5

        # Log de scoring para debug
        logger.info(f"🔍 Bank detection scores: {bank_scores}")

        # Encontrar el banco con mayor puntuación
        if bank_scores:
            detected_bank = max(bank_scores, key=bank_scores.get)
            max_score = bank_scores[detected_bank]

            if max_score >= 10:  # Umbral mínimo de confianza
                logger.info(f"✅ Detected bank: {detected_bank} (score: {max_score})")
                return detected_bank
            else:
                logger.warning(f"⚠️ Low confidence bank detection. Best guess: {detected_bank} (score: {max_score})")

        logger.warning("❌ Could not reliably detect bank from PDF content")
        return None

    def get_bank_compatibility_score(self, pdf_bank: str, account_bank: str) -> float:
        """
        Calcula un score de compatibilidad entre el banco del PDF y la cuenta

        Args:
            pdf_bank: Banco detectado en el PDF
            account_bank: Banco configurado en la cuenta

        Returns:
            Score de 0.0 a 1.0 (1.0 = perfecta compatibilidad)
        """
        if not pdf_bank or not account_bank:
            return 0.5  # Neutral si no podemos determinar

        # Normalizar nombres de bancos
        pdf_bank_norm = self._normalize_bank_name(pdf_bank)
        account_bank_norm = self._normalize_bank_name(account_bank)

        if pdf_bank_norm == account_bank_norm:
            return 1.0  # Coincidencia perfecta

        # Verificar compatibilidades conocidas
        compatible_banks = {
            'BBVA': ['BBVA MÉXICO', 'BBVA BANCOMER', 'BANCOMER'],
            'SANTANDER': ['BANCO SANTANDER', 'SANTANDER MÉXICO', 'SANTANDER SERFIN'],
            'INBURSA': ['BANCO INBURSA', 'GRUPO FINANCIERO INBURSA', 'INBURSA']
        }

        for main_bank, variants in compatible_banks.items():
            if (pdf_bank_norm in [main_bank] + variants and
                account_bank_norm in [main_bank] + variants):
                return 1.0

        return 0.0  # No compatibles

    def _normalize_bank_name(self, bank_name: str) -> str:
        """Normaliza el nombre del banco para comparación"""
        bank_name = bank_name.upper().strip()

        # Mapeo de nombres comunes
        name_mappings = {
            'BBVA MÉXICO': 'BBVA',
            'BBVA BANCOMER': 'BBVA',
            'BANCOMER': 'BBVA',
            'BANCO SANTANDER': 'SANTANDER',
            'SANTANDER MÉXICO': 'SANTANDER',
            'BANCO INBURSA': 'INBURSA',
            'GRUPO FINANCIERO INBURSA': 'INBURSA',
            'INBURSA': 'INBURSA'
        }

        return name_mappings.get(bank_name, bank_name)

    def validate_pdf_account_compatibility(self, pdf_text: str, account_bank: str) -> Dict:
        """
        Valida la compatibilidad entre PDF y cuenta

        Returns:
            Dict con resultado de validación
        """
        detected_bank = self.detect_bank_from_text(pdf_text)
        compatibility_score = self.get_bank_compatibility_score(detected_bank, account_bank)

        return {
            'detected_bank': detected_bank,
            'account_bank': account_bank,
            'compatibility_score': compatibility_score,
            'is_compatible': compatibility_score >= 0.8,
            'warning_message': self._get_warning_message(detected_bank, account_bank, compatibility_score)
        }

    def _get_warning_message(self, pdf_bank: str, account_bank: str, score: float) -> Optional[str]:
        """Genera mensaje de advertencia si hay problemas de compatibilidad"""
        if score >= 0.8:
            return None

        if pdf_bank and account_bank and score < 0.5:
            return f"⚠️ ADVERTENCIA: El PDF parece ser de {pdf_bank} pero la cuenta está configurada como {account_bank}. Esto puede causar errores de procesamiento."

        if not pdf_bank:
            return "⚠️ No se pudo detectar automáticamente el banco del PDF. Verifique que el archivo sea válido."

        return f"⚠️ Compatibilidad baja entre PDF ({pdf_bank}) y cuenta ({account_bank}). Score: {score:.1f}"
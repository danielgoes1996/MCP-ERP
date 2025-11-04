#!/usr/bin/env python3
"""
Text cleaner for PDF extraction - removes duplicate tables and reconstructs fragmented transactions
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class PDFTextCleaner:
    """Cleans and reconstructs PDF text before sending to LLM"""

    def __init__(self):
        # Support all Spanish months, not just JUL
        month_pattern = r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)'
        self.transaction_pattern = re.compile(rf'^{month_pattern}\.\s+\d{{1,2}}\s+\d{{8,}}')
        self.empty_date_pattern = re.compile(rf'^{month_pattern}\.\s+\d{{1,2}}\s*$')
        self.balance_pattern = re.compile(rf'^{month_pattern}\.\s+\d{{1,2}}\s+BALANCE\s+INICIAL')

    def clean_and_reconstruct(self, raw_text: str) -> str:
        """Main function to clean and reconstruct PDF text"""

        logger.info("🧹 Starting text cleaning and reconstruction")

        lines = raw_text.split('\n')

        # Step 1: Remove empty date lines and table headers
        cleaned_lines = self._remove_empty_dates_and_tables(lines)

        # Step 2: Reconstruct fragmented transactions
        reconstructed_lines = self._reconstruct_transactions(cleaned_lines)

        # Step 3: Remove remaining junk lines
        final_lines = self._remove_junk_lines(reconstructed_lines)

        clean_text = '\n'.join(final_lines)

        # Count all Spanish month transactions, not just JUL
        months = ['ENE.', 'FEB.', 'MAR.', 'ABR.', 'MAY.', 'JUN.', 'JUL.', 'AGO.', 'SEP.', 'OCT.', 'NOV.', 'DIC.']
        original_month_count = sum(raw_text.upper().count(month) for month in months)
        final_month_count = sum(clean_text.upper().count(month) for month in months)

        logger.info(f"📊 Cleaning results:")
        logger.info(f"   Original month lines: {original_month_count}")
        logger.info(f"   Final month lines: {final_month_count}")
        logger.info(f"   Removed noise: {original_month_count - final_month_count}")

        return clean_text

    def _remove_empty_dates_and_tables(self, lines: List[str]) -> List[str]:
        """Remove empty date lines and table headers"""

        cleaned = []
        skip_next_lines = 0

        for i, line in enumerate(lines):
            line_clean = line.strip()

            if skip_next_lines > 0:
                skip_next_lines -= 1
                continue

            # Skip table headers and their surrounding lines
            if '--- TABLA' in line_clean or 'FECHA REFERENCIA CONCEPTO' in line_clean:
                skip_next_lines = 2  # Skip this line and next 2
                continue

            # PRESERVE Balance Inicial lines
            if self.balance_pattern.match(line_clean):
                logger.debug(f"Preserving Balance Inicial: '{line_clean}'")
                cleaned.append(line)
                continue

            # Skip empty date lines (MONTH. DD with no data) - but not Balance Inicial
            if self.empty_date_pattern.match(line_clean):
                logger.debug(f"Removing empty date line: '{line_clean}'")
                continue

            # Skip lines that are just numbers or very short
            if line_clean and len(line_clean) < 3 and line_clean.isdigit():
                continue

            # Skip lines with just symbols
            if re.match(r'^[\|\s\(\)]+$', line_clean):
                continue

            cleaned.append(line)

        logger.info(f"📄 Removed {len(lines) - len(cleaned)} empty/junk lines")
        return cleaned

    def _reconstruct_transactions(self, lines: List[str]) -> List[str]:
        """Reconstruct fragmented transactions into single lines"""

        reconstructed = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # If this is a transaction start
            if self.transaction_pattern.match(line) or self.balance_pattern.match(line):
                transaction_parts = [line]
                j = i + 1

                # Look for continuation lines
                while j < len(lines) and j < i + 6:  # Max 6 lines per transaction
                    next_line = lines[j].strip()

                    # Stop if we hit another transaction or empty line
                    if (self.transaction_pattern.match(next_line) or
                        self.balance_pattern.match(next_line) or
                        not next_line or
                        next_line.startswith('---')):
                        break

                    # Check if this looks like a continuation
                    if self._is_continuation_line(next_line, transaction_parts[0]):
                        transaction_parts.append(next_line)
                        j += 1
                    else:
                        break

                # Join the transaction parts
                if len(transaction_parts) > 1:
                    full_transaction = ' '.join(transaction_parts)
                    logger.debug(f"Reconstructed transaction: {full_transaction[:100]}...")
                    reconstructed.append(full_transaction)
                else:
                    reconstructed.append(transaction_parts[0])

                i = j
            else:
                # Not a transaction, keep as is
                if line:  # Only keep non-empty lines
                    reconstructed.append(line)
                i += 1

        # Count reconstructed transactions for all months
        months = ['ENE.', 'FEB.', 'MAR.', 'ABR.', 'MAY.', 'JUN.', 'JUL.', 'AGO.', 'SEP.', 'OCT.', 'NOV.', 'DIC.']
        transaction_count = sum(1 for line in reconstructed if any(month in line.upper() for month in months))
        logger.info(f"🔧 Reconstructed {transaction_count} transactions")

        return reconstructed

    def _is_continuation_line(self, line: str, transaction_start: str) -> bool:
        """Check if a line is likely a continuation of a transaction"""

        line_clean = line.strip()

        # Skip very short lines that are just numbers
        if len(line_clean) < 3:
            return False

        # Common continuation patterns
        continuation_patterns = [
            r'^[A-Z\s]+[A-Z]$',  # Names in caps
            r'.*\d{12,}.*',       # Long numbers (account numbers)
            r'.*CLAVE DE RASTREO.*',  # Tracking codes
            r'.*TRANSFERENCIA.*',     # Transfer descriptions
            r'.*MERCADO.*PAGO.*',     # Mercado Pago
            r'.*SANTANDER.*',         # Bank names
            r'.*BBVA.*',
            r'.*MULTIVA.*',
            r'.*MIFEL.*',
            r'^\d+\.?\d*$',          # Pure numbers
            r'.*USD.*TC.*',          # Currency conversions
        ]

        for pattern in continuation_patterns:
            if re.match(pattern, line_clean, re.IGNORECASE):
                return True

        # If it contains bank-related keywords
        bank_keywords = ['BANCO', 'SPEI', 'TRANSFERENCIA', 'DEPOSITO', 'PAGO']
        if any(keyword in line_clean.upper() for keyword in bank_keywords):
            return True

        # If it's a reasonable length for a description
        if 5 < len(line_clean) < 100:
            return True

        return False

    def _remove_junk_lines(self, lines: List[str]) -> List[str]:
        """Final cleanup of remaining junk lines"""

        final_lines = []

        for line in lines:
            line_clean = line.strip()

            if not line_clean:
                continue

            # Skip page markers
            if line_clean.startswith('--- PÁGINA'):
                continue

            # Skip encoding artifacts
            if '(cid:' in line_clean:
                continue

            # Skip very short lines that are just numbers
            if len(line_clean) < 4 and line_clean.isdigit():
                continue

            # Keep everything else
            final_lines.append(line_clean)

        return final_lines

    def get_cleaning_stats(self, original_text: str, cleaned_text: str) -> dict:
        """Get statistics about the cleaning process"""

        original_lines = original_text.split('\n')
        cleaned_lines = cleaned_text.split('\n')

        # Count all month transactions, not just JUL
        months = ['ENE.', 'FEB.', 'MAR.', 'ABR.', 'MAY.', 'JUN.', 'JUL.', 'AGO.', 'SEP.', 'OCT.', 'NOV.', 'DIC.']
        original_months = sum(original_text.upper().count(month) for month in months)
        cleaned_months = sum(cleaned_text.upper().count(month) for month in months)

        # Count transaction-like lines for all months
        month_pattern = r'(?:ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)'
        original_transactions = sum(1 for line in original_lines if re.match(rf'.*{month_pattern}\.\s+\d{{1,2}}\s+\d{{8,}}', line))
        cleaned_transactions = sum(1 for line in cleaned_lines if re.match(rf'.*{month_pattern}\.\s+\d{{1,2}}\s+\d{{8,}}', line))

        return {
            'original_lines': len(original_lines),
            'cleaned_lines': len(cleaned_lines),
            'lines_removed': len(original_lines) - len(cleaned_lines),
            'original_jul_count': original_months,  # Now counts all months, not just JUL
            'cleaned_jul_count': cleaned_months,    # Now counts all months, not just JUL
            'jul_lines_removed': original_months - cleaned_months,  # Now counts all months
            'original_transactions': original_transactions,
            'cleaned_transactions': cleaned_transactions,
            'transactions_preserved': cleaned_transactions >= original_transactions
        }
#!/usr/bin/env python3
"""
Parser específico para estructura CARGOS/ABONOS de estados de cuenta bancarios
"""
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
    should_skip_transaction,
)
from core.ai_pipeline.parsers.robust_pdf_parser import RobustPDFParser

logger = logging.getLogger(__name__)


class CargosAbonosParser(RobustPDFParser):
    def __init__(self):
        super().__init__()

    def parse_transactions(self, text: str, account_id: int, user_id: int, tenant_id: int) -> Tuple[List[BankTransaction], Dict[str, Any]]:
        """Parse transactions using CARGOS/ABONOS column structure with proper multi-line grouping"""
        logger.info("🔍 Parsing MEJORADO basado en estructura CARGOS/ABONOS")

        transactions = []
        text_lines = text.split('\n')

        # Buscar el inicio de la sección de movimientos
        movement_section_started = False
        current_block = []

        for line_num, line in enumerate(text_lines):
            line = line.strip()

            # Detectar inicio de la sección de movimientos
            if "DETALLE DE MOVIMIENTOS" in line or ("FECHA" in line and "CONCEPTO" in line and "CARGOS" in line):
                movement_section_started = True
                continue

            if not movement_section_started or not line or line.startswith("Página"):
                continue

            # Detectar inicio de nueva transacción (fecha + referencia)
            if re.match(r'JUL\.\s*\d{2}\s+\d{8,}', line):
                # Procesar bloque anterior si existe
                if current_block:
                    transaction = self._parse_multiline_transaction_block(current_block, account_id, user_id, tenant_id)
                    if transaction:
                        transactions.append(transaction)

                # Iniciar nuevo bloque
                current_block = [line]

            elif current_block:
                # Verificar si la línea indica fin de transacción
                if any(marker in line for marker in ['--- TABLA', 'BANCO INBURSA', 'REGIMEN FISCAL', 'RESUMEN DE SALDOS']):
                    # Procesar bloque actual antes de continuar
                    transaction = self._parse_multiline_transaction_block(current_block, account_id, user_id, tenant_id)
                    if transaction:
                        transactions.append(transaction)
                    current_block = []
                    continue

                # Agregar línea al bloque actual
                current_block.append(line)

        # Procesar el último bloque si existe
        if current_block:
            transaction = self._parse_multiline_transaction_block(current_block, account_id, user_id, tenant_id)
            if transaction:
                transactions.append(transaction)

        # Calcular resumen
        summary = self._calculate_summary(transactions)

        logger.info(f"🎯 Parsing MEJORADO completado: {len(transactions)} transacciones encontradas")
        return transactions, summary

    def _parse_multiline_transaction_block(self, lines: List[str], account_id: int, user_id: int, tenant_id: int) -> Optional[BankTransaction]:
        """Parse a multi-line block that represents one complete transaction"""
        if not lines:
            return None

        try:
            # Extraer fecha y referencia de la primera línea
            first_line = lines[0]
            date_match = re.match(r'JUL\.\s*(\d{2})\s+(\d{8,})', first_line)
            if not date_match:
                return None

            day = int(date_match.group(1))
            reference = date_match.group(2)
            transaction_date = datetime(2024, 7, day).date()

            # Buscar cargo/abono en todas las líneas del bloque
            cargo_amount, abono_amount, saldo = self._extract_amounts_from_block(lines)

            if cargo_amount == 0 and abono_amount == 0:
                logger.warning(f"No se encontró monto válido en bloque: {' '.join(lines[:2])}")
                return None

            # Construir descripción completa (todo excepto fecha, referencia y montos finales)
            description = self._build_complete_description(lines, reference)

            # Determinar el monto final de la transacción
            if cargo_amount > 0:
                amount = -cargo_amount  # Cargos son negativos
                transaction_type = TransactionType.DEBIT
            elif abono_amount > 0:
                amount = abono_amount   # Abonos son positivos
                transaction_type = TransactionType.CREDIT
            else:
                return None

            # Clasificar tipo de movimiento
            movement_kind = self._classify_movement(description, amount)

            # Crear transacción
            transaction = BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                date=transaction_date,
                description=description[:500],
                amount=round(amount, 2),
                transaction_type=transaction_type,
                category="Sin categoría",
                confidence=0.90,
                raw_data='\n'.join(lines)[:1000],
                movement_kind=movement_kind,
                reference=reference,
                balance_after=saldo
            )

            logger.debug(f"✅ Transacción MEJORADA: {description[:50]} | ${amount} | {movement_kind.value}")
            return transaction

        except Exception as e:
            logger.warning(f"Error parseando bloque multilinea: {e}")
            return None

    def _extract_description(self, text: str) -> str:
        """Extract transaction description from text"""
        # Remover fecha y referencia del inicio
        desc = re.sub(r'^JUL\.\s*\d{2}\s+\d+\s*', '', text)

        # Remover montos del final (buscar patrones de números)
        desc = re.sub(r'\d+(?:,\d{3})*\.?\d*\s*$', '', desc)
        desc = re.sub(r'\d+(?:,\d{3})*\.?\d*\s+\d+(?:,\d{3})*\.?\d*\s*$', '', desc)

        # Limpiar espacios extra
        desc = re.sub(r'\s+', ' ', desc).strip()

        # Si queda muy corto, intentar extraer de otra manera
        if len(desc) < 10:
            # Buscar desde referencia hasta primer monto grande
            match = re.search(r'\d{8,}\s+(.+?)\s+\d+(?:,\d{3})*\.?\d*', text)
            if match:
                desc = match.group(1).strip()

        return desc or "Transacción sin descripción"

    def _extract_amounts(self, text: str) -> Tuple[float, float, Optional[float]]:
        """Extract cargo, abono and saldo amounts from text"""
        cargo_amount = 0.0
        abono_amount = 0.0
        saldo = None

        # Buscar patrones de montos más específicos
        amounts = re.findall(r'\d+(?:,\d{3})*\.?\d*', text)

        if not amounts:
            return cargo_amount, abono_amount, saldo

        # Convertir a floats
        numeric_amounts = []
        for amt in amounts:
            try:
                clean_amt = amt.replace(',', '')
                numeric_value = float(clean_amt)
                # Filtrar números demasiado pequeños (probablemente decimales o años)
                if numeric_value >= 0.01:
                    numeric_amounts.append(numeric_value)
            except:
                continue

        if not numeric_amounts:
            return cargo_amount, abono_amount, saldo

        # Estrategia mejorada: buscar el patrón específico del banco
        # Formato típico: JUL.XX REFERENCIA CONCEPTO [USD_AMOUNT] CARGO/ABONO SALDO

        # El saldo suele ser el último número o el más grande
        if len(numeric_amounts) >= 1:
            saldo = max(numeric_amounts)

        # Para transacciones USD, buscar el patrón específico
        text_upper = text.upper()
        if 'USD' in text_upper and '/TC' in text_upper:
            # Buscar patrón: USD X.XX /TC Y.YY = Z.ZZ
            usd_match = re.search(r'USD\s+([\d.]+).*?/TC.*?([\d,]+\.?\d*)', text)
            if usd_match:
                try:
                    tc_amount = float(usd_match.group(2).replace(',', ''))
                    cargo_amount = tc_amount
                    return cargo_amount, abono_amount, saldo
                except:
                    pass

        # Para otros casos, usar heurísticas basadas en el contexto
        is_likely_expense = any(keyword in text_upper for keyword in [
            'APPLE', 'GOOGLE', 'OPENAI', 'SPOTIFY', 'NETFLIX', 'AMAZON',
            'UBER', 'COMISION', 'IVA', 'CFE', 'TELMEX', 'PEMEX', 'WALMART'
        ])

        is_likely_income = any(keyword in text_upper for keyword in [
            'DEPOSITO', 'SPEI', 'INTERESES', 'REEMBOLSO', 'ABONO', 'NOMINA'
        ])

        # Buscar el monto de transacción (no el saldo)
        transaction_amounts = [amt for amt in numeric_amounts if amt != saldo and amt < saldo]

        if transaction_amounts:
            # Tomar el monto más relevante (ni muy pequeño ni muy grande)
            transaction_amount = sorted(transaction_amounts, reverse=True)[0]

            if is_likely_expense:
                cargo_amount = transaction_amount
            elif is_likely_income:
                abono_amount = transaction_amount
            else:
                # Asumir cargo para montos menores a 10,000
                if transaction_amount < 10000:
                    cargo_amount = transaction_amount
                else:
                    abono_amount = transaction_amount

        return cargo_amount, abono_amount, saldo

    def _extract_amounts_from_block(self, lines: List[str]) -> Tuple[float, float, Optional[float]]:
        """Extract cargo, abono and saldo from a complete transaction block"""
        cargo_amount = 0.0
        abono_amount = 0.0
        saldo = None

        # Combinar todas las líneas del bloque
        full_text = " ".join(lines)

        # Buscar todos los números en el bloque
        amounts = re.findall(r'\d+(?:,\d{3})*\.?\d*', full_text)
        numeric_amounts = []

        for amt_str in amounts:
            try:
                clean_amt = amt_str.replace(',', '')
                numeric_value = float(clean_amt)
                if numeric_value >= 0.01:  # Filtrar números muy pequeños
                    numeric_amounts.append(numeric_value)
            except:
                continue

        if not numeric_amounts:
            return cargo_amount, abono_amount, saldo

        # Usar la lógica de la función old que funcionaba mejor
        return self._extract_amounts_from_block_old(lines)

    def _extract_amounts_from_block_old(self, lines: List[str]) -> Tuple[float, float, Optional[float]]:
        """Extract cargo, abono and saldo from a complete transaction block (OLD VERSION)"""
        cargo_amount = 0.0
        abono_amount = 0.0
        saldo = None

        # Combinar todas las líneas del bloque
        full_text = " ".join(lines)

        # Estrategia especial para DOMICILIACION (formato: DOMICILIACION MONTO SALDO)
        text_upper = full_text.upper()
        if 'DOMICILIACION' in text_upper:
            # Buscar patrón: DOMICILIACION MONTO.XX SALDO.XX
            domiciliacion_match = re.search(r'DOMICILIACION\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)', full_text)
            if domiciliacion_match:
                try:
                    transaction_amount = float(domiciliacion_match.group(1).replace(',', ''))
                    saldo_amount = float(domiciliacion_match.group(2).replace(',', ''))
                    cargo_amount = transaction_amount  # DOMICILIACION es siempre cargo
                    saldo = saldo_amount
                    return cargo_amount, abono_amount, saldo
                except:
                    pass

        # Estrategia especial para TRASPASO ENTRE CUENTAS
        if 'TRASPASO ENTRE CUENTAS' in text_upper:
            # Buscar patrón: TRASPASO ENTRE CUENTAS MONTO.XX SALDO.XX
            traspaso_match = re.search(r'TRASPASO ENTRE CUENTAS\s+([\d,]+\.?\d*)', full_text)
            if traspaso_match:
                try:
                    transaction_amount = float(traspaso_match.group(1).replace(',', ''))
                    cargo_amount = transaction_amount  # TRASPASO es cargo
                    # Buscar el saldo al final
                    if numeric_amounts:
                        saldo = max(numeric_amounts)  # El saldo suele ser el número más grande
                    return cargo_amount, abono_amount, saldo
                except:
                    pass

        # Estrategia especial para DEPOSITO EFECTIVO CORRESPONSAL
        if 'DEPOSITO EFECTIVO CORRESPONSAL' in text_upper:
            # Buscar patrón: DEPOSITO EFECTIVO CORRESPONSAL MONTO.XX SALDO.XX
            deposito_match = re.search(r'DEPOSITO EFECTIVO CORRESPONSAL\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)', full_text)
            if deposito_match:
                try:
                    transaction_amount = float(deposito_match.group(1).replace(',', ''))
                    saldo_amount = float(deposito_match.group(2).replace(',', ''))
                    abono_amount = transaction_amount  # DEPOSITO es abono
                    saldo = saldo_amount
                    return cargo_amount, abono_amount, saldo
                except:
                    pass

        # Estrategia especial para transacciones USD con /TC
        if 'USD' in text_upper and '/TC' in text_upper:
            # Buscar patrón simplificado: /TC Y.YY
            tc_match = re.search(r'/TC\s+([\d,]+\.?\d*)', full_text)
            if tc_match:
                try:
                    tc_amount = float(tc_match.group(1).replace(',', ''))
                    cargo_amount = tc_amount  # Transacciones USD suelen ser gastos
                    # El saldo es el último número (en este caso sería 18.86 según el debug)
                    if numeric_amounts:
                        saldo = numeric_amounts[-1]
                    logger.debug(f"✅ USD/TC detectado: TC {tc_amount}, saldo: {saldo}")
                    return cargo_amount, abono_amount, saldo
                except Exception as e:
                    logger.warning(f"Error procesando USD/TC: {e}")
                    pass

        # Estrategia específica para DEPOSITO SPEI
        if 'DEPOSITO SPEI' in text_upper:
            # Para depósitos SPEI, el patrón es muy específico:
            # "DEPOSITO SPEI MONTO SALDO NOMBRE..."
            spei_match = re.search(r'DEPOSITO SPEI\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)', full_text)
            if spei_match:
                try:
                    deposit_amount = float(spei_match.group(1).replace(',', ''))
                    saldo_amount = float(spei_match.group(2).replace(',', ''))
                    abono_amount = deposit_amount  # Depósitos SPEI son siempre ingresos
                    saldo = saldo_amount
                    return cargo_amount, abono_amount, saldo
                except:
                    pass

        # Estrategia específica para comisiones e IVA
        if 'COMISION' in text_upper or 'IVA' in text_upper:
            # Para comisiones, buscar el monto que aparece después de "INBURED" o similar
            # Patrón: "IVA COMISION POR MOVIMIENTOS INBURED 2.16 41,424.89" -> monto=2.16
            if 'INBURED' in text_upper:
                # Buscar número que aparece inmediatamente después de INBURED
                inbured_match = re.search(r'INBURED\s+([\d,]+\.?\d*)', full_text, re.IGNORECASE)
                if inbured_match:
                    try:
                        commission_amount = float(inbured_match.group(1).replace(',', ''))
                        cargo_amount = commission_amount
                        if numeric_amounts:
                            saldo = numeric_amounts[-1]  # Último número como saldo
                        return cargo_amount, abono_amount, saldo
                    except:
                        pass

            # Fallback: buscar el primer número pequeño después de la descripción
            small_amounts = [amt for amt in numeric_amounts if amt < 1000 and amt > 0.01]
            if small_amounts:
                cargo_amount = small_amounts[0]  # Primer monto pequeño
                if numeric_amounts:
                    saldo = numeric_amounts[-1]  # Último número como saldo
                return cargo_amount, abono_amount, saldo

        # Estrategia inteligente: analizar el patrón completo
        # Formato típico: "JUL.XX REF CONCEPTO MONTO SALDO"
        if len(numeric_amounts) >= 2:
            # Excluir números que claramente son fechas o referencias
            filtered_amounts = []
            for amt in numeric_amounts:
                # Filtrar días del mes (1-31) y referencias largas (>1000000)
                if not (1 <= amt <= 31 or amt > 1000000):
                    filtered_amounts.append(amt)

            if len(filtered_amounts) >= 2:
                # Los últimos 2 números filtrados
                potential_amount = filtered_amounts[-2]  # Penúltimo (cargo/abono)
                saldo = filtered_amounts[-1]             # Último (saldo)

                # Validación adicional: el saldo debe ser mayor que el monto de transacción
                # Si no, intercambiar
                if potential_amount > saldo and saldo > 1:
                    potential_amount, saldo = saldo, potential_amount

                # Clasificación pura CARGO/ABONO basada en contexto bancario
                # Mantener las estrategias específicas pero clasificar solo como cargo/abono

                # Patrones típicos de ABONOS (entradas de dinero)
                abono_patterns = [
                    'DEPOSITO SPEI', 'DEPOSITO EFECTIVO', 'INTERESES GANADOS',
                    'REEMBOLSO', 'NOMINA', 'SALARIO', 'INTERES'
                ]

                # Patrones típicos de CARGOS (salidas de dinero)
                cargo_patterns = [
                    'DOMICILIACION', 'COMISION', 'IVA', 'APPLE', 'GOOGLE',
                    'STRIPE', 'PAYPAL', 'NETFLIX', 'SPOTIFY', 'AMAZON', 'UBER',
                    'PYTHAGORA', 'BUBBLE', 'TECHNOLOGIES', 'STR*', 'OPENAI',
                    'MC DONALD', 'MCDONALD', 'POLANCO', 'MX', 'RESTAURANT',
                    'TRASPASO ENTRE CUENTAS', 'TRASPASO', 'CEA QRO', 'RECARGA'
                ]

                is_abono = any(pattern in text_upper for pattern in abono_patterns)
                is_cargo = any(pattern in text_upper for pattern in cargo_patterns)

                if is_abono:
                    abono_amount = potential_amount
                elif is_cargo:
                    cargo_amount = potential_amount
                else:
                    # Heurística: si es un monto pequeño vs saldo, probablemente es cargo
                    if potential_amount < saldo * 0.1:
                        cargo_amount = potential_amount
                    else:
                        abono_amount = potential_amount
            else:
                # Fallback si no hay suficientes números filtrados
                if len(numeric_amounts) >= 2:
                    last_two = numeric_amounts[-2:]
                    potential_amount = last_two[0]
                    saldo = last_two[1]
                    cargo_amount = potential_amount  # Asumir gasto por defecto

        return cargo_amount, abono_amount, saldo

    def _build_complete_description(self, lines: List[str], reference: str) -> str:
        """Build complete description from all lines, excluding date, reference and final amounts"""
        if not lines:
            return "Sin descripción"

        # Remover fecha y referencia de la primera línea
        first_line = lines[0]
        desc_parts = []

        # Extraer la parte descriptiva de la primera línea (después de fecha + referencia)
        first_desc = re.sub(r'^JUL\.\s*\d{2}\s+\d{8,}\s*', '', first_line).strip()
        if first_desc:
            desc_parts.append(first_desc)

        # Agregar líneas intermedias (descripción completa)
        for line in lines[1:-1]:  # Excluir primera y última línea
            clean_line = line.strip()
            if clean_line and not re.match(r'^\d+(?:,\d{3})*\.?\d*\s*$', clean_line):
                desc_parts.append(clean_line)

        # Procesar última línea (podría contener descripción + montos)
        if len(lines) > 1:
            last_line = lines[-1].strip()
            # Remover los montos finales pero mantener descripción
            last_desc = re.sub(r'\d+(?:,\d{3})*\.?\d*\s+\d+(?:,\d{3})*\.?\d*\s*$', '', last_line)
            last_desc = re.sub(r'\d+(?:,\d{3})*\.?\d*\s*$', '', last_desc).strip()
            if last_desc:
                desc_parts.append(last_desc)

        # Combinar todas las partes
        complete_description = " ".join(desc_parts).strip()

        # Limpiar espacios extra
        complete_description = re.sub(r'\s+', ' ', complete_description)

        return complete_description if complete_description else "Sin descripción"

    def _classify_movement(self, description: str, amount: float) -> MovementKind:
        """Classify movement based purely on amount (CARGO/ABONO)"""
        # Clasificación simple basada únicamente en el monto:
        # - Monto positivo = ABONO (ingreso)
        # - Monto negativo = CARGO (gasto)

        if amount > 0:
            return MovementKind.INGRESO  # ABONO
        else:
            return MovementKind.GASTO    # CARGO

    def _calculate_summary(self, transactions: List[BankTransaction]) -> Dict[str, Any]:
        """Calculate summary statistics"""
        if not transactions:
            return {
                "total_transactions": 0,
                "total_credits": 0.0,
                "total_debits": 0.0,
                "period_start": None,
                "period_end": None,
                "opening_balance": 0.0,
                "closing_balance": 0.0,
                "total_incomes": 0.0,
                "total_expenses": 0.0,
                "total_transfers": 0.0,
            }

        credits_total = sum(t.amount for t in transactions if t.amount > 0)
        debits_total = sum(abs(t.amount) for t in transactions if t.amount < 0)
        incomes_total = sum(t.amount for t in transactions if t.movement_kind == MovementKind.INGRESO and t.amount > 0)
        expenses_total = sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.GASTO and t.amount < 0)
        transfers_total = sum(abs(t.amount) for t in transactions if t.movement_kind == MovementKind.TRANSFERENCIA)

        dates = [t.date for t in transactions]

        return {
            "total_transactions": len(transactions),
            "total_credits": round(credits_total, 2),
            "total_debits": round(debits_total, 2),
            "period_start": min(dates) if dates else None,
            "period_end": max(dates) if dates else None,
            "opening_balance": 0.0,
            "closing_balance": 0.0,
            "total_incomes": round(incomes_total, 2),
            "total_expenses": round(expenses_total, 2),
            "total_transfers": round(transfers_total, 2),
        }


def parse_with_cargos_abonos(file_path: str, account_id: int, user_id: int, tenant_id: int) -> Tuple[List[BankTransaction], Dict[str, Any]]:
    """Main function to parse PDF using CARGOS/ABONOS structure"""
    parser = CargosAbonosParser()
    text = parser.extract_text(file_path)
    return parser.parse_transactions(text, account_id, user_id, tenant_id)


if __name__ == "__main__":
    # Test the parser
    import sys
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        transactions, summary = parse_with_cargos_abonos(pdf_path, 1, 1, 1)
        print(f"✅ Extracted {len(transactions)} transactions using CARGOS/ABONOS structure")
        for txn in transactions[:10]:
            print(f"  {txn.date} | {txn.movement_kind.value} | ${txn.amount} | {txn.description[:60]}...")
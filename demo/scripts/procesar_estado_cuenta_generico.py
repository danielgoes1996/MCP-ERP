#!/usr/bin/env python3
"""
Template genérico para procesar estados de cuenta y conciliar con CFDIs
Funciona para cualquier mes/año y tipo de estado de cuenta (banco o tarjeta)

USO:
    python3 procesar_estado_cuenta_generico.py --tipo banco --mes 2 --año 2025 --archivo "/path/to/estado.pdf"
    python3 procesar_estado_cuenta_generico.py --tipo amex --mes 2 --año 2025 --archivo "/path/to/amex.pdf"
"""

import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# Importar configuración centralizada
sys.path.append('/Users/danielgoes96/Desktop/mcp-server')
from core.shared.db_config import (
    get_connection,
    safe_update_invoice_reconciliation,
    safe_update_bank_reconciliation,
    get_reconciliation_summary,
    truncate_field
)


class EstadoCuentaProcesador:
    """Procesador genérico de estados de cuenta"""

    def __init__(self, tipo: str, mes: int, año: int):
        """
        Args:
            tipo: 'banco' o 'amex'
            mes: Mes (1-12)
            año: Año (2025, etc)
        """
        self.tipo = tipo
        self.mes = mes
        self.año = año
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = get_connection()
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.cursor.close()
            self.conn.close()

    def obtener_cfdis_pendientes(self) -> List[Dict]:
        """Obtener CFDIs pendientes del mes"""
        self.cursor.execute("""
            SELECT
                id,
                nombre_emisor,
                rfc_emisor,
                total,
                fecha_emision,
                metodo_pago,
                forma_pago
            FROM expense_invoices
            WHERE EXTRACT(YEAR FROM fecha_emision) = %s
            AND EXTRACT(MONTH FROM fecha_emision) = %s
            AND tipo_comprobante = 'I'
            AND linked_expense_id IS NULL
            ORDER BY total DESC
        """, (self.año, self.mes))

        return [
            {
                'id': row[0],
                'nombre_emisor': row[1],
                'rfc_emisor': row[2],
                'total': float(row[3]),
                'fecha_emision': row[4],
                'metodo_pago': row[5],
                'forma_pago': row[6]
            }
            for row in self.cursor.fetchall()
        ]

    def buscar_matches_automaticos(
        self,
        transacciones: List[Dict],
        tolerancia: float = 0.5
    ) -> List[Dict]:
        """
        Buscar matches automáticos entre transacciones y CFDIs

        Args:
            transacciones: Lista de transacciones del estado de cuenta
            tolerancia: Tolerancia de diferencia en pesos (default: 50 centavos)

        Returns:
            Lista de matches encontrados
        """
        cfdis_pendientes = self.obtener_cfdis_pendientes()
        matches = []

        for tx in transacciones:
            tx_monto = abs(tx['monto'])

            for cfdi in cfdis_pendientes:
                diferencia = abs(tx_monto - cfdi['total'])

                if diferencia <= tolerancia:
                    matches.append({
                        'tx': tx,
                        'cfdi': cfdi,
                        'diferencia': diferencia,
                        'confianza': 1.0 if diferencia == 0 else 0.95
                    })
                    # Remover CFDI de pendientes para evitar duplicados
                    cfdis_pendientes.remove(cfdi)
                    break

        return matches

    def aplicar_conciliacion_banco(self, matches: List[Dict]) -> int:
        """
        Aplicar conciliaciones de transacciones bancarias

        Args:
            matches: Lista de matches banco-CFDI

        Returns:
            Número de conciliaciones aplicadas
        """
        count = 0

        for match in matches:
            tx = match['tx']
            cfdi = match['cfdi']

            # Actualizar bank_transactions (si existe el TX en la BD)
            if 'bank_tx_id' in tx:
                safe_update_bank_reconciliation(
                    self.cursor,
                    tx['bank_tx_id'],
                    cfdi['id'],
                    match['confianza'],
                    'auto'
                )

            # Actualizar expense_invoices
            method = f"Banco {tx['fecha']}: {tx['descripcion'][:70]}"
            if safe_update_invoice_reconciliation(
                self.cursor,
                cfdi['id'],
                tx.get('bank_tx_id', -2),  # -2 si no está en BD
                method,
                match['confianza']
            ):
                count += 1
                print(f"✓ CFDI-{cfdi['id']} ({cfdi['nombre_emisor'][:30]}) ← TX {tx['descripcion'][:40]}")

        return count

    def aplicar_conciliacion_amex(self, matches: List[Dict]) -> int:
        """
        Aplicar conciliaciones de tarjeta AMEX

        Args:
            matches: Lista de matches AMEX-CFDI

        Returns:
            Número de conciliaciones aplicadas
        """
        count = 0

        for match in matches:
            tx = match['tx']
            cfdi = match['cfdi']

            # Marcar con -1 para AMEX
            method = f"AMEX {tx['fecha']}: {tx['descripcion'][:50]}"
            if safe_update_invoice_reconciliation(
                self.cursor,
                cfdi['id'],
                -1,  # -1 indica AMEX
                method,
                match['confianza']
            ):
                count += 1
                print(f"✓ CFDI-{cfdi['id']} ({cfdi['nombre_emisor'][:30]}) ← AMEX {tx['descripcion'][:40]}")

        return count

    def generar_reporte(self):
        """Generar reporte de conciliación"""
        summary = get_reconciliation_summary(self.año, self.mes)

        print("\n" + "=" * 80)
        print(f"RESUMEN DE CONCILIACIÓN - {self.mes:02d}/{self.año}")
        print("=" * 80)
        print(f"CFDIs conciliados: {summary['conciliados']}/{summary['total_cfdis']} ({summary['tasa_conciliacion']:.1f}%)")
        print(f"Monto conciliado: ${summary['monto_conciliado']:,.2f} de ${summary['monto_total']:,.2f}")
        print(f"Monto pendiente: ${summary['monto_pendiente']:,.2f}")
        print()
        print("DESGLOSE:")
        print(f"  Pagos banco: {summary['pagos_banco']} CFDIs - ${summary['monto_banco']:,.2f}")
        print(f"  Pagos AMEX: {summary['pagos_amex']} CFDIs - ${summary['monto_amex']:,.2f}")
        print("=" * 80)


def extraer_transacciones_banco(archivo_pdf: str) -> List[Dict]:
    """
    Extraer transacciones de estado de cuenta bancario

    Args:
        archivo_pdf: Ruta al PDF

    Returns:
        Lista de transacciones
    """
    # TODO: Implementar extracción con Gemini Vision u OCR
    # Por ahora, retornar lista vacía
    print(f"⚠️  Extracción de {archivo_pdf} no implementada aún")
    print("    Debes implementar la extracción con Gemini Vision")
    return []


def extraer_transacciones_amex(archivo_pdf: str) -> List[Dict]:
    """
    Extraer transacciones de estado de cuenta AMEX

    Args:
        archivo_pdf: Ruta al PDF

    Returns:
        Lista de transacciones
    """
    # TODO: Implementar extracción con Gemini Vision u OCR
    print(f"⚠️  Extracción de {archivo_pdf} no implementada aún")
    print("    Debes implementar la extracción con Gemini Vision")
    return []


def main():
    parser = argparse.ArgumentParser(
        description='Procesar estado de cuenta y conciliar con CFDIs'
    )
    parser.add_argument('--tipo', required=True, choices=['banco', 'amex'],
                        help='Tipo de estado de cuenta')
    parser.add_argument('--mes', required=True, type=int,
                        help='Mes (1-12)')
    parser.add_argument('--año', required=True, type=int,
                        help='Año (2025, etc)')
    parser.add_argument('--archivo', required=False,
                        help='Ruta al archivo PDF (opcional)')
    parser.add_argument('--transacciones', required=False,
                        help='Archivo JSON con transacciones ya extraídas (opcional)')

    args = parser.parse_args()

    print("=" * 80)
    print(f"PROCESANDO ESTADO DE CUENTA {args.tipo.upper()} - {args.mes:02d}/{args.año}")
    print("=" * 80)
    print()

    # Extraer o cargar transacciones
    if args.transacciones:
        import json
        with open(args.transacciones, 'r') as f:
            transacciones = json.load(f)
        print(f"✓ Cargadas {len(transacciones)} transacciones de {args.transacciones}")
    elif args.archivo:
        if args.tipo == 'banco':
            transacciones = extraer_transacciones_banco(args.archivo)
        else:
            transacciones = extraer_transacciones_amex(args.archivo)
    else:
        print("❌ Debes proporcionar --archivo o --transacciones")
        return

    if not transacciones:
        print("⚠️  No se encontraron transacciones")
        return

    # Procesar conciliación
    with EstadoCuentaProcesador(args.tipo, args.mes, args.año) as procesador:
        print(f"Buscando matches automáticos para {len(transacciones)} transacciones...")
        matches = procesador.buscar_matches_automaticos(transacciones)

        print(f"\n✓ Encontrados {len(matches)} matches")
        print()

        if matches:
            print("Aplicando conciliaciones...")
            if args.tipo == 'banco':
                count = procesador.aplicar_conciliacion_banco(matches)
            else:
                count = procesador.aplicar_conciliacion_amex(matches)

            print(f"\n✓ {count} conciliaciones aplicadas")

        procesador.generar_reporte()


if __name__ == "__main__":
    main()

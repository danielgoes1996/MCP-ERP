#!/usr/bin/env python3
"""
Generate realistic test transaction data to simulate the 90+ transactions
"""
import sqlite3
import random
from datetime import datetime, timedelta

def generate_test_transactions():
    """Generate realistic bank transactions for July 2024"""

    transactions = []

    # Base date for July 2024
    start_date = datetime(2024, 7, 1)

    # Income transactions (salaries, deposits)
    incomes = [
        ("NOMINA JULIO 2024", 25000.00, "INGRESO", "Sueldo"),
        ("DEPOSITO SPEI CLIENTE ABC", 5500.00, "INGRESO", "Ventas"),
        ("DEPOSITO SPEI CLIENTE XYZ", 3200.00, "INGRESO", "Ventas"),
        ("REEMBOLSO SEGUROS", 1200.00, "INGRESO", "Reembolso"),
        ("INTERESES GANADOS", 45.32, "INGRESO", "Intereses"),
        ("DEPOSITO EFECTIVO", 800.00, "INGRESO", "Efectivo"),
    ]

    # Expense transactions (various categories)
    expenses = [
        ("NETFLIX SUSCRIPCION", -199.00, "GASTO", "Entretenimiento"),
        ("SPOTIFY PREMIUM", -165.00, "GASTO", "Entretenimiento"),
        ("AMAZON PRIME VIDEO", -99.00, "GASTO", "Entretenimiento"),
        ("UBER EATS PEDIDO", -320.50, "GASTO", "Comida"),
        ("UBER EATS PEDIDO", -185.75, "GASTO", "Comida"),
        ("RAPPI SUPERMERCADO", -650.00, "GASTO", "Supermercado"),
        ("SORIANA SUPERMERCADO", -1250.80, "GASTO", "Supermercado"),
        ("WALMART SUPERMERCADO", -980.45, "GASTO", "Supermercado"),
        ("OXXO CONVENIENCIA", -85.50, "GASTO", "Conveniencia"),
        ("OXXO CONVENIENCIA", -125.00, "GASTO", "Conveniencia"),
        ("TELMEX INTERNET", -599.00, "GASTO", "Servicios"),
        ("CFE ELECTRICIDAD", -850.25, "GASTO", "Servicios"),
        ("IZZI TELEVISION", -499.00, "GASTO", "Servicios"),
        ("PEMEX GASOLINA", -800.00, "GASTO", "Gasolina"),
        ("SHELL GASOLINA", -750.50, "GASTO", "Gasolina"),
        ("MOBIL GASOLINA", -680.75, "GASTO", "Gasolina"),
        ("OPENAI *CHATGPT SUBSCR US", -378.85, "GASTO", "Software"),
        ("GITHUB COPILOT", -199.00, "GASTO", "Software"),
        ("ADOBE CREATIVE CLOUD", -649.00, "GASTO", "Software"),
        ("MICROSOFT OFFICE 365", -299.00, "GASTO", "Software"),
        ("FARMACIAS SIMILARES", -185.50, "GASTO", "Farmacia"),
        ("FARMACIAS DEL AHORRO", -225.75, "GASTO", "Farmacia"),
        ("STARBUCKS COFFEE", -125.00, "GASTO", "Café"),
        ("STARBUCKS COFFEE", -98.50, "GASTO", "Café"),
        ("DOMINOS PIZZA", -389.00, "GASTO", "Comida"),
        ("MCDONALDS", -145.50, "GASTO", "Comida"),
        ("SUBURBIA ROPA", -1250.00, "GASTO", "Ropa"),
        ("LIVERPOOL DEPARTAMENTAL", -2100.00, "GASTO", "Departamental"),
        ("BEST BUY ELECTRONICA", -3500.00, "GASTO", "Electrónicos"),
        ("AMAZON MX COMPRAS", -890.75, "GASTO", "Compras Online"),
        ("AMAZON MX COMPRAS", -1250.00, "GASTO", "Compras Online"),
        ("MERCADO LIBRE", -450.00, "GASTO", "Compras Online"),
        ("COMISION POR MOVIMIENTOS INBURED", -13.50, "GASTO", "Comisiones"),
        ("IVA COMISION POR MOVIMIENTOS", -2.16, "GASTO", "Comisiones"),
        ("COMISION TRANSFERENCIA SPEI", -8.50, "GASTO", "Comisiones"),
        ("CONSULTA SALDO CAJERO", -12.00, "GASTO", "Comisiones"),
    ]

    # Transfer transactions
    transfers = [
        ("TRASPASO SPEI INBURED DANIEL GOMEZ", -5000.00, "TRANSFERENCIA", "Transferencia"),
        ("TRASPASO ENTRE CUENTAS AHORRO", -3000.00, "TRANSFERENCIA", "Transferencia"),
        ("TRASPASO SPEI CUENTA NOMINA", -2500.00, "TRANSFERENCIA", "Transferencia"),
        ("DEQSA LAB TRANSFERENCIA", -1800.00, "TRANSFERENCIA", "Transferencia"),
        ("TRANSFERENCIA SPEI FAMILIAR", -1500.00, "TRANSFERENCIA", "Transferencia"),
        ("traspaso entre cuentas", -502.00, "TRANSFERENCIA", "Transferencia"),
    ]

    # Generate transactions throughout July
    current_balance = 25000.00  # Starting balance
    ref_counter = 200000

    # Add all transactions with random dates in July
    for desc, amount, kind, category in incomes + expenses + transfers:
        # Random day in July
        day = random.randint(1, 31)
        date = datetime(2024, 7, day)

        current_balance += amount
        ref_counter += 1

        transaction = {
            'account_id': 5,
            'user_id': 9,
            'tenant_id': 3,
            'date': date.strftime('%Y-%m-%d'),
            'description': desc,
            'amount': amount,
            'transaction_type': 'CREDIT' if amount > 0 else 'DEBIT',
            'category': category,
            'confidence': round(random.uniform(0.8, 0.95), 2),
            'raw_data': 'generated_test_data',
            'movement_kind': kind,
            'reference': str(ref_counter),
            'balance_after': round(current_balance, 2)
        }
        transactions.append(transaction)

    # Add some duplicates/variations to reach ~90 transactions
    extra_transactions = [
        ("UBER VIAJE", -65.50, "GASTO", "Transporte"),
        ("UBER VIAJE", -89.75, "GASTO", "Transporte"),
        ("DIDI VIAJE", -45.25, "GASTO", "Transporte"),
        ("PEMEX GASOLINA", -725.00, "GASTO", "Gasolina"),
        ("SEVEN ELEVEN", -95.50, "GASTO", "Conveniencia"),
        ("CIRCLE K", -110.25, "GASTO", "Conveniencia"),
        ("FARMACIAS GUADALAJARA", -165.75, "GASTO", "Farmacia"),
        ("COPPEL TIENDA", -850.00, "GASTO", "Departamental"),
        ("ELEKTRA", -1200.00, "GASTO", "Electrónicos"),
        ("CHEDRAUI", -750.50, "GASTO", "Supermercado"),
        ("COSTCO WHOLESALE", -2100.00, "GASTO", "Supermercado"),
        ("SAMS CLUB", -1850.75, "GASTO", "Supermercado"),
        ("HOME DEPOT", -950.00, "GASTO", "Hogar"),
        ("OFFICE DEPOT", -320.50, "GASTO", "Oficina"),
        ("SANBORNS", -180.00, "GASTO", "Varios"),
        ("CINEPOLIS", -250.00, "GASTO", "Entretenimiento"),
        ("CINEMEX", -280.00, "GASTO", "Entretenimiento"),
        ("PAYPAL *COURSERA", -299.00, "GASTO", "Educación"),
        ("GOOGLE CLOUD PLATFORM", -125.50, "GASTO", "Software"),
        ("ZOOM VIDEOCONFERENCING", -149.99, "GASTO", "Software"),
    ]

    for desc, amount, kind, category in extra_transactions:
        day = random.randint(1, 31)
        date = datetime(2024, 7, day)
        current_balance += amount
        ref_counter += 1

        transaction = {
            'account_id': 5,
            'user_id': 9,
            'tenant_id': 3,
            'date': date.strftime('%Y-%m-%d'),
            'description': desc,
            'amount': amount,
            'transaction_type': 'CREDIT' if amount > 0 else 'DEBIT',
            'category': category,
            'confidence': round(random.uniform(0.8, 0.95), 2),
            'raw_data': 'generated_test_data',
            'movement_kind': kind,
            'reference': str(ref_counter),
            'balance_after': round(current_balance, 2)
        }
        transactions.append(transaction)

    # Sort by date
    transactions.sort(key=lambda x: x['date'])

    return transactions

def insert_transactions(transactions):
    """Insert transactions into database"""

    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    # Clear existing test data
    cursor.execute("DELETE FROM bank_movements WHERE account_id = 5 AND user_id = 9")

    # Insert all transactions
    for txn in transactions:
        cursor.execute("""
            INSERT INTO bank_movements
            (account_id, user_id, tenant_id, date, description, amount, transaction_type,
             category, confidence, raw_data, movement_kind, reference, balance_after)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn['account_id'], txn['user_id'], txn['tenant_id'], txn['date'],
            txn['description'], txn['amount'], txn['transaction_type'],
            txn['category'], txn['confidence'], txn['raw_data'],
            txn['movement_kind'], txn['reference'], txn['balance_after']
        ))

    conn.commit()

    # Show summary
    cursor.execute("""
        SELECT
            movement_kind,
            COUNT(*) as count,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_positive,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_negative
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        GROUP BY movement_kind
    """)

    results = cursor.fetchall()

    print("📊 Summary of generated transactions:")
    total_count = 0
    for kind, count, positive, negative in results:
        total = positive + negative
        print(f"  {kind}: {count} transactions, ${total:,.2f}")
        total_count += count

    print(f"\n✅ Total: {total_count} transactions generated")

    conn.close()

def main():
    print("🎯 Generating realistic test transaction data...")

    transactions = generate_test_transactions()
    print(f"📝 Generated {len(transactions)} transactions")

    insert_transactions(transactions)
    print("✅ Test data inserted successfully!")

if __name__ == "__main__":
    main()
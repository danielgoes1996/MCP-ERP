#!/usr/bin/env python3
"""
Mejorar descripciones existentes usando toda la información disponible
Especialmente para domiciliaciones con RFC y razón social completa
"""
import sqlite3
import re

def extract_enhanced_info(description: str) -> str:
    """Extraer y mejorar información completa de la descripción"""
    desc = description.strip().upper()

    # Patrones específicos para domiciliaciones con RFC
    if 'DOMICILIACION' in desc:
        # TELMEX con RFC
        if 'TME840315KT6' in desc and 'TELEFONOS DE MEXICO' in desc:
            return 'Domiciliación TELMEX (TME840315KT6) - Teléfonos de México S.A.B. de C.V.'

        # CFE con posible RFC
        if 'CFE' in desc:
            return 'Domiciliación CFE - Comisión Federal de Electricidad'

        # SKY con info completa
        if 'SKY' in desc:
            return 'Domiciliación SKY - Servicios de Televisión Digital'

        # Genérico mejorado
        if 'TELMEX' in desc:
            return 'Domiciliación TELMEX - Servicios Telefónicos'

    # SPEI con información completa
    if 'SPEI' in desc:
        if 'DEPOSITO' in desc:
            return 'Depósito SPEI - Transferencia Bancaria Recibida'
        elif 'TRASPASO' in desc:
            return 'Traspaso SPEI - Transferencia Bancaria Enviada'
        else:
            return 'Transferencia SPEI - Operación Bancaria'

    # Servicios específicos con detalles
    if 'OPENAI' in desc:
        if 'CHATGPT' in desc:
            return 'OpenAI ChatGPT Subscription - Servicio de Inteligencia Artificial'
        return 'OpenAI - Servicios de Inteligencia Artificial'

    if 'APPLE.COM' in desc:
        return 'Apple Services - Servicios Digitales Apple'

    if 'OFFICE DEPOT' in desc:
        return 'Office Depot - Suministros de Oficina y Papelería'

    if 'WALMART' in desc:
        return 'Walmart - Supermercado y Compras Generales'

    if 'COSTCO' in desc:
        return 'Costco - Membresía y Compras al Mayoreo'

    # Gasolineras con tipo
    if 'PEMEX' in desc:
        return 'Gasolinera PEMEX - Combustible y Servicios'

    if 'SHELL' in desc:
        return 'Gasolinera Shell - Combustible Premium'

    # Comisiones bancarias
    if 'COMISION' in desc:
        if 'MANEJO' in desc:
            return 'Comisión por Manejo de Cuenta - Servicio Bancario'
        elif 'IVA' in desc:
            return 'Comisión Bancaria + IVA - Servicios Bancarios'
        return 'Comisión Bancaria - Servicios del Banco'

    # Entretenimiento
    if 'NETFLIX' in desc:
        return 'Netflix - Suscripción Streaming'

    if 'SPOTIFY' in desc:
        return 'Spotify - Suscripción Música Streaming'

    if 'AMAZON' in desc:
        return 'Amazon - Compras en Línea o Servicios'

    # Si no hay mejora específica, mantener original pero capitalizado
    return desc.title()

def categorize_enhanced(description: str) -> str:
    """Categorizar basado en la descripción mejorada"""
    desc_upper = description.upper()

    # Servicios Públicos
    if any(word in desc_upper for word in ['CFE', 'COMISIÓN FEDERAL', 'ELECTRICIDAD']):
        return 'Servicios Públicos'

    # Telecomunicaciones
    if any(word in desc_upper for word in ['TELMEX', 'TELÉFONOS DE MÉXICO', 'SKY', 'TELCEL', 'MOVISTAR']):
        return 'Telecomunicaciones'

    # Tecnología
    if any(word in desc_upper for word in ['OPENAI', 'CHATGPT', 'APPLE', 'MICROSOFT', 'GOOGLE']):
        return 'Tecnología'

    # Combustible
    if any(word in desc_upper for word in ['PEMEX', 'GASOLINERA', 'SHELL', 'COMBUSTIBLE']):
        return 'Combustible'

    # Alimentación
    if any(word in desc_upper for word in ['WALMART', 'COSTCO', 'SUPERMERCADO', 'RESTAURANT']):
        return 'Alimentación'

    # Oficina
    if any(word in desc_upper for word in ['OFFICE DEPOT', 'PAPELERÍA', 'SUMINISTROS']):
        return 'Oficina'

    # Transferencias
    if any(word in desc_upper for word in ['SPEI', 'TRANSFERENCIA', 'TRASPASO', 'DEPÓSITO']):
        return 'Transferencias'

    # Servicios Bancarios
    if any(word in desc_upper for word in ['COMISIÓN', 'IVA', 'MANEJO', 'SERVICIO BANCARIO']):
        return 'Servicios Bancarios'

    # Entretenimiento
    if any(word in desc_upper for word in ['NETFLIX', 'SPOTIFY', 'AMAZON', 'STREAMING']):
        return 'Entretenimiento'

    return 'Otros'

def main():
    conn = sqlite3.connect('unified_mcp_system.db')
    cursor = conn.cursor()

    print("🔄 Mejorando descripciones con información completa...")

    # Obtener transacciones con descripciones básicas
    cursor.execute("""
        SELECT id, description, category
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        AND (description LIKE '%DOMICILIACION%'
             OR description LIKE '%SPEI%'
             OR description LIKE '%OPENAI%'
             OR description LIKE '%OFFICE DEPOT%'
             OR description IS NULL
             OR description = ''
             OR LENGTH(description) < 20)
        ORDER BY id
    """)

    transactions = cursor.fetchall()
    print(f"📊 Encontradas {len(transactions)} transacciones para mejorar")

    improved_count = 0

    for txn_id, current_desc, current_category in transactions:
        if current_desc:
            # Mejorar descripción
            enhanced_desc = extract_enhanced_info(current_desc)

            # Mejorar categoría
            enhanced_category = categorize_enhanced(enhanced_desc)

            # Solo actualizar si hay mejora real
            if enhanced_desc != current_desc.strip() or enhanced_category != current_category:
                cursor.execute("""
                    UPDATE bank_movements
                    SET description = ?, category = ?
                    WHERE id = ?
                """, (enhanced_desc, enhanced_category, txn_id))

                improved_count += 1
                print(f"  ✅ ID {txn_id}: '{current_desc[:40]}...' → '{enhanced_desc[:40]}...'")

    conn.commit()
    print(f"\n🎉 Mejoradas {improved_count} descripciones con información completa!")

    # Mostrar estadísticas finales
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9 AND category IS NOT NULL
        GROUP BY category
        ORDER BY count DESC
    """)

    categories = cursor.fetchall()
    print("\n📈 Distribución de categorías actualizada:")
    for category, count in categories:
        print(f"  {category}: {count} transacciones")

    # Mostrar algunos ejemplos de mejoras
    cursor.execute("""
        SELECT description, category
        FROM bank_movements
        WHERE account_id = 5 AND user_id = 9
        AND (description LIKE '%TELMEX%' OR description LIKE '%OpenAI%' OR description LIKE '%Office Depot%')
        LIMIT 5
    """)

    examples = cursor.fetchall()
    print("\n💡 Ejemplos de descripciones mejoradas:")
    for desc, cat in examples:
        print(f"  📝 {desc} → {cat}")

    conn.close()

if __name__ == "__main__":
    main()
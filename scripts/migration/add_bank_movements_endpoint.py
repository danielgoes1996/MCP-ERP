#!/usr/bin/env python3
"""
Script para agregar el endpoint de bank movements por cuenta al main.py
"""

def add_endpoint_to_main():
    # Leer el archivo main.py
    with open('main.py', 'r') as f:
        content = f.read()

    # Buscar el punto donde insertar el nuevo endpoint
    insertion_point = 'return BankMovementResponse(**movement)'

    if insertion_point not in content:
        print("❌ No se encontró el punto de inserción")
        return

    # Nuevo endpoint
    new_endpoint = '''
@app.get("/bank-movements/account/{account_id}")
async def get_bank_movements_by_account(
    account_id: int,
    current_user: User = Depends(get_current_active_user),
    tenancy: TenancyContext = Depends(get_tenancy_context)
) -> List[Dict[str, Any]]:
    """Get all bank movements for a specific account."""
    try:
        # Get database connection
        from core.unified_db_adapter import get_unified_adapter
        db = get_unified_adapter()

        # Query bank movements for the account
        query = """
        SELECT
            bm.id,
            bm.date,
            bm.description,
            bm.amount,
            bm.transaction_type,
            bm.raw_data,
            bm.statement_id,
            bm.created_at
        FROM bank_movements bm
        WHERE bm.account_id = ? AND bm.user_id = ? AND bm.tenant_id = ?
        ORDER BY bm.date DESC, bm.created_at DESC
        """

        movements = db.fetch_all(query, (account_id, current_user.id, tenancy.tenant_id))

        # Convert to list of dictionaries
        result = []
        for movement in movements:
            result.append({
                'id': movement[0],
                'date': movement[1],
                'description': movement[2],
                'amount': movement[3],
                'transaction_type': movement[4],
                'raw_data': movement[5],
                'statement_id': movement[6],
                'created_at': movement[7]
            })

        return result

    except Exception as e:
        logger.exception(f"Error fetching bank movements for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching transactions")
'''

    # Insertar el endpoint después del punto de inserción
    replacement = insertion_point + new_endpoint
    new_content = content.replace(insertion_point, replacement)

    # Escribir el archivo modificado
    with open('main.py', 'w') as f:
        f.write(new_content)

    print("✅ Endpoint agregado exitosamente a main.py")

if __name__ == "__main__":
    add_endpoint_to_main()
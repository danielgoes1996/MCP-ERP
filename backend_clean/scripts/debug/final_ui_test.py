#!/usr/bin/env python3
"""
Prueba final: Simular exactamente lo que ve el usuario en el navegador
"""
import requests

def simulate_user_experience():
    print("🎯 SIMULACIÓN EXACTA DE LA EXPERIENCIA DEL USUARIO")
    print("=" * 60)

    session = requests.Session()

    # 1. Usuario abre la página
    print("1️⃣ Usuario abre http://localhost:8001/payment-accounts.html")
    try:
        html_response = session.get("http://localhost:8004/payment-accounts.html")
        if html_response.status_code == 200:
            title_start = html_response.text.find("<title>") + 7
            title_end = html_response.text.find("</title>")
            title = html_response.text[title_start:title_end]
            print(f"   ✅ Página cargada. Título: {title}")
        else:
            print(f"   ❌ Error cargando página: {html_response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # 2. Usuario hace login
    print("\n2️⃣ Usuario hace login con dgomezes96@gmail.com")
    try:
        login_response = session.post("http://localhost:8004/auth/login", json={
            "email": "dgomezes96@gmail.com",
            "password": "temp123"
        })

        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data.get("access_token")
            print(f"   ✅ Login exitoso")
        else:
            print(f"   ❌ Error login: {login_response.status_code} - {login_response.text}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # 3. Usuario hace clic en AMEX Gold Card
    print("\n3️⃣ Usuario hace clic en cuenta AMEX Gold Card (ID: 5)")
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        api_response = session.get("http://localhost:8004/bank-movements/account/5", headers=headers)

        if api_response.status_code == 200:
            transactions = api_response.json()
            print(f"   ✅ API devolvió {len(transactions)} transacciones")

            # 4. Mostrar exactamente lo que ve el usuario
            print(f"\n📊 LO QUE VE EL USUARIO EN LA TABLA:")
            print(f"{'#':<3} {'Fecha':<12} {'Descripción':<50} {'Tipo':<12} {'Monto':<12} {'Saldo':<12}")
            print("-" * 105)

            for i, txn in enumerate(transactions[:10]):
                # Simular getMovementKind del frontend
                movement_kind = txn.get('movement_kind', '')
                if movement_kind:
                    kind_map = {
                        'ingreso': 'Ingreso',
                        'gasto': 'Gasto',
                        'transferencia': 'Transferencia',
                        'balance': 'Balance'
                    }
                    display_kind = kind_map.get(movement_kind.lower(), movement_kind)
                else:
                    display_kind = 'N/A'

                date = txn.get('date', 'N/A')
                desc = txn.get('description', 'N/A')[:48]
                amount = txn.get('amount', 0)
                balance = txn.get('balance_after', 'N/A')

                print(f"{i+1:<3} {date:<12} {desc:<50} {display_kind:<12} ${amount:<11.2f} ${balance}")

            # Verificaciones críticas
            print(f"\n🔍 VERIFICACIONES CRÍTICAS:")

            # Balance Inicial
            balance_inicial = None
            for i, txn in enumerate(transactions):
                if 'Balance Inicial' in txn.get('description', ''):
                    balance_inicial = txn
                    balance_position = i + 1
                    break

            if balance_inicial:
                print(f"   ✅ Balance Inicial encontrado en posición {balance_position}")
                print(f"   📋 Descripción: {balance_inicial.get('description')}")
                print(f"   💰 Saldo: ${balance_inicial.get('balance_after')}")
                print(f"   🏷️ movement_kind: {balance_inicial.get('movement_kind')}")
            else:
                print(f"   ❌ Balance Inicial NO encontrado")

            # Orden cronológico
            dates = [txn.get('date') for txn in transactions]
            is_chronological = all(dates[i] <= dates[i+1] for i in range(len(dates)-1))
            print(f"   📅 Orden cronológico: {'✅ Correcto' if is_chronological else '❌ Incorrecto'}")
            print(f"   📅 Primera fecha: {dates[0] if dates else 'N/A'}")
            print(f"   📅 Última fecha: {dates[-1] if dates else 'N/A'}")

        else:
            print(f"   ❌ Error API: {api_response.status_code} - {api_response.text}")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    print(f"\n🎯 CONCLUSIÓN:")
    print(f"Si el Balance Inicial no aparece en el UI pero sí en esta prueba,")
    print(f"entonces el problema está en el JavaScript del frontend (filtros o caché).")
    print(f"\nPara verificar abre: http://localhost:8001/test-ui-debug.html")

if __name__ == "__main__":
    simulate_user_experience()
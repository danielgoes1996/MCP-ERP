#!/usr/bin/env python3
"""Borrar facturas de carreta_verde usando el API."""

import requests
import json

company_id = "carreta_verde"
base_url = "http://localhost:8001/universal-invoice"

# 1. Obtener todas las sessions
print(f"🔍 Obteniendo facturas de {company_id}...")
response = requests.get(f"{base_url}/sessions/company/{company_id}?limit=1000")

if response.status_code != 200:
    print(f"❌ Error obteniendo facturas: {response.status_code}")
    print(response.text)
    exit(1)

data = response.json()
sessions = data.get("sessions", [])

print(f"✅ Encontradas {len(sessions)} facturas")

if len(sessions) == 0:
    print("No hay nada que borrar")
    exit(0)

# Mostrar las primeras 5 para confirmar
print("\nPrimeras facturas:")
for i, session in enumerate(sessions[:5]):
    print(f"  {i+1}. {session.get('original_filename')} - {session.get('session_id')}")

# 2. Borrar cada session
print(f"\n🗑️  Borrando {len(sessions)} facturas...")
deleted_count = 0
for session in sessions:
    session_id = session.get("session_id") or session.get("id")
    if not session_id:
        continue

    try:
        del_response = requests.delete(f"{base_url}/sessions/{session_id}")
        if del_response.status_code in [200, 204]:
            deleted_count += 1
        else:
            print(f"  ⚠️  Error borrando {session_id}: {del_response.status_code}")
    except Exception as e:
        print(f"  ⚠️  Excepción borrando {session_id}: {e}")

print(f"\n✅ COMPLETADO: {deleted_count} facturas borradas de {len(sessions)}")

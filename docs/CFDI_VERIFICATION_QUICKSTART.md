# CFDI Verification - Quick Start Guide

## What is CFDI Verification?

CFDI verification checks if a Mexican electronic invoice (CFDI) is valid according to the SAT (Mexican Tax Authority). This is critical for tax compliance because:

- Only **vigente** (valid) CFDIs can be used for tax deductions
- Cancelled or substituted CFDIs are not valid for deductions
- Using invalid CFDIs can result in tax penalties

## Quick Test

```bash
# 1. Start the API server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 2. Run the test script
python3 test_cfdi_verification.py
```

## API Endpoints

### 1. Verify Single CFDI
```bash
POST /cfdi/{uuid}/verificar
```

**Example**:
```bash
curl -X POST "http://localhost:8000/cfdi/F35DD2D6-1EA3-11F0-B58E-35B102CD55A3/verificar"
```

### 2. Batch Verification
```bash
POST /cfdi/verificar-batch
```

**Example**:
```bash
curl -X POST "http://localhost:8000/cfdi/verificar-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 2,
    "limit": 100,
    "only_unverified": true
  }'
```

### 3. Get Statistics
```bash
GET /cfdi/stats?company_id={id}
```

**Example**:
```bash
curl "http://localhost:8000/cfdi/stats?company_id=2"
```

### 4. List Invalid CFDIs
```bash
GET /cfdi/invalidos?company_id={id}&limit={n}
```

**Example**:
```bash
curl "http://localhost:8000/cfdi/invalidos?company_id=2&limit=10"
```

### 5. List Unverified CFDIs
```bash
GET /cfdi/sin-verificar?company_id={id}&limit={n}
```

**Example**:
```bash
curl "http://localhost:8000/cfdi/sin-verificar?company_id=2&limit=10"
```

## CFDI Status Types

| Status | Display Name | Valid for Tax? | Description |
|--------|--------------|----------------|-------------|
| `vigente` | Vigente | ✅ YES | Valid CFDI, can be used for deduction |
| `cancelado` | Cancelado | ❌ NO | Cancelled by issuer |
| `sustituido` | Sustituido | ❌ NO | Replaced by another CFDI |
| `por_cancelar` | Por Cancelar | ❌ NO | Cancellation pending |
| `no_encontrado` | No Encontrado | ❌ NO | Not found in SAT (possible fraud) |
| `error` | Error | ❌ NO | Verification error |

## Current Results (Company ID 2)

```
Total CFDIs: 228
├── Vigentes:       88 (38.6%) ✅ Valid
├── Cancelados:     34 (14.9%) ❌ Invalid
├── Sustituidos:    12 (5.3%)  ❌ Invalid
├── Por Cancelar:   12 (5.3%)  ❌ Invalid
└── No Encontrados: 82 (36.0%) ❌ Invalid (RISK!)

Valid for Tax Deduction: 88 CFDIs (38.6%)
Invalid/Risky: 140 CFDIs (61.4%)
```

## Database Queries

### Get all invalid CFDIs
```sql
SELECT * FROM vw_cfdis_invalidos
WHERE company_id = 2;
```

### Get verification statistics
```sql
SELECT * FROM get_cfdi_verification_stats(2);
```

### Find CFDIs not verified recently
```sql
SELECT * FROM vw_cfdis_sin_verificar
WHERE company_id = 2
LIMIT 100;
```

## Python Usage

```python
from core.sat.sat_cfdi_verifier import SATCFDIVerifier

# Initialize verifier (MOCK mode)
verifier = SATCFDIVerifier(use_mock=True)

# Verify single CFDI
success, status_info, error = verifier.check_cfdi_status(
    uuid="F35DD2D6-1EA3-11F0-B58E-35B102CD55A3",
    rfc_emisor="AAA010101AAA",
    rfc_receptor="BBB020202BBB",
    total=1000.00
)

if success:
    print(f"Status: {status_info['status']}")
    print(f"Valid for deduction: {status_info['status'] == 'vigente'}")
```

## Switching to Production Mode

**Current Mode**: MOCK (simulated responses)

**To enable real SAT verification**:

1. Edit `api/cfdi_api.py`:
```python
# Change this line:
verifier = SATCFDIVerifier(use_mock=True)

# To:
verifier = SATCFDIVerifier(use_mock=False)
```

2. Install e.firma certificates in database

3. Restart API server

## Files Reference

| File | Purpose |
|------|---------|
| `core/sat/sat_cfdi_verifier.py` | SOAP client for SAT service |
| `migrations/005_add_cfdi_verification.sql` | Database schema |
| `api/cfdi_api.py` | REST API endpoints |
| `test_cfdi_verification.py` | Test script |
| `docs/CFDI_VERIFICATION_COMPLETE.md` | Full documentation |

## Support

For detailed documentation, see: `docs/CFDI_VERIFICATION_COMPLETE.md`

## Status

✅ **System Operational**
- Mode: MOCK
- CFDIs Verified: 228/228 (100%)
- Success Rate: 100%
- Last Verification: 2025-11-09

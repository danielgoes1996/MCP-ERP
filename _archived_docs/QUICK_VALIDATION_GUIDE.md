# Quick Validation Guide - New XML Parser

**Date**: 2025-01-13
**Status**: READY FOR TESTING
**Duration**: 15-30 minutes

---

## Current Status

- **Backfill Complete**: 209/228 invoices classified (91.67%)
- **New Parser Deployed**: XML deterministic parser (replacing LLM)
- **Test User Ready**: test@contaflow.com (email verified)
- **Servers Running**: Backend (8001) and Frontend (3000)

---

## Test Credentials

```
Email: test@contaflow.com
Password: test123
Company: contaflow
```

---

## Step-by-Step Validation

### 1. Open Monitoring Terminal

```bash
# Terminal 1: Watch for parsing activity
tail -f logs/app.log | grep -E "(XML parsed|Classified|Error|DEPRECATED)"
```

### 2. Login to Application

- Navigate to: http://localhost:3000
- Login with credentials above
- Verify you can access the dashboard

### 3. Upload Test Invoice

**Find a test CFDI XML file**:
```bash
# List available invoices in uploads
ls -lh uploads/invoices/*.xml | head -3

# Or use one from ContaFlow's existing invoices
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT id, file_path FROM expense_invoices WHERE tenant_id = 2 LIMIT 3;"
```

**Upload via UI**:
- Go to Expenses or Invoice section
- Upload a CFDI XML file
- Wait for processing to complete

### 4. Verify in Logs

You should see:
```
✅ XML parsed successfully with deterministic parser: UUID=..., Total=...
✅ Classified successfully: SAT=601.84, confidence=85%
```

You should NOT see:
```
❌ DEPRECATED: extract_cfdi_metadata() called
❌ Error parsing CFDI XML
❌ Could not determine end of JSON document
```

### 5. Verify in Database

```bash
# Check latest invoice
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT id, uuid, total, accounting_classification
   FROM expense_invoices
   WHERE tenant_id = 2
   ORDER BY created_at DESC
   LIMIT 1;"
```

Expected:
- `uuid` should be populated
- `total` should match invoice
- `accounting_classification` should have SAT code

---

## Success Criteria

- [ ] Login successful with test user
- [ ] Invoice uploaded without errors
- [ ] Processing time < 5 seconds
- [ ] Logs show "XML parsed successfully with deterministic parser"
- [ ] NO deprecation warnings in logs
- [ ] Invoice appears in database with classification
- [ ] SAT account code assigned (likely 601.84)

---

## If Something Goes Wrong

### Issue: "DEPRECATED: extract_cfdi_metadata() called"
**Cause**: Code is still using old LLM parser
**Fix**: Check which endpoint is being called, verify universal_invoice_engine_system.py changes

### Issue: "Error parsing CFDI XML"
**Cause**: New parser has issues with specific XML format
**Fix**: Capture the problematic XML file, check CFDI version (3.3 vs 4.0)

### Issue: Processing takes > 10 seconds
**Cause**: Possible network issue or rate limiting on classification API
**Fix**: Check logs for which step is slow (parsing vs classification)

### Issue: No classification assigned
**Cause**: Classification API rate limit or conceptos extraction issue
**Fix**: This is expected occasionally, focus on whether parsing succeeds

---

## Rollback Plan

If critical issues found:

```bash
# Rollback universal_invoice_engine_system.py
git checkout HEAD~1 core/expenses/invoices/universal_invoice_engine_system.py
git commit -m "Rollback: XML parser causing issues"

# Restart backend
lsof -ti:8001 | xargs kill -9 && sleep 2 && python3 main.py
```

---

## After Successful Validation

Update [VALIDATION_CHECKLIST.md](VALIDATION_CHECKLIST.md):
- [ ] Mark "Test with Facturas Nuevas" as completed
- [ ] Note any issues encountered
- [ ] Proceed with 48-hour monitoring phase

---

## Next Steps (After 48 Hours)

If validation successful:
1. Retry invoice 814 (rate limit failure)
2. Begin refactoring from [POST_BACKFILL_ACTION_PLAN.md](POST_BACKFILL_ACTION_PLAN.md)
3. Create regression tests

---

## Commands Reference

**Monitor logs in real-time**:
```bash
tail -f logs/app.log | grep -i "invoice"
```

**Count today's classifications**:
```bash
docker exec mcp-postgres psql -U mcp_user -d mcp_system -c \
  "SELECT COUNT(*) FROM expense_invoices
   WHERE DATE(created_at) = CURRENT_DATE
   AND accounting_classification IS NOT NULL;"
```

**Check for deprecated parser usage**:
```bash
grep "DEPRECATED: extract_cfdi_metadata" logs/app.log | wc -l
# Should be 0
```

**Find recent errors**:
```bash
grep -i "error" logs/app.log | tail -20
```

---

**Created**: 2025-01-13
**Last Updated**: 2025-01-13 (Auto-generated)
**Estimated Time**: 15-30 minutes

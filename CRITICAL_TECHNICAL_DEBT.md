# 🚨 CRITICAL TECHNICAL DEBT

## ⚠️ NO TRANSACTION SUPPORT IN CPG VERTICAL

### The Problem

**CPG `complete_visit()` performs 3 database writes WITHOUT atomic transaction support:**

1. Create `cpg_consignment` (Money 💰)
2. Update `cpg_pos.ultima_visita` (Inventory 📦)
3. Update `cpg_visits.status = 'completed'` (Status 🏁)

**If the process crashes (kill -9, server restart, network timeout) between these writes, you will have inconsistent data.**

### Current Mitigations (Survival Mode)

#### ✅ Implemented

1. **Fail-Safe Operation Order**
   - Consignment created FIRST (if it fails, visit stays "scheduled")
   - POS updated SECOND (if it fails, we have consignment but no POS update)
   - Visit closed LAST (if it fails, we have orphaned consignment but DETECTABLE)

2. **Robust Error Logging**
   ```python
   logger.error(f"❌ [VISIT-{visit_id}] CRITICAL ERROR during completion: {e}")
   logger.error(f"   Consignment ID: {consignment_id or 'NOT_CREATED'}")
   logger.error(f"   🧹 MANUAL CLEANUP REQUIRED")
   ```

3. **Geofencing Validation**
   - Prevents GPS spoofing (vendor must be within 200m of POS)
   - Uses Haversine formula (no PostGIS dependency)

#### ⏳ Pending (Backlog)

4. **"The Janitor" Script**
   - Nightly cron job to detect orphaned data:
     - `cpg_consignment` with `visit_id` where `cpg_visits.status != 'completed'`
   - Alert Finance team for manual reconciliation
   - **File**: `scripts/maintenance/find_orphaned_consignments.py` (NOT YET CREATED)

### The Real Solution (Sprint Required)

**Refactor `unified_db_adapter.execute_query()` to support external connections:**

```python
# Current (broken for transactions)
execute_query("INSERT INTO foo...", params)
execute_query("UPDATE bar...", params)  # If this fails, first INSERT is committed 💥

# Target architecture
with get_db_connection() as conn:
    execute_query("INSERT INTO foo...", params, connection=conn)
    execute_query("UPDATE bar...", params, connection=conn)
    conn.commit()  # ✅ All or nothing
```

**Estimated Effort**: 1-2 days

**Impact**: Affects ALL code using `execute_query` (reconciliation, invoices, expenses)

**Blocker**: Requires careful testing to avoid regressions across entire codebase

### Risk Assessment

| Scenario | Probability | Impact | Mitigation |
|----------|-------------|--------|------------|
| Server restart during `complete_visit` | Low (1-2%) | HIGH 💰 | Fail-safe order + Janitor script |
| Network timeout to Postgres | Medium (5-10%) | HIGH 💰 | Retry logic + Janitor script |
| Application crash (uncaught exception) | Low (1-3%) | MEDIUM | Error logging + Manual cleanup |

### Acceptance Criteria for Fix

- [ ] `atomic_transaction()` context manager in `shared_logic.py`
- [ ] `execute_query()` accepts `connection` parameter
- [ ] `complete_visit()` wrapped in transaction
- [ ] Janitor script created and scheduled
- [ ] Integration tests cover transaction rollback scenarios

### Workaround Until Fix

**DO NOT:**
- Deploy CPG to production without Finance team approval
- Run concurrent `complete_visit` calls (no parallel processing)
- Ignore ERROR logs with "MANUAL CLEANUP REQUIRED"

**DO:**
- Monitor logs daily for orphaned consignments
- Run `find_orphaned_consignments.py` nightly (WHEN CREATED)
- Have Finance team validate consignment totals vs visit totals weekly

---

**Created**: 2025-01-04
**Owner**: Backend Team
**Severity**: CRITICAL (blocks production deployment)
**Sprint**: Q1 2025 (Infrastructure Hardening)

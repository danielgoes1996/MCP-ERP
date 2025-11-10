import sqlite3

from core.ai_pipeline.classification.classification_feedback import ensure_feedback_table, record_feedback


def test_record_feedback_persists_entry():
    conn = sqlite3.connect(":memory:")
    try:
        ensure_feedback_table(conn)
        record_feedback(
            conn,
            tenant_id=42,
            descripcion="Pago de diseño a freelancer",
            confirmed_sat_code="610.01",
            suggested_sat_code="603",
            expense_id=99,
            notes="override manual",
        )

        row = conn.execute(
            """
            SELECT classification_trace_id,
                   tenant_id,
                   descripcion_normalizada,
                   suggested_sat_code,
                   confirmed_sat_code,
                   expense_id,
                   notes
            FROM expense_classification_feedback
            """
        ).fetchone()

        assert row is not None
        assert row[0] is None
        assert row[1] == 42
        assert "disen" in row[2] or "diseno" in row[2]
        assert row[3] == "603"
        assert row[4] == "610.01"
        assert row[5] == 99
        assert row[6] == "override manual"
    finally:
        conn.close()

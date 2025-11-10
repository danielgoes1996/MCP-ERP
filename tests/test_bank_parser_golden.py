import json
from datetime import date
from pathlib import Path

import pytest

from core.reconciliation.bank.bank_file_parser import BankFileParser
from core.reconciliation.bank.bank_statements_models import BankTransaction, TransactionType


FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "bank_statements"


def _load_expected(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def _assert_summary(summary: dict, expected: dict):
    for key in [
        "opening_balance",
        "closing_balance",
        "transaction_count",
        "total_credits",
        "total_debits",
        "total_incomes",
        "total_expenses",
        "total_transfers",
    ]:
        if key in expected:
            assert summary.get(key) == pytest.approx(expected[key]), key


def _assert_transactions(transactions, expected_list):
    assert len(transactions) >= len(expected_list)
    by_signature = {
        (
            str(txn.date),
            txn.description.strip().lower(),
            round(float(txn.amount), 2),
        ): txn
        for txn in transactions
    }
    for expected in expected_list:
        signature = (
            expected["date"],
            expected["description"].strip().lower(),
            round(float(expected["amount"]), 2),
        )
        assert signature in by_signature, f"Missing transaction {expected}"
        txn = by_signature[signature]
        if "transaction_type" in expected:
            assert txn.transaction_type.value == expected["transaction_type"]


def _iter_golden_cases():
    if not FIXTURES_ROOT.exists():
        return
    for bank_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not bank_dir.is_dir():
            continue
        for expected_path in bank_dir.glob("*.expected.json"):
            pdf_path = expected_path.with_suffix(".pdf")
            if pdf_path.exists():
                yield (pdf_path, expected_path)


def test_parser_keeps_transactions_with_same_reference_but_distinct_data():
    parser = BankFileParser()
    txn_one = BankTransaction(
        account_id=1,
        user_id=1,
        tenant_id=1,
        date=date(2025, 7, 3),
        description="Compra supermercado",
        amount=-150.0,
        transaction_type=TransactionType.DEBIT,
        reference="ABC123456",
    )
    txn_two = BankTransaction(
        account_id=1,
        user_id=1,
        tenant_id=1,
        date=date(2025, 7, 4),
        description="Pago servicio",
        amount=-275.5,
        transaction_type=TransactionType.DEBIT,
        reference="ABC123456",
    )

    txn_iter = iter([txn_one, txn_two])

    parser._looks_like_transaction = lambda line: True  # type: ignore[assignment]

    def _fake_parse(line, account_id, user_id, tenant_id):  # type: ignore[override]
        return next(txn_iter, None)

    parser._parse_transaction_line = _fake_parse  # type: ignore[assignment]

    transactions = parser._extract_transactions_from_text(
        "line 1\nline 2",
        account_id=1,
        user_id=1,
        tenant_id=1,
    )

    assert len(transactions) == 2
    descriptions = {txn.description for txn in transactions}
    assert descriptions == {"Compra supermercado", "Pago servicio"}
    amounts = sorted(round(float(txn.amount), 2) for txn in transactions)
    assert amounts == [-275.5, -150.0]
    references = {txn.reference for txn in transactions}
    assert references == {"ABC123456"}


@pytest.mark.parametrize("pdf_path,expected_path", list(_iter_golden_cases()))
def test_bank_parser_against_golden(pdf_path: Path, expected_path: Path, tmp_path):
    parser = BankFileParser()

    expected = _load_expected(expected_path)

    transactions, summary = parser.parse_file(
        str(pdf_path),
        file_type="pdf",
        account_id=expected.get("account_id", 0),
        user_id=expected.get("user_id", 0),
        tenant_id=expected.get("tenant_id", 0),
    )

    _assert_summary(summary, expected)
    if "transactions" in expected:
        _assert_transactions(transactions, expected["transactions"])

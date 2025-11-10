"""Gemini PDF parser powered by google-genai client."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from google import genai
from google.genai import types

from core.reconciliation.bank.bank_statements_models import (
    BankTransaction,
    MovementKind,
    TransactionType,
    infer_movement_kind,
)

logger = logging.getLogger(__name__)

PROMPT = """You are a banking statement parser. Read the attached PDF and extract all transactions.
Respond ONLY with valid JSON in the following schema:
{
  "bank_name": string | null,
  "account_number": string | null,
  "period": {"start": "YYYY-MM-DD" | null, "end": "YYYY-MM-DD" | null},
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": string,
      "amount": number,  # positive for credits, negative for debits
      "transaction_type": "credit" | "debit",
      "balance_after": number | null,
      "reference": string | null
    }
  ]
}
Make sure the JSON is strictly valid. If a value is unknown, set it to null."""


def _extract_json(text: str) -> Dict[str, object]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json\n"):
            text = text[5:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text)


class GeminiCompleteParser:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key missing. Set GOOGLE_AI_API_KEY or GEMINI_API_KEY")

        self.model_name = os.getenv("GEMINI_COMPLETE_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=self.api_key)

    def parse_bank_statement(
        self,
        file_path: str,
        account_id: int,
        user_id: int,
        tenant_id: int,
    ) -> Tuple[List[BankTransaction], Dict[str, object]]:
        pdf_bytes = Path(file_path).read_bytes()
        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[part, PROMPT],
        )

        text = response.text
        if not text and response.candidates:
            parts = response.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") for p in parts)

        if not text:
            raise RuntimeError("Gemini response empty")

        data = _extract_json(text)
        transactions = self._convert_transactions(
            data.get("transactions", []), account_id, user_id, tenant_id
        )
        summary = self._build_summary(data, transactions)
        return transactions, summary

    def _convert_transactions(
        self,
        entries: List[dict],
        account_id: int,
        user_id: int,
        tenant_id: int,
    ) -> List[BankTransaction]:
        results: List[BankTransaction] = []
        for entry in entries:
            try:
                date_str = entry.get("date")
                txn_date = datetime.fromisoformat(date_str).date() if date_str else None
            except ValueError:
                txn_date = None

            description = (entry.get("description") or "").strip()
            amount = float(entry.get("amount") or 0)
            txn_type_str = (entry.get("transaction_type") or "").lower()

            transaction_type = (
                TransactionType.CREDIT
                if txn_type_str == "credit" or amount > 0
                else TransactionType.DEBIT
            )
            if transaction_type == TransactionType.DEBIT and amount > 0:
                amount = -abs(amount)
            if transaction_type == TransactionType.CREDIT and amount < 0:
                amount = abs(amount)

            movement = infer_movement_kind(transaction_type, description)
            if not movement:
                movement = (
                    MovementKind.INGRESO
                    if transaction_type == TransactionType.CREDIT
                    else MovementKind.GASTO
                )

            txn = BankTransaction(
                account_id=account_id,
                user_id=user_id,
                tenant_id=tenant_id,
                date=txn_date,
                description=description,
                amount=round(amount, 2),
                transaction_type=transaction_type,
                category="Sin categoría",
                reference=entry.get("reference"),
                balance_after=entry.get("balance_after"),
                movement_kind=movement,
                confidence=0.75,
                raw_data=json.dumps(entry)[:1000],
            )
            results.append(txn)

        return results

    def _build_summary(
        self, data: Dict[str, object], transactions: List[BankTransaction]
    ) -> Dict[str, object]:
        period = data.get("period") or {}
        summary = {
            "bank_name": data.get("bank_name"),
            "account_number": data.get("account_number"),
            "period_start": period.get("start"),
            "period_end": period.get("end"),
            "parser_used": "gemini-2.5-flash",
        }

        if transactions:
            total_credits = sum(t.amount for t in transactions if t.amount > 0)
            total_debits = sum(-t.amount for t in transactions if t.amount < 0)
            summary.update(
                {
                    "total_credits": round(total_credits, 2),
                    "total_debits": round(total_debits, 2),
                    "transaction_count": len(transactions),
                }
            )
        else:
            summary.update({
                "total_credits": 0.0,
                "total_debits": 0.0,
                "transaction_count": 0,
            })

        return summary

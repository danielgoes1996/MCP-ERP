# Bank Statement Fixtures

Each subdirectory represents a bank and contains:

```
tests/fixtures/bank_statements/<bank>/<identifier>.pdf
tests/fixtures/bank_statements/<bank>/<identifier>.expected.json
```

The JSON file should describe the expected results for the parser:

```json
{
  "opening_balance": 1234.56,
  "closing_balance": 4321.09,
  "transaction_count": 42,
  "total_credits": 10000.00,
  "total_debits": 1234.00,
  "transactions": [
    {
      "date": "2024-02-01",
      "description": "SPEI RECIBIDO",
      "amount": 1500.00,
      "transaction_type": "credit"
    }
  ]
}
```

Transactions are optional; include only those you want to assert explicitly.

During tests, each expected file is compared against the parser output to
ensure there are no regressions.

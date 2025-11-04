# Bank Statement Golden Suite

To validate the parsing pipeline we maintain a set of anonymised bank
statements. Each case lives under `tests/fixtures/bank_statements/<bank>/` and
consists of the original PDF (or CSV/XLSX if applicable) plus a JSON file with
the expected result.

```text
tests/fixtures/bank_statements/
  inbursa/
    2024-01.pdf
    2024-01.expected.json
  bbva/
    2024-03.pdf
    2024-03.expected.json
  ...
```

### Expected JSON Schema

The JSON describes the relevant output we want to assert. Only the keys that
you include are checked by the test; everything else is optional.

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

### Running the Golden Tests

```bash
source venv/bin/activate
python scripts/run_bank_parser_suite.py
# or with forwarded arguments
python scripts/run_bank_parser_suite.py -vv
```

If the suite is empty, the test is skipped. Add new statements as soon as a
new bank/layout is successfully parsed so future changes keep it working.

### Workflow

1. Drop the original document in the appropriate bank directory.
2. Run the parser manually and capture the summary output.
3. Create the `.expected.json` using the schema above.
4. Add both files to the repository and run the test to ensure it passes.

This suite can later be executed in CI (GitHub Actions) so that any PR affecting
the parser must pass against all known layouts.

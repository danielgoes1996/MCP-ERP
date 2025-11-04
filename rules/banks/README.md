# Bank Parsing Rules

This directory stores bank–specific rules that extend the generic parsing
heuristics. Each file is a JSON document named after the bank identifier
returned by `BankDetector` (lowercase, spaces replaced with underscores).

Example structure:

```json
{
  "credit_keywords": ["depósito extraordinario"],
  "debit_keywords": ["cargo por servicio"],
  "amount_patterns": ["\\$\\s*([\\d,]+\\.\\d{2})"],
  "skip_patterns": ["saldo corte"]
}
```

Only the keys that are present will be merged; missing sections fall back to
the defaults defined in `core.bank_file_parser.BankFileParser`.

The files are intended to be generated (or updated) automatically by the
self-healing pipeline, but they are versioned in Git so every change can be
reviewed through a pull request.

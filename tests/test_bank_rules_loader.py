import importlib

from core import bank_rules_loader
from core.reconciliation.bank.bank_file_parser import BankFileParser


def test_load_bank_specific_rules(tmp_path, monkeypatch):
    rules = bank_rules_loader.load_bank_rules('Inbursa')
    assert isinstance(rules, dict)
    assert 'credit_keywords' in rules
    assert any('traspaso' in kw for kw in rules['credit_keywords'])


def test_apply_bank_rules_updates_keywords():
    parser = BankFileParser()

    base_credit = set(parser.credit_keywords)
    base_debit = set(parser.debit_keywords)

    parser._apply_bank_rules('Inbursa')

    assert 'traspaso spei' in parser.credit_keywords
    assert base_credit.issubset(parser.credit_keywords)
    assert base_debit.issubset(parser.debit_keywords)
    assert parser.last_bank_rules_applied == 'Inbursa'

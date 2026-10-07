"""Insurance policy parsing and lifecycle state."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from fava.core import FavaLedger
from fava.core.insurance import parse_insurance_policies

if TYPE_CHECKING:  # pragma: no cover
    from fava.beans.abc import Custom


def test_parse_insurance_policies(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "alice-health" Expenses:Insurance
      insured: "Alice"
      category: "medical"
      subtype: "supplemental"
      product: "Health Plus"
      issuer: "Example Insurance"
      effective: 2024-02-01
      renewal: 2025-01-01
      expiration: 2025-02-01
      premium: 1200 USD
      coverage: 100000 USD
      deductible: 500 USD
      frequency: "yearly"
      note: "Family policy"
      document: "alice-health-policy.pdf"
      document-2: "alice-health-card.pdf"

    2024-03-01 custom "insurance" "bob-accident"
      insured: "Bob"
      category: "accident"
      product: "Accident Cover"
      effective: 2024-03-01
      cancellation: 2024-08-15
      premium: 25 EUR

    2024-01-01 custom "unrelated" "ignored"
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert not errors
    assert [policy.policy_id for policy in policies] == [
        "alice-health",
        "bob-accident",
    ]

    alice, bob = policies
    assert alice.insured == "Alice"
    assert alice.account == "Expenses:Insurance"
    assert [
        (document.key, document.filename) for document in alice.documents
    ] == [
        ("document", "alice-health-policy.pdf"),
        ("document-2", "alice-health-card.pdf"),
    ]
    assert alice.subtype == "supplemental"
    assert alice.premium is not None
    assert alice.premium.number == Decimal(1200)
    assert alice.premium.currency == "USD"
    assert alice.coverage is not None
    assert alice.coverage.number == Decimal(100000)
    assert alice.status_on(date(2023, 12, 31)) == "not_started"
    assert alice.status_on(date(2024, 1, 31)) == "waiting"
    assert alice.status_on(date(2024, 2, 1)) == "active"
    assert alice.status_on(date(2025, 2, 1)) == "expired"

    assert bob.status_on(date(2024, 8, 14)) == "active"
    assert bob.status_on(date(2024, 8, 15)) == "cancelled"


def test_reject_invalid_insurance_document_account(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "alice-health" "not-an-account"
      insured: "Alice"
      category: "medical"
      product: "Health Plus"
      effective: 2024-02-01
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert not policies
    assert len(errors) == 1
    assert "document account must be an account" in errors[0].message


def test_report_invalid_insurance_policies(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "valid"
      insured: "Alice"
      category: "medical"
      product: "Health Plus"
      effective: 2024-02-01

    2024-01-02 custom "insurance" "valid"
      insured: "Bob"
      category: "medical"
      product: "Duplicate ID"
      effective: 2024-02-01

    2024-01-03 custom "insurance" "missing-product"
      insured: "Alice"
      category: "medical"
      effective: 2024-02-01

    2024-01-04 custom "insurance" "bad-dates"
      insured: "Alice"
      category: "medical"
      product: "Impossible Dates"
      effective: 2023-12-01

    2024-01-05 custom "insurance" "negative-premium"
      insured: "Alice"
      category: "medical"
      product: "Invalid Premium"
      effective: 2024-02-01
      premium: -1 USD
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert [policy.policy_id for policy in policies] == ["valid"]
    assert len(errors) == 4
    assert "Duplicate insurance policy ID" in errors[0].message
    assert "Metadata `product`" in errors[1].message
    assert "Effective date" in errors[2].message
    assert "Metadata `premium`" in errors[3].message


def test_insurance_module_loads_with_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / "insurance.beancount"
    ledger_path.write_text(
        """
2024-01-01 custom "insurance" "alice-health"
  insured: "Alice"
  category: "medical"
  product: "Health Plus"
  effective: 2024-02-01
  premium: 1200 USD

2024-01-02 custom "insurance" "invalid"
  insured: "Bob"
  category: "medical"
  effective: 2024-02-01
""",
    )

    ledger = FavaLedger(str(ledger_path))

    assert [policy.policy_id for policy in ledger.insurance.policies] == [
        "alice-health",
    ]
    assert len(ledger.insurance.errors) == 1
    assert ledger.insurance.errors[0] in ledger.errors
    assert "Metadata `product`" in ledger.insurance.errors[0].message

    ledger_path.write_text(
        """
2025-01-01 custom "insurance" "bob-accident"
  insured: "Bob"
  category: "accident"
  product: "Accident Cover"
  effective: 2025-01-01
""",
    )
    ledger.load_file()

    assert [policy.policy_id for policy in ledger.insurance.policies] == [
        "bob-accident",
    ]
    assert not ledger.insurance.errors


def test_insurance_document_uses_fava_statement_resolution(
    tmp_path: Path,
) -> None:
    documents_path = tmp_path / "documents" / "Expenses" / "Insurance"
    documents_path.mkdir(parents=True)
    policy_document = documents_path / "2024-01-01 alice-health-policy.pdf"
    policy_document.write_bytes(b"%PDF-1.4\n")
    ledger_path = tmp_path / "insurance.beancount"
    ledger_path.write_text(
        """
option "documents" "documents"

2023-12-31 open Expenses:Insurance

2024-01-01 custom "insurance" "alice-health" Expenses:Insurance
  insured: "Alice"
  category: "medical"
  product: "Health Plus"
  effective: 2024-02-01
  document: "2024-01-01 alice-health-policy.pdf"
""",
    )

    ledger = FavaLedger(str(ledger_path))
    policy = ledger.insurance.policies[0]

    assert Path(ledger.statement_path(policy.entry_hash, "document")) == (
        policy_document
    )


def test_reject_insurance_renewal_outside_coverage(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "before-effective"
      insured: "Alice"
      category: "medical"
      product: "Health Plus"
      effective: 2024-02-01
      renewal: 2024-01-15

    2024-01-01 custom "insurance" "after-expiration"
      insured: "Bob"
      category: "medical"
      product: "Health Plus"
      effective: 2024-02-01
      renewal: 2025-03-01
      expiration: 2025-02-01
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert not policies
    assert len(errors) == 2
    assert "effective date" in errors[0].message
    assert "expiration date" in errors[1].message


def test_reject_invalid_insurance_field_types(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "bad-issuer"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      issuer: 123
    2024-01-01 custom "insurance" "bad-effective"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: "tomorrow"
    2024-01-01 custom "insurance" "bad-renewal"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      renewal: "next year"
    2024-01-01 custom "insurance" "bad-premium"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      premium: "expensive"
    2024-01-01 custom "insurance" "too-many" Expenses:Insurance "extra"
    2024-01-01 custom "insurance" 1 USD
    2024-01-01 custom "insurance" " "
    2024-01-01 custom "insurance" "bad-document"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      document: 123
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert not policies
    messages = "\n".join(error.message for error in errors)
    assert "Metadata `issuer` must be a non-empty string" in messages
    assert "Metadata `effective` must be a date" in messages
    assert "Metadata `renewal` must be a date" in messages
    assert "Metadata `premium` must be an amount" in messages
    assert "require a policy ID" in messages
    assert "policy ID must be a string" in messages
    assert "Policy ID must not be empty" in messages
    assert "Metadata `document` must be a non-empty string" in messages


def test_reject_invalid_insurance_date_order(
    load_doc_custom_entries: list[Custom],
) -> None:
    """
    2024-01-01 custom "insurance" "expiration"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      expiration: 2024-02-01
    2024-01-01 custom "insurance" "cancellation-before-purchase"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      cancellation: 2023-12-31
    2024-01-01 custom "insurance" "cancellation-after-expiration"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      expiration: 2024-12-01
      cancellation: 2025-01-01
    2024-01-01 custom "insurance" "renewal-after-cancellation"
      insured: "Alice"
      category: "medical"
      product: "Health"
      effective: 2024-02-01
      renewal: 2024-12-01
      cancellation: 2024-11-01
    """
    policies, errors = parse_insurance_policies(load_doc_custom_entries)

    assert not policies
    messages = "\n".join(error.message for error in errors)
    assert "Expiration date must be after" in messages
    assert "Cancellation date must not precede" in messages
    assert "Cancellation date must not follow" in messages
    assert "Renewal date must not follow the cancellation" in messages

"""Parsing and modelling insurance policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal
from typing import TYPE_CHECKING

from beancount.core.account import TYPE as ACCOUNT_TYPE
from beancount.core.amount import Amount

from fava.beans.funcs import hash_entry
from fava.core.module_base import FavaModule
from fava.helpers import BeancountError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence

    from fava.beans.abc import Custom
    from fava.core import FavaLedger


InsuranceStatus = Literal[
    "not_started",
    "waiting",
    "active",
    "expired",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class InsuranceDocument:
    """A document attached to an insurance policy."""

    key: str
    filename: str


@dataclass(frozen=True, slots=True)
class InsurancePolicy:
    """A single insurance policy and its coverage period."""

    policy_id: str
    entry_hash: str
    insured: str
    category: str
    product: str
    purchased: date
    effective: date
    account: str | None = None
    documents: tuple[InsuranceDocument, ...] = ()
    issuer: str | None = None
    subtype: str | None = None
    renewal: date | None = None
    expiration: date | None = None
    cancellation: date | None = None
    premium: Amount | None = None
    coverage: Amount | None = None
    deductible: Amount | None = None
    frequency: str | None = None
    note: str | None = None

    def status_on(self, day: date) -> InsuranceStatus:
        """Return the policy status on a given day."""
        if day < self.purchased:
            return "not_started"
        if self.cancellation is not None and day >= self.cancellation:
            return "cancelled"
        if self.expiration is not None and day >= self.expiration:
            return "expired"
        if day < self.effective:
            return "waiting"
        return "active"


class InsuranceError(BeancountError):
    """Error while parsing an insurance policy."""


class InsuranceModule(FavaModule):
    """Insurance policies declared in the ledger."""

    def __init__(self, ledger: FavaLedger) -> None:
        super().__init__(ledger)
        self.policies: Sequence[InsurancePolicy] = []
        self.errors: Sequence[InsuranceError] = []

    def load_file(self) -> None:  # noqa: D102
        self.policies, self.errors = parse_insurance_policies(
            self.ledger.all_entries_by_type.Custom,
        )


def _required_string(entry: Custom, key: str) -> str:
    value = entry.meta.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Metadata `{key}` must be a non-empty string"
        raise TypeError(msg)
    return value


def _optional_string(entry: Custom, key: str) -> str | None:
    value = entry.meta.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        msg = f"Metadata `{key}` must be a non-empty string"
        raise TypeError(msg)
    return value


def _required_date(entry: Custom, key: str) -> date:
    value = entry.meta.get(key)
    if not isinstance(value, date):
        msg = f"Metadata `{key}` must be a date"
        raise TypeError(msg)
    return value


def _optional_date(entry: Custom, key: str) -> date | None:
    value = entry.meta.get(key)
    if value is None:
        return None
    if not isinstance(value, date):
        msg = f"Metadata `{key}` must be a date"
        raise TypeError(msg)
    return value


def _optional_amount(entry: Custom, key: str) -> Amount | None:
    value = entry.meta.get(key)
    if value is None:
        return None
    if not isinstance(value, Amount):
        msg = f"Metadata `{key}` must be an amount"
        raise TypeError(msg)
    if value.number < 0:
        msg = f"Metadata `{key}` must not be negative"
        raise ValueError(msg)
    return value


def _policy_identity(entry: Custom) -> tuple[str, str | None]:
    if len(entry.values) not in (1, 2):
        msg = "Insurance entries require a policy ID and optional account"
        raise TypeError(msg)
    if not isinstance(entry.values[0].value, str):
        msg = "Insurance policy ID must be a string"
        raise TypeError(msg)

    policy_id = entry.values[0].value.strip()
    if not policy_id:
        msg = "Policy ID must not be empty"
        raise ValueError(msg)

    if len(entry.values) == 1:
        return policy_id, None

    account_value = entry.values[1]
    if account_value.dtype != ACCOUNT_TYPE or not isinstance(
        account_value.value, str
    ):
        msg = "Insurance document account must be an account"
        raise TypeError(msg)
    return policy_id, account_value.value


def _documents(entry: Custom) -> tuple[InsuranceDocument, ...]:
    documents = []
    for key, value in entry.meta.items():
        if not key.startswith("document"):
            continue
        if not isinstance(value, str) or not value.strip():
            msg = f"Metadata `{key}` must be a non-empty string"
            raise TypeError(msg)
        documents.append(InsuranceDocument(key, value))
    return tuple(documents)


def _parse_policy(entry: Custom) -> InsurancePolicy:
    policy_id, account = _policy_identity(entry)

    effective = _required_date(entry, "effective")
    renewal = _optional_date(entry, "renewal")
    expiration = _optional_date(entry, "expiration")
    cancellation = _optional_date(entry, "cancellation")

    if effective < entry.date:
        msg = "Effective date must not precede the purchase date"
        raise ValueError(msg)
    if renewal is not None and renewal < effective:
        msg = "Renewal date must not precede the effective date"
        raise ValueError(msg)
    if expiration is not None and expiration <= effective:
        msg = "Expiration date must be after the effective date"
        raise ValueError(msg)
    if cancellation is not None and cancellation < entry.date:
        msg = "Cancellation date must not precede the purchase date"
        raise ValueError(msg)
    if (
        cancellation is not None
        and expiration is not None
        and cancellation > expiration
    ):
        msg = "Cancellation date must not follow the expiration date"
        raise ValueError(msg)
    if renewal is not None and expiration is not None and renewal > expiration:
        msg = "Renewal date must not follow the expiration date"
        raise ValueError(msg)
    if (
        renewal is not None
        and cancellation is not None
        and renewal > cancellation
    ):
        msg = "Renewal date must not follow the cancellation date"
        raise ValueError(msg)

    return InsurancePolicy(
        policy_id=policy_id,
        entry_hash=hash_entry(entry),
        insured=_required_string(entry, "insured"),
        category=_required_string(entry, "category"),
        product=_required_string(entry, "product"),
        purchased=entry.date,
        effective=effective,
        account=account,
        documents=_documents(entry),
        issuer=_optional_string(entry, "issuer"),
        subtype=_optional_string(entry, "subtype"),
        renewal=renewal,
        expiration=expiration,
        cancellation=cancellation,
        premium=_optional_amount(entry, "premium"),
        coverage=_optional_amount(entry, "coverage"),
        deductible=_optional_amount(entry, "deductible"),
        frequency=_optional_string(entry, "frequency"),
        note=_optional_string(entry, "note"),
    )


def _register_policy_id(policy_id: str, policy_ids: set[str]) -> None:
    if policy_id in policy_ids:
        msg = f"Duplicate insurance policy ID: {policy_id}"
        raise ValueError(msg)
    policy_ids.add(policy_id)


def parse_insurance_policies(
    custom_entries: Sequence[Custom],
) -> tuple[list[InsurancePolicy], list[InsuranceError]]:
    """Parse ``custom "insurance"`` directives.

    The directive date is the purchase date and its single value is a stable
    policy ID. Policy details are expressed as typed metadata, for example::

        2024-01-01 custom "insurance" "alice-health-2024" Expenses:Insurance
          insured: "Alice"
          category: "medical"
          product: "Health Plus"
          effective: 2024-02-01
          expiration: 2025-02-01
          premium: 1200 USD
          coverage: 100000 USD
          document: "2024-01-01 policy.pdf"

    Invalid policies are reported individually so one malformed directive does
    not prevent the remaining policies from being displayed.
    """
    policies = []
    errors = []
    policy_ids: set[str] = set()

    for entry in (
        entry for entry in custom_entries if entry.type == "insurance"
    ):
        try:
            policy = _parse_policy(entry)
            _register_policy_id(policy.policy_id, policy_ids)
            policies.append(policy)
        except (TypeError, ValueError) as error:
            errors.append(
                InsuranceError(
                    entry.meta,
                    f"Failed to parse insurance policy: {error!s}",
                    entry,
                ),
            )

    policies.sort(
        key=lambda policy: (
            policy.insured.casefold(),
            policy.purchased,
            policy.policy_id,
        ),
    )
    return policies, errors

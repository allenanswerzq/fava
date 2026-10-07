Insurance policies can be tracked with typed `custom` directives. The
directive date is the purchase date, and its value is a stable policy ID:

```beancount
2024-01-01 custom "insurance" "alice-health-2024" Expenses:Insurance
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
  document: "2024-01-01 health-policy.pdf"
```

The `insured`, `category`, `product`, and `effective` metadata fields are
required. All other metadata is optional.

The optional account after the policy ID is the filing account for policy
documents. With a [documents folder](./features) configured, you can drop a
PDF onto the policy row to store it in Fava and attach it to the policy. Attached
files use the standard `document`, `document-2`, and subsequent metadata keys and
can be opened from the policy details. Existing documents can also be attached
by adding their filename as document metadata.

The Insurance report shows the waiting and coverage periods on a shared
timeline and lists the policy details. A policy is considered waiting between
its purchase and effective dates, active after its effective date, and ended
at its cancellation or expiration date.

To record a cancellation, add `cancellation` metadata to the policy. Fava will
validate policy IDs, dates, and amounts while loading the ledger and report
invalid policy directives on the Errors page.

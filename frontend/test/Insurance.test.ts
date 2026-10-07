import { equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import type { InsurancePolicy } from "../src/api/validators.ts";
import { insurance_policy_validator } from "../src/api/validators.ts";
import { Amount } from "../src/entries/amount.ts";
import Insurance from "../src/reports/insurance/Insurance.svelte";
import { setup_jsdom, user_events } from "./dom.ts";
import { initialise_ledger_data } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(() => {
  setup_jsdom();
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get: () => 900,
  });
  globalThis.ResizeObserver = class {
    readonly #callback: ResizeObserverCallback;
    readonly #targets = new Set<Element>();

    constructor(callback: ResizeObserverCallback) {
      this.#callback = callback;
    }

    observe(target: Element): void {
      this.#targets.add(target);
      const size = { inlineSize: 900, blockSize: 300 };
      this.#callback(
        [
          {
            target,
            contentRect: DOMRect.fromRect({ width: 900, height: 300 }),
            borderBoxSize: [size],
            contentBoxSize: [size],
            devicePixelContentBoxSize: [size],
          },
        ],
        this,
      );
    }
    unobserve(target: Element): void {
      this.#targets.delete(target);
    }
    disconnect(): void {
      this.#targets.clear();
    }
  };
});

const policy = (overrides: Partial<InsurancePolicy> = {}): InsurancePolicy => ({
  policy_id: "alice-health",
  entry_hash: "a".repeat(32),
  insured: "Alice",
  category: "medical",
  product: "Health Plus",
  purchased: new Date("2024-01-01"),
  effective: new Date("2024-02-01"),
  status: "active",
  account: "Expenses:Insurance",
  documents: [{ key: "document", filename: "2024-01-01 health-policy.pdf" }],
  issuer: "Example Insurance",
  subtype: "supplemental",
  renewal: new Date("2025-01-01"),
  expiration: null,
  cancellation: null,
  premium: new Amount(1200, "USD"),
  coverage: new Amount(100000, "USD"),
  deductible: new Amount(500, "USD"),
  frequency: "yearly",
  note: "Family policy",
  ...overrides,
});

test("validate insurance policy API data", () => {
  const result = insurance_policy_validator({
    policy_id: "alice-health",
    entry_hash: "a".repeat(32),
    insured: "Alice",
    category: "medical",
    product: "Health Plus",
    purchased: "2024-01-01",
    effective: "2024-02-01",
    status: "active",
    account: null,
    documents: [],
    issuer: null,
    subtype: null,
    renewal: null,
    expiration: null,
    cancellation: null,
    premium: { number: "1200", currency: "USD" },
    coverage: null,
    deductible: null,
    frequency: "yearly",
    note: null,
  }).unwrap();

  equal(result.purchased.toISOString().slice(0, 10), "2024-01-01");
  ok(result.premium instanceof Amount);
  equal(result.premium.number, 1200);
});

test("filter the insurance report", async () => {
  const target = document.querySelector("article");
  ok(target);
  const component = mount(Insurance, {
    target,
    props: {
      policies: [
        policy(),
        policy({
          policy_id: "bob-accident",
          entry_hash: "b".repeat(32),
          insured: "Bob",
          category: "accident",
          product: "Accident Cover",
          status: "cancelled",
          cancellation: new Date("2025-03-01"),
          premium: new Amount(25, "EUR"),
        }),
      ],
    },
  });
  await tick();

  equal(target.querySelectorAll("tbody tr").length, 1);
  equal(target.querySelectorAll("svg .coverage").length, 1);
  equal(target.querySelectorAll("svg .waiting").length, 1);
  const active_row = target.querySelector<HTMLTableRowElement>("tbody tr");
  ok(active_row);
  equal(active_row.classList.contains("droptarget"), true);
  equal(active_row.dataset.accountName, "Expenses:Insurance");
  const document_link = active_row.querySelector<HTMLAnchorElement>(
    'a[href*="statement/"]',
  );
  ok(document_link);
  equal(document_link.href.includes("key=document"), true);

  const status = target.querySelectorAll<HTMLSelectElement>("select")[1];
  ok(status);
  equal(status.value, "active");

  const policy_line = target.querySelector<SVGLineElement>("svg .hit-area");
  ok(policy_line);
  policy_line.dispatchEvent(
    new window.MouseEvent("mouseenter", { bubbles: true }),
  );
  policy_line.dispatchEvent(
    new window.MouseEvent("mousemove", {
      bubbles: true,
      clientX: 400,
      clientY: 200,
    }),
  );
  const tooltip = target.querySelector<HTMLElement>(".tooltip");
  ok(tooltip);
  equal(tooltip.textContent.includes("Health Plus"), true);
  equal(tooltip.style.opacity, "1");

  status.value = "all";
  status.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  equal(target.querySelectorAll("tbody tr").length, 2);

  const search = target.querySelector<HTMLInputElement>('input[type="search"]');
  ok(search);

  user_events.type(search, "Accident Cover");
  equal(target.querySelectorAll("tbody tr").length, 1);
  const bob = target.querySelector("tbody tr");
  ok(bob);
  equal(bob.textContent.includes("Bob"), true);

  user_events.type(search, "");
  status.value = "active";
  status.dispatchEvent(new window.Event("change", { bubbles: true }));
  await tick();
  equal(target.querySelectorAll("tbody tr").length, 1);
  const alice = target.querySelector("tbody tr");
  ok(alice);
  equal(alice.textContent.includes("Alice"), true);

  await unmount(component);
});

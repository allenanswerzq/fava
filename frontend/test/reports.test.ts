import { equal } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import { Document } from "../src/entries/index.ts";
import { array } from "../src/lib/validation.ts";
import { journal_sort } from "../src/stores/journal.ts";
import { setup_jsdom, user_events } from "./dom.ts";
import { initialise_ledger_data, load_json_snapshot } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(setup_jsdom);

test("render documents report", async () => {
  const documents_component = (
    await import("../src/reports/documents/Documents.svelte")
  ).default;

  const data = await load_json_snapshot(
    "test_json_api-test_api-documents.json",
  );
  const documents = array(Document.validator)(data).unwrap();

  const component = mount(documents_component, {
    target: document.body,
    props: { documents },
  });

  await tick();

  equal(document.querySelectorAll("table tbody tr").length, documents.length);

  await unmount(component);
});

test("journal loads additional pages on demand", async () => {
  const journal_table = (
    await import("../src/reports/journal/JournalTable.svelte")
  ).default;

  globalThis.IntersectionObserver = class implements IntersectionObserver {
    readonly root = null;
    readonly rootMargin = "";
    readonly scrollMargin = "";
    readonly thresholds = [];

    disconnect(): void {
      // No browser viewport in this unit test.
    }
    observe(): void {
      // The test exercises the explicit fallback button.
    }
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
    unobserve(): void {
      // The observer does not retain targets in this test.
    }
  };
  journal_sort.set(["date", "desc"]);

  const fragment = document.createDocumentFragment();
  const first = document.createElement("li");
  first.textContent = "first page";
  fragment.append(first);

  const component = mount(journal_table, {
    target: document.body,
    props: {
      journal: fragment,
      initial_sort: ["date", "desc"],
      show_change_and_balance: false,
      load_next_page: async () => {
        await tick();
        const next_fragment = document.createDocumentFragment();
        const second = document.createElement("li");
        second.textContent = "second page";
        next_fragment.append(second);
        return { fragment: next_fragment, has_more: false };
      },
    },
  });

  await tick();
  equal(document.querySelectorAll("ol.journal > li").length, 2);

  const load_more = document.querySelector<HTMLButtonElement>(
    ".journal-load-more button",
  );
  if (load_more == null) {
    throw new Error("Expected the journal load-more button.");
  }
  user_events.click(load_more);
  await new Promise((resolve) => setTimeout(resolve, 0));
  await tick();

  equal(document.querySelectorAll("ol.journal > li").length, 3);
  equal(document.querySelector(".journal-load-more"), null);

  await unmount(component);
});

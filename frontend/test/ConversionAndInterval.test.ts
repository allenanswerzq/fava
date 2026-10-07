import { equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import { setup_jsdom } from "./dom.ts";
import { initialise_ledger_data } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(setup_jsdom);

test("hide the interval selector when requested", async () => {
  const conversion_and_interval = (
    await import("../src/charts/ConversionAndInterval.svelte")
  ).default;
  const component = mount(conversion_and_interval, {
    target: document.body,
    props: { show_interval: false },
  });

  await tick();

  const selectors = document.querySelectorAll('button[role="combobox"]');
  equal(selectors.length, 1);
  const conversion_selector = selectors[0];
  ok(conversion_selector);
  equal(conversion_selector.textContent.trim(), "At Cost");

  await unmount(component);
});

test("show conversion and interval selectors by default", async () => {
  const conversion_and_interval = (
    await import("../src/charts/ConversionAndInterval.svelte")
  ).default;
  const component = mount(conversion_and_interval, {
    target: document.body,
  });

  await tick();

  const selectors = document.querySelectorAll('button[role="combobox"]');
  equal(selectors.length, 2);
  const conversion_selector = selectors[0];
  const interval_selector = selectors[1];
  ok(conversion_selector);
  ok(interval_selector);
  equal(conversion_selector.textContent.trim(), "At Cost");
  equal(interval_selector.textContent.trim(), "Monthly");

  await unmount(component);
});

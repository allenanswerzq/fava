import { equal } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import { setup_jsdom } from "./dom.ts";
import { initialise_ledger_data } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(setup_jsdom);

test("hide the interval selector when requested", async () => {
  const ConversionAndInterval = (
    await import("../src/charts/ConversionAndInterval.svelte")
  ).default;
  const component = mount(ConversionAndInterval, {
    target: document.body,
    props: { show_interval: false },
  });

  await tick();

  const selectors = document.querySelectorAll('button[role="combobox"]');
  equal(selectors.length, 1);
  equal(selectors[0]?.textContent?.trim(), "At Cost");

  await unmount(component);
});

test("show conversion and interval selectors by default", async () => {
  const ConversionAndInterval = (
    await import("../src/charts/ConversionAndInterval.svelte")
  ).default;
  const component = mount(ConversionAndInterval, {
    target: document.body,
  });

  await tick();

  const selectors = document.querySelectorAll('button[role="combobox"]');
  equal(selectors.length, 2);
  equal(selectors[0]?.textContent?.trim(), "At Cost");
  equal(selectors[1]?.textContent?.trim(), "Monthly");

  await unmount(component);
});

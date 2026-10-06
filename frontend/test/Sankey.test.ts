import { equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { mount, tick, unmount } from "svelte";

import Sankey from "../src/charts/Sankey.svelte";
import { sankey_validator } from "../src/charts/sankey.ts";
import { Tooltip } from "../src/charts/tooltip.ts";
import { setup_jsdom } from "./dom.ts";
import { initialise_ledger_data } from "./helpers.ts";

test.before(initialise_ledger_data);
test.beforeEach(setup_jsdom);

test("render a dense Sankey at a readable responsive size", async () => {
  const leaves = Array.from({ length: 14 }, (_, index) => ({
    id: `leaf-${index.toString()}`,
    account: `Income:Long leaf account ${index.toString()}`,
    kind: "account" as const,
    role: null,
    column: 0,
    level: 1,
    balance: { USD: "1" },
  }));
  const data = sankey_validator({
    nodes: [
      ...leaves,
      {
        id: "root",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: { USD: "14" },
      },
    ],
    links: leaves.map(({ id }) => ({
      source: id,
      target: "root",
      value: { USD: "1" },
    })),
  }).unwrap();
  const target = document.querySelector("article");
  ok(target);
  const component = mount(Sankey, {
    target,
    props: {
      data,
      currency: "USD",
      width: 220,
      tooltip: new Tooltip(),
    },
  });

  await tick();

  const svg = target.querySelector("svg");
  ok(svg);
  ok(Number(svg.getAttribute("width")) > 220);
  equal(Number(svg.getAttribute("height")), 544);
  const nodes = [...target.querySelectorAll<SVGRectElement>("rect.node")];
  const links = [...target.querySelectorAll<SVGPathElement>("path.flow")];
  equal(nodes.length, 15);
  equal(links.length, 14);
  ok(nodes.every((node) => Number(node.getAttribute("height")) > 0));
  ok(links.every((link) => Number(link.getAttribute("stroke-width")) > 0));

  await unmount(component);
});

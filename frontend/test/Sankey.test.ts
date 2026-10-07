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

test("inspect a dense Sankey branch without expanding the overview", async () => {
  const accounts = Array.from(
    { length: 14 },
    (_, index) => `Expenses:Category ${index.toString()}`,
  );
  const leaves = accounts.map((account, index) => ({
    id: `leaf-${index.toString()}`,
    account,
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
        account: "Expenses",
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
  target.getBoundingClientRect = () =>
    ({
      left: 100,
      top: 50,
      right: 320,
      bottom: 410,
      width: 220,
      height: 360,
      x: 100,
      y: 50,
      toJSON: () => ({}),
    }) satisfies DOMRect;
  const tooltip = new Tooltip();
  tooltip.init(target);
  const component = mount(Sankey, {
    target,
    props: {
      data,
      currency: "USD",
      width: 220,
      tooltip,
    },
  });

  await tick();

  const svg = target.querySelector(".overview > .scroll > svg");
  ok(svg);
  ok(Number(svg.getAttribute("width")) > 220);
  equal(Number(svg.getAttribute("height")), 360);
  equal(target.querySelectorAll("rect.node").length, 1);
  equal(target.querySelectorAll("path.flow").length, 0);
  const inspect = target.querySelector<SVGTextElement>("text.branch-inspect");
  ok(inspect);
  equal(inspect.textContent, "+14");
  equal(inspect.getAttribute("aria-haspopup"), "dialog");
  inspect.dispatchEvent(new MouseEvent("click", { bubbles: true }));

  await tick();

  equal(Number(svg.getAttribute("height")), 360);
  equal(target.querySelectorAll(".overview > .scroll rect.node").length, 1);
  equal(target.querySelectorAll(".overview > .scroll path.flow").length, 0);
  const focus = target.querySelector<HTMLElement>("div.focus");
  ok(focus);
  equal(focus.getAttribute("role"), "dialog");
  equal(focus.getAttribute("aria-label"), "Details for Expenses");
  ok(target.querySelector("svg.connector path"));
  equal(target.querySelector(".overview.dimmed"), null);
  equal(focus.querySelector("h3"), null);
  const account = focus.querySelector("p.account");
  ok(account);
  equal(account.textContent.trim(), "Expenses");
  const focused_svg = focus.querySelector("svg");
  ok(focused_svg);
  equal(Number(focused_svg.getAttribute("height")), 528);
  const nodes = [...focus.querySelectorAll<SVGRectElement>("rect.node")];
  const links = [...focus.querySelectorAll<SVGPathElement>("path.flow")];
  const link_targets = [
    ...focus.querySelectorAll<SVGPathElement>("path.flow-target"),
  ];
  equal(nodes.length, 15);
  equal(links.length, 14);
  equal(link_targets.length, 14);
  ok(nodes.every((node) => Number(node.getAttribute("height")) > 0));
  ok(links.every((link) => Number(link.getAttribute("stroke-width")) > 0));
  ok(
    link_targets.every(
      (link) => Number(link.getAttribute("stroke-width")) >= 16,
    ),
  );
  ok(link_targets.every((link) => link.getAttribute("aria-hidden") === "true"));
  const first_link_target = link_targets[0];
  ok(first_link_target);
  first_link_target.dispatchEvent(new MouseEvent("mouseenter"));
  first_link_target.dispatchEvent(
    new MouseEvent("mousemove", { clientX: 160, clientY: 90 }),
  );
  const tooltip_element = target.querySelector(".tooltip");
  ok(tooltip_element);
  equal(
    tooltip_element.getAttribute("style"),
    "opacity: 1; left: 60px; top: 40px;",
  );
  equal(tooltip_element.textContent.includes("→ Expenses"), true);
  const root = focus.querySelector<SVGAElement>('a[aria-label="Expenses"]');
  ok(root);
  const root_rect = root.querySelector("rect.node");
  const first_leaf = focus.querySelector<SVGAElement>(
    `a[aria-label="${accounts[0] ?? ""}"]`,
  );
  const first_leaf_rect = first_leaf?.querySelector("rect.node");
  ok(root_rect);
  ok(first_leaf_rect);
  // Moving the overlay to the other side of its trigger must not mirror the
  // focused graph. Preserve the same semantic columns as the overview.
  ok(
    Number(root_rect.getAttribute("x")) >
      Number(first_leaf_rect.getAttribute("x")),
  );
  const root_group = root.parentElement;
  ok(root_group);
  root_group.dispatchEvent(new MouseEvent("mouseenter"));
  equal(tooltip_element.textContent.includes("←"), true);
  const first_account = accounts[0];
  ok(first_account !== undefined);
  equal(
    tooltip_element.textContent.includes(first_account.split(":").at(-1) ?? ""),
    true,
  );
  const backdrop = target.querySelector("button.backdrop");
  ok(backdrop);
  equal(backdrop.getAttribute("tabindex"), "-1");
  const close = focus.querySelector<HTMLButtonElement>("button.close");
  ok(close);
  equal(document.activeElement, close);
  close.dispatchEvent(new MouseEvent("click", { bubbles: true }));

  await tick();

  equal(Number(svg.getAttribute("height")), 360);
  equal(target.querySelector("div.focus"), null);
  equal(target.querySelectorAll(".overview > .scroll rect.node").length, 1);
  equal(inspect.textContent, "+14");
  equal(document.activeElement, inspect);

  inspect.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "Enter",
      bubbles: true,
      cancelable: true,
    }),
  );
  await tick();
  ok(target.querySelector("div.focus"));
  window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
  await tick();
  equal(target.querySelector("div.focus"), null);
  equal(document.activeElement, inspect);

  await unmount(component);
});

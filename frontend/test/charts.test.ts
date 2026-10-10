import { deepEqual, equal, ok } from "node:assert/strict";
import { test } from "node:test";

import { get as store_get } from "svelte/store";

import { ParsedBarChart } from "../src/charts/bar.ts";
import {
  colors10,
  colors15,
  filter_ticks,
  include_zero,
  pad_extent,
} from "../src/charts/helpers.ts";
import { ParsedHierarchyChart } from "../src/charts/hierarchy.ts";
import { charts_validator } from "../src/charts/index.ts";
import { LineChart, ParsedLineChart } from "../src/charts/line.ts";
import {
  layout_sankey,
  ParsedSankeyChart,
  type SankeyGraph,
  sankey_currencies,
  sankey_default_visible_nodes,
  sankey_focused_graph,
  sankey_graph_for_currency,
  sankey_graph_view,
  sankey_link_geometry,
  sankey_validator,
} from "../src/charts/sankey.ts";
import { ScatterPlot } from "../src/charts/scatterplot.ts";
import { load_json_snapshot } from "./helpers.ts";
import { complex_sankey_graph } from "./sankey-layout-example.ts";

test("chart helpers (filter ticks)", () => {
  deepEqual(filter_ticks(["1", "2", "3"], 2), ["1", "3"]);
  deepEqual(filter_ticks(["1", "2", "3"], 4), ["1", "2", "3"]);
});

test("chart helpers (color scales)", () => {
  equal(colors10[0], "rgb(126, 174, 253)");
  equal(colors15[0], "rgb(173, 200, 254)");
});

test("chart helpers (include zero in extent)", () => {
  deepEqual(include_zero([2, 5]), [0, 5]);
  deepEqual(include_zero([-12, -5]), [-12, 0]);
  deepEqual(include_zero([-5, 5]), [-5, 5]);
  deepEqual(include_zero([undefined, undefined]), [0, 1]);
});

test("chart helpers (pad extent)", () => {
  deepEqual(pad_extent([0, 1]), [-0.03, 1.03]);
  deepEqual(pad_extent([undefined, undefined]), [0, 1]);
});

test("build a single-currency Sankey graph", () => {
  const data = sankey_validator({
    nodes: [
      {
        id: "salary",
        account: "Income:Salary",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: { USD: "100" },
      },
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: { EUR: "50", USD: "80" },
      },
      {
        id: "reversal",
        account: "Income:Reversal",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: { USD: "20" },
      },
      {
        id: "eur-expense",
        account: "Expenses:Travel",
        kind: "account",
        role: null,
        column: 3,
        level: 1,
        balance: { EUR: "50" },
      },
    ],
    links: [
      { source: "salary", target: "income", value: { USD: "100" } },
      { source: "income", target: "reversal", value: { USD: "20" } },
      {
        source: "income",
        target: "eur-expense",
        value: { EUR: "50" },
      },
    ],
  }).unwrap();

  deepEqual(sankey_currencies(data), ["EUR", "USD"]);
  deepEqual(sankey_graph_for_currency(data, "USD"), {
    currency: "USD",
    nodes: [
      {
        id: "salary",
        account: "Income:Salary",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: 100,
      },
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: 80,
      },
      {
        id: "reversal",
        account: "Income:Reversal",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: 20,
      },
    ],
    links: [
      { source: "salary", target: "income", value: 100 },
      { source: "income", target: "reversal", value: 20 },
    ],
  });
});

test("prepare a Sankey chart using the preferred available currency", () => {
  const data = sankey_validator({
    nodes: [
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 0,
        level: 0,
        balance: { EUR: "50", USD: "100" },
      },
      {
        id: "expenses",
        account: "Expenses",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: { EUR: "50", USD: "100" },
      },
    ],
    links: [
      {
        source: "income",
        target: "expenses",
        value: { EUR: "50", USD: "100" },
      },
    ],
  }).unwrap();
  const chart = new ParsedSankeyChart("Sankey", data).with_context({
    currencies: ["GBP", "USD"],
    date_format: () => "",
  });

  deepEqual(store_get(chart.currencies), ["EUR", "USD"]);
  equal(store_get(chart.currency), "USD");
});

test("load Sankey data lazily and cache it", async () => {
  let calls = 0;
  const data = sankey_validator({
    nodes: [
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 0,
        level: 0,
        balance: { USD: "10" },
      },
      {
        id: "expenses",
        account: "Expenses",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: { USD: "10" },
      },
    ],
    links: [{ source: "income", target: "expenses", value: { USD: "10" } }],
  }).unwrap();
  const parsed = new ParsedSankeyChart("Sankey", async () => {
    calls += 1;
    return Promise.resolve(data);
  });
  const context = { currencies: ["USD"], date_format: () => "" };
  const chart = parsed.with_context(context);

  equal(calls, 0);
  equal(store_get(chart.data), null);
  await chart.load();
  equal(calls, 1);
  equal(store_get(chart.data), data);
  deepEqual(store_get(chart.currencies), ["USD"]);

  const second_chart = parsed.with_context(context);
  await second_chart.load();
  equal(calls, 1);
  equal(store_get(second_chart.data), data);
});

test("layout a Sankey graph in fixed semantic columns", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "salary",
        account: "Income:Salary",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: 100,
      },
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: 80,
      },
      {
        id: "reversal",
        account: "Income:Reversal",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: 20,
      },
      {
        id: "costs",
        account: "Expenses",
        kind: "account",
        role: null,
        column: 2,
        level: 0,
        balance: 60,
      },
      {
        id: "housing",
        account: "Expenses:Housing",
        kind: "account",
        role: null,
        column: 3,
        level: 1,
        balance: 70,
      },
      {
        id: "refund",
        account: "Expenses:Refund",
        kind: "account",
        role: null,
        column: 3,
        level: 1,
        balance: 10,
      },
      {
        id: "profit",
        account: null,
        kind: "result",
        role: "net_profit",
        column: 2,
        level: null,
        balance: 20,
      },
    ],
    links: [
      { source: "salary", target: "income", value: 100 },
      { source: "income", target: "reversal", value: 20 },
      { source: "income", target: "costs", value: 60 },
      { source: "income", target: "profit", value: 20 },
      { source: "costs", target: "housing", value: 70 },
      { source: "refund", target: "costs", value: 10 },
    ],
  };

  const layout = layout_sankey(graph, {
    width: 400,
    height: 200,
    node_width: 10,
    node_padding: 10,
  });
  const nodes = new Map(layout.nodes.map((node) => [node.id, node]));
  const links = new Map(
    layout.links.map((link) => [`${link.source.id}->${link.target.id}`, link]),
  );

  equal(nodes.get("salary")?.x0, 0);
  equal(nodes.get("income")?.x0, 130);
  equal(nodes.get("costs")?.x0, 260);
  equal(nodes.get("housing")?.x0, 390);
  for (const ids of [
    ["salary", "reversal"],
    ["costs", "profit"],
    ["housing", "refund"],
  ]) {
    const column = ids
      .map((id) => nodes.get(id))
      .filter((node) => node != null)
      .sort((a, b) => a.y0 - b.y0);
    ok(column[0] && column[1] && column[0].y1 <= column[1].y0);
  }
  ok(
    (links.get("income->reversal")?.source.x0 ?? 0) >
      (links.get("income->reversal")?.target.x0 ?? 0),
  );
  ok(
    (links.get("refund->costs")?.source.x0 ?? 0) >
      (links.get("refund->costs")?.target.x0 ?? 0),
  );
  ok(layout.links.every((link) => link.width > 0));
  ok(
    layout.links.every(
      (link) =>
        link.y0 >= link.source.y0 &&
        link.y0 <= link.source.y1 &&
        link.y1 >= link.target.y0 &&
        link.y1 <= link.target.y1,
    ),
  );

  const forward = links.get("salary->income");
  const backward = links.get("income->reversal");
  ok(forward && backward);
  const forward_geometry = sankey_link_geometry(forward);
  const backward_geometry = sankey_link_geometry(backward);
  ok(forward_geometry.path.startsWith(`M${forward.source.x1.toString()},`));
  ok(
    forward_geometry.path.endsWith(
      `,${forward.target.x0.toString()},${forward.y1.toString()}`,
    ),
  );
  ok(backward_geometry.path.startsWith(`M${backward.source.x0.toString()},`));
  ok(
    backward_geometry.path.endsWith(
      `,${backward.target.x1.toString()},${backward.y1.toString()}`,
    ),
  );
});

test("keep a dense Sankey column visible", () => {
  const leaf_nodes: SankeyGraph["nodes"] = Array.from(
    { length: 14 },
    (_, index) => ({
      id: `leaf-${index.toString()}`,
      account: `Income:Leaf${index.toString()}`,
      kind: "account",
      role: null,
      column: 0,
      level: 1,
      balance: 1,
    }),
  );
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      ...leaf_nodes,
      {
        id: "root",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: 14,
      },
    ],
    links: leaf_nodes.map(({ id }) => ({
      source: id,
      target: "root",
      value: 1,
    })),
  };

  const layout = layout_sankey(graph, {
    width: 400,
    height: 230.4,
    node_width: 10,
    node_padding: 20,
  });

  ok(layout.nodes.every((node) => node.y1 > node.y0));
  ok(layout.links.every((link) => link.width > 0));
});

test("expand a terminal single-child Sankey branch when it fits", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "root",
        account: "Income",
        kind: "account",
        role: null,
        column: 1,
        level: 0,
        balance: 10,
      },
      {
        id: "only-child",
        account: "Income:Only",
        kind: "account",
        role: null,
        column: 0,
        level: 1,
        balance: 10,
      },
    ],
    links: [{ source: "only-child", target: "root", value: 10 }],
  };

  const visible = sankey_default_visible_nodes(graph);
  deepEqual([...visible], ["root", "only-child"]);
  const view = sankey_graph_view(graph, visible);
  deepEqual(
    view.graph.nodes.map(({ id }) => id),
    ["root", "only-child"],
  );
  equal(view.graph.nodes[0]?.fixedValue, undefined);
});

test("select important Sankey nodes across account branches", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "b-small",
        account: "Income:B:Small",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 20,
      },
      {
        id: "a-small",
        account: "Income:A:Small",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 30,
      },
      {
        id: "group-b",
        account: "Income:B",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 80,
      },
      {
        id: "b-large",
        account: "Income:B:Large",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 60,
      },
      {
        id: "income",
        account: "Income",
        kind: "account",
        role: null,
        column: 2,
        level: 0,
        balance: 180,
      },
      {
        id: "a-large",
        account: "Income:A:Large",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 70,
      },
      {
        id: "group-a",
        account: "Income:A",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 100,
      },
    ],
    links: [
      { source: "b-small", target: "group-b", value: 20 },
      { source: "a-small", target: "group-a", value: 30 },
      { source: "group-b", target: "income", value: 80 },
      { source: "b-large", target: "group-b", value: 60 },
      { source: "a-large", target: "group-a", value: 70 },
      { source: "group-a", target: "income", value: 100 },
    ],
  };

  const layout = layout_sankey(graph, {
    width: 400,
    height: 400,
    node_width: 10,
    node_padding: 10,
  });
  const nodes_by_column = Map.groupBy(layout.nodes, (node) => node.column);
  const ordered_ids = (column: number) =>
    (nodes_by_column.get(column) ?? [])
      .sort((left, right) => left.y0 - right.y0)
      .map(({ id }) => id);

  deepEqual(ordered_ids(0), ["a-large", "a-small", "b-large", "b-small"]);
  deepEqual(ordered_ids(1), ["group-a", "group-b"]);

  const all_visible = sankey_default_visible_nodes(graph);
  deepEqual([...all_visible].sort(), [
    "a-large",
    "a-small",
    "b-large",
    "b-small",
    "group-a",
    "group-b",
    "income",
  ]);
  equal(sankey_graph_view(graph, all_visible).graph.nodes.length, 7);

  const visible = sankey_default_visible_nodes(graph, 2);
  deepEqual(
    [...visible],
    ["income", "group-a", "group-b", "a-large", "b-large"],
  );
  const view = sankey_graph_view(graph, visible);
  deepEqual(view.graph.nodes.map(({ id }) => id).sort(), [
    "a-large",
    "b-large",
    "group-a",
    "group-b",
    "income",
  ]);
  deepEqual(view.branches.get("group-a"), {
    hidden_accounts: 1,
  });
  deepEqual(view.branches.get("group-b"), {
    hidden_accounts: 1,
  });
  equal(view.graph.nodes.find(({ id }) => id === "group-a")?.fixedValue, 100);
  equal(view.graph.nodes.find(({ id }) => id === "group-b")?.fixedValue, 80);
});

test("hide negligible Sankey nodes below the flow threshold", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "root",
        account: "Expenses",
        kind: "account",
        role: null,
        column: 0,
        level: 0,
        balance: 100,
      },
      {
        id: "important",
        account: "Expenses:Important",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 99,
      },
      {
        id: "tiny",
        account: "Expenses:Tiny",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 1,
      },
    ],
    links: [
      { source: "root", target: "important", value: 99 },
      { source: "root", target: "tiny", value: 1 },
    ],
  };

  const visible = sankey_default_visible_nodes(graph, 12, 0.02);
  deepEqual([...visible], ["root", "important"]);
  const view = sankey_graph_view(graph, visible);
  deepEqual(view.branches.get("root"), { hidden_accounts: 1 });
  equal(view.graph.nodes.find(({ id }) => id === "root")?.fixedValue, 100);
});

test("select and lay out a complex Sankey graph", () => {
  const visible = sankey_default_visible_nodes(
    complex_sankey_graph,
    4,
    0.02,
    4,
  );
  deepEqual([...visible].sort(), [
    "bonus",
    "dining",
    "dividends",
    "employer-a",
    "employer-b",
    "expenses",
    "flights",
    "groceries",
    "housing",
    "income",
    "interest",
    "investments",
    "living",
    "main",
    "net-profit",
    "refund",
    "rent",
    "salary",
    "travel",
  ]);
  ok(!visible.has("fees"));
  ok(!visible.has("misc-income"));
  ok(!visible.has("rounding"));
  ok(!visible.has("utilities"));

  const view = sankey_graph_view(complex_sankey_graph, visible);
  deepEqual(
    [...view.branches].map(([id, branch]) => [id, branch.hidden_accounts]),
    [
      ["salary", 1],
      ["income", 1],
      ["expenses", 1],
      ["housing", 1],
      ["living", 2],
      ["travel", 1],
    ],
  );
  for (const [id, value] of [
    ["salary", 900],
    ["income", 1200],
    ["expenses", 1030],
    ["housing", 450],
    ["living", 430],
    ["travel", 140],
  ] as const) {
    equal(view.graph.nodes.find((node) => node.id === id)?.fixedValue, value);
  }
  equal(view.graph.links.length, 18);
  ok(
    view.graph.links.every(
      ({ source, target }) => visible.has(source) && visible.has(target),
    ),
  );

  const layout = layout_sankey(view.graph, {
    width: 700,
    height: 520,
    node_width: 10,
    node_padding: 12,
  });
  const nodes = new Map(layout.nodes.map((node) => [node.id, node]));
  const nodes_by_column = Map.groupBy(layout.nodes, (node) => node.column);
  const ordered_ids = (column: number) =>
    (nodes_by_column.get(column) ?? [])
      .toSorted((left, right) => left.y0 - right.y0)
      .map(({ id }) => id);

  deepEqual(ordered_ids(0), ["employer-a", "employer-b"]);
  deepEqual(ordered_ids(1), ["main", "bonus", "dividends", "interest"]);
  deepEqual(ordered_ids(4), ["expenses", "net-profit"]);
  deepEqual(ordered_ids(5), ["housing", "living", "travel", "refund"]);
  deepEqual(ordered_ids(6), ["rent", "groceries", "dining", "flights"]);
  for (const [column_index, column] of nodes_by_column) {
    equal(column.length <= 4, true);
    const ordered = column.toSorted((left, right) => left.y0 - right.y0);
    for (const [index, node] of ordered.entries()) {
      equal(node.x0, column_index * 115);
      equal(node.x1, node.x0 + 10);
      ok(node.y1 > node.y0);
      const next = ordered[index + 1];
      if (next) {
        ok(node.y1 <= next.y0);
      }
    }
  }
  ok(
    (nodes.get("salary")?.y1 ?? 0) - (nodes.get("salary")?.y0 ?? 0) >
      (nodes.get("investments")?.y1 ?? 0) - (nodes.get("investments")?.y0 ?? 0),
  );
  ok(
    layout.links.every(
      (link) =>
        link.width > 0 &&
        link.y0 - link.width / 2 >= link.source.y0 - 1e-9 &&
        link.y0 + link.width / 2 <= link.source.y1 + 1e-9 &&
        link.y1 - link.width / 2 >= link.target.y0 - 1e-9 &&
        link.y1 + link.width / 2 <= link.target.y1 + 1e-9,
    ),
  );
  const refund = layout.links.find(
    (link) => link.source.id === "refund" && link.target.id === "expenses",
  );
  ok(refund && refund.source.x0 > refund.target.x0);
  ok(
    layout.links.every((link) => {
      const geometry = sankey_link_geometry(link);
      const forward = link.source.x0 < link.target.x0;
      const source_x = forward ? link.source.x1 : link.source.x0;
      const target_x = forward ? link.target.x0 : link.target.x1;
      return (
        geometry.path.startsWith(
          `M${source_x.toString()},${link.y0.toString()}`,
        ) &&
        geometry.path.endsWith(`,${target_x.toString()},${link.y1.toString()}`)
      );
    }),
  );
});

test("limit and compact Sankey account hierarchy levels", () => {
  const visible = sankey_default_visible_nodes(
    complex_sankey_graph,
    4,
    0.02,
    3,
  );
  ok(visible.has("main"));
  ok(!visible.has("employer-a"));
  ok(!visible.has("employer-b"));
  ok(
    complex_sankey_graph.nodes
      .filter(({ id }) => visible.has(id))
      .every(({ level }) => level == null || level < 3),
  );

  const view = sankey_graph_view(complex_sankey_graph, visible);
  deepEqual(view.branches.get("main"), { hidden_accounts: 2 });
  equal(view.graph.nodes.find(({ id }) => id === "main")?.fixedValue, 700);
  equal(Math.min(...view.graph.nodes.map(({ column }) => column)), 0);
  equal(Math.max(...view.graph.nodes.map(({ column }) => column)), 5);
  equal(view.graph.nodes.find(({ id }) => id === "income")?.column, 2);
  equal(view.graph.nodes.find(({ id }) => id === "expenses")?.column, 3);
});

test("order partially collapsed Sankey nodes by their retained value", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "large",
        account: "Income:Large",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 100,
        fixedValue: 100,
      },
      {
        id: "large-visible-child",
        account: "Income:Large:Visible",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 1,
      },
      {
        id: "medium",
        account: "Income:Medium",
        kind: "account",
        role: null,
        column: 1,
        level: 1,
        balance: 50,
      },
      {
        id: "medium-child",
        account: "Income:Medium:Child",
        kind: "account",
        role: null,
        column: 0,
        level: 2,
        balance: 50,
      },
    ],
    links: [
      { source: "large-visible-child", target: "large", value: 1 },
      { source: "medium-child", target: "medium", value: 50 },
    ],
  };

  const layout = layout_sankey(graph, {
    width: 200,
    height: 200,
    node_width: 10,
    node_padding: 10,
  });
  const nodes = new Map(layout.nodes.map((node) => [node.id, node]));
  const large = nodes.get("large");
  const medium = nodes.get("medium");
  ok(large && medium);
  ok(large.y0 < medium.y0);
  ok(large.y1 - large.y0 > medium.y1 - medium.y0);
});

test("build a rebased Sankey graph for one focused account branch", () => {
  const graph: SankeyGraph = {
    currency: "USD",
    nodes: [
      {
        id: "outside",
        account: "Expenses:Outside",
        kind: "account",
        role: null,
        column: 4,
        level: 1,
        balance: 30,
      },
      {
        id: "focus",
        account: "Expenses:Focus",
        kind: "account",
        role: null,
        column: 4,
        level: 1,
        balance: 70,
      },
      {
        id: "child",
        account: "Expenses:Focus:Child",
        kind: "account",
        role: null,
        column: 5,
        level: 2,
        balance: 70,
      },
      {
        id: "expenses",
        account: "Expenses",
        kind: "account",
        role: null,
        column: 3,
        level: 0,
        balance: 100,
      },
    ],
    links: [
      { source: "expenses", target: "outside", value: 30 },
      { source: "expenses", target: "focus", value: 70 },
      { source: "focus", target: "child", value: 70 },
    ],
  };

  const focused = sankey_focused_graph(graph, "focus");
  deepEqual(
    focused.nodes.map(({ id, column }) => [id, column]),
    [
      ["focus", 0],
      ["child", 1],
    ],
  );
  deepEqual(focused.links, [{ source: "focus", target: "child", value: 70 }]);
});

test("handle data for hierarchical chart", async () => {
  const ctx = { currencies: ["USD"], date_format: () => "DATE" };
  ok(ParsedHierarchyChart.validator({ label: "name", data: "" }).is_err);
  const data = await load_json_snapshot(
    "test_internal_api-test_chart_api.json",
  );
  const validated = charts_validator(data).unwrap();

  const [hierarchy, balances, net_worth] = validated;
  ok(hierarchy instanceof ParsedHierarchyChart);
  ok(balances instanceof ParsedLineChart);
  ok(net_worth instanceof ParsedLineChart);
  const hierarchy_with_context = hierarchy.with_context(ctx);
  deepEqual(hierarchy_with_context.currencies, ["USD"]);
  ok(hierarchy_with_context.data.get("USD"));
});

test("handle data for balances chart", () => {
  ok(ParsedLineChart.validator({ label: "name", data: "" }).is_err);
  const data: unknown = [
    { date: "2000-01-01", balance: { EUR: "10", USD: "10" } },
    { date: "2000-02-01", balance: { EUR: "10" } },
  ];
  const parsed = ParsedLineChart.validator({ label: "name", data })
    .unwrap()
    .with_context();
  ok(parsed instanceof LineChart);
  deepEqual(parsed.filter([]), [
    {
      name: "EUR",
      values: [
        { date: new Date("2000-01-01"), name: "EUR", value: 10 },
        { date: new Date("2000-02-01"), name: "EUR", value: 10 },
      ],
    },
    {
      name: "USD",
      values: [{ date: new Date("2000-01-01"), name: "USD", value: 10 }],
    },
  ]);
});

test("handle data for scatterplot chart", () => {
  ok(ScatterPlot.validator("asdfasdf").is_err);
  ok(ScatterPlot.validator({ label: "name", data: "" }).is_err);
  const data: unknown = [
    { type: "test", date: "2000-01-01", description: "desc" },
  ];
  const parsed = ScatterPlot.validator({ label: "name", data })
    .unwrap()
    .with_context();
  ok(parsed instanceof ScatterPlot);
  deepEqual(
    parsed,
    new ScatterPlot("name", [
      { date: new Date("2000-01-01"), description: "desc", type: "test" },
    ]),
  );
});

test("handle data for bar chart with stacked data", () => {
  const data: unknown = [
    {
      date: "2000-01-01",
      balance: { EUR: "10", USD: "10" },
      budgets: { USD: "20" },
      account_balances: {
        "Expenses:Dining": { USD: "8" },
        "Expenses:Transportation": { EUR: "6" },
        "Expenses:Taxes": { USD: "2", EUR: "4" },
      },
    },
    {
      date: "2000-02-01",
      balance: { EUR: "100" },
      budgets: { EUR: "50" },
      account_balances: {
        "Expenses:Shoes": { EUR: "60" },
        "Expenses:Taxes": { EUR: "40" },
      },
    },
  ];
  const ctx = { currencies: ["EUR", "USD"], date_format: () => "DATE" };
  const chart = ParsedBarChart.validator({ label: "name", data })
    .unwrap()
    .with_context(ctx);
  equal(true, chart.hasStackedData);
  deepEqual(chart.accounts, [
    "Expenses:Dining",
    "Expenses:Shoes",
    "Expenses:Taxes",
    "Expenses:Transportation",
  ]);
  const result = chart.filter([]);
  const simplified_stacks = result.stacks.map(([currency, series_arr]) => [
    currency,
    series_arr.map((series) => ({
      key: series.key,
      index: series.index,
      points: series.map((p) => [p[0], p[1]]),
    })),
  ]);
  deepEqual(simplified_stacks, [
    [
      "EUR",
      [
        { key: "Expenses:Shoes", index: 1, points: [[0, 60]] },
        {
          key: "Expenses:Taxes",
          index: 2,
          points: [
            [0, 4],
            [60, 100],
          ],
        },
        { key: "Expenses:Transportation", index: 3, points: [[4, 10]] },
      ],
    ],
    [
      "USD",
      [
        { key: "Expenses:Dining", index: 0, points: [[0, 8]] },
        { key: "Expenses:Taxes", index: 2, points: [[8, 10]] },
      ],
    ],
  ]);
  deepEqual(result.bar_groups, [
    {
      date: new Date("2000-01-01"),
      label: "DATE",
      values: [
        {
          currency: "EUR",
          value: 10,
          budget: 0,
        },
        {
          currency: "USD",
          value: 10,
          budget: 20,
        },
      ],
      account_balances: {
        "Expenses:Dining": { USD: 8 },
        "Expenses:Transportation": { EUR: 6 },
        "Expenses:Taxes": { USD: 2, EUR: 4 },
      },
    },
    {
      date: new Date("2000-02-01"),
      label: "DATE",
      values: [
        {
          currency: "EUR",
          value: 100,
          budget: 50,
        },
        {
          currency: "USD",
          value: 0,
          budget: 0,
        },
      ],
      account_balances: {
        "Expenses:Shoes": { EUR: 60 },
        "Expenses:Taxes": { EUR: 40 },
      },
    },
  ]);
});

test("handle data for bar chart without stacked data", () => {
  const data: unknown = [
    {
      date: "2000-01-01",
      balance: { EUR: "10", USD: "10" },
      budgets: { USD: "20" },
      account_balances: {},
    },
    {
      date: "2000-02-01",
      balance: { EUR: "100" },
      budgets: { EUR: "50" },
      account_balances: {},
    },
  ];
  // even without the operating currencies, the two most popular ones will be selected
  const ctx = { currencies: [], date_format: () => "DATE" };
  const chart = ParsedBarChart.validator({ label: "name", data })
    .unwrap()
    .with_context(ctx);
  equal(false, chart.hasStackedData);
  deepEqual(chart.filter([]).stacks, [
    ["EUR", []],
    ["USD", []],
  ]);
  const without_usd = chart.filter(["USD"]);
  deepEqual(without_usd.stacks, [["EUR", []]]);
  deepEqual(without_usd.bar_groups, [
    {
      date: new Date("2000-01-01"),
      label: "DATE",
      values: [{ currency: "EUR", value: 10, budget: 0 }],
      account_balances: {},
    },
    {
      date: new Date("2000-02-01"),
      label: "DATE",
      values: [{ currency: "EUR", value: 100, budget: 50 }],
      account_balances: {},
    },
  ]);
});

test("only use currencies in records for bar chart", () => {
  const data: unknown = [
    {
      date: "2000-01-01",
      balance: { AUD: "10", USD: "10" },
      budgets: { USD: "20" },
      account_balances: {},
    },
    {
      date: "2000-02-01",
      balance: { AUD: "100" },
      budgets: { AUD: "50" },
      account_balances: {},
    },
  ];
  const ctx = { currencies: ["EUR", "USD"], date_format: () => "DATE" };
  const chart = ParsedBarChart.validator({ label: "name", data })
    .unwrap()
    .with_context(ctx);
  equal(false, chart.hasStackedData);
  deepEqual(chart.filter([]).stacks, [
    ["USD", []],
    ["AUD", []],
  ]);
  deepEqual(chart.filter([]).bar_groups, [
    {
      date: new Date("2000-01-01"),
      label: "DATE",
      values: [
        { currency: "USD", value: 10, budget: 20 },
        { currency: "AUD", value: 10, budget: 0 },
      ],
      account_balances: {},
    },
    {
      date: new Date("2000-02-01"),
      label: "DATE",
      values: [
        { currency: "USD", value: 0, budget: 0 },
        { currency: "AUD", value: 100, budget: 50 },
      ],
      account_balances: {},
    },
  ]);
});

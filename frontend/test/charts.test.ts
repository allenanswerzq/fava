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
  sankey_graph_for_currency,
  sankey_link_geometry,
  sankey_validator,
} from "../src/charts/sankey.ts";
import { ScatterPlot } from "../src/charts/scatterplot.ts";
import { load_json_snapshot } from "./helpers.ts";

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
  equal(forward_geometry.direction, "forward");
  equal(backward_geometry.direction, "backward");
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
  ok(Math.abs(forward_geometry.arrow.angle) < 90);
  ok(Math.abs(backward_geometry.arrow.angle) > 90);
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

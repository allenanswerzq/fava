import { sankey } from "d3-sankey";
import { type Writable, writable } from "svelte/store";

import type { ValidationT } from "../lib/validation.ts";
import {
  array,
  constants,
  decimal,
  number,
  object,
  optional,
  record,
  string,
} from "../lib/validation.ts";
import type { ChartContext } from "./context.ts";
import type { ParsedFavaChart } from "./index.ts";

const sankey_node_validator = object({
  id: string,
  account: optional(string),
  kind: constants("account", "result"),
  role: optional(string),
  column: number,
  level: optional(number),
  balance: record(decimal),
});

const sankey_link_validator = object({
  source: string,
  target: string,
  value: record(decimal),
});

/** Generic, validated data for a Sankey chart. */
export const sankey_validator = object({
  nodes: array(sankey_node_validator),
  links: array(sankey_link_validator),
});

export type SankeyData = ValidationT<typeof sankey_validator>;
export type SankeyNode = SankeyData["nodes"][number];
export type SankeyLink = SankeyData["links"][number];

/** A node reduced to the values needed to draw one currency. */
export interface SankeyGraphNode extends Omit<SankeyNode, "balance"> {
  balance: number;
}

/** A directed link reduced to one positive width. */
export interface SankeyGraphLink extends Omit<SankeyLink, "value"> {
  value: number;
}

/** A single-currency graph ready to be passed to a layout function. */
export interface SankeyGraph {
  currency: string;
  nodes: SankeyGraphNode[];
  links: SankeyGraphLink[];
}

/** A node with all coordinates required by the renderer. */
export interface SankeyLayoutNode extends SankeyGraphNode {
  value: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  sourceLinks: SankeyLayoutLink[];
  targetLinks: SankeyLayoutLink[];
}

/** A link with resolved nodes and vertical attachment points. */
export interface SankeyLayoutLink
  extends Omit<SankeyGraphLink, "source" | "target"> {
  source: SankeyLayoutNode;
  target: SankeyLayoutNode;
  width: number;
  y0: number;
  y1: number;
}

/** A fully positioned single-currency graph. */
export interface SankeyLayoutGraph {
  currency: string;
  nodes: SankeyLayoutNode[];
  links: SankeyLayoutLink[];
}

export interface SankeyLayoutOptions {
  width: number;
  height: number;
  node_width?: number;
  node_padding?: number;
}

/** Geometry for a link path and its directional arrow. */
export interface SankeyLinkGeometry {
  path: string;
  direction: "forward" | "backward";
  arrow: {
    x: number;
    y: number;
    angle: number;
  };
}

export type SankeyDataSource = SankeyData | (() => Promise<SankeyData>);

/** List the currencies for which at least one visible link exists. */
export function sankey_currencies(data: SankeyData): string[] {
  return [
    ...new Set(
      data.links.flatMap(({ value }) =>
        Object.entries(value)
          .filter(([, number]) => number > 0)
          .map(([currency]) => currency),
      ),
    ),
  ].sort();
}

/** A Sankey chart ready to be rendered. */
export class SankeyChart {
  readonly type = "sankey";
  readonly label: string | null;
  readonly role_labels: Readonly<Record<string, string>>;
  readonly data: Writable<SankeyData | null>;
  readonly currencies: Writable<readonly string[]>;
  readonly currency: Writable<string | null>;
  private readonly source: SankeyDataSource;
  private readonly preferred_currencies: readonly string[];
  private loading: Promise<void> | null = null;

  constructor(
    label: string | null,
    source: SankeyDataSource,
    role_labels: Readonly<Record<string, string>>,
    preferred_currencies: readonly string[],
  ) {
    this.label = label;
    this.source = source;
    this.role_labels = role_labels;
    this.preferred_currencies = preferred_currencies;
    const data = typeof source === "function" ? null : source;
    const currencies = data ? sankey_currencies(data) : [];
    this.data = writable(data);
    this.currencies = writable(currencies);
    this.currency = writable(this.preferred_currency(currencies));
  }

  /** Load lazy Sankey data at most once for this rendered chart. */
  async load(): Promise<void> {
    if (typeof this.source !== "function") {
      return Promise.resolve();
    }
    this.loading ??= this.source()
      .then((data) => {
        const currencies = sankey_currencies(data);
        this.data.set(data);
        this.currencies.set(currencies);
        this.currency.set(this.preferred_currency(currencies));
      })
      .catch((error: unknown) => {
        this.loading = null;
        throw error;
      });
    return this.loading;
  }

  private preferred_currency(currencies: readonly string[]): string | null {
    return (
      this.preferred_currencies.find((currency) =>
        currencies.includes(currency),
      ) ??
      currencies[0] ??
      null
    );
  }
}

/** Sankey data that still needs the chart context's preferred currency. */
export class ParsedSankeyChart implements ParsedFavaChart {
  readonly label: string | null;
  readonly role_labels: Readonly<Record<string, string>>;
  private readonly source: SankeyDataSource;
  private loaded_data: SankeyData | null;
  private loading: Promise<SankeyData> | null = null;

  constructor(
    label: string | null,
    source: SankeyDataSource,
    role_labels: Readonly<Record<string, string>> = {},
  ) {
    this.label = label;
    this.source = source;
    this.loaded_data = typeof source === "function" ? null : source;
    this.role_labels = role_labels;
  }

  with_context({ currencies }: ChartContext): SankeyChart {
    return new SankeyChart(
      this.label,
      this.loaded_data ?? (async () => this.load()),
      this.role_labels,
      currencies,
    );
  }

  private async load(): Promise<SankeyData> {
    if (this.loaded_data) {
      return Promise.resolve(this.loaded_data);
    }
    if (typeof this.source !== "function") {
      return Promise.resolve(this.source);
    }
    this.loading ??= this.source()
      .then((data) => {
        this.loaded_data = data;
        return data;
      })
      .catch((error: unknown) => {
        this.loading = null;
        throw error;
      });
    return this.loading;
  }
}

/** Build a fresh, single-currency graph without mutating the API data. */
export function sankey_graph_for_currency(
  data: SankeyData,
  currency: string,
): SankeyGraph {
  const links = data.links.flatMap(({ source, target, value }) => {
    const width = value[currency] ?? 0;
    return width > 0 ? [{ source, target, value: width }] : [];
  });
  const linked_node_ids = new Set(
    links.flatMap(({ source, target }) => [source, target]),
  );
  const nodes = data.nodes
    .filter(({ id }) => linked_node_ids.has(id))
    .map(({ balance, ...node }) => ({
      ...node,
      balance: balance[currency] ?? 0,
    }));

  return { currency, nodes, links };
}

const node_center = (node: SankeyLayoutNode) => (node.y0 + node.y1) / 2;

/** Position a graph while keeping every node in its semantic column. */
export function layout_sankey(
  graph: SankeyGraph,
  { width, height, node_width = 8, node_padding = 16 }: SankeyLayoutOptions,
): SankeyLayoutGraph {
  if (!graph.nodes.length) {
    return { currency: graph.currency, nodes: [], links: [] };
  }

  const initial = sankey<SankeyGraphNode, SankeyGraphLink>()
    .nodeId(({ id }) => id)
    .nodeWidth(Math.min(node_width, width))
    .nodePadding(node_padding)
    .size([width, height])({
    nodes: graph.nodes.map((node) => ({ ...node })),
    links: graph.links.map((link) => ({ ...link })),
  });
  const nodes = initial.nodes as SankeyLayoutNode[];
  const links = initial.links as SankeyLayoutLink[];
  const columns = new Map<number, SankeyLayoutNode[]>();
  for (const node of nodes) {
    const column = columns.get(node.column);
    if (column) {
      column.push(node);
    } else {
      columns.set(node.column, [node]);
    }
  }
  const max_column = Math.max(...columns.keys());
  const max_nodes_in_column = Math.max(
    ...[...columns.values()].map((column) => column.length),
  );
  const padding_slots = max_nodes_in_column - 1;
  const padding =
    padding_slots > 0
      ? Math.min(node_padding, height / (padding_slots * 2))
      : 0;
  const scale = Math.min(
    ...[...columns.values()].map((column) => {
      const value = column.reduce((sum, node) => sum + node.value, 0);
      const available = height - padding * (column.length - 1);
      return value > 0 ? available / value : 0;
    }),
  );
  const column_width =
    max_column > 0 ? (width - Math.min(node_width, width)) / max_column : 0;

  for (const [column_index, column] of columns) {
    column.sort((a, b) => a.y0 - b.y0 || a.id.localeCompare(b.id));
    const used_height =
      column.reduce((sum, node) => sum + node.value * scale, 0) +
      padding * (column.length - 1);
    let y = (height - used_height) / 2;
    for (const node of column) {
      node.x0 = column_index * column_width;
      node.x1 = node.x0 + Math.min(node_width, width);
      node.y0 = y;
      node.y1 = y + node.value * scale;
      y = node.y1 + padding;
    }
  }

  for (const link of links) {
    link.width = link.value * scale;
  }
  for (const node of nodes) {
    node.sourceLinks.sort(
      (a, b) =>
        node_center(a.target) - node_center(b.target) ||
        a.target.id.localeCompare(b.target.id),
    );
    node.targetLinks.sort(
      (a, b) =>
        node_center(a.source) - node_center(b.source) ||
        a.source.id.localeCompare(b.source.id),
    );

    let source_y =
      node.y0 +
      (node.y1 -
        node.y0 -
        node.sourceLinks.reduce((sum, link) => sum + link.width, 0)) /
        2;
    for (const link of node.sourceLinks) {
      link.y0 = source_y + link.width / 2;
      source_y += link.width;
    }

    let target_y =
      node.y0 +
      (node.y1 -
        node.y0 -
        node.targetLinks.reduce((sum, link) => sum + link.width, 0)) /
        2;
    for (const link of node.targetLinks) {
      link.y1 = target_y + link.width / 2;
      target_y += link.width;
    }
  }

  return { currency: graph.currency, nodes, links };
}

/** Build a horizontal curve and arrow position for a directed link. */
export function sankey_link_geometry(
  link: SankeyLayoutLink,
): SankeyLinkGeometry {
  const forward = link.source.x0 < link.target.x0;
  const source_x = forward ? link.source.x1 : link.source.x0;
  const target_x = forward ? link.target.x0 : link.target.x1;
  const middle_x = (source_x + target_x) / 2;
  const middle_y = (link.y0 + link.y1) / 2;
  const tangent_x = (target_x - source_x) * 0.75;
  const tangent_y = (link.y1 - link.y0) * 1.5;

  return {
    path: `M${source_x.toString()},${link.y0.toString()}C${middle_x.toString()},${link.y0.toString()},${middle_x.toString()},${link.y1.toString()},${target_x.toString()},${link.y1.toString()}`,
    direction: forward ? "forward" : "backward",
    arrow: {
      x: middle_x,
      y: middle_y,
      angle: (Math.atan2(tangent_y, tangent_x) * 180) / Math.PI,
    },
  };
}

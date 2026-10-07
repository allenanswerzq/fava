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
  /** Preserve the full branch width when descendants are hidden. */
  fixedValue?: number;
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

/** Expansion metadata for one visible account branch. */
export interface SankeyBranch {
  expanded: boolean;
  hidden_accounts: number;
}

/** A graph filtered to its currently expanded account branches. */
export interface SankeyGraphView {
  graph: SankeyGraph;
  branches: ReadonlyMap<string, SankeyBranch>;
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
  max_column?: number;
}

/** Geometry for a directed link path. */
export interface SankeyLinkGeometry {
  path: string;
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

function compare_order_paths(
  left: readonly number[],
  right: readonly number[],
): number {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const difference = (left[index] ?? 0) - (right[index] ?? 0);
    if (difference !== 0) {
      return difference;
    }
  }
  return left.length - right.length;
}

interface SankeyHierarchy {
  parent: Map<string, string>;
  children: Map<string, SankeyGraphNode[]>;
  roots: SankeyGraphNode[];
}

function sankey_hierarchy(graph: SankeyGraph): SankeyHierarchy {
  const account_ids = new Map(
    graph.nodes.flatMap((node) =>
      node.account == null ? [] : [[node.account, node.id] as const],
    ),
  );
  const parent = new Map<string, string>();
  const children = new Map<string, SankeyGraphNode[]>();
  for (const node of graph.nodes) {
    if (node.account == null) {
      continue;
    }
    let account = node.account;
    while (account.includes(":")) {
      account = account.slice(0, account.lastIndexOf(":"));
      const parent_id = account_ids.get(account);
      if (parent_id != null) {
        parent.set(node.id, parent_id);
        const siblings = children.get(parent_id);
        if (siblings) {
          siblings.push(node);
        } else {
          children.set(parent_id, [node]);
        }
        break;
      }
    }
  }
  return {
    parent,
    children,
    roots: graph.nodes.filter(({ id }) => !parent.has(id)),
  };
}

function sankey_node_flow(graph: SankeyGraph): Map<string, number> {
  const incoming = new Map(graph.nodes.map(({ id }) => [id, 0]));
  const outgoing = new Map(graph.nodes.map(({ id }) => [id, 0]));
  for (const link of graph.links) {
    outgoing.set(link.source, (outgoing.get(link.source) ?? 0) + link.value);
    incoming.set(link.target, (incoming.get(link.target) ?? 0) + link.value);
  }
  return new Map(
    graph.nodes.map(({ id }) => [
      id,
      Math.max(incoming.get(id) ?? 0, outgoing.get(id) ?? 0),
    ]),
  );
}

/** Choose the most valuable branches that fit within a column node budget. */
export function sankey_default_expanded_nodes(
  graph: SankeyGraph,
  max_nodes_per_column = 12,
): Set<string> {
  const hierarchy = sankey_hierarchy(graph);
  const flow = sankey_node_flow(graph);
  const column_counts = new Map<number, number>();
  for (const node of hierarchy.roots) {
    column_counts.set(node.column, (column_counts.get(node.column) ?? 0) + 1);
  }
  const budget = Math.max(1, Math.floor(max_nodes_per_column));
  const candidates = hierarchy.roots.filter((node) =>
    hierarchy.children.has(node.id),
  );
  const expanded = new Set<string>();
  const sort_candidates = () => {
    candidates.sort(
      (left, right) =>
        (flow.get(right.id) ?? 0) - (flow.get(left.id) ?? 0) ||
        left.id.localeCompare(right.id),
    );
  };
  sort_candidates();

  while (candidates.length > 0) {
    const node = candidates.shift();
    if (node == null) {
      break;
    }
    const children = hierarchy.children.get(node.id) ?? [];
    const additions = new Map<number, number>();
    for (const child of children) {
      additions.set(child.column, (additions.get(child.column) ?? 0) + 1);
    }
    const fits = [...additions].every(
      ([column, count]) => (column_counts.get(column) ?? 0) + count <= budget,
    );
    if (!fits) {
      continue;
    }
    expanded.add(node.id);
    for (const [column, count] of additions) {
      column_counts.set(column, (column_counts.get(column) ?? 0) + count);
    }
    candidates.push(
      ...children.filter((child) => hierarchy.children.has(child.id)),
    );
    sort_candidates();
  }
  return expanded;
}

/** Filter a Sankey graph to roots and descendants of expanded branches. */
export function sankey_graph_view(
  graph: SankeyGraph,
  expanded_nodes: ReadonlySet<string>,
): SankeyGraphView {
  const hierarchy = sankey_hierarchy(graph);
  const flow = sankey_node_flow(graph);
  const visible = new Set<string>();
  const visit = (node: SankeyGraphNode) => {
    visible.add(node.id);
    if (expanded_nodes.has(node.id)) {
      for (const child of hierarchy.children.get(node.id) ?? []) {
        visit(child);
      }
    }
  };
  for (const root of hierarchy.roots) {
    visit(root);
  }

  const descendant_counts = new Map<string, number>();
  const count_descendants = (id: string): number => {
    const cached = descendant_counts.get(id);
    if (cached != null) {
      return cached;
    }
    const count = (hierarchy.children.get(id) ?? []).reduce(
      (sum, child) => sum + 1 + count_descendants(child.id),
      0,
    );
    descendant_counts.set(id, count);
    return count;
  };
  const branches = new Map<string, SankeyBranch>();
  for (const node of graph.nodes) {
    const children = hierarchy.children.get(node.id) ?? [];
    if (visible.has(node.id) && children.length > 0) {
      branches.set(node.id, {
        expanded: expanded_nodes.has(node.id),
        hidden_accounts: count_descendants(node.id),
      });
    }
  }

  return {
    graph: {
      currency: graph.currency,
      nodes: graph.nodes.flatMap((node) => {
        if (!visible.has(node.id)) {
          return [];
        }
        const branch = branches.get(node.id);
        return branch != null && !branch.expanded
          ? [{ ...node, fixedValue: flow.get(node.id) ?? 0 }]
          : [node];
      }),
      links: graph.links.filter(
        ({ source, target }) => visible.has(source) && visible.has(target),
      ),
    },
    branches,
  };
}

/** Build a self-contained graph for inspecting one account subtree. */
export function sankey_focused_graph(
  graph: SankeyGraph,
  root_id: string,
): SankeyGraph {
  const hierarchy = sankey_hierarchy(graph);
  const visible = new Set<string>();
  const visit = (id: string) => {
    visible.add(id);
    for (const child of hierarchy.children.get(id) ?? []) {
      visit(child.id);
    }
  };
  visit(root_id);

  const nodes = graph.nodes.filter(({ id }) => visible.has(id));
  const min_column =
    nodes.length > 0 ? Math.min(...nodes.map(({ column }) => column)) : 0;
  return {
    currency: graph.currency,
    nodes: nodes.map((node) => ({
      ...node,
      column: node.column - min_column,
    })),
    links: graph.links.filter(
      ({ source, target }) => visible.has(source) && visible.has(target),
    ),
  };
}

/** Derive stable, hierarchy-aware order paths for all visible nodes. */
function sankey_order_paths(graph: SankeyGraph): Map<string, number[]> {
  const { parent, children } = sankey_hierarchy(graph);
  const flow = sankey_node_flow(graph);

  const compare_nodes = (left: SankeyGraphNode, right: SankeyGraphNode) =>
    (right.kind === "account" ? 1 : 0) - (left.kind === "account" ? 1 : 0) ||
    (flow.get(right.id) ?? 0) - (flow.get(left.id) ?? 0) ||
    left.id.localeCompare(right.id);
  for (const siblings of children.values()) {
    siblings.sort(compare_nodes);
  }

  const roots_by_column = new Map<number, SankeyGraphNode[]>();
  for (const node of graph.nodes) {
    if (!parent.has(node.id)) {
      const roots = roots_by_column.get(node.column);
      if (roots) {
        roots.push(node);
      } else {
        roots_by_column.set(node.column, [node]);
      }
    }
  }

  const paths = new Map<string, number[]>();
  const assign = (node: SankeyGraphNode, path: number[]) => {
    paths.set(node.id, path);
    for (const [index, child] of (children.get(node.id) ?? []).entries()) {
      assign(child, [...path, index]);
    }
  };
  for (const roots of roots_by_column.values()) {
    roots.sort(compare_nodes);
    for (const [index, root] of roots.entries()) {
      assign(root, [index]);
    }
  }
  return paths;
}

function move_node(node: SankeyLayoutNode, offset: number): void {
  node.y0 += offset;
  node.y1 += offset;
}

function resolve_column_collisions(
  column: SankeyLayoutNode[],
  height: number,
  padding: number,
): void {
  let next_y = 0;
  for (const node of column) {
    if (node.y0 < next_y) {
      move_node(node, next_y - node.y0);
    }
    next_y = node.y1 + padding;
  }

  next_y = height;
  for (const node of [...column].reverse()) {
    if (node.y1 > next_y) {
      move_node(node, next_y - node.y1);
    }
    next_y = node.y0 - padding;
  }
}

/** Align parents with their child groups while preserving hierarchy order. */
function relax_columns(
  columns: Map<number, SankeyLayoutNode[]>,
  height: number,
  padding: number,
): void {
  const ordered_columns = [...columns.entries()]
    .sort(([left], [right]) => left - right)
    .map(([, column]) => column);
  for (let iteration = 0; iteration < 8; iteration += 1) {
    const alpha = 0.55 * (1 - iteration / 10);
    const sweep =
      iteration % 2 === 0 ? ordered_columns : [...ordered_columns].reverse();
    for (const column of sweep) {
      for (const node of column) {
        let weighted_center = 0;
        let total_weight = 0;
        for (const link of [...node.sourceLinks, ...node.targetLinks]) {
          const neighbour = link.source === node ? link.target : link.source;
          if (neighbour.column === node.column) {
            continue;
          }
          weighted_center += node_center(neighbour) * link.value;
          total_weight += link.value;
        }
        if (total_weight > 0) {
          move_node(
            node,
            (weighted_center / total_weight - node_center(node)) * alpha,
          );
        }
      }
      resolve_column_collisions(column, height, padding);
    }
  }
}

/** Position a graph while keeping every node in its semantic column. */
export function layout_sankey(
  graph: SankeyGraph,
  {
    width,
    height,
    node_width = 8,
    node_padding = 16,
    max_column: requested_max_column,
  }: SankeyLayoutOptions,
): SankeyLayoutGraph {
  if (!graph.nodes.length) {
    return { currency: graph.currency, nodes: [], links: [] };
  }

  const order_paths = sankey_order_paths(graph);
  const initial = sankey<SankeyGraphNode, SankeyGraphLink>()
    .nodeId(({ id }) => id)
    .nodeWidth(Math.min(node_width, width))
    .nodePadding(node_padding)
    .nodeSort((left, right) =>
      compare_order_paths(
        order_paths.get(left.id) ?? [],
        order_paths.get(right.id) ?? [],
      ),
    )
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
  const max_column = Math.max(requested_max_column ?? 0, ...columns.keys());
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
    column.sort(
      (left, right) =>
        compare_order_paths(
          order_paths.get(left.id) ?? [],
          order_paths.get(right.id) ?? [],
        ) || left.id.localeCompare(right.id),
    );
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

  relax_columns(columns, height, padding);

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

/** Build a horizontal curve for a directed link. */
export function sankey_link_geometry(
  link: SankeyLayoutLink,
): SankeyLinkGeometry {
  const forward = link.source.x0 < link.target.x0;
  const source_x = forward ? link.source.x1 : link.source.x0;
  const target_x = forward ? link.target.x0 : link.target.x1;
  const middle_x = (source_x + target_x) / 2;

  return {
    path: `M${source_x.toString()},${link.y0.toString()}C${middle_x.toString()},${link.y0.toString()},${middle_x.toString()},${link.y1.toString()},${target_x.toString()},${link.y1.toString()}`,
  };
}

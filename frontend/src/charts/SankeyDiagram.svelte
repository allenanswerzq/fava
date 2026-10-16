<script lang="ts">
  import { untrack } from "svelte";

  import { url_for_account } from "../helpers.ts";
  import { _, format } from "../i18n.ts";
  import { leaf } from "../lib/account.ts";
  import { ctx } from "../stores/format.ts";
  import { get_chart_tooltip } from "./context.ts";
  import { sunburst_scale } from "./helpers.ts";
  import {
    layout_sankey,
    type SankeyBranch,
    type SankeyGraph,
    type SankeyGraphNode,
    type SankeyLayoutLink,
    type SankeyLayoutNode,
    sankey_link_geometry,
  } from "./sankey.ts";
  import type { Tooltip } from "./tooltip.ts";

  const DEFAULT_OVERVIEW_HEIGHT = 320;
  const MIN_OUTER_LABEL_SPACE = 12;
  const MAX_OUTER_LABEL_SPACE = 200;
  const LABEL_PADDING = 16;
  const LABEL_OFFSET = 7;
  const BRANCH_LABEL_OFFSET = 30;
  const MIN_FLOW_TARGET_WIDTH = 16;

  interface Props {
    graph: SankeyGraph;
    width: number;
    height?: number | undefined;
    max_column?: number | undefined;
    branches?: ReadonlyMap<string, SankeyBranch>;
    node_label?: ((node: SankeyGraphNode) => string) | undefined;
    role_labels?: Readonly<Record<string, string>>;
    tooltip?: Tooltip | undefined;
    compact?: boolean;
    hidden_node_labels?: ReadonlySet<string>;
    inspect_branch?:
      | ((
          node: SankeyGraphNode,
          anchor: {
            trigger: SVGElement;
            left: number;
            right: number;
            top: number;
            bottom: number;
          },
        ) => void)
      | undefined;
  }

  let {
    graph,
    width,
    height: requested_height,
    max_column: requested_max_column,
    branches = new Map(),
    node_label,
    role_labels = {},
    tooltip: provided_tooltip,
    compact = false,
    hidden_node_labels = new Set(),
    inspect_branch,
  }: Props = $props();

  const tooltip = untrack(() => provided_tooltip) ?? get_chart_tooltip();
  let max_column = $derived(
    requested_max_column ??
      Math.max(0, ...graph.nodes.map((node) => node.column)),
  );
  function estimated_label_width(value: string): number {
    let width = 0;
    for (const character of value) {
      if ("ilIjtfr".includes(character)) {
        width += 3.5;
      } else if ("mwMW".includes(character)) {
        width += 9.5;
      } else if (/[A-Z]/.test(character)) {
        width += 7.5;
      } else if (/[0-9]/.test(character)) {
        width += 6.5;
      } else if (character === " ") {
        width += 3.5;
      } else {
        width += 6;
      }
    }
    return width;
  }

  let outer_label_space = $derived.by(() => {
    let left = MIN_OUTER_LABEL_SPACE;
    let right = MIN_OUTER_LABEL_SPACE;
    for (const node of graph.nodes) {
      if (hidden_node_labels.has(node.id)) {
        continue;
      }
      const branch_offset =
        branches.has(node.id) && inspect_branch
          ? BRANCH_LABEL_OFFSET
          : LABEL_OFFSET;
      const required = Math.ceil(
        estimated_label_width(label(node)) + branch_offset + LABEL_PADDING,
      );
      if (max_column === 0 || node.column === max_column) {
        right = Math.max(right, required);
      } else if (node.column === 0) {
        left = Math.max(left, required);
      }
    }
    return {
      left: Math.min(MAX_OUTER_LABEL_SPACE, left),
      right: Math.min(MAX_OUTER_LABEL_SPACE, right),
    };
  });
  let margin = $derived(
    compact
      ? { top: 12, right: 12, bottom: 12, left: 12 }
      : {
          top: 20,
          right: outer_label_space.right,
          bottom: 20,
          left: outer_label_space.left,
        },
  );
  let chart_width = $derived(
    Math.max(
      width,
      margin.left + margin.right + Math.max(1, max_column) * 150 + 10,
    ),
  );
  let height = $derived(requested_height ?? DEFAULT_OVERVIEW_HEIGHT);
  let inner_width = $derived(
    Math.max(1, chart_width - margin.left - margin.right),
  );
  let inner_height = $derived(Math.max(1, height - margin.top - margin.bottom));
  let layout = $derived(
    layout_sankey(graph, {
      width: inner_width,
      height: inner_height,
      node_width: 10,
      node_padding: 20,
      max_column,
    }),
  );
  let incoming_links = $derived(
    Map.groupBy(layout.links, ({ target }) => target.id),
  );
  let outgoing_links = $derived(
    Map.groupBy(layout.links, ({ source }) => source.id),
  );

  function label(node: SankeyGraphNode): string {
    if (node_label) {
      return node_label(node);
    }
    if (node.account != null && node.account !== "") {
      return leaf(node.account);
    }
    if (node.role != null && node.role !== "") {
      return role_labels[node.role] ?? node.role.replaceAll("_", " ");
    }
    return node.id;
  }

  function label_after_node(node: SankeyLayoutNode): boolean {
    if (compact) {
      if (node.column === 0) {
        return true;
      }
      if (node.column === max_column) {
        return false;
      }
    }
    if (max_column === 0) {
      return true;
    }
    if (node.column === 0) {
      return false;
    }
    if (node.column === max_column) {
      return true;
    }
    return node.column > max_column / 2;
  }

  function inspect_from_keyboard(
    event: KeyboardEvent,
    node: SankeyGraphNode,
  ): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      inspect(node, event.currentTarget);
    }
  }

  function inspect(node: SankeyGraphNode, target: EventTarget | null): void {
    if (!(target instanceof SVGElement)) {
      return;
    }
    const bounds = target.getBoundingClientRect();
    const node_bounds =
      target.previousElementSibling
        ?.querySelector("rect.node")
        ?.getBoundingClientRect() ?? bounds;
    inspect_branch?.(node, {
      trigger: target,
      left: node_bounds.left,
      right: node_bounds.right,
      top: node_bounds.top,
      bottom: node_bounds.bottom,
    });
  }

  const link_tooltip = (link: SankeyLayoutLink) => [
    $ctx.amount(link.value, graph.currency),
    document.createElement("br"),
    `${link.source.account ?? label(link.source)} → ${link.target.account ?? label(link.target)}`,
  ];

  function node_tooltip(node: SankeyLayoutNode): (Node | string)[] {
    const content: (Node | string)[] = [
      $ctx.amount(node.balance, graph.currency),
      document.createElement("br"),
      node.account ?? label(node),
    ];
    for (const link of incoming_links.get(node.id) ?? []) {
      content.push(
        document.createElement("br"),
        `← ${label(link.source)}: ${$ctx.amount(link.value, graph.currency)}`,
      );
    }
    for (const link of outgoing_links.get(node.id) ?? []) {
      content.push(
        document.createElement("br"),
        `→ ${label(link.target)}: ${$ctx.amount(link.value, graph.currency)}`,
      );
    }
    return content;
  }
</script>

<div class="scroll">
  <svg
    width={chart_width}
    {height}
    viewBox={`0 0 ${chart_width.toString()} ${height.toString()}`}
    role="img"
    aria-label={format(_("Sankey diagram for %(currency)s"), {
      currency: graph.currency,
    })}
  >
    {#if layout.nodes.length === 0}
      <text x={chart_width / 2} y={height / 2} text-anchor="middle">
        {_("Chart is empty.")}
      </text>
    {:else}
      <g
        transform={`translate(${margin.left.toString()},${margin.top.toString()})`}
      >
        <g class="links">
          {#each layout.links as link (`${link.source.id}:${link.target.id}`)}
            {@const geometry = sankey_link_geometry(link)}
            <g class="link">
              <path
                class="flow"
                d={geometry.path}
                stroke={$sunburst_scale(link.source.account ?? link.source.id)}
                stroke-width={link.width}
              />
              <path
                class="flow-target"
                d={geometry.path}
                stroke-width={Math.max(MIN_FLOW_TARGET_WIDTH, link.width)}
                aria-hidden="true"
                {@attach tooltip.following(() => link_tooltip(link))}
              />
            </g>
          {/each}
        </g>
        <g class="nodes">
          {#each layout.nodes as node (node.id)}
            {@const label_after = label_after_node(node)}
            {@const branch = branches.get(node.id)}
            {@const inspectable = branch != null}
            {@const label_offset = inspectable
              ? BRANCH_LABEL_OFFSET
              : LABEL_OFFSET}
            {#if node.account != null && node.account !== ""}
              <g {@attach tooltip.following(() => node_tooltip(node))}>
                <a
                  href={$url_for_account(node.account)}
                  aria-label={node.account}
                >
                  <rect
                    class="node"
                    fill={$sunburst_scale(node.account)}
                    x={node.x0}
                    y={node.y0}
                    width={node.x1 - node.x0}
                    height={node.y1 - node.y0}
                  />
                  {#if !hidden_node_labels.has(node.id)}
                    <text
                      x={label_after
                        ? node.x1 + label_offset
                        : node.x0 - label_offset}
                      y={(node.y0 + node.y1) / 2}
                      text-anchor={label_after ? "start" : "end"}
                      dominant-baseline="middle">{label(node)}</text
                    >
                  {/if}
                </a>
              </g>
            {:else}
              <g {@attach tooltip.following(() => node_tooltip(node))}>
                <rect
                  class="node"
                  fill={$sunburst_scale(node.id)}
                  x={node.x0}
                  y={node.y0}
                  width={node.x1 - node.x0}
                  height={node.y1 - node.y0}
                />
                {#if !hidden_node_labels.has(node.id)}
                  <text
                    x={label_after ? node.x1 + 7 : node.x0 - 7}
                    y={(node.y0 + node.y1) / 2}
                    text-anchor={label_after ? "start" : "end"}
                    dominant-baseline="middle">{label(node)}</text
                  >
                {/if}
              </g>
            {/if}
            {#if inspectable && inspect_branch}
              <text
                class="branch-inspect"
                x={label_after ? node.x1 + 7 : node.x0 - 7}
                y={(node.y0 + node.y1) / 2}
                text-anchor={label_after ? "start" : "end"}
                dominant-baseline="middle"
                role="button"
                tabindex="0"
                aria-haspopup="dialog"
                aria-label={format(_("Inspect %(account)s"), {
                  account: label(node),
                })}
                onclick={(event) => {
                  inspect(node, event.currentTarget);
                }}
                onkeydown={(event) => {
                  inspect_from_keyboard(event, node);
                }}
                {@attach tooltip.following(() => node_tooltip(node))}
                >+{branch.hidden_accounts}</text
              >
            {/if}
          {/each}
        </g>
      </g>
    {/if}
  </svg>
</div>

<style>
  .scroll {
    max-width: 100%;
    overflow-x: auto;
  }

  svg {
    display: block;
    max-width: none;
  }

  .flow {
    pointer-events: none;
    opacity: 0.32;
    fill: none;
    stroke-linecap: butt;
    transition: opacity 100ms ease;
  }

  .link:hover .flow {
    opacity: 0.65;
  }

  .flow-target {
    pointer-events: stroke;
    fill: none;
    stroke: transparent;
  }

  .node {
    stroke: var(--background);
    stroke-width: 1px;
  }

  .branch-inspect {
    cursor: pointer;
    fill: var(--link-color);
  }

  .branch-inspect:hover,
  .branch-inspect:focus {
    fill: var(--link-hover-color);
  }

  text {
    font-size: 12px;
    fill: var(--text-color);
    stroke: var(--background);
    stroke-width: 2px;
    stroke-linejoin: round;
    paint-order: stroke;
  }

  a:hover text,
  a:focus text {
    fill: var(--link-hover-color);
  }

  a {
    text-decoration: none;
  }
</style>

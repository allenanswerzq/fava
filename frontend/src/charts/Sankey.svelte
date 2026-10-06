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
    type SankeyData,
    type SankeyLayoutLink,
    type SankeyLayoutNode,
    sankey_graph_for_currency,
    sankey_link_geometry,
  } from "./sankey.ts";
  import type { Tooltip } from "./tooltip.ts";

  interface Props {
    data: SankeyData;
    currency: string;
    width: number;
    height?: number;
    node_label?: (node: SankeyLayoutNode) => string;
    role_labels?: Readonly<Record<string, string>>;
    tooltip?: Tooltip;
  }

  let {
    data,
    currency,
    width,
    height: requested_height,
    node_label,
    role_labels = {},
    tooltip: provided_tooltip,
  }: Props = $props();

  const tooltip = untrack(() => provided_tooltip) ?? get_chart_tooltip();
  let graph = $derived(sankey_graph_for_currency(data, currency));
  let max_column = $derived(
    Math.max(0, ...graph.nodes.map((node) => node.column)),
  );
  let max_nodes_in_column = $derived(
    Math.max(
      0,
      ...Array.from(
        { length: max_column + 1 },
        (_, column) =>
          graph.nodes.filter((node) => node.column === column).length,
      ),
    ),
  );
  let outer_label_lengths = $derived.by(() => {
    let left = 0;
    let right = 0;
    for (const node of graph.nodes) {
      if (node.column === 0) {
        left = Math.max(left, label(node).length);
      }
      if (node.column === max_column) {
        right = Math.max(right, label(node).length);
      }
    }
    return { left, right };
  });
  let margin = $derived({
    top: 20,
    right: Math.min(180, Math.max(64, outer_label_lengths.right * 7 + 16)),
    bottom: 20,
    left: Math.min(180, Math.max(64, outer_label_lengths.left * 7 + 16)),
  });
  let chart_width = $derived(
    Math.max(
      width,
      margin.left + margin.right + Math.max(1, max_column) * 150 + 10,
    ),
  );
  let height = $derived(
    requested_height ?? Math.max(360, max_nodes_in_column * 36 + 40),
  );
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
    }),
  );

  function label(node: SankeyLayoutNode): string {
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
    if (node.column === 0) {
      return true;
    }
    if (node.column === max_column) {
      return false;
    }
    return node.column > max_column / 2;
  }

  function arrow_path(link: SankeyLayoutLink): string {
    const size = Math.max(4, Math.min(8, link.width / 3));
    return `M${(-size).toString()},${(-size).toString()}L0,0L${(-size).toString()},${size.toString()}`;
  }

  const link_tooltip = (link: SankeyLayoutLink) => [
    $ctx.amount(link.value, currency),
    document.createElement("br"),
    `${label(link.source)} → ${label(link.target)}`,
  ];

  const node_tooltip = (node: SankeyLayoutNode) => [
    $ctx.amount(node.balance, currency),
    document.createElement("br"),
    node.account ?? label(node),
  ];
</script>

<div class="scroll">
  <svg
    width={chart_width}
    {height}
    viewBox={`0 0 ${chart_width.toString()} ${height.toString()}`}
    role="img"
    aria-label={format(_("Sankey diagram for %(currency)s"), { currency })}
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
            <path
              class="flow"
              d={geometry.path}
              stroke={$sunburst_scale(link.source.account ?? link.source.id)}
              stroke-width={link.width}
              data-direction={geometry.direction}
              {@attach tooltip.following(() => link_tooltip(link))}
            />
          {/each}
        </g>
        <g class="arrows" aria-hidden="true">
          {#each layout.links as link (`${link.source.id}:${link.target.id}`)}
            {@const geometry = sankey_link_geometry(link)}
            <path
              d={arrow_path(link)}
              transform={`translate(${geometry.arrow.x.toString()},${geometry.arrow.y.toString()}) rotate(${geometry.arrow.angle.toString()})`}
            />
          {/each}
        </g>
        <g class="nodes">
          {#each layout.nodes as node (node.id)}
            {@const label_after = label_after_node(node)}
            {#if node.account != null && node.account !== ""}
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
                  {@attach tooltip.following(() => node_tooltip(node))}
                />
                <text
                  x={label_after ? node.x1 + 7 : node.x0 - 7}
                  y={(node.y0 + node.y1) / 2}
                  text-anchor={label_after ? "start" : "end"}
                  dominant-baseline="middle">{label(node)}</text
                >
              </a>
            {:else}
              <g>
                <rect
                  class="node"
                  fill={$sunburst_scale(node.id)}
                  x={node.x0}
                  y={node.y0}
                  width={node.x1 - node.x0}
                  height={node.y1 - node.y0}
                  {@attach tooltip.following(() => node_tooltip(node))}
                />
                <text
                  x={label_after ? node.x1 + 7 : node.x0 - 7}
                  y={(node.y0 + node.y1) / 2}
                  text-anchor={label_after ? "start" : "end"}
                  dominant-baseline="middle">{label(node)}</text
                >
              </g>
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
    opacity: 0.32;
    fill: none;
    stroke-linecap: butt;
  }

  .arrows path {
    fill: none;
    stroke: var(--text-color);
    stroke-width: 2px;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .arrows {
    pointer-events: none;
  }

  .node {
    stroke: var(--background);
    stroke-width: 1px;
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

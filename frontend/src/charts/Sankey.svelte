<script lang="ts">
  import { tick, untrack } from "svelte";

  import { _, format } from "../i18n.ts";
  import { leaf } from "../lib/account.ts";
  import { get_chart_tooltip } from "./context.ts";
  import { sunburst_scale } from "./helpers.ts";
  import SankeyDiagram from "./SankeyDiagram.svelte";
  import {
    type SankeyData,
    type SankeyGraphNode,
    sankey_default_expanded_nodes,
    sankey_focused_graph,
    sankey_graph_for_currency,
    sankey_graph_view,
  } from "./sankey.ts";
  import type { Tooltip } from "./tooltip.ts";

  interface Props {
    data: SankeyData;
    currency: string;
    width: number;
    height?: number;
    max_nodes_per_column?: number;
    node_label?: (node: SankeyGraphNode) => string;
    role_labels?: Readonly<Record<string, string>>;
    tooltip?: Tooltip;
  }

  interface BranchAnchor {
    trigger: SVGElement;
    left: number;
    right: number;
    top: number;
    bottom: number;
  }

  interface FocusPosition {
    left: number;
    top: number;
    width: number;
    height: number;
    diagram_height: number;
    connector: {
      start_x: number;
      start_y: number;
      end_x: number;
      end_y: number;
    };
  }

  let {
    data,
    currency,
    width,
    height,
    max_nodes_per_column = 12,
    node_label,
    role_labels = {},
    tooltip: provided_tooltip,
  }: Props = $props();

  const tooltip = untrack(() => provided_tooltip) ?? get_chart_tooltip();
  let graph = $derived(sankey_graph_for_currency(data, currency));
  let graph_key = $derived(JSON.stringify({ graph, max_nodes_per_column }));
  let focused_graph_key = $state("");
  let focused_node_id: string | null = $state(null);
  let focus_mirrored = $state(false);
  let chart_container: HTMLDivElement | undefined = $state();
  let close_button: HTMLButtonElement | undefined = $state();
  let focus_trigger: SVGElement | undefined;
  let focus_position: FocusPosition = $state({
    left: 16,
    top: 16,
    width: 340,
    height: 180,
    diagram_height: 140,
    connector: { start_x: 0, start_y: 0, end_x: 0, end_y: 0 },
  });

  $effect(() => {
    if (graph_key !== focused_graph_key) {
      focused_graph_key = graph_key;
      focused_node_id = null;
      focus_mirrored = false;
      focus_trigger = undefined;
    }
  });

  $effect(() => {
    if (focused_node_id != null && close_button) {
      close_button.focus();
    }
  });

  let expanded_nodes = $derived(
    sankey_default_expanded_nodes(graph, max_nodes_per_column),
  );
  let graph_view = $derived(sankey_graph_view(graph, expanded_nodes));
  let max_column = $derived(
    Math.max(0, ...graph.nodes.map((node) => node.column)),
  );
  let focused_node = $derived(
    focused_node_id == null
      ? null
      : (graph.nodes.find(({ id }) => id === focused_node_id) ?? null),
  );
  let focused_graph = $derived(
    focused_node_id == null
      ? null
      : sankey_focused_graph(graph, focused_node_id),
  );
  let displayed_focused_graph = $derived.by(() => {
    if (focused_graph == null || !focus_mirrored) {
      return focused_graph;
    }
    const focused_max_column = Math.max(
      0,
      ...focused_graph.nodes.map(({ column }) => column),
    );
    return {
      ...focused_graph,
      nodes: focused_graph.nodes.map((focused_node) => ({
        ...focused_node,
        column: focused_max_column - focused_node.column,
      })),
    };
  });
  let hidden_focused_labels = $derived(
    new Set(focused_node_id == null ? [] : [focused_node_id]),
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

  function inspect_branch(node: SankeyGraphNode, anchor: BranchAnchor): void {
    const bounds = chart_container?.getBoundingClientRect();
    if (!bounds) {
      return;
    }
    const container_width = bounds.width || width;
    const container_height =
      bounds.height ||
      Number(chart_container?.querySelector("svg")?.getAttribute("height")) ||
      360;
    const focus_graph = sankey_focused_graph(graph, node.id);
    const focus_root = focus_graph.nodes.find(({ id }) => id === node.id);
    const root_column = focus_root?.column ?? 0;
    const min_column = Math.min(
      root_column,
      ...focus_graph.nodes.map(({ column }) => column),
    );
    const max_column = Math.max(
      root_column,
      ...focus_graph.nodes.map(({ column }) => column),
    );
    const left_depth = root_column - min_column;
    const right_depth = max_column - root_column;
    const preferred_direction: "left" | "right" =
      right_depth >= left_depth ? "right" : "left";
    const has_node_bounds = anchor.right > anchor.left;
    const node_left = has_node_bounds
      ? anchor.left - bounds.left
      : container_width / 2 - 5;
    const node_right = has_node_bounds
      ? anchor.right - bounds.left
      : container_width / 2 + 5;
    const node_y = has_node_bounds
      ? (anchor.top + anchor.bottom) / 2 - bounds.top
      : container_height / 2;
    const available = {
      left: node_left - 24,
      right: container_width - node_right - 24,
    };
    const column_span = Math.max(1, max_column - min_column);
    const desired_width = Math.min(620, Math.max(340, column_span * 150 + 80));
    const other_direction: "left" | "right" =
      preferred_direction === "right" ? "left" : "right";
    const direction =
      available[preferred_direction] >= Math.min(280, desired_width)
        ? preferred_direction
        : other_direction;
    const overlay_width = Math.min(
      desired_width,
      Math.max(1, container_width - 32),
      Math.max(180, available[direction]),
    );
    const column_counts = Map.groupBy(
      focus_graph.nodes,
      ({ column }) => column,
    );
    const max_nodes = Math.max(
      1,
      ...[...column_counts.values()].map((nodes) => nodes.length),
    );
    const diagram_height = Math.max(140, max_nodes * 36 + 24);
    const overlay_height = Math.min(
      Math.max(1, container_height - 32),
      Math.max(150, Math.min(diagram_height + 56, 380)),
    );
    const preferred_left =
      direction === "right" ? node_right + 18 : node_left - overlay_width - 18;
    const left = Math.max(
      16,
      Math.min(preferred_left, container_width - overlay_width - 16),
    );
    const top = Math.max(
      16,
      Math.min(
        node_y - overlay_height / 2,
        container_height - overlay_height - 16,
      ),
    );
    focus_position = {
      left,
      top,
      width: overlay_width,
      height: overlay_height,
      diagram_height,
      connector: {
        start_x: direction === "right" ? node_right : node_left,
        start_y: node_y,
        end_x: direction === "right" ? left : left + overlay_width,
        end_y: top + overlay_height / 2,
      },
    };
    focus_mirrored = direction !== preferred_direction;
    focus_trigger = anchor.trigger;
    focused_node_id = node.id;
  }

  function close_focus(): void {
    focused_node_id = null;
    focus_mirrored = false;
    const trigger = focus_trigger;
    focus_trigger = undefined;
    void tick().then(() => {
      if (trigger?.isConnected === true) {
        trigger.focus();
      }
    });
  }

  function connector_path(): string {
    const { start_x, start_y, end_x, end_y } = focus_position.connector;
    const middle_x = (start_x + end_x) / 2;
    return `M${start_x.toString()},${start_y.toString()}C${middle_x.toString()},${start_y.toString()},${middle_x.toString()},${end_y.toString()},${end_x.toString()},${end_y.toString()}`;
  }
</script>

<svelte:window
  onkeydown={(event: KeyboardEvent) => {
    if (focused_node_id != null && event.key === "Escape") {
      close_focus();
    }
  }}
/>

<div class="chart-container" bind:this={chart_container}>
  <div class="overview">
    <SankeyDiagram
      graph={graph_view.graph}
      {width}
      {height}
      {max_column}
      branches={graph_view.branches}
      {node_label}
      {role_labels}
      {tooltip}
      {inspect_branch}
    />
  </div>

  {#if focused_node && displayed_focused_graph}
    <button
      type="button"
      class="backdrop"
      tabindex="-1"
      aria-label={_("Close details")}
      onclick={close_focus}
    ></button>
    <svg class="connector" aria-hidden="true">
      <path
        d={connector_path()}
        stroke={$sunburst_scale(focused_node.account ?? focused_node.id)}
      />
    </svg>
    <div
      class="focus"
      role="dialog"
      aria-label={format(_("Details for %(account)s"), {
        account: label(focused_node),
      })}
      style:left={`${focus_position.left.toString()}px`}
      style:top={`${focus_position.top.toString()}px`}
      style:width={`${focus_position.width.toString()}px`}
      style:height={`${focus_position.height.toString()}px`}
    >
      <div class="focus-header">
        <div>
          <h3>
            {format(_("Details for %(account)s"), {
              account: label(focused_node),
            })}
          </h3>
          {#if focused_node.account}
            <p class="account">{focused_node.account}</p>
          {/if}
        </div>
        <button
          type="button"
          class="close"
          bind:this={close_button}
          aria-label={_("Close details")}
          onclick={close_focus}>×</button
        >
      </div>
      <div class="focus-chart">
        <SankeyDiagram
          graph={displayed_focused_graph}
          width={Math.max(1, focus_position.width - 2)}
          height={focus_position.diagram_height}
          {node_label}
          {role_labels}
          {tooltip}
          compact={true}
          hidden_node_labels={hidden_focused_labels}
        />
      </div>
    </div>
  {/if}
</div>

<style>
  .chart-container {
    position: relative;
  }

  .backdrop {
    position: absolute;
    z-index: 1;
    inset: 0;
    padding: 0;
    background: transparent;
    border: 0;
    cursor: default;
  }

  .connector {
    position: absolute;
    z-index: 2;
    inset: 0;
    width: 100%;
    height: 100%;
    overflow: visible;
    pointer-events: none;
  }

  .connector path {
    opacity: 0.8;
    fill: none;
    stroke-linecap: round;
    stroke-width: 3px;
  }

  .focus {
    position: absolute;
    z-index: 3;
    display: flex;
    flex-direction: column;
    min-width: 0;
    max-width: calc(100% - 32px);
    max-height: calc(100% - 32px);
    overflow: hidden;
    background: var(--background);
    border: thin solid var(--sidebar-border);
    border-radius: 3px;
    box-shadow: var(--box-shadow-overlay);
  }

  .focus-header {
    display: flex;
    flex: none;
    align-items: start;
    justify-content: space-between;
    gap: 1em;
    min-height: 34px;
    padding: 0.4em 0.6em;
  }

  h3 {
    margin: 0;
    font-size: 0.95em;
  }

  .account {
    margin: 0.1em 0 0;
    color: var(--text-color-muted);
    font-size: 0.85em;
  }

  .close {
    flex: none;
    padding: 0 0.25em;
    font-size: 1.4em;
    line-height: 1;
  }

  .focus-chart {
    min-height: 0;
    overflow: auto;
    border-top: thin solid var(--sidebar-border);
  }
</style>

<script lang="ts">
  import { extent } from "d3-array";
  import { axisBottom } from "d3-axis";
  import { scaleUtc } from "d3-scale";

  import type { BudgetPlanNode } from "../../api/validators.ts";
  import Axis from "../../charts/Axis.svelte";
  import { domHelpers, Tooltip } from "../../charts/tooltip.ts";
  import { day } from "../../format.ts";
  import { _ } from "../../i18n.ts";
  import { ctx } from "../../stores/format.ts";
  import { ratio } from "./inventory.ts";

  interface Props {
    rows: { node: BudgetPlanNode; depth: number }[];
  }

  let { rows }: Props = $props();
  let width = $state(0);
  const tooltip = new Tooltip();
  const today = new Date();
  const day_ms = 24 * 60 * 60 * 1000;
  const row_height = 34;
  const margin = { top: 22, right: 20, bottom: 34, left: 190 };

  let chart_width = $derived(Math.max(560, width));
  let inner_width = $derived(
    Math.max(180, chart_width - margin.left - margin.right),
  );
  let inner_height = $derived(Math.max(70, rows.length * row_height));
  let height = $derived(inner_height + margin.top + margin.bottom);
  let date_extent = $derived(
    extent(rows.flatMap(({ node }) => [node.date_start, node.date_end])),
  );
  let domain = $derived.by((): [Date, Date] => {
    const start = date_extent[0] ?? today;
    const end = date_extent[1] ?? today;
    return +start === +end
      ? [new Date(+start - day_ms), new Date(+end + day_ms)]
      : [start, end];
  });
  let x = $derived(scaleUtc([0, inner_width]).domain(domain).nice());
  let x_axis = $derived(
    axisBottom(x)
      .ticks(Math.max(2, width / 150))
      .tickSizeOuter(0),
  );

  const progress_date = (node: BudgetPlanNode, progress: number): Date =>
    new Date(
      +node.date_start +
        Math.min(1, Math.max(0, progress)) *
          Math.max(day_ms, +node.date_end - +node.date_start),
    );
  const amounts = (values: Record<string, number>): string => {
    const entries = Object.entries(values);
    return entries.length
      ? entries
          .map(([currency, value]) => $ctx.amount(value, currency))
          .join(", ")
      : "—";
  };
  const truncate = (value: string, length: number): string =>
    value.length > length ? `${value.slice(0, length - 1)}…` : value;
  const tooltip_content = (node: BudgetPlanNode): (Node | string)[] => {
    const usage = ratio(node.budget, node.actual_total);
    return [
      node.name,
      domHelpers.em(node.account),
      domHelpers.em(
        `${_("Dates")}: ${day(node.date_start)} – ${day(node.date_end)}`,
      ),
      domHelpers.em(`${_("Budget")}: ${amounts(node.budget)}`),
      domHelpers.em(`${_("Spent")}: ${amounts(node.actual_total)}`),
      domHelpers.em(`${_("Time elapsed")}: ${$ctx.percentage(node.progress)}`),
      domHelpers.em(
        `${_("Budget used")}: ${usage == null ? "—" : $ctx.percentage(usage)}`,
      ),
    ];
  };
</script>

<div class="timeline-container" {@attach tooltip.init.bind(tooltip)}>
  <div class="timeline" bind:clientWidth={width}>
    {#if width > 0 && rows.length}
      <svg
        width={chart_width}
        viewBox={`0 0 ${chart_width.toString()} ${height.toString()}`}
      >
        <g
          transform={`translate(${margin.left.toString()},${margin.top.toString()})`}
        >
          {#if domain[0] <= today && today <= domain[1]}
            <line class="today" x1={x(today)} x2={x(today)} y2={inner_height} />
            <text class="today-label" x={x(today)} y={-8}>{_("Today")}</text>
          {/if}

          {#each rows as { node, depth }, index (node.plan_id)}
            {@const row_y = index * row_height + row_height / 2}
            {@const usage = ratio(node.budget, node.actual_total)}
            <g
              class="plan-row"
              class:ended={node.status === "ended"}
              {@attach tooltip.following(() => tooltip_content(node))}
            >
              <text
                class="plan-name"
                x={-margin.left + 4 + depth * 14}
                y={row_y + 4}
                >{truncate(node.name, Math.max(10, 23 - depth * 2))}</text
              >
              <line class="guide" x2={inner_width} y1={row_y} y2={row_y} />
              <line
                class="hit-area"
                x1={-margin.left}
                x2={inner_width}
                y1={row_y}
                y2={row_y}
              />
              <line
                class="schedule"
                x1={x(node.date_start)}
                x2={x(node.date_end)}
                y1={row_y}
                y2={row_y}
              />
              {#if usage != null}
                <line
                  class="spending"
                  class:ahead={usage > node.progress}
                  x1={x(node.date_start)}
                  x2={x(progress_date(node, usage))}
                  y1={row_y}
                  y2={row_y}
                />
                <circle
                  class="spending-marker"
                  class:ahead={usage > node.progress}
                  cx={x(progress_date(node, usage))}
                  cy={row_y}
                  r="4"
                />
              {/if}
              <line
                class="start"
                x1={x(node.date_start)}
                x2={x(node.date_start)}
                y1={row_y - 6}
                y2={row_y + 6}
              />
              <line
                class="end"
                x1={x(node.date_end)}
                x2={x(node.date_end)}
                y1={row_y - 6}
                y2={row_y + 6}
              />
            </g>
          {/each}

          <Axis x axis={x_axis} {inner_height} />
        </g>
      </svg>
    {/if}
  </div>
</div>

<div class="legend">
  <span><i class="schedule-key"></i>{_("Plan window")}</span>
  <span><i class="on-pace"></i>{_("On pace")}</span>
  <span><i class="ahead-key"></i>{_("Spending ahead")}</span>
</div>

<style>
  .timeline-container {
    position: relative;
  }

  .timeline {
    width: 100%;
    overflow-x: auto;
  }

  svg {
    display: block;
  }

  .hit-area {
    pointer-events: stroke;
    stroke: transparent;
    stroke-width: 28px;
  }

  .guide {
    opacity: 0.45;
    stroke: var(--border);
    stroke-width: 1px;
  }

  .schedule {
    stroke: var(--background-darker);
    stroke-width: 8px;
    stroke-linecap: round;
  }

  .spending {
    stroke: var(--green);
    stroke-width: 6px;
    stroke-linecap: round;
  }

  .spending.ahead {
    stroke: var(--red);
  }

  .spending-marker {
    fill: var(--green);
    stroke: var(--background);
    stroke-width: 2px;
  }

  .spending-marker.ahead {
    fill: var(--red);
  }

  .start,
  .end {
    stroke: var(--text-color-lightest);
    stroke-width: 1px;
  }

  .today {
    stroke: var(--link-color);
    stroke-width: 1.5px;
    stroke-dasharray: 3 3;
  }

  .today-label {
    font-size: 11px;
    text-anchor: middle;
    fill: var(--link-color);
  }

  .plan-name {
    font-weight: 500;
    fill: var(--text-color);
  }

  .plan-row.ended {
    opacity: 0.65;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
    margin-top: 0.5rem;
    color: var(--text-color-lightest);
  }

  .legend span {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
  }

  .legend i {
    display: inline-block;
    width: 18px;
    height: 4px;
    background: var(--green);
  }

  .legend .schedule-key {
    height: 7px;
    background: var(--background-darker);
  }

  .legend .ahead-key {
    background: var(--red);
  }
</style>

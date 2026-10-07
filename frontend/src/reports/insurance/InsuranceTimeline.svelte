<script lang="ts">
  import { extent } from "d3-array";
  import { axisBottom } from "d3-axis";
  import { scaleOrdinal, scaleUtc } from "d3-scale";

  import type { InsurancePolicy } from "../../api/validators.ts";
  import Axis from "../../charts/Axis.svelte";
  import { colors10 } from "../../charts/helpers.ts";
  import { domHelpers, Tooltip } from "../../charts/tooltip.ts";
  import { day } from "../../format.ts";
  import { _ } from "../../i18n.ts";

  interface Props {
    policies: InsurancePolicy[];
  }

  let { policies }: Props = $props();
  let width = $state(0);
  const tooltip = new Tooltip();

  const today = new Date();
  const row_height = 38;
  const group_gap = 18;
  const margin = { top: 22, right: 22, bottom: 34, left: 250 };

  let ordered = $derived(
    policies.toSorted(
      (a, b) =>
        a.insured.localeCompare(b.insured) ||
        +a.effective - +b.effective ||
        a.product.localeCompare(b.product),
    ),
  );
  let group_starts = $derived(
    new Set(
      ordered
        .map((policy, index) =>
          index === 0 || ordered[index - 1]?.insured !== policy.insured
            ? index
            : -1,
        )
        .filter((index) => index >= 0),
    ),
  );
  let group_index = $derived.by(() => {
    let current = -1;
    return ordered.map((_policy, index) => {
      if (group_starts.has(index)) {
        current += 1;
      }
      return current;
    });
  });
  let groups = $derived(group_starts.size);
  let chart_width = $derived(Math.max(700, width));
  let inner_width = $derived(
    Math.max(200, chart_width - margin.left - margin.right),
  );
  let inner_height = $derived(
    Math.max(
      80,
      ordered.length * row_height + Math.max(0, groups - 1) * group_gap,
    ),
  );
  let height = $derived(inner_height + margin.top + margin.bottom);

  const policy_end = (policy: InsurancePolicy): Date | null =>
    policy.cancellation ?? policy.expiration;
  const truncate = (value: string, length: number): string =>
    value.length > length ? `${value.slice(0, length - 1)}…` : value;
  const displayed_end = (policy: InsurancePolicy): Date =>
    policy_end(policy) ?? (policy.effective > today ? policy.effective : today);
  const y = (index: number) =>
    index * row_height + (group_index[index] ?? 0) * group_gap + row_height / 2;

  let dates = $derived(
    ordered.flatMap((policy) => [
      policy.purchased,
      policy.effective,
      displayed_end(policy),
      ...(policy.renewal ? [policy.renewal] : []),
    ]),
  );
  let date_extent = $derived(extent(dates));
  let domain = $derived.by((): [Date, Date] => {
    const start = date_extent[0] ?? today;
    const end = date_extent[1] ?? today;
    return +start === +end
      ? [new Date(+start - 86400000), new Date(+end + 86400000)]
      : [start, end];
  });
  let x = $derived(scaleUtc([0, inner_width]).domain(domain).nice());
  let x_axis = $derived(
    axisBottom(x)
      .ticks(Math.max(2, width / 140))
      .tickSizeOuter(0),
  );

  let categories = $derived([
    ...new Set(ordered.map((policy) => policy.category)),
  ]);
  let category_color = $derived(scaleOrdinal(colors10).domain(categories));

  const tooltip_content = (policy: InsurancePolicy): (Node | string)[] => {
    const end = policy_end(policy);
    return [
      policy.product,
      domHelpers.em(`${policy.insured} · ${policy.category}`),
      domHelpers.em(`${_("Purchased")}: ${day(policy.purchased)}`),
      domHelpers.em(`${_("Effective")}: ${day(policy.effective)}`),
      domHelpers.em(end ? `${_("Ends")}: ${day(end)}` : _("No scheduled end")),
    ];
  };
</script>

<div class="timeline-container" {@attach tooltip.init.bind(tooltip)}>
  <div class="timeline" bind:clientWidth={width}>
    {#if width > 0 && ordered.length}
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

          {#each ordered as policy, index (policy.policy_id)}
            {@const row_y = y(index)}
            {@const end = policy_end(policy)}
            {@const color = category_color(policy.category)}
            <g
              class="policy-row"
              {@attach tooltip.following(() => tooltip_content(policy))}
            >
              {#if group_starts.has(index)}
                <text class="insured" x={-margin.left + 4} y={row_y + 4}>
                  {truncate(policy.insured, 12)}
                </text>
              {/if}
              <text class="product" x={-margin.left + 88} y={row_y + 4}>
                {truncate(policy.product, 22)}
              </text>
              <line class="guide" x2={inner_width} y1={row_y} y2={row_y} />
              <line
                class="hit-area"
                x1={-margin.left}
                x2={inner_width}
                y1={row_y}
                y2={row_y}
              />
              {#if policy.purchased < policy.effective}
                <line
                  class="waiting"
                  x1={x(policy.purchased)}
                  x2={x(policy.effective)}
                  y1={row_y}
                  y2={row_y}
                />
              {/if}
              <line
                class="coverage"
                class:ended={end != null}
                x1={x(policy.effective)}
                x2={x(displayed_end(policy))}
                y1={row_y}
                y2={row_y}
                stroke={color}
              />
              <circle
                class="milestone"
                cx={x(policy.purchased)}
                cy={row_y}
                r="4"
              />
              <circle
                class="effective"
                cx={x(policy.effective)}
                cy={row_y}
                r="5"
                fill={color}
              />
              {#if policy.renewal}
                <path
                  class="renewal"
                  d={`M ${x(policy.renewal).toString()} ${(row_y - 6).toString()} l 6 6 l -6 6 l -6 -6 z`}
                  fill={color}
                />
              {/if}
              {#if end}
                <rect
                  class:cancelled={policy.cancellation != null}
                  class:expired={policy.cancellation == null}
                  x={x(end) - 5}
                  y={row_y - 5}
                  width="10"
                  height="10"
                  fill={color}
                />
              {/if}
            </g>
          {/each}

          <Axis x axis={x_axis} {inner_height} />
        </g>
      </svg>
    {/if}
  </div>
</div>

<div class="legend">
  <span><i class="purchase"></i>{_("Purchase")}</span>
  <span><i class="wait"></i>{_("Waiting period")}</span>
  <span><i class="effective-key"></i>{_("Effective")}</span>
  <span><i class="renew"></i>{_("Renewal")}</span>
  <span><i class="expire"></i>{_("Expiration")}</span>
  <span><i class="cancel"></i>{_("Cancellation")}</span>
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
    stroke-width: 30px;
  }

  .guide {
    opacity: 0.55;
    stroke: var(--border);
    stroke-width: 1px;
  }

  .waiting {
    stroke: var(--text-color-lightest);
    stroke-width: 4px;
    stroke-dasharray: 6 5;
  }

  .coverage {
    stroke-width: 7px;
    stroke-linecap: round;
  }

  .coverage.ended {
    opacity: 0.65;
  }

  .milestone {
    fill: var(--background);
    stroke: var(--text-color-lightest);
    stroke-width: 2px;
  }

  .effective {
    stroke: var(--background);
    stroke-width: 2px;
  }

  .renewal {
    stroke: var(--background);
    stroke-width: 1px;
  }

  .cancelled {
    fill: var(--error);
  }

  .expired {
    fill: var(--text-color-lightest);
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

  .insured {
    font-weight: 500;
    fill: var(--text-color);
  }

  .product {
    fill: var(--text-color-lightest);
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.25rem;
    margin-top: 0.75rem;
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
    background: var(--link-color);
  }

  .legend .purchase {
    width: 8px;
    height: 8px;
    background: var(--background);
    border: 2px solid var(--text-color-lightest);
    border-radius: 50%;
  }

  .legend .wait {
    height: 0;
    background: none;
    border-top: 3px dashed var(--text-color-lightest);
  }

  .legend .effective-key {
    width: 9px;
    height: 9px;
    border-radius: 50%;
  }

  .legend .renew {
    width: 8px;
    height: 8px;
    transform: rotate(45deg);
  }

  .legend .expire,
  .legend .cancel {
    width: 9px;
    height: 9px;
  }

  .legend .expire {
    background: var(--text-color-lightest);
  }

  .legend .cancel {
    background: var(--error);
  }
</style>

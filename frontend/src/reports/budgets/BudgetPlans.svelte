<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import type {
    BudgetPlanNode,
    BudgetPlanStatus,
  } from "../../api/validators.ts";
  import { day } from "../../format.ts";
  import { url_for_account } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import Amounts from "./Amounts.svelte";
  import BudgetProgress from "./BudgetProgress.svelte";
  import { ratio, subtract, usage } from "./inventory.ts";
  import PlanTimeline from "./PlanTimeline.svelte";

  interface Props {
    plans: BudgetPlanNode[];
  }

  interface Row {
    node: BudgetPlanNode;
    depth: number;
    open: boolean;
  }

  let { plans }: Props = $props();
  let search = $state("");
  let status = $state<BudgetPlanStatus | "all">("active");
  let toggled = $state<string[]>([]);

  const includes_query = (node: BudgetPlanNode, query: string): boolean =>
    [node.name, node.account, node.plan_id].some((value) =>
      value.toLocaleLowerCase().includes(query),
    ) || node.children.some((child) => includes_query(child, query));

  const node_open = (node: BudgetPlanNode, depth: number, query: string) => {
    const default_open = depth === 0;
    return (
      query.length > 0 ||
      (toggled.includes(node.plan_id) ? !default_open : default_open)
    );
  };

  const flatten_children = (nodes: BudgetPlanNode[], depth = 1): Row[] => {
    const query = search.trim().toLocaleLowerCase();
    return nodes.flatMap((node) => {
      if (query && !includes_query(node, query)) {
        return [];
      }
      const open = node_open(node, depth, query);
      return [
        { node, depth, open },
        ...(open ? flatten_children(node.children, depth + 1) : []),
      ];
    });
  };

  const flatten_timeline = (nodes: BudgetPlanNode[], depth = 1): Row[] => {
    const query = search.trim().toLocaleLowerCase();
    return nodes.flatMap((node) =>
      query && !includes_query(node, query)
        ? []
        : [
            { node, depth, open: true },
            ...flatten_timeline(node.children, depth + 1),
          ],
    );
  };

  let visible_plans = $derived(
    plans.filter((node) => {
      const query = search.trim().toLocaleLowerCase();
      return (
        (status === "all" || node.status === status) &&
        (!query || includes_query(node, query))
      );
    }),
  );
  let column_currency = $derived.by(() => {
    const currencies = new SvelteSet<string>();
    const collect = (nodes: BudgetPlanNode[]) => {
      for (const node of nodes) {
        for (const inventory of [node.budget, node.actual_total]) {
          for (const currency of Object.keys(inventory)) {
            currencies.add(currency);
          }
        }
        collect(node.children);
      }
    };
    collect(visible_plans);
    return currencies.size === 1 ? ([...currencies][0] ?? null) : null;
  });
  let timeline_rows = $derived(
    visible_plans.flatMap((plan) => [
      { node: plan, depth: 0, open: true },
      ...flatten_timeline(plan.children),
    ]),
  );
  const toggle = (plan_id: string) => {
    toggled = toggled.includes(plan_id)
      ? toggled.filter((item) => item !== plan_id)
      : [...toggled, plan_id];
  };
  const plan_time = (node: BudgetPlanNode) =>
    `${day(node.date_start)} - ${day(node.date_end)}`;
  const plan_pace = (
    node: BudgetPlanNode,
  ): { label: string; state: "muted" | "positive" | "warning" } => {
    const used = ratio(node.budget, node.actual_total);
    if (node.status === "upcoming") {
      return used != null && used > 0
        ? { label: _("Spending early"), state: "warning" }
        : { label: _("Upcoming"), state: "muted" };
    }
    if (node.status === "ended") {
      return used != null && used > 1
        ? { label: _("Over budget"), state: "warning" }
        : { label: _("Ended"), state: "muted" };
    }
    if (used == null) {
      return { label: _("Active"), state: "muted" };
    }
    return used > node.progress
      ? { label: _("Spending fast"), state: "warning" }
      : { label: _("On track"), state: "positive" };
  };
</script>

<div class="toolbar">
  <label>
    <span>{_("Search plans")}</span>
    <input
      bind:value={search}
      type="search"
      placeholder={_("Plan or account…")}
    />
  </label>
  <label>
    <span>{_("Status")}</span>
    <select bind:value={status}>
      <option value="active">{_("Active")}</option>
      <option value="upcoming">{_("Upcoming")}</option>
      <option value="ended">{_("Ended")}</option>
      <option value="all">{_("All")}</option>
    </select>
  </label>
</div>

{#if visible_plans.length}
  <section class="timeline-section">
    <h3>{_("Schedule and spending pace")}</h3>
    <PlanTimeline rows={timeline_rows} />
  </section>
  <ol class="flex-table tree-table-new plan-tree">
    <li class="head">
      <p>
        <span class="plan-cell">{_("Plan")}</span>
        <span class="pace-cell">{_("Pace")}</span>
        <span class="num other budget-cell"
          >{_("Budget")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="num other"
          >{_("Spent")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="num other"
          >{_("Left")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="progress-cell">{_("Used")}</span>
      </p>
    </li>
    {#each visible_plans as plan (plan.plan_id)}
      {@const query = search.trim().toLocaleLowerCase()}
      {@const open = node_open(plan, 0, query)}
      {@const children = open ? flatten_children(plan.children) : []}
      {@const pace = plan_pace(plan)}
      <li class="root" data-plan-card>
        <p>
          <span class="plan-cell">
            <span class="plan-content" style:--depth={0}>
              {#if plan.children.length}
                <button
                  type="button"
                  class="unset"
                  aria-label={_("Toggle children")}
                  onclick={() => {
                    toggle(plan.plan_id);
                  }}>{open ? "▾" : "▸"}</button
                >
              {:else}
                <span class="tree-placeholder"></span>
              {/if}
              <a
                class="plan-link"
                href={$url_for_account(plan.account, {
                  time: plan_time(plan),
                })}
                title={plan.account}>{plan.name}</a
              >
            </span>
          </span>
          <span class="pace-cell pace-{pace.state}">{pace.label}</span>
          <span class="num other budget-cell"
            ><Amounts values={plan.budget} {column_currency} /></span
          >
          <span class="num other"
            ><Amounts values={plan.actual_total} {column_currency} /></span
          >
          <span class="num other"
            ><Amounts
              values={subtract(plan.budget, plan.actual_total)}
              {column_currency}
            /></span
          >
          <span class="progress-cell">
            <span class="bar">
              <BudgetProgress
                budget={plan.budget}
                actual={plan.actual_total}
                marker={plan.progress}
              />
            </span>
            <span class="percent">{usage(plan.budget, plan.actual_total)}</span>
          </span>
        </p>
      </li>
      {#each children as { node, depth, open: child_open } (node.plan_id)}
        {@const pace = plan_pace(node)}
        <li data-plan-row>
          <p>
            <span class="plan-cell">
              <span class="plan-content" style:--depth={depth}>
                {#if node.children.length}
                  <button
                    type="button"
                    class="unset"
                    aria-label={_("Toggle children")}
                    onclick={() => {
                      toggle(node.plan_id);
                    }}>{child_open ? "▾" : "▸"}</button
                  >
                {:else}
                  <span class="tree-placeholder"></span>
                {/if}
                <a
                  class="plan-link"
                  href={$url_for_account(node.account, {
                    time: plan_time(node),
                  })}
                  title={node.account}>{node.name}</a
                >
              </span>
            </span>
            <span class="pace-cell pace-{pace.state}">{pace.label}</span>
            <span class="num other budget-cell"
              ><Amounts values={node.budget} {column_currency} /></span
            >
            <span class="num other"
              ><Amounts values={node.actual_total} {column_currency} /></span
            >
            <span class="num other"
              ><Amounts
                values={subtract(node.budget, node.actual_total)}
                {column_currency}
              /></span
            >
            <span class="progress-cell">
              <span class="bar">
                <BudgetProgress
                  budget={node.budget}
                  actual={node.actual_total}
                  marker={node.progress}
                />
              </span>
              <span class="percent"
                >{usage(node.budget, node.actual_total)}</span
              >
            </span>
          </p>
        </li>
      {/each}
    {/each}
  </ol>
{:else}
  <p class="empty">{_("No plans match the current filters.")}</p>
{/if}

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
    margin-bottom: 1rem;
  }

  label {
    display: grid;
    gap: 0.2rem;
  }

  label span,
  .empty {
    color: var(--text-color-lightest);
  }

  select {
    min-height: 32px;
    padding: 0 0.5rem;
    color: var(--text-color);
    background: var(--placeholder-background);
    border: 1px solid var(--border-darker);
  }

  input {
    width: min(360px, 70vw);
  }

  .timeline-section {
    padding-bottom: 1rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--border);
  }

  .timeline-section h3 {
    margin: 0 0 0.5rem;
  }

  .plan-tree {
    width: 100%;
  }

  .plan-tree p {
    display: grid;
    grid-template-columns:
      minmax(13rem, 2.7fr) minmax(6.5rem, 0.85fr)
      repeat(3, minmax(0, 1fr)) minmax(9rem, 1.3fr);
  }

  .plan-tree p > span {
    min-width: 0;
  }

  .plan-cell {
    display: flex;
    align-items: center;
  }

  .plan-content {
    display: flex;
    align-items: center;
    min-width: 0;
    margin-left: calc(var(--depth) * 1em);
  }

  .plan-content button,
  .tree-placeholder {
    width: 1em;
    padding: 0;
    color: var(--treetable-expander);
    text-align: center;
  }

  .plan-link {
    display: block;
    min-width: 0;
    margin-left: 0.35em;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 500;
    white-space: nowrap;
  }

  .pace-cell {
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text-color-lightest);
    white-space: nowrap;
  }

  .pace-positive {
    color: var(--green);
  }

  .pace-warning {
    color: var(--red);
  }

  .plan-tree .other {
    width: auto;
    overflow: hidden;
  }

  .progress-cell {
    display: flex;
    gap: 0.5em;
    align-items: center;
  }

  .head .progress-cell {
    justify-content: flex-end;
  }

  .bar {
    flex: 1;
    min-width: 0;
  }

  .percent {
    width: 3.5em;
    font-family: var(--font-family-monospaced);
    text-align: right;
  }

  .root p > span {
    background: var(--table-background-even);
  }

  @media (width <= 900px) {
    .plan-tree p {
      grid-template-columns:
        minmax(10rem, 2fr) minmax(5.5rem, 0.8fr) repeat(3, minmax(0, 1fr))
        minmax(7rem, 1.2fr);
    }

    .bar {
      display: none;
    }

    .percent {
      width: 100%;
    }
  }
</style>

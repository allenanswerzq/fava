<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";

  import type { BudgetAccountNode } from "../../api/validators.ts";
  import { day } from "../../format.ts";
  import { url_for_account } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import Amounts from "./Amounts.svelte";
  import BudgetProgress from "./BudgetProgress.svelte";
  import { subtract, usage } from "./inventory.ts";

  interface Props {
    accounts: BudgetAccountNode[];
    unbudgeted: BudgetAccountNode | null;
    progress: number;
    date_range: { begin: Date; end: Date };
  }

  interface Row {
    node: BudgetAccountNode;
    depth: number;
    unbudgeted: boolean;
    open: boolean;
    key: string;
  }

  let { accounts, unbudgeted, progress, date_range }: Props = $props();
  let search = $state("");
  let toggled = $state<string[]>([]);

  const includes_query = (node: BudgetAccountNode, query: string): boolean =>
    node.account.toLocaleLowerCase().includes(query) ||
    node.children.some((child) => includes_query(child, query));

  const flatten = (
    nodes: BudgetAccountNode[],
    depth = 0,
    is_unbudgeted = false,
  ): Row[] => {
    const query = search.trim().toLocaleLowerCase();
    return nodes.flatMap((node) => {
      if (query && !includes_query(node, query)) {
        return [];
      }
      const key = `${is_unbudgeted ? "u" : "b"}:${node.account}`;
      const default_open = depth === 0 && !is_unbudgeted;
      const open =
        query.length > 0 ||
        (toggled.includes(key) ? !default_open : default_open);
      return [
        { node, depth, unbudgeted: is_unbudgeted, open, key },
        ...(open ? flatten(node.children, depth + 1, is_unbudgeted) : []),
      ];
    });
  };

  let rows = $derived([
    ...flatten(accounts),
    ...(unbudgeted ? flatten([unbudgeted], 0, true) : []),
  ]);
  let column_currency = $derived.by(() => {
    const currencies = new SvelteSet<string>();
    const collect = (nodes: BudgetAccountNode[]) => {
      for (const node of nodes) {
        for (const inventory of [node.budget_total, node.actual_total]) {
          for (const currency of Object.keys(inventory)) {
            currencies.add(currency);
          }
        }
        collect(node.children);
      }
    };
    collect(unbudgeted == null ? accounts : [...accounts, unbudgeted]);
    return currencies.size === 1 ? ([...currencies][0] ?? null) : null;
  });
  let end_inclusive = $derived(
    new Date(date_range.end.getTime() - 24 * 60 * 60 * 1000),
  );
  let time = $derived(`${day(date_range.begin)} - ${day(end_inclusive)}`);

  const toggle = (key: string) => {
    toggled = toggled.includes(key)
      ? toggled.filter((item) => item !== key)
      : [...toggled, key];
  };
</script>

<div class="toolbar">
  <label>
    <span>{_("Search accounts")}</span>
    <input bind:value={search} type="search" placeholder={_("Account…")} />
  </label>
  <p class="period">
    {_("Budget period")}:
    <time datetime={day(date_range.begin)}
      >{day(date_range.begin)} –
      {day(end_inclusive)}</time
    >
  </p>
</div>

{#if rows.length}
  <ol class="flex-table tree-table-new budget-tree">
    <li class="head">
      <p>
        <span class="account-cell">{_("Account")}</span>
        <span class="num other budget-cell"
          >{_("Budget")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="num other"
          >{_("Actual")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="num other"
          >{_("Remaining")}{column_currency != null
            ? ` (${column_currency})`
            : ""}</span
        >
        <span class="progress-cell">{_("Progress")}</span>
      </p>
    </li>
    {#each rows as { node, depth, unbudgeted: is_unbudgeted, open, key } (key)}
      <li
        class:root={depth === 0}
        class:unbudgeted={is_unbudgeted}
        data-budget-row
      >
        <p>
          <span class="account-cell">
            <span class="account-content" style:--depth={depth}>
              {#if node.children.length}
                <button
                  type="button"
                  class="unset"
                  aria-label={_("Toggle children")}
                  onclick={() => {
                    toggle(key);
                  }}>{open ? "▾" : "▸"}</button
                >
              {:else}
                <span class="tree-placeholder"></span>
              {/if}
              <span>
                <a
                  class="account"
                  href={$url_for_account(node.account, { time })}
                  title={node.account}>{node.name}</a
                >
              </span>
            </span>
          </span>
          <span class="num other budget-cell">
            {#if !is_unbudgeted}
              <Amounts values={node.budget_total} {column_currency} />
            {/if}
          </span>
          <span class="num other"
            ><Amounts values={node.actual_total} {column_currency} /></span
          >
          <span class="num other">
            {#if !is_unbudgeted}
              <Amounts
                values={subtract(node.budget_total, node.actual_total)}
                {column_currency}
              />
            {/if}
          </span>
          <span class="progress-cell">
            {#if !is_unbudgeted}
              <span class="bar">
                <BudgetProgress
                  budget={node.budget_total}
                  actual={node.actual_total}
                  marker={progress}
                />
              </span>
              <span class="percent"
                >{usage(node.budget_total, node.actual_total)}</span
              >
            {/if}
          </span>
        </p>
      </li>
    {/each}
  </ol>
{:else}
  <p class="empty">{_("No account budgets match the current filters.")}</p>
{/if}

<style>
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
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

  input {
    width: min(360px, 70vw);
  }

  .period {
    margin: 0 0 0.45rem auto;
    color: var(--text-color-lightest);
    white-space: nowrap;
  }

  .period time {
    margin-left: 0.25em;
    font-family: var(--font-family-monospaced);
    color: var(--text-color);
  }

  .budget-tree {
    width: 100%;
  }

  .budget-tree p {
    display: grid;
    grid-template-columns:
      minmax(12rem, 2.4fr) repeat(3, minmax(0, 1fr))
      minmax(9rem, 1.35fr);
  }

  .budget-tree p > span {
    min-width: 0;
  }

  .account-cell {
    display: flex;
    align-items: center;
  }

  .account-content {
    display: flex;
    align-items: center;
    min-width: 0;
    margin-left: calc(var(--depth) * 1em);
  }

  .account-content > span:last-child {
    min-width: 0;
  }

  .account-content button,
  .tree-placeholder {
    width: 1em;
    padding: 0;
    color: var(--treetable-expander);
    text-align: center;
  }

  .account {
    display: block;
    margin-left: 0.35em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .budget-tree .other {
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

  .unbudgeted p > span,
  .root:not(.unbudgeted) p > span {
    background: var(--table-background-even);
  }

  @media (width <= 700px) {
    .budget-tree p {
      grid-template-columns:
        minmax(10rem, 2fr) repeat(3, minmax(0, 1fr))
        minmax(7rem, 1.2fr);
    }

    .percent {
      display: none;
    }
  }
</style>

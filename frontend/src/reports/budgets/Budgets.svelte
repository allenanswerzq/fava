<script lang="ts">
  import ConversionAndInterval from "../../charts/ConversionAndInterval.svelte";
  import { _ } from "../../i18n.ts";
  import AccountBudgets from "./AccountBudgets.svelte";
  import BudgetPlans from "./BudgetPlans.svelte";
  import type { BudgetReportProps } from "./index.ts";

  let { date_range, progress, accounts, unbudgeted, plans }: BudgetReportProps =
    $props();
  let view = $state<"accounts" | "plans">("accounts");
</script>

<div class="header">
  <nav aria-label={_("Budget view")}>
    <button
      type="button"
      class:active={view === "accounts"}
      onclick={() => (view = "accounts")}>{_("Account budgets")}</button
    >
    <button
      type="button"
      class:active={view === "plans"}
      onclick={() => (view = "plans")}>{_("Plans")}</button
    >
  </nav>
  <div class="conversion"><ConversionAndInterval show_interval={false} /></div>
</div>

{#if view === "accounts"}
  <AccountBudgets {accounts} {unbudgeted} {progress} {date_range} />
{:else}
  <BudgetPlans {plans} />
{/if}

<style>
  .header {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  nav {
    display: flex;
    color: var(--text-color-lightest);
  }

  nav button {
    padding: 0 0.6em;
    color: inherit;
    background: none;
    border: 0;
  }

  nav button + button {
    border-left: 1px solid var(--text-color-lighter);
  }

  nav button.active,
  nav button:hover {
    color: var(--text-color-lighter);
  }

  .conversion {
    display: flex;
    gap: 0.5rem;
  }
</style>

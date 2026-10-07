<script lang="ts">
  import type { BudgetInventory } from "../../api/validators.ts";
  import { ctx } from "../../stores/format.ts";

  interface Props {
    values: BudgetInventory;
    /** Currency already displayed by the containing column header. */
    column_currency?: string | null;
  }

  let { values, column_currency = null }: Props = $props();
  let entries = $derived(
    Object.entries(values).toSorted(([a], [b]) => a.localeCompare(b)),
  );
</script>

{#each entries as [currency, value] (currency)}
  <span>
    {currency === column_currency
      ? $ctx.num(value, currency)
      : $ctx.amount(value, currency)}
  </span>
{:else}
  <span class="empty">—</span>
{/each}

<style>
  span {
    display: block;
    white-space: nowrap;
  }

  .empty {
    color: var(--text-color-lightest);
  }
</style>

<script lang="ts">
  import type { BudgetInventory } from "../../api/validators.ts";
  import { ctx } from "../../stores/format.ts";

  interface Props {
    budget: BudgetInventory;
    actual: BudgetInventory;
    marker?: number | null;
  }

  let { budget, actual, marker = null }: Props = $props();
  let currencies = $derived(
    [...new Set([...Object.keys(budget), ...Object.keys(actual)])].toSorted(),
  );
  const ratio = (currency: string) => {
    const limit = budget[currency] ?? 0;
    return limit > 0 ? (actual[currency] ?? 0) / limit : 0;
  };
</script>

<div class="progress-list">
  {#each currencies as currency (currency)}
    <div
      class="progress"
      class:over={ratio(currency) > 1}
      title={`${$ctx.percentage(ratio(currency))} ${currency}`}
    >
      <span
        class="fill"
        style:width={`${(Math.min(1, Math.max(0, ratio(currency))) * 100).toString()}%`}
      ></span>
      {#if marker != null}
        <span
          class="marker"
          style:left={`${(Math.min(1, Math.max(0, marker)) * 100).toString()}%`}
        ></span>
      {/if}
    </div>
  {:else}
    <span class="empty">—</span>
  {/each}
</div>

<style>
  .progress-list {
    display: grid;
    gap: 0.3rem;
    min-width: 0;
  }

  .progress {
    position: relative;
    height: 0.65rem;
    overflow: hidden;
    background: var(--background-darker);
    border: 1px solid var(--border);
    border-radius: 999px;
  }

  .fill {
    position: absolute;
    inset: 0 auto 0 0;
    background: var(--green);
  }

  .over .fill {
    background: var(--red);
  }

  .marker {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 2px;
    background: var(--text-color);
    transform: translateX(-1px);
  }

  .empty {
    color: var(--text-color-lightest);
  }
</style>

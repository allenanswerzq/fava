<script lang="ts">
  import type { InsurancePolicy } from "../../api/validators.ts";
  import { url_for } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import InsuranceTable from "./InsuranceTable.svelte";
  import InsuranceTimeline from "./InsuranceTimeline.svelte";
  import type { InsuranceReportProps } from "./index.ts";

  let { policies }: InsuranceReportProps = $props();
  let search = $state("");
  let status = $state<InsurancePolicy["status"] | "all">("active");
  let insured = $state("all");

  const matches = (policy: InsurancePolicy): boolean => {
    if (status !== "all" && policy.status !== status) {
      return false;
    }
    if (insured !== "all" && policy.insured !== insured) {
      return false;
    }
    const query = search.trim().toLocaleLowerCase();
    if (!query) {
      return true;
    }
    return [
      policy.policy_id,
      policy.insured,
      policy.category,
      policy.subtype,
      policy.product,
      policy.issuer,
      policy.note,
    ].some((value) => value?.toLocaleLowerCase().includes(query) === true);
  };

  let filtered = $derived(policies.filter(matches));
  let insured_people = $derived(
    [...new Set(policies.map((policy) => policy.insured))].toSorted(),
  );
</script>

{#if policies.length}
  <div class="toolbar">
    <label>
      <span>{_("Search policies")}</span>
      <input
        bind:value={search}
        type="search"
        placeholder={_("Person, product, issuer…")}
      />
    </label>
    <label>
      <span>{_("Insured")}</span>
      <select bind:value={insured}>
        <option value="all">{_("All")}</option>
        {#each insured_people as person (person)}
          <option value={person}>{person}</option>
        {/each}
      </select>
    </label>
    <label>
      <span>{_("Status")}</span>
      <select bind:value={status}>
        <option value="all">{_("All")}</option>
        <option value="active">{_("Active")}</option>
        <option value="waiting">{_("Waiting")}</option>
        <option value="not_started">{_("Not started")}</option>
        <option value="expired">{_("Expired")}</option>
        <option value="cancelled">{_("Cancelled")}</option>
      </select>
    </label>
  </div>

  {#if filtered.length}
    <section>
      <h3>{_("Coverage timeline")}</h3>
      <InsuranceTimeline policies={filtered} />
    </section>
    <section>
      <h3>{_("Policy details")}</h3>
      <InsuranceTable policies={filtered} />
    </section>
  {:else}
    <p>{_("No policies match the current filters.")}</p>
  {/if}
{:else}
  <div class="empty">
    <h3>{_("No insurance policies")}</h3>
    <p>
      {_(
        "Add custom insurance directives to your Beancount file to track coverage here.",
      )}
    </p>
    <a href={$url_for("help/insurance")}>{_("View insurance syntax")}</a>
  </div>
{/if}

<style>
  label span {
    color: var(--text-color-lightest);
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: end;
    margin-bottom: 1.25rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  input {
    width: min(360px, 70vw);
  }

  select {
    min-height: 32px;
    padding: 0 0.5rem;
    color: var(--text-color);
    background: var(--placeholder-background);
    border: 1px solid var(--border-darker);
  }

  section {
    padding: 1rem;
    margin-bottom: 1.25rem;
    background: var(--background);
    border: 1px solid var(--border);
    border-radius: 4px;
  }

  .empty {
    max-width: 520px;
    padding: 2rem;
    text-align: center;
    background: var(--background-darker);
    border: 1px solid var(--border);
  }
</style>

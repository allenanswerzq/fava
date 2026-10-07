<script lang="ts">
  import type { InsurancePolicy } from "../../api/validators.ts";
  import { day } from "../../format.ts";
  import { url_for_account, url_for_raw } from "../../helpers.ts";
  import { _ } from "../../i18n.ts";
  import { basename } from "../../lib/paths.ts";
  import { DateColumn, Sorter, StringColumn } from "../../sort/index.ts";
  import SortHeader from "../../sort/SortHeader.svelte";
  import { ctx } from "../../stores/format.ts";

  interface Props {
    policies: InsurancePolicy[];
  }

  let { policies }: Props = $props();

  type Row = InsurancePolicy & { date: string };
  const rows = (items: InsurancePolicy[]): Row[] =>
    items.map((policy) => ({ ...policy, date: day(policy.effective) }));
  const columns = [
    new StringColumn<Row>(_("Insured"), (policy) => policy.insured),
    new StringColumn<Row>(_("Product"), (policy) => policy.product),
    new StringColumn<Row>(_("Category"), (policy) => policy.category),
    new StringColumn<Row>(_("Status"), (policy) => policy.status),
    new DateColumn<Row>(_("Effective")),
  ] as const;
  let sorter = $state(new Sorter(columns[0], "asc"));
  let sorted = $derived(sorter.sort(rows(policies)));

  const end_date = (policy: InsurancePolicy): Date | null =>
    policy.cancellation ?? policy.expiration;
  const format_end = (policy: InsurancePolicy): string => {
    const end = end_date(policy);
    return end ? day(end) : "—";
  };
  const amount = (value: InsurancePolicy["premium"]): string =>
    value?.str($ctx) ?? "—";
  const status_label = (status: InsurancePolicy["status"]): string =>
    ({
      not_started: _("Not started"),
      waiting: _("Waiting"),
      active: _("Active"),
      expired: _("Expired"),
      cancelled: _("Cancelled"),
    })[status];
</script>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        {#each columns as column (column)}
          <SortHeader bind:sorter {column} />
        {/each}
        <th>{_("Coverage")}</th>
        <th>{_("Premium")}</th>
        <th>{_("Ends")}</th>
        <th>{_("Details")}</th>
      </tr>
    </thead>
    <tbody>
      {#each sorted as policy (policy.policy_id)}
        <tr
          class:droptarget={policy.account != null}
          data-account-name={policy.account}
          data-entry-date={day(policy.purchased)}
          data-entry-hash={policy.entry_hash}
        >
          <td>{policy.insured}</td>
          <td><a href={`#context-${policy.entry_hash}`}>{policy.product}</a></td
          >
          <td>
            {policy.category}{#if policy.subtype}<small>{policy.subtype}</small
              >{/if}
          </td>
          <td>
            <span class={`status ${policy.status}`}>
              {status_label(policy.status)}
            </span>
          </td>
          <td>{day(policy.effective)}</td>
          <td class="num">{amount(policy.coverage)}</td>
          <td class="num">
            {amount(policy.premium)}
            {#if policy.frequency}<small>{policy.frequency}</small>{/if}
          </td>
          <td>{format_end(policy)}</td>
          <td>
            <details>
              <summary>{_("View")}</summary>
              <dl>
                <div>
                  <dt>{_("Policy ID")}</dt>
                  <dd>{policy.policy_id}</dd>
                </div>
                {#if policy.issuer}
                  <div>
                    <dt>{_("Issuer")}</dt>
                    <dd>{policy.issuer}</dd>
                  </div>
                {/if}
                {#if policy.account}
                  <div>
                    <dt>{_("Account")}</dt>
                    <dd>
                      <a href={$url_for_account(policy.account)}>
                        {policy.account}
                      </a>
                    </dd>
                  </div>
                {/if}
                <div>
                  <dt>{_("Purchased")}</dt>
                  <dd>{day(policy.purchased)}</dd>
                </div>
                {#if policy.renewal}
                  <div>
                    <dt>{_("Renewal")}</dt>
                    <dd>{day(policy.renewal)}</dd>
                  </div>
                {/if}
                {#if policy.frequency}
                  <div>
                    <dt>{_("Frequency")}</dt>
                    <dd>{policy.frequency}</dd>
                  </div>
                {/if}
                {#if policy.deductible}
                  <div>
                    <dt>{_("Deductible")}</dt>
                    <dd>{amount(policy.deductible)}</dd>
                  </div>
                {/if}
                {#if policy.documents.length || policy.account}
                  <div class="documents">
                    <dt>{_("Documents")}</dt>
                    <dd>
                      {#each policy.documents as document (document.key)}
                        <a
                          href={$url_for_raw("statement/", {
                            entry_hash: policy.entry_hash,
                            key: document.key,
                          })}
                          target="_blank"
                          data-remote>{basename(document.filename)}</a
                        >
                      {:else}
                        <span>{_("Drop a file on this row to attach it.")}</span
                        >
                      {/each}
                    </dd>
                  </div>
                {/if}
                {#if policy.note}
                  <div class="note">
                    <dt>{_("Note")}</dt>
                    <dd>{policy.note}</dd>
                  </div>
                {/if}
              </dl>
            </details>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-wrap {
    overflow-x: auto;
  }

  table {
    width: 100%;
  }

  small {
    display: block;
    color: var(--text-color-lightest);
  }

  .status {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    font-size: 0.85em;
    color: var(--text-color);
    background: var(--background-darkest);
    border-radius: 1rem;
  }

  .status.active {
    color: light-dark(hsl(145deg 70% 24%), hsl(145deg 70% 72%));
    background: light-dark(hsl(145deg 60% 91%), hsl(145deg 45% 18%));
  }

  .status.waiting,
  .status.not_started {
    color: light-dark(hsl(42deg 80% 25%), hsl(42deg 85% 70%));
    background: light-dark(hsl(48deg 90% 90%), hsl(42deg 50% 18%));
  }

  .status.cancelled {
    color: var(--error);
  }

  details {
    position: relative;
  }

  summary {
    color: var(--link-color);
    cursor: pointer;
  }

  dl {
    width: max-content;
    min-width: 260px;
    padding: 0.75rem;
    margin-top: 0.5rem;
    background: var(--background);
    border: 1px solid var(--border);
    box-shadow: var(--box-shadow-button);
  }

  dl div {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 0.75rem;
  }

  dt {
    color: var(--text-color-lightest);
  }

  dd {
    margin: 0;
  }

  .note dd {
    max-width: 300px;
    white-space: normal;
  }

  .documents dd {
    display: flex;
    flex-direction: column;
  }

  .documents span {
    color: var(--text-color-lightest);
  }
</style>

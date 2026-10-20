<script lang="ts">
  import { untrack } from "svelte";

  import { _ } from "../../i18n.ts";
  import { get_el } from "../../lib/dom.ts";
  import { shallow_equal } from "../../lib/equals.ts";
  import { log_error } from "../../log.ts";
  import { is_supported_datatransfer } from "../../modals/document-upload.ts";
  import { notify_err } from "../../notifications.ts";
  import { is_loading } from "../../router.ts";
  import {
    type JournalSort,
    journal_show,
    journal_sort,
  } from "../../stores/journal.ts";
  import { get_account_from_url } from "../accounts/index.ts";
  import { handle_journal_click } from "./click_handler.ts";
  import JournalFilters from "./JournalFilters.svelte";
  import JournalHeaders from "./JournalHeaders.svelte";
  import type { JournalPageChunk } from "./page.ts";
  import type { JournalSortColumn } from "./sort.ts";
  import { sort_journal } from "./sort.ts";

  interface Props {
    initial_sort: JournalSort;
    journal: DocumentFragment;
    load_next_page?: (() => Promise<JournalPageChunk>) | null;
    show_change_and_balance: boolean;
  }

  let {
    initial_sort,
    journal,
    load_next_page = null,
    show_change_and_balance,
  }: Props = $props();

  let ol: HTMLOListElement | undefined = $state();
  let has_next_page = $state(false);
  let loading_next_page = $state(false);

  async function append_next_page(): Promise<void> {
    if (!ol || load_next_page == null || !has_next_page || loading_next_page) {
      return;
    }

    loading_next_page = true;
    try {
      const page = await load_next_page();
      // The journal rows are server-rendered HTML fragments.
      // eslint-disable-next-line svelte/no-dom-manipulating
      ol.append(page.fragment);
      has_next_page = page.has_more;
      const sort = $journal_sort;
      if (!shallow_equal(sort, initial_sort)) {
        sort_journal(ol, sort);
      }
    } catch (error) {
      const load_error =
        error instanceof Error
          ? error
          : new Error("Failed to load journal entries.");
      log_error(load_error.message, error);
      notify_err(load_error);
    } finally {
      loading_next_page = false;
    }
  }

  /** Set the data attributes for drag-and-drop on dragenter */
  function ondragenter(event: DragEvent) {
    const closest_element = get_el(event.target);
    const description = closest_element?.closest(".description");
    // Get the closest `<li>` to also find the first posting account in a transaction.
    const li = description?.closest("li");
    if (
      description instanceof Element &&
      li &&
      is_supported_datatransfer(event.dataTransfer)
    ) {
      const account = [...li.querySelectorAll("a")]
        .map((a) => new URL(a.href))
        .map(get_account_from_url)
        .find((res) => res.is_ok)?.value;
      if (account != null) {
        description.setAttribute("data-account-name", account);
        description.classList.add("dragover");
        event.preventDefault();

        const date_link = description
          .closest(".journal > li")
          ?.querySelector(".datecell")
          ?.querySelector("a");
        if (date_link != null) {
          const entry_date = date_link.innerText;
          const hash = new URL(date_link.href).hash;
          if (hash.startsWith("#context-")) {
            const entry_hash = hash.slice(9);
            description.setAttribute("data-entry-date", entry_date);
            description.setAttribute("data-entry-hash", entry_hash);
          }
        }
      }
    }
  }
</script>

<JournalFilters />
<JournalHeaders
  disabled={$is_loading}
  {show_change_and_balance}
  set_sort_column={(column: JournalSortColumn) => {
    const sort: JournalSort = [
      column,
      shallow_equal($journal_sort, [column, "asc"]) ? "desc" : "asc",
    ];
    if (ol) {
      sort_journal(ol, sort);
      $journal_sort = sort;
    }
  }}
/>
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<ol
  class={["flex-table", "journal", ...$journal_show.map((s) => `show-${s}`)]}
  bind:this={ol}
  onclick={handle_journal_click}
  {ondragenter}
  {@attach (node: HTMLOListElement) => {
    // Re-run on any change to the journal
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    journal;
    untrack(() => {
      const sort = $journal_sort;
      node.innerHTML = "";
      node.append(journal);
      has_next_page = load_next_page != null;
      loading_next_page = false;
      // If the data is already sorted by the fetched order, we do not need to sort again
      const needs_sorting = !shallow_equal(sort, initial_sort);
      if (needs_sorting) {
        sort_journal(node, sort);
      }
    });
  }}
></ol>
{#if has_next_page}
  <div
    class="journal-load-more"
    {@attach (node: HTMLDivElement) => {
      const observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((entry) => entry.isIntersecting)) {
            void append_next_page();
          }
        },
        { rootMargin: "800px 0px" },
      );
      observer.observe(node);
      return () => {
        observer.disconnect();
      };
    }}
  >
    <button
      disabled={loading_next_page}
      onclick={() => {
        void append_next_page();
      }}
    >
      {loading_next_page ? _("Loading…") : _("Load more")}
    </button>
  </div>
{/if}

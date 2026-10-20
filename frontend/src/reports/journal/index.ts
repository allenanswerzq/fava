import { get as store_get } from "svelte/store";

import { get_journal_page } from "../../api/index.ts";
import { _ } from "../../i18n.ts";
import { fragment_from_string } from "../../lib/dom.ts";
import { shallow_equal } from "../../lib/equals.ts";
import { get_url_filters } from "../../stores/filters.ts";
import { type JournalSort, journal_sort } from "../../stores/journal.ts";
import { Route } from "../route.ts";
import Journal from "./Journal.svelte";
import type { JournalPageChunk } from "./page.ts";

export interface JournalReportProps {
  journal: DocumentFragment;
  initial_sort: JournalSort;
  load_next_page: (() => Promise<JournalPageChunk>) | null;
}

export const journal = new Route<JournalReportProps>(
  "journal",
  Journal,
  async (url: URL) => {
    const filters = get_url_filters(url);
    const $journal_sort = store_get(journal_sort);
    const order = shallow_equal($journal_sort, ["date", "asc"])
      ? "asc"
      : "desc";
    const { journal, total_pages } = await get_journal_page({
      ...filters,
      page: 1,
      order,
    });

    let next_page = 2;
    const load_next_page =
      total_pages > 1
        ? async (): Promise<JournalPageChunk> => {
            const page = next_page;
            const result = await get_journal_page({ ...filters, page, order });
            next_page = page + 1;
            return {
              fragment: fragment_from_string(result.journal),
              has_more: page < result.total_pages,
            };
          }
        : null;

    return {
      journal: fragment_from_string(journal),
      initial_sort: ["date", order],
      load_next_page,
    };
  },
  () => _("Journal"),
);

import { get as store_get } from "svelte/store";

import {
  get_account_journal_page,
  get_account_report,
} from "../../api/index.ts";
import type { AccountBudget } from "../../api/validators.ts";
import type { AccountTreeNode } from "../../charts/hierarchy.ts";
import type { ParsedFavaChart } from "../../charts/index.ts";
import type { NonRelativeUrlPathError } from "../../helpers.ts";
import { get_url_path } from "../../helpers.ts";
import { fragment_from_string } from "../../lib/dom.ts";
import { err, ok, type Result } from "../../lib/result.ts";
import { get_url_filters } from "../../stores/filters.ts";
import { type JournalSort, journal_sort } from "../../stores/journal.ts";
import type { JournalPageChunk } from "../journal/page.ts";
import { Route } from "../route.ts";
import AccountReport from "./AccountReport.svelte";

export type AccountReportType = "journal" | "balances" | "changes";

const to_report_type = (s: string | null): AccountReportType =>
  s === "balances" || s === "changes" ? s : "journal";

export interface AccountReportProps {
  account: string;
  report_type: AccountReportType;
  charts: ParsedFavaChart[];
  journal: DocumentFragment | null;
  interval_balances: AccountTreeNode[] | null;
  dates: { begin: Date; end: Date }[] | null;
  budgets: Record<string, AccountBudget[]> | null;
  initial_sort: JournalSort;
  load_next_page: (() => Promise<JournalPageChunk>) | null;
}

class NotAnAccountUrlError extends Error {
  constructor(pathname: string) {
    super(`Path '${pathname}' is not a path for the account report.`);
  }
}

/**
 * Get the account from the given URL.
 */
export function get_account_from_url(
  url: URL,
): Result<string, NonRelativeUrlPathError | NotAnAccountUrlError> {
  return get_url_path(url).and_then((relative_path) => {
    const [base, account] = relative_path.split("/");
    if (base === "account" && account != null) {
      return ok(account);
    }
    return err(new NotAnAccountUrlError(relative_path));
  });
}

export const account_report = new Route<AccountReportProps>(
  "account",
  AccountReport,
  async (url) => {
    const account = get_account_from_url(url).unwrap();
    const report_type = to_report_type(url.searchParams.get("r"));
    const filters = get_url_filters(url);
    const $journal_sort = store_get(journal_sort);
    const order =
      $journal_sort[0] === "date" && $journal_sort[1] === "asc"
        ? "asc"
        : "desc";
    const { charts, journal, total_pages, interval_balances, dates, budgets } =
      await get_account_report({
        ...filters,
        a: account,
        r: report_type,
        order,
      });

    let next_page = 2;
    const load_next_page =
      journal != null && total_pages != null && total_pages > 1
        ? async (): Promise<JournalPageChunk> => {
            const page = next_page;
            const result = await get_account_journal_page({
              ...filters,
              a: account,
              page,
              order,
            });
            next_page = page + 1;
            return {
              fragment: fragment_from_string(result.journal),
              has_more: page < result.total_pages,
            };
          }
        : null;

    return {
      charts,
      journal: journal != null ? fragment_from_string(journal) : null,
      interval_balances,
      dates,
      budgets,
      account,
      report_type,
      initial_sort: ["date", order],
      load_next_page,
    };
  },
  ({ account }) => `account:${account}`,
);

import { get_budgets } from "../../api/index.ts";
import type { BudgetReport } from "../../api/validators.ts";
import { _ } from "../../i18n.ts";
import { get_url_filters } from "../../stores/filters.ts";
import { Route } from "../route.ts";
import Budgets from "./Budgets.svelte";

export type BudgetReportProps = BudgetReport;

export const budgets = new Route<BudgetReportProps>(
  "budgets",
  Budgets,
  async (url) => get_budgets(get_url_filters(url)),
  () => _("Budget"),
);

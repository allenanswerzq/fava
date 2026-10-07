import { get_insurance } from "../../api/index.ts";
import type { InsurancePolicy } from "../../api/validators.ts";
import { _ } from "../../i18n.ts";
import { Route } from "../route.ts";
import Insurance from "./Insurance.svelte";

export interface InsuranceReportProps {
  policies: InsurancePolicy[];
}

export const insurance = new Route<InsuranceReportProps>(
  "insurance",
  Insurance,
  async () => ({ policies: await get_insurance() }),
  () => _("Insurance"),
);

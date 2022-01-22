/**
 * This module contains the main code to render Fava's charts.
 *
 * The charts heavily use d3 libraries.
 */

import { getScriptTagValue } from "../lib/dom";
import type { Result } from "../lib/result";
import { ok } from "../lib/result";
import { array, object, string, unknown } from "../lib/validation";

import { bar } from "./bar";
import type { BarChart } from "./bar";
import type { ChartContext } from "./context";
import { hierarchy } from "./hierarchy";
import type { HierarchyChart } from "./hierarchy";
import { balances, commodities } from "./line";
import type { LineChart } from "./line";
import { scatterplot } from "./scatterplot";
import type { ScatterPlot } from "./scatterplot";
import { sankeyplot } from "./sankeyplot";
import type { SankeyPlot } from "./sankeyplot";

const parsers: Partial<
  Record<
    string,
    (
      json: unknown,
      ctx: ChartContext,
      label: string
    ) => Result<ChartTypes, string>
  >
> = {
  balances,
  commodities,
  bar,
  hierarchy,
  scatterplot,
  sankeyplot,
};

export type ChartTypes =
  | HierarchyChart
  | BarChart
  | ScatterPlot
  | LineChart
  | SankeyPlot;
export type NamedChartTypes = ChartTypes & { name?: string };

const chart_data_validator = array(
  object({ label: string, type: string, data: unknown })
);

export function parseChartData(
  ctx: ChartContext
): Result<NamedChartTypes[], string> {
  const res = getScriptTagValue("#chart-data", chart_data_validator);
  if (!res.success) {
    return res;
  }
  const chartData = res.value;
  const result: NamedChartTypes[] = [];
  chartData.forEach((chart) => {
    const parser = parsers[chart.type];
    if (parser) {
      console.log("Parsing chart data....", chart.type);
      console.log(chart.data);
      const r = parser(chart.data, ctx, chart.label);
      if (r.success) {
        result.push({ name: chart.label, ...r.value });
      }
    }
  });
  return ok(result);
}

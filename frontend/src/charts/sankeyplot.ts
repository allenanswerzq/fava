import { ok } from "../lib/result";
import type { Result } from "../lib/result";
import {
  array,
  boolean,
  date,
  number,
  object,
  record,
  string,
  tuple,
} from "../lib/validation";

export type SankeyPlotNode = {
  id: string;
};

export type SankeyPlotLink = {
  source: string;
  target: string;
  value: number;
};
export type SankeyPlotData = {
  nodes: SankeyPlotNode[];
  links: SankeyPlotLink[];
  budget_actual: SankeyPlotLink[];
};
export interface SankeyPlot {
  type: "sankeyplot";
  data?: SankeyPlotData;
  tooltipText?: undefined;
}

const sankeyplot_validator = array(
  object({ nodes_ss: string, links_ss: string })
);

export function sankeyplot(json: undefined): Result<SankeyPlot, string> {
  const res = sankeyplot_validator(json);
  if (!res.success) {
    return res;
  }
  const parsedData = res.value;
  // Define data and initialize
  let data: SankeyPlotData = { nodes: [], links: [], budget_actual : []};
  for (const { nodes_ss, links_ss } of parsedData) {
    let nodes = JSON.parse(nodes_ss);
    for (const node of nodes) {
      data.nodes.push({ id: node });
    }
    let links = JSON.parse(links_ss);
    for (const link of links) {
      let val_ss = link[2].split(' ');
      data.links.push({
        source: link[0],
        target: link[1],
        value: Number(val_ss[0]),
      });
      if (val_ss.length == 2) {
        data.budget_actual.push({
          source: link[0],
          target: link[1],
          value: Number(val_ss[1]),
        });
      }
    }
    // console.log(data)
    // console.log(nodes);
    // console.log(links_ss)
  }
  return ok({ type: "sankeyplot" as const, data });
}

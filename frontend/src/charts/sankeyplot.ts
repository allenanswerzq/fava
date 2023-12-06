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

export type SankeyPlotCollapsed = {
  source: string;
  target: string;
  value: number;
};

export type SankeyPlotData = {
  nodes: SankeyPlotNode[];
  links: SankeyPlotLink[];
  budget_actual: SankeyPlotLink[];
  collapsed_links: SankeyPlotCollapsed[];
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
  let data: SankeyPlotData = { nodes: [], links: [], budget_actual: [], collapsed_links: []};
  for (const { nodes_ss, links_ss } of parsedData) {
    let links = JSON.parse(links_ss);
    let collapsed_map = new Map();
    for (const link of links) {
      let val_ss = link[2].split(' ');
      if (val_ss.length == 1) {
        data.links.push({
          source: link[0],
          target: link[1],
          value: Number(val_ss[0]),
        });
      }
      else if (val_ss.length == 2) {
        if (val_ss[1] == "collapsed") {
          // collapsed links
          let first_part = link[0].split(":")[0].split("_")[1];
          // console.log("AAAAAAAA", first_part);
          if (first_part.includes("Assets") || first_part.includes("Expenses") || first_part.includes("Equity")) {
            console.log("Collapsing", link[1]);
            collapsed_map.set(link[1], true);
          }
          else {
            console.log("Collapsing", link[0]);
            collapsed_map.set(link[0], true);
          }

          data.collapsed_links.push({
            source: link[0],
            target: link[1],
            value: Number(val_ss[0]),
          });
        }
        else {
          data.links.push({
            source: link[0],
            target: link[1],
            value: Number(val_ss[0]),
          });

          // see budget_tree.py
          data.budget_actual.push({
            source: link[0],
            target: link[1],
            value: Number(val_ss[1]),
          });
        }
      }
    }

    let nodes = JSON.parse(nodes_ss);
    for (const node of nodes) {
      let ok = collapsed_map.get(node);
      if (ok == true) continue;
      console.log("GET", node, ok);
      data.nodes.push({ id: node });
    }
    // console.log(data)
    // console.log("AAAAAAAA", data.nodes);
    // console.log(links_ss)
  }
  return ok({ type: "sankeyplot" as const, data });
}

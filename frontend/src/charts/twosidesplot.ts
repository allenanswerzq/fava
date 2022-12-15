import { ok } from "../lib/result";
import type { Result } from "../lib/result";
import {
  array,
  date,
  number,
  object,
  record,
  string,
  tuple,
} from "../lib/validation";

export type TwoSidesPlotValue = {
  account: string;
  value: number;
};

export type TwoSidesPlotData = {
  assets: TwoSidesPlotValue[];
  others: TwoSidesPlotValue[];
};

export interface TwoSidesPlot {
  type: "twosidessplot";
  data: TwoSidesPlotData;
  tooltipText?: undefined;
}

const twosidesplot_validator = array(
  object({ assets_ss: string, others_ss: string })
);

export function twosidesplot(json: undefined): Result<TwoSidesPlot, string> {
  const res = twosidesplot_validator(json);
  if (!res.success) {
    return res;
  }
  const parsedData = res.value;
  // Define data and initialize
  let data: TwoSidesPlotData = { assets: [], others: []};
  for (const { assets_ss, others_ss } of parsedData) {
    let assets = JSON.parse(assets_ss);
    for (const asset of assets) {
      data.assets.push({ account: asset.account, value: asset.value});
    }

    let others = JSON.parse(others_ss);
    for (const other of others) {
      data.others.push({ account: other.account, value: other.value});
    }
}
return ok({ type: "twosidesplot" as const, data });
}

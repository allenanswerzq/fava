<script lang="ts">
  import { Line } from "@codemirror/state";
import { extent } from "d3-array";
  import { axisBottom, axisLeft } from "d3-axis";
  import { quadtree } from "d3-quadtree";
  import { scalePoint, scaleUtc } from "d3-scale";
  import { } from "os";

  import { day } from "../format";

  import Axis from "./Axis.svelte";
  import { scatterplotScale } from "./helpers";
  import type { ScatterPlotDatum } from "./scatterplot";
  import type { TooltipFindNode } from "./tooltip";
  import { domHelpers, positionedTooltip } from "./tooltip";

  export let data: ScatterPlotDatum[];
  export let width: number;

  const today = new Date();
  const margin = {
    top: 10,
    right: 10,
    bottom: 30,
    left: 70,
  };
  const height = 250;
  $: innerWidth = width - margin.left - margin.right;
  $: innerHeight = height - margin.top - margin.bottom;

  // Scales
  $: dateExtent = extent(data, (d) => d.date);
  $: x = scaleUtc()
    .domain(dateExtent[0] ? dateExtent : [0, 1])
    .range([0, innerWidth]);
  $: y = scalePoint()
    .padding(1)
    .domain(data.map((d) => d.type))
    .range([innerHeight, 0]);

  // Axes
  $: xAxis = axisBottom(x).tickSizeOuter(0);
  $: yAxis = axisLeft(y)
    .tickPadding(6)
    .tickSize(-innerWidth)
    .tickFormat((d) => d);

  /** Quadtree for hover. */
  $: quad = quadtree(
    data,
    (d) => x(d.date),
    (d) => y(d.type) ?? 0
  );

  function tooltipText(d: ScatterPlotDatum) {
    return [domHelpers.t(d.description), domHelpers.em(day(d.date))];
  }

  const tooltipFindNode: TooltipFindNode = (xPos, yPos) => {
    const d = quad.find(xPos, yPos);
    return d && [x(d.date), y(d.type) ?? 0, tooltipText(d)];
  };

  let groups:any[] = [];
  let id_map = new Map();
  let id = 0;
  for (const d of data) {
    if (!d.type.includes("Insurance_")) continue;
    if (id_map.has(d.type)) {
      let p = id_map.get(d.type);
      groups[p].push(d);
    }
    else {
      id_map.set(d.type, id);
      groups[id++] = [d];
    }
  }
  // console.log(groups);
</script>

<svg {width} {height}>
  <g
    use:positionedTooltip={tooltipFindNode}
    transform={`translate(${margin.left},${margin.top})`}
  >
    <Axis x axis={xAxis} {innerHeight} />
    <Axis y axis={yAxis} />
    <g>
      {#each data as dot}
        <circle
          r="4"
          fill={scatterplotScale(dot.description)}
          cx={x(dot.date)}
          cy={y(dot.type)}
          class:desaturate={dot.date > today}
        />
      {/each}

      {#if groups.length > 0}
        {#each groups as g}
          <line
            x1={x(g[0].date)}
            y1={y(g[0].type)}
            x2={x(g[g.length - 1].date)}
            y2={y(g[g.length - 1].type)}
            style="stroke:rgb(125,0,0);stroke-width:1"
          />
        {/each}

        <line
          x1={x(today)}
          y1=0
          x2={x(today)}
          y2={height}
          style="stroke:rgb(125,0,0);stroke-width:1"
        />
      {/if}

    </g>
  </g>
</svg>

<style>
  svg > g {
    pointer-events: all;
  }

  .desaturate {
    filter: saturate(50%);
  }
</style>

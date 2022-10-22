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
  const height = 350;
  $: innerWidth = width - margin.left - margin.right;
  $: innerHeight = height - margin.top - margin.bottom;

  // Scales
  $: dateExtent = extent(data, (d) => d.date);
  $: x = scaleUtc()
    .domain(dateExtent[0] ? dateExtent : [0, 1])
    .range([0, innerWidth]);
  $: y = scalePoint()
    .padding(1)
    // control how lable on y axis displayed
    .domain(data.map((d) => d.type.split('_')[1]))
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
  let group_wait = new Array();
  let group_buy = new Array();
  for (const group of groups) {
    let wait_pos = -1;
    let start_pos = -1;
    for (let i = 0; i < group.length; i++) {
      if (group[i].description.includes("buy")) {
        start_pos = i;
      }
      else if (group[i].description.includes("wait")) {
        wait_pos = i;
      }
      else if (group[i].type.includes("SPLIT")) {
        wait_pos = -2; // Do not draw any lines
        break;
      }
    }
    group_wait.push(wait_pos);
    group_buy.push(start_pos);
  }
  console.log(groups);
  console.log(group_wait);
  console.log(group_buy)
</script>

<svg {width} {height}>
  <g
    use:positionedTooltip={tooltipFindNode}
    transform={`translate(${margin.left},${margin.top})`}
  >

    <Axis x axis={xAxis} {innerHeight} />
    <Axis y axis={yAxis} />
    <g>
      {#each groups as g}
        {#each g as dot, i}
          {#if i > 0}
            <circle
              r="4"
              fill={scatterplotScale(dot.type + dot.description)}
              cx={x(dot.date)}
              cy={y(dot.type.split('_')[1])}
              class:desaturate={dot.date > today}
            />
          {/if}
        {/each}
      {/each}

      {#each groups as g, i}
        {#if group_buy[i] != -1 && group_wait[i] != -1}
          <line
            x1={x(g[group_buy[i]].date)}
            y1={y(g[group_buy[i]].type.split('_')[1])}
            x2={x(g[group_wait[i]].date)}
            y2={y(g[group_wait[i]].type.split('_')[1])}
            style="stroke:rgb(255,0,0);stroke-width:1"
            stroke-dasharray="5,5,5"
          />
        {/if}

        {#if group_wait[i] == -1}
          <line
            x1=0
            y1={y(g[0].type.split('_')[1])}
            x2={x(g[g.length - 1].date)}
            y2={y(g[g.length - 1].type.split('_')[1])}
            style="stroke:rgb(125,0,0);stroke-width:1"
          />
        {:else if group_wait[i] != -2}
          <line
            x1={x(g[group_wait[i]].date)}
            y1={y(g[group_wait[i]].type.split('_')[1])}
            x2={x(g[g.length - 1].date)}
            y2={y(g[g.length - 1].type.split('_')[1])}
            style="stroke:rgb(125,0,0);stroke-width:1"
          />
        {/if}
      {/each}

      <line
        x1={x(today)}
        y1=0
        x2={x(today)}
        y2={height}
        style="stroke:rgb(125,0,0);stroke-width:1"
      />

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

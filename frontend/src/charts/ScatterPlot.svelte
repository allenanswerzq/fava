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
    .domain(data.map((d) => d.type))
    .range([innerHeight, 0]);

  // Axes
  $: xAxis = axisBottom(x).tickSizeOuter(0);
  $: yAxis = axisLeft(y)
    .tickPadding(6)
    .tickSize(-innerWidth)
    .tickFormat((d) => d.split('#')[0].split('_')[1]);

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
  let plot_insurance = false;
  for (const d of data) {
    if (!d.type.includes("Insurance_")) continue;
    plot_insurance = true;
    if (id_map.has(d.type)) {
      let p = id_map.get(d.type);
      groups[p].push(d);
    }
    else {
      id_map.set(d.type, id);
      groups[id++] = [d];
    }
  }
  let group_start = new Map();
  let group_wait = new Array();
  let group_buy = new Array();
  let group_stop = new Array();
  let group_colors = new Array();
  for (const group of groups) {
    let buy_pos = -1;
    let wait_pos = -1;
    let stop_pos = -1;
    let end_pos = -1;
    for (let i = 0; i < group.length; i++) {
      if (group[i].description.includes("start")) {
        group_start.set(i, 1); // Find all start position, used for SPLIT
      }
      else if (group[i].description.includes("buy")) {
        // assert(buy_pos == -1);
        buy_pos = i;
      }
      else if (group[i].description.includes("wait")) {
        // assert(wait_pos == -1);
        wait_pos = i;
      }
      else if (group[i].description.includes("stop")) {
        stop_pos = i; // Find the last stop pos
      }
      else if (group[i].description.includes("end")) {
        end_pos = i;
      }
    }
    if (end_pos != -1) {
      stop_pos = end_pos;
    }
    group_wait.push(wait_pos);
    group_buy.push(buy_pos);
    group_stop.push(stop_pos);

    let type = group[0].type.split('#')[1];
    if (type == "团险") {
      group_colors.push("rgb(0, 0, 0)");
    }
    else if (type == "防癌") {
      group_colors.push("rgb(0, 0, 255)");
      group_colors.push(scatterplotScale(type));
    }
    else if (type == "意外") {
      group_colors.push("rgb(0, 255, 100)");
    }
    else if (type == "医疗") {
      group_colors.push("rgb(205, 0, 0)");
    }
    else if (type == "寿险") {
      group_colors.push("rgb(0, 255, 0)");
    }
    else {
      group_colors.push("rgb(255, 255, 255)");
    }
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
      {#if plot_insurance}
        {#each groups as g}
          {#each g as dot, i}
            {#if !group_start.get(i) }
              <circle
                r="4"
                fill={scatterplotScale(dot.description)}
                cx={x(dot.date)}
                cy={y(dot.type)}
                class:desaturate={dot.date > today}
              />
            {/if}
          {/each}
        {/each}
      {:else}
        {#each data as dot, i}
            <circle
              r="4"
              fill={scatterplotScale(dot.type + dot.description)}
              cx={x(dot.date)}
              cy={y(dot.type)}
              class:desaturate={dot.date > today}
            />
        {/each}
      {/if}

      {#each groups as g, i}
        {#if group_buy[i] == -1 && group_wait[i] != -1}
          <line
            x1=0
            y1={y(g[group_wait[i]].type)}
            x2={x(g[group_wait[i]].date)}
            y2={y(g[group_wait[i]].type)}
            style="stroke-width:1"
            stroke-dasharray="5,5,5"
            stroke="rgb(125,0,0)"
          />
        {:else if group_buy[i] != -1 && group_wait[i] != -1}
          <line
            x1={x(g[group_buy[i]].date)}
            y1={y(g[group_buy[i]].type)}
            x2={x(g[group_wait[i]].date)}
            y2={y(g[group_wait[i]].type)}
            style="stroke-width:1"
            stroke-dasharray="5,5,5"
            stroke="rgb(125,0,0)"
          />
        {/if}

        {#if group_wait[i] == -1 && group_stop[i] != -1}
          <line
            x1=0
            y1={y(g[group_stop[i]].type)}
            x2={x(g[group_stop[i]].date)}
            y2={y(g[group_stop[i]].type)}
            style="stroke-width:1"
            stroke={group_colors[i]}
          />
        {:else if group_wait[i] != -1 && group_stop[i] != -1}
          <line
            x1={x(g[group_wait[i]].date)}
            y1={y(g[group_wait[i]].type)}
            x2={x(g[group_stop[i]].date)}
            y2={y(g[group_stop[i]].type)}
            style="stroke-width:1"
            stroke={group_colors[i]}
          />
        {:else if group_wait[i] != -1 && group_stop[i] == -1}
          <line
            x1={x(g[group_wait[i]].date)}
            y1={y(g[group_wait[i]].type)}
            x2={width}
            y2={y(g[group_wait[i]].type)}
            style="stroke:rgb(125,0,0);stroke-width:1"
            stroke={group_colors[i]}
          />
        {:else if group_wait[i] == -1 && group_stop[i] == -1}
          {#if group_buy[i] != -1}
            <line
              x1={x(g[group_buy[i]].date)}
              y1={y(g[group_buy[i]].type)}
              x2={width}
              y2={y(g[group_buy[i]].type)}
              style="stroke-width:1"
              stroke={group_colors[i]}
            />
          {/if}
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

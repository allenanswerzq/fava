<script lang="ts">
  import { Line } from "@codemirror/state";
import { extent } from "d3-array";
  import { axisBottom, axisLeft } from "d3-axis";
  import { quadtree } from "d3-quadtree";
  import { scalePoint, scaleUtc } from "d3-scale";
  import { } from "os";

  import { day } from "../format";
  import { string } from "../lib/validation";

  import Axis from "./Axis.svelte";
  import Axisx from "./Axisx.svelte";
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
    left: 120,
  };

  let groups:any[] = [];
  let id_map = new Map();
  let id = 0;
  for (const d of data) {
    if (id_map.has(d.type)) {
      let p = id_map.get(d.type);
      groups[p].push(d);
    }
    else {
      id_map.set(d.type, id);
      groups[id++] = [d];
    }
  }

  const height = 100;
  $: innerWidth = width - margin.left - margin.right;
  $: innerHeight = height - margin.top - margin.bottom;

  let person_groups = new Map();
  for (const group of groups) {
    let person = group[0].type.split("-")[0]

    if (group[0].type[0] == "_") {
      // NOTE: hack for Event
      person = "_NormalEvents"
    }

    if (person_groups.has(person)) {
      person_groups.get(person).push(group);
    }
    else {
      person_groups.set(person, [group]);
    }
  }

  let group_wait = new Map();
  let group_buy = new Map();
  let group_stop = new Map();
  let group_colors = new Map();
  $: for (const [person, groups] of person_groups.entries()) {
    for (const group of groups) {
      let buy_pos = -1;
      let wait_pos = -1;
      let stop_pos = -1;
      let end_pos = -1;
      for (let i = 0; i < group.length; i++) {
        if (group[i].description.includes("buy")) {
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

      if (group_wait.has(person))
        group_wait.get(person).push(wait_pos);
      else
        group_wait.set(person, [wait_pos]);

      if (group_buy.has(person))
        group_buy.get(person).push(buy_pos);
      else
        group_buy.set(person, [buy_pos]);

      if (group_stop.has(person))
        group_stop.get(person).push(stop_pos);
      else
        group_stop.set(person, [stop_pos]);

      let type = group[0].type.split('#')[1];
      // console.log("AAA", type);
      if (type == "团险") {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(0, 0, 0)");
        else
          group_colors.set(person, ["rgb(0, 0, 0)"]);
      }
      else if (type == "防癌") {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(0, 0, 255)");
        else
          group_colors.set(person, ["rgb(0, 0, 255)"]);
      }
      else if (type == "意外") {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(0, 255, 100)");
        else
          group_colors.set(person, ["rgb(0, 255, 100)"]);
      }
      else if (type == "医疗") {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(205, 0, 0)");
        else
          group_colors.set(person, ["rgb(205, 0, 0)"]);
      }
      else if (type == "寿险") {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(0, 255, 0)");
        else
          group_colors.set(person, ["rgb(0, 255, 0)"]);
      }
      else {
        if (group_colors.has(person))
          group_colors.get(person).push("rgb(255, 255, 255)");
        else
          group_colors.set(person, ["rgb(255, 255, 255)"]);
      }
    }
  }

  console.log(groups);
  console.log(group_wait);
  console.log(group_buy)

  $: group_y = new Map();
  $: group_yAxis = new Map();
  $: group_xAxis = new Map();
  $: group_tiptext = new Map();
    // Scales
  $: dateExtent = extent(data, (d) => d.date);
  $: x = scaleUtc().domain(dateExtent[0] ? dateExtent : [0, 1]).range([0, innerWidth]);
  $: count = 0;
  $: for (const [person, groups] of person_groups.entries()) {
    let cur_data = new Array();
    for (const g of groups) {
      for (const d of g)
        cur_data.push(d);
    }

    let y = scalePoint()
        .padding(1)
        .domain(cur_data.map((d) => d.type))
        .range([innerHeight, 0]);

    function tick_format(d : string) {
      return d.split('#')[0].split('_')[1];
    }

    let yAxis = axisLeft(y)
      .tickPadding(6)
      // .tickSize(-innerWidth)
      .tickFormat(tick_format);

    if (count + 1 < person_groups.size) {
      let xAxis = axisBottom(x).tickSizeOuter(0).tickFormat(d => "");
      group_xAxis.set(person, xAxis);
    } else {
      let xAxis = axisBottom(x).tickSizeOuter(0);
      group_xAxis.set(person, xAxis);
    }
    count++;

    /** Quadtree for hover. */
    let quad = quadtree(
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

    group_y.set(person, y)
    group_yAxis.set(person, yAxis);
    group_tiptext.set(person, tooltipFindNode);
  }

  console.log("Person", person_groups);
  console.log(group_colors);
</script>

{#each [...person_groups] as [person, groups], i}

<svg {width} {height}>
  <g use:positionedTooltip={group_tiptext.get(person)} transform={`translate(${margin.left},${margin.top})`} >
    {#if i + 1 < person_groups.size }
      <Axisx x axis={group_xAxis.get(person)} {innerHeight}/>
      <Axis y axis={group_yAxis.get(person)} />
    {:else}
      <Axis x axis={group_xAxis.get(person)} {innerHeight}/>
      <Axis y axis={group_yAxis.get(person)} />
    {/if}

    {#each groups as group}
      {#each group as dot, j}
        <circle
          r="4"
          fill={scatterplotScale(dot.description)}
          cx={x(dot.date)}
          cy={group_y.get(person)(dot.type)}
          class:desaturate={dot.date > today}
        />
      {/each}
    {/each}

    {#each groups as g, i}
      {#if person == "_NormalEvents" }
        <line
          x1={x(g[0].date)}
          y1={group_y.get(person)(g[0].type)}
          x2={x(g[g.length - 1].date)}
          y2={group_y.get(person)(g[g.length - 1].type)}
          style="stroke-width:1"
          stroke-dasharray="5,5,5"
          stroke="rgb(125,0,0)"
        />
      {/if}

      {#if group_buy.get(person)[i] == -1 && group_wait.get(person)[i] != -1}
        <line
          x1=0
          y1={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          x2={x(g[group_wait.get(person)[i]].date)}
          y2={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          style="stroke-width:1"
          stroke-dasharray="5,5,5"
          stroke="rgb(125,0,0)"
        />
      {:else if group_buy.get(person)[i] != -1 && group_wait.get(person)[i] != -1}
        <line
          x1={x(g[group_buy.get(person)[i]].date)}
          y1={group_y.get(person)(g[group_buy.get(person)[i]].type)}
          x2={x(g[group_wait.get(person)[i]].date)}
          y2={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          style="stroke-width:1"
          stroke-dasharray="5,5,5"
          stroke="rgb(125,0,0)"
        />
      {/if}

      {#if group_wait.get(person)[i] == -1 && group_stop.get(person)[i] != -1}
        <line
          x1=0
          y1={group_y.get(person)(g[group_stop.get(person)[i]].type)}
          x2={x(g[group_stop.get(person)[i]].date)}
          y2={group_y.get(person)(g[group_stop.get(person)[i]].type)}
          style="stroke-width:1"
          stroke={group_colors.get(person)[i]}
        />
      {:else if group_wait.get(person)[i] != -1 && group_stop.get(person)[i] != -1}
        <line
          x1={x(g[group_wait.get(person)[i]].date)}
          y1={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          x2={x(g[group_stop.get(person)[i]].date)}
          y2={group_y.get(person)(g[group_stop.get(person)[i]].type)}
          style="stroke-width:1"
          stroke={group_colors.get(person)[i]}
        />
      {:else if group_wait.get(person)[i] != -1 && group_stop.get(person)[i] == -1}
        <line
          x1={x(g[group_wait.get(person)[i]].date)}
          y1={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          x2={width}
          y2={group_y.get(person)(g[group_wait.get(person)[i]].type)}
          style="stroke-width:1"
          stroke={group_colors.get(person)[i]}
        />
      {:else if group_wait.get(person)[i] == -1 && group_stop.get(person)[i] == -1}
        {#if group_buy.get(person)[i] != -1}
          <line
            x1={x(g[group_buy.get(person)[i]].date)}
            y1={group_y.get(person)(g[group_buy.get(person)[i]].type)}
            x2={width}
            y2={group_y.get(person)(g[group_buy.get(person)[i]].type)}
            style="stroke-width:1"
            stroke={group_colors.get(person)[i]}
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
</svg>

{/each}

<style>
  svg > g {
    pointer-events: all;
  }

  .desaturate {
    filter: saturate(50%);
  }

</style>

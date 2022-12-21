<script lang="ts">
  import { scaleBand, scaleLinear } from "d3-scale";
  import { fly } from "svelte/transition";
  import type { TwoSidesPlot } from "./twosidesplot"


  export let data: TwoSidesPlot["data"];
  export let width: number;
  // export let tooltipText: TwoSidesPlot["tooltipText"];

  const height = 250;
  const fontSize = 10;
  // export let colortext = (d) => "#263238";

  $: assets = data.others;
  $: others = data.assets;

  // const margin = { top: 20, bottom: 20, left: 20, right: 20 };

  $: yScale = scaleBand()
    .domain(assets.map((d) => d.account))
    .range([0, height])
    .paddingInner(0.15);

  $: xScale = scaleLinear()
    .domain([0, Math.max(...assets.map((d) => d.value))])
    .range([0, width]);

  $: bScale = scaleBand()
    .domain(others.map((d) => d.account))
    .range([0, height])
    .paddingInner(0.15);

  $: aScale = scaleLinear()
    .domain([0, Math.max(...others.map((d) => d.value))])
    .range([0, width]);

    // ---------------- x
    //         |
    //         |
    //         y
</script>

<svg {width} {height}>
  {#each assets as asset, i}
    <rect class="right-side"
      x={width / 2 + 6}
      y={yScale(asset.account)}
      width={xScale(asset.value)}
      height={yScale.bandwidth()}
      in:fly={{ x: -200, duration: 1000, delay: i * 50 }}
    />

    <!-- <text
      x={width / 2}
      y={bScale(asset.account)}
      dy={fontSize / 2 - 2}
    > { asset.account } </text> -->

  {/each}

  {#each others as other, i}
    <rect class="left-side"
      x={width / 2 - 6 - aScale(other.value)}
      y={bScale(other.account)}
      width={aScale(other.value)}
      height={bScale.bandwidth()}
      in:fly={{ x: -200, duration: 1000, delay: i * 50 }}
    />

    <!-- <text
      x={width / 2}
      y={bScale(other.account)}
      dy={fontSize / 2 - 2}
    > { other.account.split(":")[1] } </text> -->

  {/each}
</svg>

<style>
  .left-side {
    fill: #13293d;
  }

  .right-side {
    fill: #732781;
  }
</style>
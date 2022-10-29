<script lang="ts">
  import { LayerCake, Svg } from "layercake";
  import Sankey from "./Sankey.svelte";
  import type { SankeyPlot } from "./sankeyplot";

  export let data: SankeyPlot["data"];
</script>

<div class="chart-container">
  <LayerCake {data}>
    <Svg>
      <Sankey />
    </Svg>
  </LayerCake>
</div>

<style>
  .chart-container {
    width: 100%;
    height: 450px;
    margin-top: 20px;
  }
</style>

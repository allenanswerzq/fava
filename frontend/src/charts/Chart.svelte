<script lang="ts">
  import type { Snippet } from "svelte";

  import { _ } from "../i18n.ts";
  import { router } from "../router.ts";
  import {
    bar_chart_mode,
    chart_toggled_currencies,
    hierarchy_chart_mode,
    line_chart_mode,
  } from "../stores/chart.ts";
  import { show_charts } from "../stores/url.ts";
  import BarChart from "./BarChart.svelte";
  import ChartLegend from "./ChartLegend.svelte";
  import { set_chart_tooltip } from "./context.ts";
  import HierarchyContainer from "./HierarchyContainer.svelte";
  import type { FavaChart } from "./index.ts";
  import LineChart from "./LineChart.svelte";
  import ModeSwitch from "./ModeSwitch.svelte";
  import Sankey from "./Sankey.svelte";
  import ScatterPlot from "./ScatterPlot.svelte";
  import { Tooltip } from "./tooltip.ts";

  interface Props {
    /** The chart to render. */
    chart: FavaChart;
    /** Additional elements to render in the top right. */
    children?: Snippet;
  }

  let { chart, children }: Props = $props();

  const tooltip = new Tooltip();
  set_chart_tooltip(tooltip);

  /** Width of the chart. */
  let width = $state<number>();
  let sankey_currency = $derived(
    chart.type === "sankey" ? chart.currency : null,
  );
  let sankey_currencies = $derived(
    chart.type === "sankey" ? chart.currencies : null,
  );
  let sankey_data = $derived(chart.type === "sankey" ? chart.data : null);
  let sankey_load_failed = $state(false);

  $effect(() => {
    if (chart.type === "sankey" && $show_charts) {
      sankey_load_failed = false;
      void chart.load().catch(() => {
        sankey_load_failed = true;
      });
    }
  });
</script>

<div class="flex-row">
  {#if $show_charts}
    {#if chart.type === "barchart"}
      <ChartLegend
        legend={chart.currencies}
        color={!($bar_chart_mode === "stacked" && chart.hasStackedData)}
        toggled={chart_toggled_currencies}
      />
    {/if}
    {#if chart.type === "linechart"}
      <ChartLegend
        legend={chart.series_names}
        color={true}
        toggled={chart_toggled_currencies}
      />
    {/if}
    {#if chart.type === "hierarchy" && $hierarchy_chart_mode === "treemap" && chart.treemap_currency}
      <ChartLegend
        legend={chart.currencies}
        color={false}
        active={chart.treemap_currency}
      />
    {/if}
    {#if chart.type === "sankey"}
      <ChartLegend
        legend={$sankey_currencies ?? []}
        color={false}
        active={chart.currency}
      />
    {/if}
    <span class="spacer"></span>
    {#if chart.type === "hierarchy"}
      <ModeSwitch store={hierarchy_chart_mode} />
    {:else if chart.type === "linechart"}
      <ModeSwitch store={line_chart_mode} />
    {:else if chart.type === "barchart" && chart.hasStackedData}
      <ModeSwitch store={bar_chart_mode} />
    {/if}
  {:else}<span class="spacer"></span>{/if}
  {@render children?.()}
  <button
    type="button"
    class="show-charts"
    onclick={() => {
      router.set_search_param("charts", $show_charts ? "false" : "");
    }}
  >
    {$show_charts ? "▼" : "◀"}
  </button>
</div>
<div
  class="chart-wrapper"
  hidden={!$show_charts}
  bind:clientWidth={width}
  {@attach tooltip.init.bind(tooltip)}
>
  {#if width != null && width > 0 && $show_charts}
    {#if chart.type === "barchart"}
      <BarChart {chart} {width} />
    {:else if chart.type === "hierarchy"}
      <HierarchyContainer {chart} {width} />
    {:else if chart.type === "linechart"}
      <LineChart {chart} {width} />
    {:else if chart.type === "scatterplot"}
      <ScatterPlot {chart} {width} />
    {:else if chart.type === "sankey"}
      {#if $sankey_data}
        <Sankey
          data={$sankey_data}
          currency={$sankey_currency ?? ""}
          role_labels={chart.role_labels}
          {width}
        />
      {:else if sankey_load_failed}
        <p role="alert">{_("Loading chart failed.")}</p>
      {:else}
        <p aria-busy="true">{_("Loading chart...")}</p>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .flex-row {
    margin-bottom: var(--flex-gap);
  }

  .chart-wrapper {
    position: relative;
  }

  @media print {
    button.show-charts {
      display: none;
    }
  }
</style>

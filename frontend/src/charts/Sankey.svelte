<script lang="ts">
  import { getContext } from "svelte";
  import * as Sankey from "d3-sankey";
  import { urlForAccount } from "../helpers";
  import router from "../router";
  import { number } from "../lib/validation";

  import { domHelpers, positionedTooltip } from "./tooltip";
  import { showPanel } from "@codemirror/view";

  import { scaleOrdinal } from "d3-scale";
  import { hclColorRange, } from "./helpers";

  /** The currently hovered account. */
  let highlighted: string | null = null;

  const colors10 = hclColorRange(10);
  const scatterplotScale = scaleOrdinal(colors10);

  const { data, width, height } = getContext("LayerCake");

  const stringToColour = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i += 1) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash); // eslint-disable-line no-bitwise
    }
    let colour = "#";
    for (let i = 0; i < 3; i += 1) {
      const value = (hash >> (i * 8)) & 0xff; // eslint-disable-line no-bitwise
      colour += ("00" + value.toString(16)).substr(-2);
    }
    return colour;
  };

  /** @type {Function} A function to return a color for the links. */
  export let colorLinks = (d) => {
    let src = d.source.id.includes("Income");
    let tar = d.target.id.includes("Income");
    // console.log("AAAA", d.source.id, d.target.id);
    if (src && tar) {
      // income to income
      return scatterplotScale(d.source.id);
    }
    else if (src) {
      // income to expense
      return scatterplotScale(d.target.id);
    }
    else {
      let tmp = d.source.id.split(":");
      if (tmp.length == 1) {
        // expnese to first level expense
        return scatterplotScale(d.target.id);
      }
      else {
        // first level expense to second level expenses
        return scatterplotScale(d.source.id);
      }
    }
  };

  /** @type {Function} A function to return a color for the node. */
  // export let colorNodes = d => '#333';
  export let colorNodes = (d) => stringToColour(d.id);

  /** @type {Function} A function to return a color for each text label. */
  export let colortext = (d) => "#263238";

  /** @type {Number} The width of each node, in pixels, passed to [`sankey.nodeWidth`](https://github.com/d3/d3-sankey#sankey_nodeWidth). */
  export let nodeWidth = 5;

  /** @type {Number} The padding between nodes, passed to [`sankey.nodePadding`](https://github.com/d3/d3-sankey#sankey_nodePadding). */
  export let nodePadding = 20;
  let exclude_percent = 0.005;
  $: fontSize = $width <= 320 ? 8 : 11.5;

  /** @type {Function} How to sort the links, passed to [`sankey.linkSort`](https://github.com/d3/d3-sankey#sankey_linkSort). */
  //   export let linkSort = null;

  /** @type {Function} The ID field accessor, passed to [`sankey.nodeId`](https://github.com/d3/d3-sankey#sankey_nodeId). */
  export let nodeId = (d) => d.id;

  /** @type {Function} An alignment function to position the Sankey blocks. See the [d3-sankey documentation](https://github.com/d3/d3-sankey#alignments) for more. */
  export let nodeAlign = Sankey.sankeyLeft;

  $: sankey = Sankey.sankey()
    .nodeAlign(nodeAlign)
    .nodeWidth(nodeWidth)
    .nodePadding(nodePadding)
    .nodeId(nodeId)
    .size([$width, $height])
    .nodeSort((a, b) => { return a.id.localeCompare(b.id); }); // sort by name
  // .linkSort((a, b) => b.value - a.value);

  // console.log(data)

  $: sankeyData = sankey($data);

  $: link = Sankey.sankeyLinkHorizontal();

  let node_max = 0;
  const compute_total = (g: typeof $data) => {
    const ans = new Array(g.nodes.length).fill(0);
    const in_degree = new Array(g.nodes.length).fill(0);
    for (const edge of g.links) {
      const target = edge.target.index;
      in_degree[target] += 1;
    }

    // console.log(in_degree);

    for (const edge of g.links) {
      // console.log(edge)
      const source = edge.source.index;
      const target = edge.target.index;
      let value = edge.value;

      if (in_degree[source] === 0) {
        value += ans[source];
        ans[source] = Math.round((value + Number.EPSILON) * 100) / 100;
      }

      value = ans[target] + edge.value;
      ans[target] = Math.round((value + Number.EPSILON) * 100) / 100;
      node_max = Math.max(node_max, ans[target]);
      //   console.log(edge.source.id, edge.target.id, value, ans[source], ans[target]);
    }

    console.log(ans);
    return ans;
  };
  $: nodes_total = compute_total($data);

  const compute_percent = (g: typeof $data) => {
    const ans = new Array(g.nodes.length).fill(0);
    for (const edge of g.links) {
      let source = edge.source.index;
      let target = edge.target.index;
      if (edge.target.id.includes("Income") || edge.target.id.includes("Assets")) {
        let tmp = target;
        target = source;
        source = tmp;
      }
      else if (edge.source.id.includes("Income") || edge.source.id.includes("Assets")) {
        ans[source] = 1;
      }
      if (nodes_total[source] > 0) {
        let value = nodes_total[target] / nodes_total[source];
        if (edge.target.id.includes("Expenses") && edge.target.id.split(":").length > 2) {
          ans[target] = Math.round((value + Number.EPSILON) * 100) / 100 * ans[source];
        }
        else {
          ans[target] = Math.round((value + Number.EPSILON) * 100) / 100;
        }
      }
    }
    return ans;
  };
  $: nodes_percent = compute_percent($data);


  const compute_budget_actual = (g: typeof $data) => {
    let name_index_map = new Map();
    for (const edge of g.links) {
      let target = edge.target;
      name_index_map.set(target.id, target.index);
    }
    const actual = new Array(g.nodes.length).fill(0);
    for (const edge of g.budget_actual) {
      let target = name_index_map.get(edge.target);
      actual[target] = edge.value;
    }
    return actual;
  };
  $: nodes_actual = compute_budget_actual($data);

  const compute_name = (g: typeof $data) => {
    const ans = new Array(g.nodes.length).fill("");
    for (const node of g.nodes) {
      const index = node.index;
      const id = node.id.split(":");
      const n = id.length;
      var ss = id[n - 1];
      if (ss.search('_') != -1) {
        const sp = ss.split("_");
        ss = sp[sp.length - 1];
      }
      if (g.budget_actual.length == 0) {
        if (n > 2 && nodes_percent[index] < exclude_percent) {
          ans[index] = "";
        } else {
          ans[index] = ss + ": ";
          ans[index] += nodes_total[index].toFixed(2);
          ans[index] += " (" + (nodes_percent[index] * 100).toFixed(0) + "%)";
        }
      }
      else {
        ans[index] = node.id.split("_")[1]
        ans[index] += " [";
        ans[index] += nodes_total[index].toFixed(2) + "/";
        // ans[index] += nodes_actual[index].toFixed(2)
        ans[index] += (nodes_total[index] - nodes_actual[index]).toFixed(2);
        ans[index] += "]";
        ans[index] += " (" + (nodes_percent[index] * 100).toFixed(0) + "%)";
      }
    }
    // console.log(ans);
    return ans;
  };
  $: nodes_name = compute_name($data);

  const compute_accounts_name = (g: typeof $data) => {
    const ans = new Array(g.nodes.length).fill("");
    for (const node of g.nodes) {
      const index = node.index;
      const id = node.id.split("_");
      ans[index] = id[id.length - 1];
    }
    return ans;
  };
  $: accounts_name = compute_accounts_name($data);
</script>

<g class="sankey-layer">
  <g class="link-group" >
    {#each sankeyData.links as d}
      {#if d.target.id.includes("Income")}
        <path class:faded={highlighted && highlighted != d.source.id}
          d={link(d)}
          fill="none"
          stroke={colorLinks(d)}
          stroke-opacity="0.8"
          stroke-width={d.width}
          on:mouseover={() => {
            highlighted = d.source.id;
          }}
          on:focus={() => {
            highlighted = d.source.id;
          }}
          on:mouseout={() => {
            highlighted = null;
          }}
          on:blur={() => {
            highlighted = null;
          }}
          on:click={() => router.navigate(urlForAccount(accounts_name[d.source.index]))}
        />
      {:else}
        <path class:faded={highlighted && highlighted != d.target.id}
          d={link(d)}
          fill="none"
          stroke={colorLinks(d)}
          stroke-opacity="0.8"
          stroke-width={d.width}
          on:mouseover={() => {
            highlighted = d.target.id;
          }}
          on:focus={() => {
            highlighted = d.target.id;
          }}
          on:mouseout={() => {
            highlighted = null;
          }}
          on:blur={() => {
            highlighted = null;
          }}
          on:click={() => router.navigate(urlForAccount(accounts_name[d.target.index]))}
        />
      {/if}
    {/each}
  </g>
  <g class="rect-group">
    {#each sankeyData.nodes as d, i}
      <rect
        x={d.x0}
        y={d.y0}
        height={d.y1 - d.y0}
        width={d.x1 - d.x0 + 4}
        fill={colorNodes(d)}
      />
      <text
        x={d.x0 < $width / 4 ? d.x1 + 6 : d.x0 - 6}
        y={(d.y1 + d.y0) / 2 - 6}
        dy={fontSize / 2 - 2}
        style="
          font-size: {fontSize}px;
          text-anchor: {d.x0 < $width / 4
          ? 'start'
          : 'end'};fill: {colortext(d)};"
      >
        {nodes_name[d.index]}
      </text>
    {/each}
  </g>
</g>

<style>
  text {
    pointer-events: none;
  }

  .faded {
    opacity: 0.5;
  }
</style>

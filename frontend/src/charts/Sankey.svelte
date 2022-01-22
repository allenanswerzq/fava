<script lang="ts">
  import { getContext } from "svelte";
  import * as Sankey from "d3-sankey";
  import { number } from "../lib/validation";

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
    const str = d.source.id + d.target.id;
    return stringToColour(str);
  };

  /** @type {Function} A function to return a color for the node. */
  // export let colorNodes = d => '#333';
  export let colorNodes = (d) => stringToColour(d.id);

  /** @type {Function} A function to return a color for each text label. */
  export let colortext = (d) => "#263238";

  /** @type {Number} The width of each node, in pixels, passed to [`sankey.nodeWidth`](https://github.com/d3/d3-sankey#sankey_nodeWidth). */
  export let nodeWidth = 5;

  /** @type {Number} The padding between nodes, passed to [`sankey.nodePadding`](https://github.com/d3/d3-sankey#sankey_nodePadding). */
  export let nodePadding = 10;

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

  $: fontSize = $width <= 320 ? 8 : 12;

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
      //   console.log(edge.source.id, edge.target.id, value, ans[source], ans[target]);
    }

    console.log(ans);
    return ans;
  };
  $: nodes_total = compute_total($data);

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
      ans[index] = ss;
    }
    // console.log(ans);
    return ans;
  };
  $: nodes_name = compute_name($data);
</script>

<g class="sankey-layer">
  <g class="link-group">
    {#each sankeyData.links as d}
      <path
        d={link(d)}
        fill="none"
        stroke={colorLinks(d)}
        stroke-opacity="0.5"
        stroke-width={d.width}
      />
    {/each}
  </g>
  <g class="rect-group">
    {#each sankeyData.nodes as d, i}
      <rect
        x={d.x0}
        y={d.y0}
        height={d.y1 - d.y0}
        width={d.x1 - d.x0}
        fill={colorNodes(d)}
      />
      <text
        x={d.x0 < $width / 4 ? d.x1 + 6 : d.x0 - 6}
        y={(d.y1 + d.y0) / 2}
        dy={fontSize / 2 - 2}
        style="
                            font-size: {fontSize}px;
                            text-anchor: {d.x0 < $width / 4
          ? 'start'
          : 'end'};fill: {colortext(d)};"
      >
        {nodes_name[d.index] + ": " + nodes_total[d.index]}
      </text>
    {/each}
  </g>
</g>

<style>
  text {
    pointer-events: none;
  }
</style>

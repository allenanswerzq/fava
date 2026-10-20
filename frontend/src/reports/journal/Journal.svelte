<script lang="ts">
  import type { JournalReportProps } from "./index.ts";
  import JournalTable from "./JournalTable.svelte";

  let { journal, initial_sort, load_next_page }: JournalReportProps = $props();
</script>

<JournalTable
  {journal}
  {initial_sort}
  {load_next_page}
  show_change_and_balance={false}
/>

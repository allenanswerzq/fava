<script lang="ts">
  import { _ } from "../i18n.ts";

  interface Props {
    /** Whether anything is changed - the button is disabled otherwise. */
    changed: boolean;
    /** Whether a patch is currently being written. */
    patching: boolean;
    /** Write the edited entry to its patch file. */
    onpatch: () => Promise<void>;
  }

  let { changed, patching, onpatch }: Props = $props();

  let button_content = $derived(patching ? _("Patching…") : _("Patch"));
</script>

<button
  type="button"
  class="muted"
  disabled={!changed || patching}
  onclick={onpatch}
>
  {button_content}
</button>

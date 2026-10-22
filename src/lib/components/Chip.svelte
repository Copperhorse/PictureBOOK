<script lang="ts">
  import type { BookStatus } from "$lib/api";
  let { status }: { status: BookStatus } = $props();
  const text: Record<BookStatus, string> = { draft: "Not started", planned: "Needs your OK", generating: "Making…", review: "Ready", failed: "Failed", interrupted: "Interrupted" };
  const kind: Record<BookStatus, string> = { draft: "", planned: "warn", generating: "warn", review: "ok", failed: "bad", interrupted: "warn" };
</script>
<span class="chip {kind[status]}">{text[status]}</span>

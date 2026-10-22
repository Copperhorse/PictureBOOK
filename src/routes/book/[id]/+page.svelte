<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { getBook } from "$lib/api";
  import { runningJob } from "$lib/state.svelte";

  let message = $state("Opening…");
  onMount(async () => {
    const id = page.params.id!;
    try {
      const b = await getBook(id);
      const generating = b.status === "generating" || runningJob(id)?.kind === "generate";
      const where = generating ? "generating" : b.status === "review" ? "review" : b.status === "planned" ? "characters" : "generating";
      await goto(`/book/${id}/${where}`, { replaceState: true });
    } catch (e) { message = String(e); }
  });
</script>
<p class="muted">{message}</p>
{#if message !== "Opening…"}<a class="btn ghost" href="/">Back to the library</a>{/if}

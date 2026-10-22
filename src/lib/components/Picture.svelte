<script lang="ts">
  import { pictureUrl } from "$lib/images";
  let { path, version = 0, maxSide = 0, alt = "", cover = false }: { path: string | null; version?: string | number; maxSide?: number; alt?: string; cover?: boolean } = $props();
  let src = $state<string | null>(null);
  let failed = $state(false);
  $effect(() => {
    const p = path, v = version, m = maxSide;
    src = null; failed = false;
    if (!p) return;
    let live = true;
    pictureUrl(p, v, m).then((u) => { if (live) src = u; }).catch(() => { if (live) failed = true; });
    return () => { live = false; };
  });
</script>
{#if src}<img {src} {alt} class:cover />{:else if failed}<span class="ph label">Picture not readable</span>{:else}<span class="ph label">Loading…</span>{/if}
<style>
  img { width: 100%; height: 100%; object-fit: contain; display: block; } img.cover { object-fit: cover; }
  .ph { display: grid; place-items: center; width: 100%; height: 100%; color: var(--text-faint); }
</style>

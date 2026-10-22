<script lang="ts">
  import { onMount } from "svelte";
  import { getSettings, libraryInfo, setSettings, type LibraryInfo, type Settings } from "$lib/api";
  import { app, toast } from "$lib/state.svelte";

  let settings = $state<Settings | null>(null);
  let info = $state<LibraryInfo | null>(null);
  onMount(async () => { try { [settings, info] = await Promise.all([getSettings(), libraryInfo()]); } catch (e) { toast(String(e), "error"); } });
  async function save() { if (settings) try { settings = await setSettings(settings); toast("Saved."); } catch (e) { toast(String(e), "error"); } }
  const gpu = $derived(app.sidecar.gpu);
</script>

<div class="stack" style="max-width: 640px">
  <h1>Settings</h1>
  <div class="card stack">
    <div class="row between"><h2>Picture engine</h2><span class="chip" class:ok={app.sidecar.state === "ready"} class:warn={app.sidecar.state === "starting"} class:bad={app.sidecar.state === "failed"}>{app.sidecar.state}</span></div>
    {#if app.sidecar.version}<p class="muted" style="margin: 0">Version {app.sidecar.version}</p>{/if}
    {#if gpu}<p class="muted" style="margin: 0">{gpu.name}, {gpu.vram_used_mib} of {gpu.vram_total_mib} MiB in use</p>
    {:else if app.sidecar.state === "ready"}<p class="muted" style="margin: 0">No graphics card was reported (is the NVIDIA driver loaded?).</p>{/if}
    {#if app.sidecar.error}<p style="color: var(--danger); margin: 0; font-family: var(--font-mono); font-size: 0.85rem">{app.sidecar.error}</p>{/if}
  </div>
  <div class="card row between"><div><h2>Is everything installed?</h2><p class="muted" style="margin: 4px 0 0">Checks the graphics card, the models and the helper programs.</p></div><a class="btn ghost" href="/setup">Run the check</a></div>
  <div class="card stack">
    <h2>Where your books are kept</h2>
    {#if info}<p class="mono" style="margin: 0; overflow-wrap: anywhere">{info.path}</p>
      <p class="faint" style="margin: 0; font-size: 0.85rem">Each book is a folder you can copy, rename or back up. The app finds books again by what is inside the folder, not by its name.</p>{/if}
  </div>
  {#if settings}
    <div class="card stack">
      <h2>New books</h2>
      <div class="row">
        <label class="stack" style="gap: 6px; flex: 1"><span class="label">Default style</span>
          <select bind:value={settings.style}><option value="crayon">Crayon and coloured pencil</option><option value="flat">Flat paper cut-out</option><option value="watercolour">Soft watercolour</option></select></label>
        <label class="stack" style="gap: 6px; width: 140px"><span class="label">Default pages</span><input type="number" min="1" max="10" bind:value={settings.pages} /></label>
      </div>
      <label class="row" style="gap: 10px"><input type="checkbox" bind:checked={settings.approve_first} style="width: auto" /><span>Let me check the characters before the pictures are drawn <span class="muted">(recommended)</span></span></label>
      <label class="row" style="gap: 10px"><input type="checkbox" bind:checked={settings.keep_recordings} style="width: auto" /><span>Keep my recordings <span class="muted">(off: a recording is deleted once the story has been written down)</span></span></label>
      <div><button class="btn" onclick={save}>Save</button></div>
    </div>
  {/if}
  {#if info}<p class="faint" style="font-size: 0.8rem">Pipeline scripts: <span class="mono">{info.scripts}</span></p>{/if}
</div>

<style>.mono { font-family: var(--font-mono); font-size: 0.85rem; }</style>

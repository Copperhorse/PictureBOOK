<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { beginBook, createBook, getSettings, pickAudioFile, type Style } from "$lib/api";
  import { app, blockers, toast } from "$lib/state.svelte";

  let mode = $state<"text" | "audio">("text");
  let title = $state(""), text = $state(""), audio = $state<string | null>(null);
  let style = $state<Style>("crayon"), pages = $state(6);
  let busy = $state(false);
  const MAX = 30000;

  onMount(async () => { try { const s = await getSettings(); style = s.style; pages = s.pages; } catch { /* defaults */ } });

  const ready = $derived(app.sidecar.state === "ready");
  const canMake = $derived(ready && !busy && (mode === "text" ? text.trim().length > 0 && text.length <= MAX : audio !== null));
  const fileName = $derived(audio ? audio.split(/[\\/]/).pop() : null);

  async function choose() { try { audio = (await pickAudioFile()) ?? audio; } catch (e) { toast(String(e), "error"); } }
  async function make() {
    busy = true;
    try {
      const book = await createBook({ title, text: mode === "text" ? text : undefined, audioPath: mode === "audio" ? (audio ?? undefined) : undefined, style, pages });
      try { await beginBook(book.meta.id); } catch (e) { toast(String(e), "error"); }
      await goto(`/book/${book.meta.id}/generating`);
    } catch (e) { toast(String(e), "error"); busy = false; }
  }
</script>

<div class="stack" style="max-width: 720px">
  <h1>New book</h1>
  {#if blockers().length}<p class="card warn">Something is missing on this computer ({blockers().map((b) => b.title).join(", ")}). <a href="/setup" style="text-decoration: underline">See what to do</a>.</p>{/if}
  {#if !ready}<p class="card warn">{app.sidecar.state === "starting" ? "The picture engine is still starting. You can write your story meanwhile." : `The picture engine is not running: ${app.sidecar.error ?? "unknown problem"}`}</p>{/if}

  <div class="card stack">
    <div class="row" role="tablist" aria-label="How to give the story">
      <button class="btn small" class:ghost={mode !== "text"} role="tab" aria-selected={mode === "text"} onclick={() => (mode = "text")}>Type the story</button>
      <button class="btn small" class:ghost={mode !== "audio"} role="tab" aria-selected={mode === "audio"} onclick={() => (mode = "audio")}>Use an audio file</button>
    </div>
    {#if mode === "text"}
      <label class="stack" style="gap: 6px"><span class="label">Story</span>
        <textarea rows="10" bind:value={text} placeholder="Once upon a time…"></textarea></label>
      <span class="faint" style="font-size: 0.8rem; text-align: right" class:over={text.length > MAX}>{text.length.toLocaleString()} / {MAX.toLocaleString()}</span>
    {:else}
      <div class="row"><button class="btn ghost" onclick={choose}>Choose a file…</button><span class="muted">{fileName ?? "wav, mp3, m4a, flac or ogg, English"}</span></div>
    {/if}
    <label class="stack" style="gap: 6px"><span class="label">Title (optional)</span><input bind:value={title} placeholder="The app picks one from the story" maxlength="80" /></label>
    <div class="row">
      <label class="stack" style="gap: 6px; flex: 1"><span class="label">Style</span>
        <select bind:value={style}><option value="crayon">Crayon and coloured pencil</option><option value="flat">Flat paper cut-out</option><option value="watercolour">Soft watercolour</option></select></label>
      <label class="stack" style="gap: 6px; width: 140px"><span class="label">Pages</span><input type="number" min="1" max="10" bind:value={pages} /></label>
    </div>
    <div class="row between"><span class="muted" style="font-size: 0.85rem">A 6-page book takes about 7 minutes; a long story with 8 pages about 15. You can check the characters before the pictures are drawn.</span>
      <button class="btn" style="white-space: nowrap" onclick={make} disabled={!canMake}>{busy ? "Starting…" : "Make the book"}</button></div>
  </div>
</div>

<style>
  .warn { border-color: var(--warn); color: var(--warn); }
  .over { color: var(--danger); }
</style>

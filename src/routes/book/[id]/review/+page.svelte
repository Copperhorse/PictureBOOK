<script lang="ts">
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { cancelJob, getBook, openBook, regenPages, undoPage, type BookDetail } from "$lib/api";
  import Picture from "$lib/components/Picture.svelte";
  import { app, runningJob, toast } from "$lib/state.svelte";
  import Chip from "$lib/components/Chip.svelte";

  const id = page.params.id!;
  let book = $state<BookDetail | null>(null);
  let loadError = $state<string | null>(null);
  let checked = $state<Record<number, boolean>>({});
  let lightbox = $state<{ path: string; version: string; title: string } | null>(null);
  let dlg = $state<HTMLDialogElement | undefined>();

  const job = $derived(runningJob(id));
  const picked = $derived(Object.entries(checked).filter(([, v]) => v).map(([k]) => Number(k)));
  const ver = (p: { redrawn: number }) => `${book?.meta.updated_at ?? 0}-${p.redrawn}-${app.booksVersion}`;

  async function load() { try { book = await getBook(id); loadError = null; } catch (e) { loadError = String(e); } }
  onMount(load);
  $effect(() => { app.booksVersion; load(); });
  $effect(() => { if (lightbox) dlg?.showModal(); else dlg?.close(); });

  async function redraw(pages: number[]) { try { await regenPages(id, pages); checked = {}; await load(); } catch (e) { toast(String(e), "error"); } }
  async function undo(n: number) { try { await undoPage(id, n); await load(); } catch (e) { toast(String(e), "error"); } }
  async function stop() { if (job) try { await cancelJob(job.jobId); } catch (e) { toast(String(e), "error"); } }
  async function open(what: "pdf" | "folder") { try { await openBook(id, what); } catch (e) { toast(String(e), "error"); } }
</script>

{#if loadError}
  <p class="card" style="color: var(--danger)">{loadError}</p><a class="btn ghost" href="/">Back to the library</a>
{:else if !book}<p class="muted">Loading…</p>
{:else}
  <div class="stack">
    <div class="row between wrap">
      <div><p class="label">Review</p><h1>{book.meta.title}</h1></div>
      <div class="row wrap">
        <button class="btn ghost small" onclick={() => open("folder")}>Open folder</button>
        <button class="btn small" onclick={() => open("pdf")} disabled={!book.pdf}>Open PDF</button>
      </div>
    </div>

    {#if job}
      <div class="card stack" role="status">
        <div class="row between"><strong>{job.kind === "regen" ? "Redrawing" : job.kind === "undo" ? "Restoring" : "Working"}: {job.message || "starting"}</strong><button class="btn ghost small" onclick={stop}>Cancel</button></div>
        <div class="bar"><div class="fill" style="width: {job.fraction * 100}%"></div></div>
      </div>
    {/if}

    <details class="card">
      <summary><strong>What to look for</strong> <span class="muted">(the computer cannot see these reliably)</span></summary>
      <ul class="muted">
        <li>Every person and animal has two hands and two legs, unless hidden.</li>
        <li>Every character appears exactly once.</li>
        <li>Everyone stands or sits on something solid.</li>
        <li>The picture shows what the sentence says.</li>
        <li>Hair and clothes match the other pages.</li>
      </ul>
      <p class="faint" style="margin: 0">If something is wrong, press <strong>Redraw</strong> on that page: it gets a new random drawing and the old one is kept.</p>
    </details>

    {#each book.problems as p}<p class="card" style="border-color: var(--warn); color: var(--warn)">{p}</p>{/each}

    {#if book.pages.length === 0}
      <p class="card muted">This book has no pages yet. {#if book.status !== "review"}<a href={`/book/${id}/generating`} style="text-decoration: underline">Open the generating screen</a>.{/if}</p>
    {/if}

    {#if picked.length}
      <div class="row sticky card"><span>{picked.length} page{picked.length === 1 ? "" : "s"} selected</span><button class="btn small" onclick={() => redraw(picked)} disabled={!!job}>Redraw selected</button><button class="btn ghost small" onclick={() => (checked = {})}>Clear</button></div>
    {/if}

    <div class="pages">
      {#each book.pages as p (p.index)}
        <article class="card pg" aria-label={`Page ${p.index}`}>
          <div class="row between"><label class="row"><input type="checkbox" bind:checked={checked[p.index]} aria-label={`Select page ${p.index}`} style="width: auto" /><strong>Page {p.index}</strong></label>
            {#if p.redrawn}<span class="chip warn">redrawn ×{p.redrawn}</span>{/if}</div>
          {#if p.image}
            <button class="pic" onclick={() => (lightbox = { path: p.image!, version: ver(p), title: `Page ${p.index}` })} aria-label={`View page ${p.index} full size`}><Picture path={p.image} version={ver(p)} alt={`Illustration for page ${p.index}: ${p.text}`} /></button>
          {:else}<div class="pic missing"><span class="muted">The picture is missing.</span></div>{/if}
          <p class="text">{p.text}</p>
          {#if p.hints.length}<ul class="notes">{#each p.hints as h}<li>{h}</li>{/each}</ul>{:else if !p.checked}<p class="note0" style="color: var(--warn)">Not checked since this page was redrawn. Look carefully at hands and characters.</p>{:else}<p class="faint note0">Computer notes: none. Check the hands yourself.</p>{/if}
          {#if p.versions.length}
            <div class="row versions"><span class="faint label">Earlier</span>
              {#each p.versions as v, i}<button class="thumb" onclick={() => (lightbox = { path: v, version: ver(p), title: `Page ${p.index}, earlier drawing ${i + 1}` })} aria-label={`View earlier drawing ${i + 1} of page ${p.index}`}><Picture path={v} version={ver(p)} maxSide={160} cover /></button>{/each}
            </div>
          {/if}
          <div class="row"><button class="btn small" onclick={() => redraw([p.index])} disabled={!!job}>Redraw</button>
            <button class="btn ghost small" onclick={() => undo(p.index)} disabled={!!job || !p.versions.length} title={p.versions.length ? "Put the previous drawing back" : "No earlier drawing"}>Undo</button></div>
        </article>
      {/each}
    </div>
    <div><Chip status={book.status} /></div>
  </div>

  <dialog bind:this={dlg} onclose={() => (lightbox = null)} onclick={() => (lightbox = null)} aria-label={lightbox?.title}>
    {#if lightbox}<div class="big"><Picture path={lightbox.path} version={lightbox.version} alt={lightbox.title} /></div>{/if}
  </dialog>
{/if}

<style>
  .wrap { flex-wrap: wrap; }
  details summary { cursor: pointer; } details ul { margin: 10px 0; padding-left: 20px; }
  .pages { display: grid; gap: 20px; max-width: 760px; }
  .pg { display: flex; flex-direction: column; gap: 12px; }
  .pic { padding: 0; border: 0; background: var(--surface-2); border-radius: var(--radius-s); overflow: hidden; display: block; width: 100%; aspect-ratio: 1; cursor: zoom-in; }
  .pic.missing { display: grid; place-items: center; cursor: default; border: 1px dashed var(--warn); }
  .text { margin: 0; line-height: 1.55; } .notes { margin: 0; padding-left: 20px; color: var(--warn); font-size: 0.9rem; } .note0 { margin: 0; font-size: 0.85rem; }
  .versions { flex-wrap: wrap; gap: 8px; } .thumb { padding: 0; border: 1px solid var(--border); border-radius: 6px; width: 64px; height: 64px; overflow: hidden; background: var(--surface-2); }
  .sticky { position: sticky; top: 8px; z-index: 5; }
  dialog { border: 0; padding: 0; background: transparent; max-width: 96vw; max-height: 96vh; } dialog::backdrop { background: rgba(0, 0, 0, 0.8); }
  .big { width: min(92vw, 92vh); height: min(92vw, 92vh); border-radius: var(--radius-m); overflow: hidden; background: var(--surface-2); }
</style>

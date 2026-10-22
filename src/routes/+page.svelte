<script lang="ts">
  import { onMount } from "svelte";
  import { deleteBook, deleteDamaged, listBooks, type LibraryEntry } from "$lib/api";
  import Picture from "$lib/components/Picture.svelte";
  import { app, toast } from "$lib/state.svelte";
  import Chip from "$lib/components/Chip.svelte";

  let entries = $state<LibraryEntry[] | null>(null);
  let loadError = $state<string | null>(null);
  let confirming = $state<string | null>(null);

  async function load() {
    try { entries = await listBooks(); loadError = null; } catch (e) { loadError = String(e); }
  }
  onMount(load);
  $effect(() => { app.booksVersion; load(); });

  const when = (s: number) => new Date(s * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  async function remove(entry: LibraryEntry) {
    try {
      if (entry.kind === "book") await deleteBook(entry.meta.id); else await deleteDamaged(entry.folder_name);
      confirming = null; toast("Deleted."); await load();
    } catch (e) { toast(String(e), "error"); }
  }
  const key = (e: LibraryEntry) => (e.kind === "book" ? e.meta.id : "d:" + e.folder_name);
</script>

<div class="stack">
  <div class="row between">
    <h1>Library</h1>
    <div class="row"><button class="btn ghost small" onclick={load}>Refresh</button><a class="btn" href="/new">New book</a></div>
  </div>

  {#if loadError}<p class="card" style="color: var(--danger)">{loadError}</p>
  {:else if entries === null}<p class="muted">Loading…</p>
  {:else if entries.length === 0}
    <div class="card empty"><h2>No books yet</h2><p class="muted">Tell a story and the app draws it as a picture book.</p><a class="btn" href="/new" style="align-self: flex-start">Make the first book</a></div>
  {:else}
    <ul class="grid">
      {#each entries as e (key(e))}
        <li class="card item">
          {#if e.kind === "book"}
            <a class="cover" href={`/book/${e.meta.id}`} aria-label={`Open ${e.meta.title}`}>
              {#if e.cover}<Picture path={e.cover} version={e.meta.updated_at} maxSide={480} cover />{:else}<span class="label">{e.status === "generating" ? "Drawing…" : e.page_count ? "Cover picture missing" : "No pictures yet"}</span>{/if}
            </a>
            <div class="info">
              <a class="title" href={`/book/${e.meta.id}`}>{e.meta.title}</a>
              <div class="row between"><Chip status={e.status} /><span class="faint small">{e.page_count ? `${e.page_count} pages · ` : ""}{when(e.meta.created_at)}</span></div>
            </div>
            <div class="row actions">
              {#if confirming === e.meta.id}
                <span class="muted small">Delete this book?</span>
                <button class="btn danger small" onclick={() => remove(e)}>Yes, delete</button><button class="btn ghost small" onclick={() => (confirming = null)}>No</button>
              {:else}
                <button class="btn ghost small" onclick={() => (confirming = e.meta.id)} disabled={e.status === "generating"}>Delete</button>
              {/if}
            </div>
          {:else}
            <div class="cover damaged"><span class="label">Damaged folder</span></div>
            <div class="info"><span class="title">{e.folder_name}</span><span class="muted small">{e.reason}</span></div>
            <div class="row actions">
              {#if confirming === "d:" + e.folder_name}
                <span class="muted small">Delete this folder?</span>
                <button class="btn danger small" onclick={() => remove(e)}>Yes, delete</button><button class="btn ghost small" onclick={() => (confirming = null)}>No</button>
              {:else}<button class="btn ghost small" onclick={() => (confirming = "d:" + e.folder_name)}>Delete folder</button>{/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .grid { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 20px; }
  .item { padding: 12px; display: flex; flex-direction: column; gap: 12px; }
  .cover { display: grid; place-items: center; aspect-ratio: 1; border-radius: var(--radius-s); background: var(--surface-2); overflow: hidden; text-align: center; padding: 8px; }
  .cover.damaged { border: 1px dashed var(--danger); }
  .info { display: flex; flex-direction: column; gap: 8px; min-height: 64px; }
  .title { font-weight: 600; overflow-wrap: anywhere; }
  .small { font-size: 0.8rem; }
  .actions { justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
  .empty { display: flex; flex-direction: column; gap: 12px; max-width: 520px; }
</style>

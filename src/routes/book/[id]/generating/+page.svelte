<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { beginBook, cancelJob, getBook, type BookDetail } from "$lib/api";
  import { app, formatSeconds, KIND_LABEL, STAGES_OF, STAGE_LABELS, toast } from "$lib/state.svelte";

  const id = page.params.id!;
  let book = $state<BookDetail | null>(null);
  let loadError = $state<string | null>(null);
  let now = $state(Date.now());
  let starting = $state(false);
  const timer = setInterval(() => (now = Date.now()), 1000);
  onDestroy(() => clearInterval(timer));

  const job = $derived(["generate", "plan", "assets", "pages"].includes(app.jobs[id]?.kind) ? app.jobs[id] : null);
  const running = $derived(job?.state === "running");
  const baseStages = $derived(STAGES_OF[job?.kind ?? "generate"]);
  const stageList = $derived([...baseStages, ...Object.keys(job?.stages ?? {}).filter((s) => !baseStages.includes(s))]);
  const elapsed = $derived(job ? ((job.endedAt ?? now) - job.startedAt) / 1000 : 0);

  async function load() { try { book = await getBook(id); loadError = null; } catch (e) { loadError = String(e); } }
  onMount(load);
  $effect(() => { app.booksVersion; load(); });
  // a finished book goes straight to the review; a planned one (or one whose characters were just drawn) to the characters screen
  $effect(() => {
    if (running || !book || !(job === null || job.state === "done")) return;
    const to = book.status === "review" ? "review" : book.status === "planned" ? "characters" : null;
    if (to) { const t = setTimeout(() => goto(`/book/${id}/${to}`, { replaceState: true }), job ? 900 : 0); return () => clearTimeout(t); }
  });

  async function begin() { starting = true; try { if (book?.has_plan) { await goto(`/book/${id}/characters`); return; } await beginBook(id); } catch (e) { toast(String(e), "error"); } starting = false; await load(); }
  async function stop() { if (job) try { await cancelJob(job.jobId); } catch (e) { toast(String(e), "error"); } }
  const icon = (s: string) => (job?.stages[s] === "done" ? "✓" : job?.stages[s] === "running" ? "●" : job?.stages[s] === "failed" ? "✗" : "○");
</script>

<div class="stack" style="max-width: 640px">
  {#if loadError}
    <p class="card" style="color: var(--danger)">{loadError}</p><a class="btn ghost" href="/">Back to the library</a>
  {:else if !book}<p class="muted">Loading…</p>
  {:else}
    <div><p class="label">{running ? (KIND_LABEL[job?.kind ?? "generate"]) : job?.state === "error" || book.status === "failed" ? "Stopped" : job?.state === "cancelled" ? "Cancelled" : "Not started"}</p><h1>{book.meta.title}</h1></div>

    {#if running || job?.state === "done"}
      <div class="card stack">
        <div class="row between"><strong>{job?.message || "Starting…"}</strong><span class="muted mono">{formatSeconds(elapsed)}</span></div>
        <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round((job?.fraction ?? 0) * 100)}><div class="fill" style="width: {(job?.fraction ?? 0) * 100}%"></div></div>
        <ol class="stages">{#each stageList as s}<li class:done={job?.stages[s] === "done"} class:now={job?.stages[s] === "running"}><span class="mark" aria-hidden="true">{icon(s)}</span>{STAGE_LABELS[s] ?? s}</li>{/each}</ol>
        {#if running}<div class="row between"><span class="faint" style="font-size: 0.85rem">You can leave this screen; the book keeps being made.</span><button class="btn ghost small" onclick={stop}>Cancel</button></div>{/if}
      </div>
    {:else}
      <div class="card stack">
        {#if job?.state === "error"}
          <p style="color: var(--danger)"><strong>The book could not be finished.</strong></p>
          <details><summary class="muted">Details</summary><pre>{job.error}</pre></details>
        {:else if job?.state === "cancelled"}<p class="muted">You stopped the generation.</p>
        {:else if book.status === "interrupted"}<p class="muted">The app was closed while this book was being made.</p>
        {:else if book.status === "failed"}<p class="muted">The last attempt failed.</p>
        {:else}<p class="muted">This book has not been made yet.</p>{/if}
        <div class="row"><button class="btn" onclick={begin} disabled={starting || app.sidecar.state !== "ready"}>{starting ? "Starting…" : book.has_plan ? "Back to the characters" : book.status === "draft" ? "Make the book" : "Try again"}</button><a class="btn ghost" href="/">Library</a></div>
        {#if app.sidecar.state !== "ready"}<p class="muted" style="font-size: 0.85rem">The picture engine is {app.sidecar.state}.</p>{/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .mono { font-family: var(--font-mono); font-size: 0.85rem; }
  .stages { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  .stages li { color: var(--text-faint); display: flex; gap: 10px; }
  .stages li.done { color: var(--text-muted); } .stages li.now { color: var(--text); font-weight: 600; }
  .mark { width: 1.2em; text-align: center; } .now .mark { color: var(--accent); } .done .mark { color: var(--ok); }
  pre { white-space: pre-wrap; font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted); max-height: 240px; overflow: auto; }
</style>

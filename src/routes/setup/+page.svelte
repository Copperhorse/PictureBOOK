<script lang="ts">
  import { onMount } from "svelte";
  import { app, runSetupCheck, toast } from "$lib/state.svelte";
  import type { DiagnosticCheck } from "$lib/api";

  let busy = $state(false);
  let failed = $state<string | null>(null);
  async function check() {
    busy = true; failed = null;
    try { await runSetupCheck(); } catch (e) { failed = String(e); }
    busy = false;
  }
  onMount(() => { if (app.sidecar.state === "ready") check(); });
  $effect(() => { if (app.sidecar.state === "ready" && !app.setup && !busy && !failed) check(); });

  const checks = $derived(app.setup?.checks ?? []);
  const blocking = $derived(checks.filter((c) => c.blocking));
  const warns = $derived(checks.filter((c) => c.status === "warn" && !c.blocking));
  const mark = (c: DiagnosticCheck) => (c.status === "ok" ? "✓" : c.status === "warn" ? "!" : "✗");
  async function copy(text: string) { try { await navigator.clipboard.writeText(text); toast("Copied."); } catch { /* the text is selectable anyway */ } }
  const command = (fix: string) => fix.match(/`([^`]+)`/)?.[1] ?? null;
</script>

<div class="stack" style="max-width: 720px">
  <div><p class="label">Setup</p><h1>Is everything installed?</h1></div>

  {#if app.sidecar.state !== "ready"}
    <p class="card muted">The picture engine is {app.sidecar.state}. {app.sidecar.error ?? ""} The check starts as soon as it is ready.</p>
  {/if}
  {#if failed}<p class="card" style="color: var(--danger)">{failed}</p>{/if}

  {#if app.setup}
    <div class="card row between" class:okbox={!blocking.length}>
      <div>
        <strong>{blocking.length ? `${blocking.length} thing${blocking.length === 1 ? "" : "s"} must be fixed before making books` : warns.length ? "Ready, with a few notes" : "Everything is ready"}</strong>
        <p class="muted" style="margin: 4px 0 0">{blocking.length ? "Each item below says how to fix it. The app changes nothing and downloads nothing by itself." : "You can make books now."}</p>
      </div>
      <button class="btn ghost small" onclick={check} disabled={busy}>{busy ? "Checking…" : "Check again"}</button>
    </div>

    <ul class="list">
      {#each checks as c (c.id)}
        <li class="card item" data-status={c.status}>
          <span class="mark" aria-hidden="true">{mark(c)}</span>
          <div class="stack" style="gap: 6px; min-width: 0">
            <div class="row between"><strong>{c.title}</strong>
              <span class="chip" class:ok={c.status === "ok"} class:warn={c.status === "warn"} class:bad={c.status === "missing"}>{c.status === "ok" ? "ready" : c.status === "warn" ? "note" : c.needed_for === "audio" ? "needed for recordings" : "missing"}</span></div>
            <span class="muted detail">{c.detail}</span>
            {#if c.fix}
              <span class="fix">{c.fix}</span>
              {#if command(c.fix)}<button class="btn ghost small" style="align-self: flex-start" onclick={() => copy(command(c.fix)!)}>Copy the command</button>{/if}
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {:else if !failed && app.sidecar.state === "ready"}<p class="muted">Checking…</p>{/if}
</div>

<style>
  .list { list-style: none; padding: 0; margin: 0; display: grid; gap: 12px; }
  .item { display: grid; grid-template-columns: 28px 1fr; gap: 12px; padding: 16px 20px; }
  .mark { font-family: var(--font-mono); font-size: 1.1rem; text-align: center; }
  [data-status="ok"] .mark { color: var(--ok); } [data-status="warn"] .mark { color: var(--warn); } [data-status="missing"] .mark { color: var(--danger); }
  [data-status="missing"] { border-color: var(--danger); }
  .detail { overflow-wrap: anywhere; font-size: 0.9rem; } .fix { font-size: 0.9rem; overflow-wrap: anywhere; }
  .okbox { border-color: var(--ok); }
</style>

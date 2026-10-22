<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { beginBook, createBookFromRecording, getSettings, type Style } from "$lib/api";
  import { Recorder, micErrorMessage } from "$lib/recorder";
  import { app, blockers, toast } from "$lib/state.svelte";
  import { formatDuration, MAX_SECONDS } from "$lib/wav";

  type Phase = "idle" | "starting" | "recording" | "paused" | "done" | "saving";
  let phase = $state<Phase>("idle");
  let error = $state<string | null>(null);
  let seconds = $state(0), level = $state(0), peakHold = $state(0);
  let result = $state<{ wav: Uint8Array; seconds: number } | null>(null);
  let playUrl = $state<string | null>(null);
  let title = $state(""), style = $state<Style>("crayon"), pages = $state(6);
  let rec: Recorder | null = null;
  let heldTimer: ReturnType<typeof setInterval> | null = null;

  onMount(async () => { try { const s = await getSettings(); style = s.style; pages = s.pages; } catch { /* defaults */ } });
  onDestroy(() => { rec?.discard(); if (heldTimer) clearInterval(heldTimer); if (playUrl) URL.revokeObjectURL(playUrl); });

  const ready = $derived(app.sidecar.state === "ready");
  const needSpeech = $derived(blockers().some((b) => b.id === "whisper" || b.needed_for === "all"));

  async function start() {
    error = null; seconds = 0; level = 0; peakHold = 0; phase = "starting";
    rec = new Recorder({
      level: (p) => { level = Math.min(1, p * 1.6); peakHold = Math.max(peakHold, level); },
      tick: (s) => (seconds = s),
      limit: () => { toast("That is 15 minutes, the longest recording. It was stopped here."); void stop(); },
    });
    try { await rec.start(); phase = "recording"; heldTimer = setInterval(() => (peakHold = Math.max(0, peakHold - 0.04)), 100); }
    catch (e) { rec = null; phase = "idle"; error = micErrorMessage(e); }
  }
  function pause() { rec?.pause(); phase = "paused"; level = 0; }
  function resume() { rec?.resume(); phase = "recording"; }
  async function stop() {
    if (!rec) return;
    if (heldTimer) { clearInterval(heldTimer); heldTimer = null; }
    const r = await rec.finish(); rec = null; level = 0;
    if (!r || r.seconds < 1) { phase = "idle"; error = "Nothing was recorded. Hold the record button a little longer and speak."; return; }
    result = r;
    if (playUrl) URL.revokeObjectURL(playUrl);
    playUrl = URL.createObjectURL(new Blob([r.wav.buffer as ArrayBuffer], { type: "audio/wav" }));
    phase = "done";
  }
  function again() { result = null; if (playUrl) { URL.revokeObjectURL(playUrl); playUrl = null; } seconds = 0; phase = "idle"; }
  async function use() {
    if (!result) return;
    phase = "saving";
    try {
      const book = await createBookFromRecording(result.wav, { title, style, pages });
      try { await beginBook(book.meta.id); } catch (e) { toast(String(e), "error"); }
      await goto(`/book/${book.meta.id}/generating`);
    } catch (e) { error = String(e); phase = "done"; }
  }
</script>

<div class="stack" style="max-width: 640px">
  <div><p class="label">{phase === "recording" ? "Recording" : phase === "paused" ? "Paused" : phase === "done" || phase === "saving" ? "Recorded" : "Record"}</p><h1>Tell your story</h1></div>

  {#if !ready}<p class="card warn">The picture engine is {app.sidecar.state}. You can already record; making the book needs the engine.</p>{/if}
  {#if needSpeech && blockers().length}<p class="card warn">Something is missing on this computer ({blockers().map((b) => b.title).join(", ")}). <a href="/setup" style="text-decoration: underline">See what to do</a>.</p>{/if}
  {#if error}<p class="card" style="border-color: var(--danger); color: var(--danger)" role="alert">{error}</p>{/if}

  {#if phase === "done" || phase === "saving"}
    <div class="card stack">
      <div class="row between"><strong>Your recording</strong><span class="mono">{formatDuration(result?.seconds ?? 0)}</span></div>
      {#if playUrl}<audio controls src={playUrl} style="width: 100%"></audio>{/if}
      <label class="stack" style="gap: 6px"><span class="label">Title (optional)</span><input bind:value={title} maxlength="80" placeholder="The app picks one from the story" disabled={phase === "saving"} /></label>
      <div class="row">
        <label class="stack" style="gap: 6px; flex: 1"><span class="label">Style</span>
          <select bind:value={style} disabled={phase === "saving"}><option value="crayon">Crayon and coloured pencil</option><option value="flat">Flat paper cut-out</option><option value="watercolour">Soft watercolour</option></select></label>
        <label class="stack" style="gap: 6px; width: 120px"><span class="label">Pages</span><input type="number" min="1" max="10" bind:value={pages} disabled={phase === "saving"} /></label>
      </div>
      <div class="row between"><button class="btn ghost" onclick={again} disabled={phase === "saving"}>Record again</button>
        <button class="btn" style="white-space: nowrap" onclick={use} disabled={phase === "saving" || !ready}>{phase === "saving" ? "Saving…" : "Use this recording"}</button></div>
      <p class="faint" style="margin: 0; font-size: 0.85rem">The recording is turned into text on this computer and then deleted (you can change that in Settings).</p>
    </div>
  {:else}
    <div class="card stage">
      <div class="meter" role="meter" aria-label="Microphone level" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(level * 100)}>
        <div class="bar" style="height: {Math.max(2, level * 100)}%"></div><div class="hold" style="bottom: {peakHold * 100}%"></div>
      </div>
      <div class="center stack" style="align-items: center; gap: 18px">
        <div class="time mono" aria-live="off">{formatDuration(seconds)} <span class="faint">/ {formatDuration(MAX_SECONDS)}</span></div>
        {#if phase === "idle" || phase === "starting"}
          <button class="rec" onclick={start} disabled={phase === "starting"} aria-label="Start recording"><span class="dot"></span></button>
          <span class="muted">{phase === "starting" ? "Opening the microphone…" : "Press the red button and tell the story. Speak clearly, in English."}</span>
        {:else}
          <button class="rec on" onclick={stop} aria-label="Stop recording"><span class="sq"></span></button>
          <div class="row">
            {#if phase === "recording"}<button class="btn ghost" onclick={pause}>Pause</button>{:else}<button class="btn ghost" onclick={resume}>Continue</button>{/if}
            <button class="btn" onclick={stop}>Finish</button>
          </div>
          <span class="muted">{phase === "paused" ? "Paused. Nothing is being recorded." : "Recording… press the square or Finish when the story is told."}</span>
        {/if}
      </div>
    </div>
    <p class="faint" style="font-size: 0.85rem; margin: 0">The sound stays on this computer. Nothing is sent anywhere.</p>
  {/if}
</div>

<style>
  .warn { border-color: var(--warn); color: var(--warn); }
  .mono { font-family: var(--font-mono); }
  .stage { display: grid; grid-template-columns: 36px 1fr; gap: 24px; padding: 28px; min-height: 340px; }
  .center { justify-content: center; }
  .time { font-size: 2.4rem; letter-spacing: 0.04em; }
  .meter { position: relative; width: 22px; height: 100%; min-height: 280px; background: var(--surface-2); border-radius: 999px; overflow: hidden; align-self: center; }
  .meter .bar { position: absolute; left: 0; right: 0; bottom: 0; background: var(--ok); transition: height 0.06s linear; }
  .meter .hold { position: absolute; left: 0; right: 0; height: 3px; background: var(--text); }
  .rec { width: 104px; height: 104px; border-radius: 50%; border: 3px solid var(--accent); background: transparent; display: grid; place-items: center; padding: 0; }
  .rec .dot { width: 72px; height: 72px; border-radius: 50%; background: var(--accent); }
  .rec .sq { width: 40px; height: 40px; border-radius: 8px; background: var(--accent); }
  .rec.on { animation: pulse 1.6s ease-in-out infinite; }
  .rec:disabled { opacity: 0.5; }
  @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(212, 80, 63, 0.4); } 50% { box-shadow: 0 0 0 14px rgba(212, 80, 63, 0); } }
  @media (prefers-reduced-motion: reduce) { .rec.on { animation: none; } .meter .bar { transition: none; } }
</style>

<script lang="ts">
  import { untrack } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { cancelJob, getBook, getPlan, planOptions, savePlanItem, startStep, type BookDetail, type OutfitItem, type PlanItem, type PlanOptions, type PlanSummary } from "$lib/api";
  import { app, KIND_LABEL, runningJob, toast } from "$lib/state.svelte";
  import Picture from "$lib/components/Picture.svelte";

  const id = page.params.id!;
  let book = $state<BookDetail | null>(null);
  let plan = $state<PlanSummary | null>(null);
  let options = $state<PlanOptions | null>(null);
  let loadError = $state<string | null>(null);
  // what the parent is typing: one editable copy per item, keyed "character:Name" / "place:Name"
  let draft = $state<Record<string, Record<string, any>>>({});
  let saving = $state(false);

  const job = $derived(runningJob(id));
  const busy = $derived(!!job);

  const TEXT_CHARACTER: [string, string, string][] = [
    ["species", "Kind of being", "human, fox, bear …"], ["hair", "Hair or fur colour", "brown, grey … (None if it has none)"], ["headwear", "Hat or hood", "None, or for example a red cap"],
    ["eyewear", "Glasses", "None, or round glasses"], ["face", "Face", "freckles, a long white beard …"], ["skin_colour", "Skin colour", "fair, tan, dark …"],
    ["accessories", "Carries or holds", "None, a red kite, a fishing rod"], ["distinguishing_marks", "Special marks", "None, a scar on the chin"],
  ];
  const SELECT_CHARACTER: [string, string][] = [["age_group", "Age"], ["build", "Build"], ["height_relative", "Height"], ["hair_style", "Hair style"]];
  const TEXT_PLACE: [string, string][] = [["location", "What it looks like"], ["weather", "Weather"], ["lighting", "Light"], ["mood", "Mood"]];
  const SELECT_PLACE: [string, string][] = [["setting", "Indoors or outdoors"], ["time_of_day", "Time of day"], ["season", "Season"]];
  const nice = (v: string) => v.replaceAll("_", " ");

  const keyOf = (kind: string, name: string) => `${kind}:${name}`;
  function fresh(item: PlanItem, kind: "character" | "place") {
    const spec = structuredClone($state.snapshot(item.spec));
    if (kind === "place") { spec.palette = (spec.palette ?? []).join(", "); spec.key_objects = (spec.key_objects ?? []).join(", "); }
    return spec;
  }
  function toPayload(kind: "character" | "place", d: Record<string, any>) {
    const out = structuredClone($state.snapshot(d));
    if (kind === "place") {
      out.palette = String(d.palette ?? "").split(",").map((x) => x.trim()).filter(Boolean);
      out.key_objects = String(d.key_objects ?? "").split(",").map((x) => x.trim()).filter(Boolean);
    }
    return out;
  }
  /** Fields whose value differs from what is saved (only these are sent). */
  function changed(item: PlanItem, kind: "character" | "place"): Record<string, unknown> {
    const d = draft[keyOf(kind, item.name)];
    if (!d) return {};
    const now = toPayload(kind, d), was = toPayload(kind, { ...item.spec, ...(kind === "place" ? { palette: (item.spec.palette ?? []).join(", "), key_objects: (item.spec.key_objects ?? []).join(", ") } : {}) });
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(now)) if (k !== "name" && k !== "inferred_fields" && JSON.stringify(now[k]) !== JSON.stringify(was[k])) out[k] = now[k];
    return out;
  }
  const dirtyItems = $derived(plan ? [...plan.characters.map((c) => ({ c, kind: "character" as const })), ...plan.places.map((c) => ({ c, kind: "place" as const }))].filter(({ c, kind }) => Object.keys(changed(c, kind)).length) : []);
  const dirty = $derived(dirtyItems.length > 0);

  async function load() {
    try {
      [book, plan] = await Promise.all([getBook(id), getPlan(id)]);
      options ??= await planOptions();
      for (const c of plan.characters) draft[keyOf("character", c.name)] = fresh(c, "character");
      for (const p of plan.places) draft[keyOf("place", p.name)] = fresh(p, "place");
      loadError = null;
    } catch (e) { loadError = String(e); }
  }
  // reload when the library changed on disk (a job finished), but never throw away what the parent is typing
  $effect(() => { app.booksVersion; untrack(() => { if (!dirty) load(); }); });

  const editable = $derived(!!plan?.editable && book?.status !== "review" && !busy);
  const wasGuessed = (item: PlanItem, f: string) => item.guessed.includes(f);

  async function saveAll(): Promise<boolean> {
    saving = true;
    try {
      for (const { c, kind } of dirtyItems) await savePlanItem(id, kind, c.name, changed(c, kind));
      await load();
      return true;
    } catch (e) { toast(String(e), "error"); return false; }
    finally { saving = false; }
  }
  async function discard() { await load(); }
  async function draw(only?: string) {
    if (dirty && !(await saveAll())) return;
    try { await startStep(id, "assets", only); } catch (e) { toast(String(e), "error"); }
  }
  async function approve() {
    if (dirty && !(await saveAll())) return;
    try { await startStep(id, "pages"); await goto(`/book/${id}/generating`); } catch (e) { toast(String(e), "error"); }
  }
  async function stop() { if (job) try { await cancelJob(job.jobId); } catch (e) { toast(String(e), "error"); } }

  function addOutfit(key: string) { const o: OutfitItem[] = draft[key].outfit; if (o.length < 4) o.push({ item: "", colour: "", detail: "None" }); }
  function removeOutfit(key: string, i: number) { const o: OutfitItem[] = draft[key].outfit; if (o.length > 1) o.splice(i, 1); }
</script>

{#if loadError}
  <div class="stack"><p class="card" style="color: var(--danger)">{loadError}</p><a class="btn ghost" href="/" style="align-self: flex-start">Back to the library</a></div>
{:else if !plan || !book || !options}<p class="muted">Loading…</p>
{:else}
  <div class="stack">
    <div><p class="label">Characters and places</p><h1>{book.meta.title}</h1></div>

    {#if book.status === "review"}
      <p class="card muted">This book is finished, so the characters can no longer be changed. To try other looks, make a new book from the same story.</p>
    {:else if !plan.editable}
      <p class="card muted">The pages are already drawn, so nothing here can be changed any more.</p>
    {:else}
      <p class="muted" style="margin: 0; max-width: 640px">Check how each character and place will look. Change anything that does not fit your story, then draw them. Words marked <span class="chip warn">guessed</span> were not in your story, so the app made them up.</p>
    {/if}

    {#if job}
      <div class="card stack" role="status">
        <div class="row between"><strong>{KIND_LABEL[job.kind] ?? "Working"}: {job.message || "starting"}</strong><button class="btn ghost small" onclick={stop}>Cancel</button></div>
        <div class="bar"><div class="fill" style="width: {job.fraction * 100}%"></div></div>
      </div>
    {/if}
    {#if app.jobs[id]?.state === "error"}<p class="card" style="border-color: var(--danger); color: var(--danger)">The last step did not finish: {(app.jobs[id].error ?? "").split("\n").slice(-1)[0]}</p>{/if}

    {#if dirty}
      <div class="card row between sticky" role="status"><span>{dirtyItems.length} unsaved change{dirtyItems.length === 1 ? "" : "s"}</span>
        <span class="row"><button class="btn ghost small" onclick={discard} disabled={saving}>Discard</button><button class="btn small" onclick={saveAll} disabled={saving}>{saving ? "Saving…" : "Save changes"}</button></span></div>
    {/if}

    <h2>Characters</h2>
    <div class="items">
      {#each plan.characters as c (c.name)}
        {@const key = keyOf("character", c.name)}
        {#if draft[key]}
          <article class="card item" aria-label={c.name}>
            <div class="pic">{#if c.image}<Picture path={c.image} version={`${c.draws}-${app.booksVersion}`} alt={`${c.name}`} />{:else}<span class="label">Not drawn yet</span>{/if}</div>
            <div class="form">
              <div class="row between"><h3>{c.name}</h3><button class="btn ghost small" onclick={() => draw(c.name)} disabled={!editable || saving}>{c.image ? "Draw again" : "Draw"}</button></div>
              <div class="grid">
                {#each SELECT_CHARACTER as [f, label]}
                  <label><span class="label">{label}{#if wasGuessed(c, f)} <span class="chip warn">guessed</span>{/if}</span>
                    <select bind:value={draft[key][f]} disabled={!editable}>{#each options[f as keyof PlanOptions] as v}<option value={v}>{nice(v)}</option>{/each}</select></label>
                {/each}
                {#each TEXT_CHARACTER as [f, label, hint]}
                  <label><span class="label">{label}{#if wasGuessed(c, f)} <span class="chip warn">guessed</span>{/if}</span><input bind:value={draft[key][f]} placeholder={hint} maxlength="60" disabled={!editable} /></label>
                {/each}
              </div>
              <div class="stack" style="gap: 8px"><span class="label">Clothes{#if wasGuessed(c, "outfit")} <span class="chip warn">guessed</span>{/if}</span>
                {#each draft[key].outfit as o, i}
                  <div class="outfit"><input bind:value={o.item} placeholder="what (coat, dress)" maxlength="30" disabled={!editable} aria-label="Clothing item" /><input bind:value={o.colour} placeholder="colour" maxlength="30" disabled={!editable} aria-label="Colour" /><input bind:value={o.detail} placeholder="detail (None)" maxlength="60" disabled={!editable} aria-label="Detail" />
                    <button class="btn ghost small" onclick={() => removeOutfit(key, i)} disabled={!editable || draft[key].outfit.length < 2} aria-label="Remove this piece of clothing">Remove</button></div>
                {/each}
                <button class="btn ghost small" style="align-self: flex-start" onclick={() => addOutfit(key)} disabled={!editable || draft[key].outfit.length >= 4}>Add clothing</button>
              </div>
            </div>
          </article>
        {/if}
      {/each}
    </div>

    <h2>Places</h2>
    <div class="items">
      {#each plan.places as p (p.name)}
        {@const key = keyOf("place", p.name)}
        {#if draft[key]}
          <article class="card item" aria-label={p.name}>
            <div class="pic">{#if p.image}<Picture path={p.image} version={`${p.draws}-${app.booksVersion}`} alt={p.name} />{:else}<span class="label">Not drawn yet</span>{/if}</div>
            <div class="form">
              <div class="row between"><h3>{p.name}</h3><button class="btn ghost small" onclick={() => draw(p.name)} disabled={!editable || saving}>{p.image ? "Draw again" : "Draw"}</button></div>
              <div class="grid">
                {#each SELECT_PLACE as [f, label]}
                  <label><span class="label">{label}{#if wasGuessed(p, f)} <span class="chip warn">guessed</span>{/if}</span>
                    <select bind:value={draft[key][f]} disabled={!editable}>{#each options[f as keyof PlanOptions] as v}<option value={v}>{nice(v)}</option>{/each}</select></label>
                {/each}
                {#each TEXT_PLACE as [f, label]}
                  <label class:wide={f === "location"}><span class="label">{label}{#if wasGuessed(p, f)} <span class="chip warn">guessed</span>{/if}</span>
                    {#if f === "location"}<textarea rows="2" bind:value={draft[key][f]} maxlength="80" disabled={!editable}></textarea>{:else}<input bind:value={draft[key][f]} maxlength="60" disabled={!editable} />{/if}</label>
                {/each}
                <label><span class="label">Colours (2 to 4, separated by commas){#if wasGuessed(p, "palette")} <span class="chip warn">guessed</span>{/if}</span><input bind:value={draft[key].palette} disabled={!editable} /></label>
                <label><span class="label">Things in it (up to 6, separated by commas){#if wasGuessed(p, "key_objects")} <span class="chip warn">guessed</span>{/if}</span><input bind:value={draft[key].key_objects} disabled={!editable} /></label>
              </div>
            </div>
          </article>
        {/if}
      {/each}
    </div>

    {#if editable || dirty}
      <div class="card row between sticky bottom">
        <span class="muted">{plan.all_drawn ? "Everything is drawn. Happy with it?" : "The pictures of the characters and places have not all been drawn yet."}</span>
        <span class="row">
          {#if !plan.all_drawn}<button class="btn" onclick={() => draw()} disabled={!editable || saving || app.sidecar.state !== "ready"}>Draw characters and places</button>
          {:else}<button class="btn" onclick={approve} disabled={!editable || saving || app.sidecar.state !== "ready"}>Looks good: draw the pages</button>{/if}
        </span>
      </div>
    {/if}
  </div>
{/if}

<style>
  h2 { margin-top: 8px; } h3 { font-size: 1.05rem; }
  .items { display: grid; gap: 20px; max-width: 900px; }
  .item { display: grid; grid-template-columns: 240px 1fr; gap: 20px; padding: 16px; }
  .pic { aspect-ratio: 1; border-radius: var(--radius-s); background: var(--surface-2); overflow: hidden; display: grid; place-items: center; align-self: start; }
  .form { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
  .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .grid label { display: flex; flex-direction: column; gap: 4px; } .wide { grid-column: 1 / -1; }
  .outfit { display: grid; grid-template-columns: 1.2fr 1fr 1.2fr auto; gap: 8px; }
  .sticky { position: sticky; top: 8px; z-index: 5; } .sticky.bottom { top: auto; bottom: 8px; }
  @media (max-width: 1000px) { .item { grid-template-columns: 1fr; } .pic { max-width: 280px; } }
</style>

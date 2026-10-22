<script lang="ts">
  import "../app.css";
  import { onMount } from "svelte";
  import { page } from "$app/state";
  import { goto } from "$app/navigation";
  import { app, initApp, runSetupCheck } from "$lib/state.svelte";
  let { children } = $props();
  onMount(() => { initApp(); });
  // once the engine is up, look at the machine; open the Setup screen by itself (once) only when something blocks the app
  $effect(() => {
    if (app.sidecar.state !== "ready" || app.setup || app.setupShown) return;
    app.setupShown = true;
    runSetupCheck().then((d) => { if (d && d.blockers.length && page.url.pathname !== "/setup") goto("/setup"); }).catch(() => {});
  });
  const nav = [
    { href: "/", label: "Library", match: (p: string) => p === "/" || p.startsWith("/book") },
    { href: "/new", label: "New book", match: (p: string) => p === "/new" },
    { href: "/record", label: "Record", match: (p: string) => p === "/record" },
    { href: "/settings", label: "Settings", match: (p: string) => p === "/settings" || p === "/setup" },
  ];
</script>

<div class="shell">
  <nav aria-label="Main">
    <div class="brand">PictureBOOK</div>
    <ul>
      {#each nav as n}
        <li><a href={n.href} class:active={n.match(page.url.pathname)} aria-current={n.match(page.url.pathname) ? "page" : undefined}>{n.label}</a></li>
      {/each}
    </ul>
    <div class="status label" title={app.sidecar.error ?? ""}>
      <span class="dot" data-state={app.sidecar.state}></span>
      {app.sidecar.state === "ready" ? "Engine ready" : app.sidecar.state === "starting" ? "Engine starting" : "Engine problem"}
    </div>
  </nav>
  <main>{@render children()}</main>
</div>

<div class="toasts" role="status" aria-live="polite">
  {#each app.toasts as t (t.id)}<div class="toast" class:error={t.kind === "error"}>{t.text}</div>{/each}
</div>

<style>
  .shell { display: grid; grid-template-columns: 200px 1fr; min-height: 100vh; }
  nav { background: var(--surface-1); border-right: 1px solid var(--border); padding: 24px 14px; display: flex; flex-direction: column; gap: 24px; position: sticky; top: 0; height: 100vh; }
  .brand { font-family: var(--font-mono); letter-spacing: 0.08em; font-size: 0.8rem; text-transform: uppercase; padding: 0 10px; }
  ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; flex: 1; }
  li a { display: block; padding: 9px 12px; border-radius: var(--radius-s); color: var(--text-muted); }
  li a:hover { background: var(--surface-2); color: var(--text); }
  li a.active { background: var(--surface-2); color: var(--text); }
  .status { display: flex; align-items: center; gap: 8px; padding: 0 10px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-faint); }
  .dot[data-state="ready"] { background: var(--ok); } .dot[data-state="starting"] { background: var(--warn); } .dot[data-state="failed"] { background: var(--danger); }
  main { padding: 36px 40px 80px; min-width: 0; max-width: 1100px; }
  .toasts { position: fixed; right: 20px; bottom: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 50; }
  .toast { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-s); padding: 10px 16px; max-width: 360px; }
  .toast.error { border-color: var(--danger); color: var(--danger); }
</style>

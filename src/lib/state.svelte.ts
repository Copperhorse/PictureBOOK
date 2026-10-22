import { firstRunCheck, onBooksChanged, onJobEvent, onSidecarState, sidecarStatus, type Diagnostics, type JobEvent, type SidecarStatus } from "./api";

/** Order and wording of the generation stages (the sidecar sends the stage names; this is only for display). */
export const STAGE_LABELS: Record<string, string> = {
  transcribe: "Reading the story", plan: "Planning the pages", assets: "Drawing characters and places", critic_assets: "Checking the characters",
  ref_repair: "Fixing a character", critic_refs: "Checking the fix", render: "Drawing the pages", critic_pages_r0: "Checking the pages",
  repair: "Repairing pages", critic_pages_r1: "Checking the repairs", hints: "Preparing notes for the review", export: "Making the PDF", review: "Preparing the review",
};
export const GENERATE_STAGES = ["transcribe", "plan", "assets", "critic_assets", "render", "critic_pages_r0", "hints", "export", "review"];
/** Stages shown for each kind of job (the approval flow runs them in three parts). */
export const STAGES_OF: Record<string, string[]> = {
  generate: GENERATE_STAGES, plan: ["transcribe", "plan"], assets: ["assets", "critic_assets"], pages: ["render", "critic_pages_r0", "hints", "export", "review"],
};
export const KIND_LABEL: Record<string, string> = { generate: "Making the book", plan: "Planning the book", assets: "Drawing characters and places", pages: "Drawing the pages", regen: "Redrawing", undo: "Restoring" };

export interface JobView {
  jobId: string; bookId: string; kind: JobEvent["kind"];
  state: "running" | "done" | "error" | "cancelled";
  fraction: number; label: string; message: string; error: string | null;
  stages: Record<string, "running" | "done" | "failed">; startedAt: number; endedAt: number | null;
}
export interface Toast { id: number; text: string; kind: "info" | "error" }

export const app = $state({
  sidecar: { state: "starting", error: null, version: null, gpu: null } as SidecarStatus,
  jobs: {} as Record<string, JobView>,   // by book id: the latest job of that book
  booksVersion: 0,                        // bumped whenever the library changed on disk
  toasts: [] as Toast[],
  setup: null as Diagnostics | null,       // result of the last first-run check (null = not checked yet)
  setupShown: false,                        // the Setup screen is opened by itself at most once per session
});

let toastId = 0;
export function toast(text: string, kind: Toast["kind"] = "info") {
  const id = ++toastId;
  app.toasts.push({ id, text, kind });
  setTimeout(() => { app.toasts = app.toasts.filter((t) => t.id !== id); }, kind === "error" ? 9000 : 4000);
}

export function handleJobEvent(e: JobEvent) {
  let j = app.jobs[e.book_id];
  if (!j || j.jobId !== e.job_id) {
    j = { jobId: e.job_id, bookId: e.book_id, kind: e.kind, state: "running", fraction: 0, label: "", message: "", error: null, stages: {}, startedAt: Date.now(), endedAt: null };
    app.jobs[e.book_id] = j;
  }
  if (e.event === "progress") {
    j.fraction = Number(e.data.fraction ?? j.fraction);
    j.label = String(e.data.label ?? j.label);
    j.message = String(e.data.message ?? j.message);
    const stage = String(e.data.stage ?? ""), st = String(e.data.state ?? "");
    if (stage && (st === "start" || st === "running")) j.stages[stage] ??= "running";
    if (stage && st === "start") j.stages[stage] = "running";
    if (stage && st === "done") j.stages[stage] = "done";
    if (stage && st === "failed") j.stages[stage] = "failed";
  } else if (e.event === "done") {
    j.state = "done"; j.fraction = 1; j.endedAt = Date.now();
    toast(e.kind === "generate" || e.kind === "pages" ? "The book is ready." : e.kind === "plan" ? "The plan is ready. Have a look at the characters." : e.kind === "assets" ? "Characters and places drawn." : e.kind === "regen" ? "Pages redrawn." : "Previous picture restored.");
  } else if (e.event === "cancelled") {
    j.state = "cancelled"; j.endedAt = Date.now(); toast("Stopped.");
  } else if (e.event === "error") {
    j.state = "error"; j.endedAt = Date.now(); j.error = String(e.data.message ?? "something went wrong");
    toast(j.error.split("\n").slice(-1)[0] || "Something went wrong.", "error");
  }
  if (j.state !== "running") app.booksVersion++;
}

export async function runSetupCheck(): Promise<Diagnostics | null> {
  try { app.setup = await firstRunCheck(); } catch (e) { app.setup = null; throw e; }
  return app.setup;
}
export const blockers = () => (app.setup?.checks ?? []).filter((c) => c.blocking);

let started = false;
export async function initApp() {
  if (started) return;
  started = true;
  sidecarStatus().then((s) => { app.sidecar = s; }).catch((e) => { app.sidecar = { ...app.sidecar, state: "failed", error: String(e) }; });
  await onSidecarState((s) => { app.sidecar = s; });
  await onJobEvent(handleJobEvent);
  await onBooksChanged(() => app.booksVersion++);
}

export const runningJob = (bookId: string) => (app.jobs[bookId]?.state === "running" ? app.jobs[bookId] : null);
export function formatSeconds(s: number) { const m = Math.floor(s / 60); return m ? `${m} min ${Math.round(s % 60)} s` : `${Math.round(s)} s`; }

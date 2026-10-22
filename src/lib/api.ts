import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";

export type SidecarState = "starting" | "ready" | "failed";
export interface SidecarStatus { state: SidecarState; error: string | null; version: string | null; gpu: { name: string; vram_total_mib: number; vram_used_mib: number } | null }

export type BookStatus = "draft" | "planned" | "generating" | "review" | "failed" | "interrupted";
export type Style = "crayon" | "flat" | "watercolour";
export interface BookMeta { id: string; title: string; status: BookStatus; style: Style; pages: number | null; source: "text" | "audio"; created_at: number; updated_at: number; [k: string]: unknown }
export interface BookSummary { meta: BookMeta; dir: string; status: BookStatus; page_count: number; cover: string | null }
export type LibraryEntry = ({ kind: "book" } & BookSummary) | { kind: "damaged"; dir: string; folder_name: string; reason: string };
export interface PageDetail { index: number; text: string; image: string | null; versions: string[]; redrawn: number; hints: string[]; checked: boolean }
export interface BookDetail { meta: BookMeta; dir: string; status: BookStatus; pages: PageDetail[]; pdf: string | null; problems: string[]; has_plan: boolean }
export interface OutfitItem { item: string; colour: string; detail: string }
export interface PlanItem { name: string; spec: Record<string, any>; image: string | null; guessed: string[]; draws: number }
export interface PlanSummary { title: string; characters: PlanItem[]; places: PlanItem[]; editable: boolean; all_drawn: boolean }
export type PlanOptions = Record<"age_group" | "build" | "height_relative" | "hair_style" | "setting" | "time_of_day" | "season", string[]>
export interface Settings { library_dir: string | null; style: Style; pages: number; approve_first: boolean; keep_recordings: boolean }
export interface LibraryInfo { path: string; scripts: string }

export interface DiagnosticCheck { id: string; title: string; status: "ok" | "warn" | "missing"; detail: string; fix: string; needed_for: "all" | "audio" | "optional"; blocking: boolean }
export interface Diagnostics { checks: DiagnosticCheck[]; blockers: string[]; audio_ready: boolean }

export interface JobEvent { job_id: string; book_id: string; kind: "generate" | "plan" | "assets" | "pages" | "regen" | "undo"; event: "progress" | "done" | "error" | "cancelled" | string; data: Record<string, any> }

export const sidecarStatus = () => invoke<SidecarStatus>("sidecar_status");
export const firstRunCheck = () => invoke<Diagnostics>("first_run_check");
export const libraryInfo = () => invoke<LibraryInfo>("library_info");
export const listBooks = () => invoke<LibraryEntry[]>("list_books");
export const getBook = (id: string) => invoke<BookDetail>("get_book", { id });
export const createBook = (a: { title: string; text?: string; audioPath?: string; style: Style; pages?: number }) =>
  invoke<BookSummary>("create_book", { title: a.title, text: a.text ?? null, audioPath: a.audioPath ?? null, style: a.style, pages: a.pages ?? null });
export const beginBook = (id: string) => invoke<string>("begin_book", { id });
export const startStep = (id: string, step: "plan" | "assets" | "pages", only?: string) => invoke<string>("start_step", { id, step, only: only ?? null });
export const getPlan = (id: string) => invoke<PlanSummary>("get_plan", { id });
export const planOptions = () => invoke<PlanOptions>("plan_options");
export const savePlanItem = (id: string, kind: "character" | "place", name: string, fields: Record<string, unknown>) => invoke<Record<string, any>>("save_plan_item", { id, kind, name, fields });
/** A recording from the Record screen: the WAV bytes are the request body, title/style/pages travel in headers. */
export const createBookFromRecording = (wav: Uint8Array, a: { title: string; style: Style; pages: number }) =>
  invoke<BookSummary>("create_book_from_recording", wav, { headers: { "x-title": encodeURIComponent(a.title), "x-style": a.style, "x-pages": String(a.pages) } });
export const startGeneration = (id: string) => invoke<string>("start_generation", { id });
export const regenPages = (id: string, pages: number[]) => invoke<string>("regen_pages", { id, pages });
export const undoPage = (id: string, page: number) => invoke<string>("undo_page", { id, page });
export const cancelJob = (jobId: string) => invoke<boolean>("cancel_job", { jobId });
export const deleteBook = (id: string) => invoke<void>("delete_book", { id });
export const deleteDamaged = (folderName: string) => invoke<void>("delete_damaged", { folderName });
export const openBook = (id: string, what: "folder" | "pdf") => invoke<void>("open_book", { id, what });
export const getSettings = () => invoke<Settings>("get_settings");
export const setSettings = (settings: Settings) => invoke<Settings>("set_settings", { settings });

export async function pickAudioFile(): Promise<string | null> {
  const r = await open({ multiple: false, directory: false, filters: [{ name: "Audio", extensions: ["wav", "mp3", "m4a", "flac", "ogg"] }] });
  return typeof r === "string" ? r : null;
}

export const onSidecarState = (cb: (s: SidecarStatus) => void): Promise<UnlistenFn> => listen<SidecarStatus>("sidecar-state", (e) => cb(e.payload));
export const onJobEvent = (cb: (e: JobEvent) => void): Promise<UnlistenFn> => listen<JobEvent>("job-event", (e) => cb(e.payload));
export const onBooksChanged = (cb: () => void): Promise<UnlistenFn> => listen("books-changed", () => cb());

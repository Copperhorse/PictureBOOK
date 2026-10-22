//! Tauri shell: owns the sidecar and the book library, exposes commands to the UI and forwards job events as Tauri events.
//! All logic that does not need the UI toolkit lives in `picturebook-core` (where it is tested without a GUI).
//!
//! The UI never talks to the sidecar. The books are plain folders (see `picturebook_core::books`); pictures reach the
//! webview through the asset protocol, whose scope is the library folder only.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::Arc;

use picturebook_core::books::{BookDetail, BookRepository, BookStatus, BookSummary, LibraryEntry, PlanSummary, Source};
use picturebook_core::jobs::{is_final, status_after, JobKind};
use picturebook_core::settings::Settings;
use picturebook_core::sidecar::{Diagnostics, Sidecar, SidecarConfig};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tokio::sync::Mutex;

enum Slot {
    Starting,
    Ready(Arc<Sidecar>),
    Failed(String),
}

struct RunningJob {
    book_id: String,
}

struct AppState {
    sidecar: Mutex<Slot>,
    repo: Arc<BookRepository>,
    settings_path: PathBuf,
    settings: Mutex<Settings>,
    jobs: Mutex<HashMap<String, RunningJob>>,
}

#[derive(Serialize, Clone)]
struct StatusDto {
    state: &'static str,
    error: Option<String>,
    version: Option<String>,
    gpu: Option<serde_json::Value>,
}

#[derive(Serialize, Clone)]
struct JobEvent {
    job_id: String,
    book_id: String,
    kind: &'static str,
    event: String,
    data: serde_json::Value,
}

#[derive(Serialize)]
struct LibraryInfo {
    path: PathBuf,
    scripts: PathBuf,
}

/// Development layout: the uv virtualenv next to the sources. Packaged builds will ship their own environment (not done yet).
fn sidecar_python() -> Result<PathBuf, String> {
    if let Some(p) = std::env::var_os("PICTUREBOOK_SIDECAR_PYTHON") {
        return Ok(PathBuf::from(p));
    }
    if cfg!(debug_assertions) {
        return Ok(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../sidecar/.venv/bin/python"));
    }
    Err("no sidecar interpreter configured (set PICTUREBOOK_SIDECAR_PYTHON)".into())
}

fn scripts_dir() -> PathBuf {
    std::env::var_os("PICTUREBOOK_SCRIPTS").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../scripts"))
}

/// A desktop launcher often has a short PATH; the `llama` binary lives in `~/.local/bin`.
fn path_with_local_bin() -> String {
    let mut parts: Vec<String> = Vec::new();
    if let Some(home) = std::env::var_os("HOME") {
        parts.push(Path::new(&home).join(".local/bin").display().to_string());
    }
    parts.push(std::env::var("PATH").unwrap_or_default());
    parts.join(":")
}

async fn status_of(state: &AppState) -> StatusDto {
    match &*state.sidecar.lock().await {
        Slot::Starting => StatusDto { state: "starting", error: None, version: None, gpu: None },
        Slot::Failed(e) => StatusDto { state: "failed", error: Some(e.clone()), version: None, gpu: None },
        Slot::Ready(s) => match s.health().await {
            Ok(h) => StatusDto { state: "ready", error: None, version: Some(h.version), gpu: h.gpu },
            Err(e) => StatusDto { state: "failed", error: Some(e.to_string()), version: None, gpu: None },
        },
    }
}

async fn ready_sidecar(state: &AppState) -> Result<Arc<Sidecar>, String> {
    match &*state.sidecar.lock().await {
        Slot::Ready(s) => Ok(Arc::clone(s)),
        Slot::Starting => Err("the sidecar is still starting, try again in a moment".into()),
        Slot::Failed(e) => Err(format!("the sidecar is not running: {e}")),
    }
}

async fn running_ids(state: &AppState) -> HashSet<String> {
    state.jobs.lock().await.values().map(|j| j.book_id.clone()).collect()
}

fn err<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}

// ---------------------------------------------------------------- commands

#[tauri::command]
async fn sidecar_status(state: State<'_, AppState>) -> Result<StatusDto, String> {
    Ok(status_of(&state).await)
}

/// First-run check. Only reads the machine; the UI shows what is missing and how to fix it.
#[tauri::command]
async fn first_run_check(state: State<'_, AppState>) -> Result<Diagnostics, String> {
    ready_sidecar(&state).await?.diagnostics().await.map_err(err)
}

#[tauri::command]
async fn library_info(state: State<'_, AppState>) -> Result<LibraryInfo, String> {
    Ok(LibraryInfo { path: state.repo.root().to_path_buf(), scripts: scripts_dir() })
}

#[tauri::command]
async fn list_books(state: State<'_, AppState>) -> Result<Vec<LibraryEntry>, String> {
    let running = running_ids(&state).await;
    state.repo.scan(&running).map_err(err)
}

#[tauri::command]
async fn get_book(state: State<'_, AppState>, id: String) -> Result<BookDetail, String> {
    let running = running_ids(&state).await.contains(&id);
    state.repo.detail(&id, running).map_err(err)
}

/// Make the book folder, then let `write` put the story or the audio into it; a half-made book is never left behind.
async fn make_book(state: &AppState, title: &str, style: &str, pages: Option<u32>, source: Source, auto_title: &str, write: impl FnOnce(&Path) -> Result<(), String> + Send + 'static) -> Result<BookSummary, String> {
    let settings = state.settings.lock().await.clone();
    let style = if ["crayon", "flat", "watercolour"].contains(&style) { style.to_string() } else { settings.style.clone() };
    let pages = pages.map(|p| p.clamp(1, 10));
    let auto = title.trim().is_empty();
    let shown = if auto { auto_title.to_string() } else { title.to_string() };
    let book = state.repo.create(&shown, &style, pages, source).map_err(err)?;
    let dir = book.dir.clone();
    let written = tauri::async_runtime::spawn_blocking(move || write(&dir)).await.map_err(err).and_then(|r| r);
    let result = written.and_then(|_| if auto { state.repo.set_extra(&book.meta.id, "title_auto", serde_json::json!(true)).map_err(err) } else { Ok(()) });
    if let Err(e) = result {
        let _ = state.repo.delete(&book.meta.id);
        return Err(e);
    }
    Ok(book)
}

/// Create a book folder from a typed story or an imported audio file. Exactly one of `text` and `audio_path` must be given.
/// An imported file is converted to a 16 kHz mono WAV (ffmpeg) and checked before anything is stored.
#[tauri::command]
async fn create_book(state: State<'_, AppState>, title: String, text: Option<String>, audio_path: Option<String>, style: String, pages: Option<u32>) -> Result<BookSummary, String> {
    match (text, audio_path) {
        (Some(t), None) => {
            let t = t.trim().to_string();
            if t.is_empty() {
                return Err("the story is empty".into());
            }
            if t.chars().count() > 30_000 {
                return Err("the story is too long (at most 30,000 characters)".into());
            }
            let first_words = t.split_whitespace().take(6).collect::<Vec<_>>().join(" ");
            make_book(&state, &title, &style, pages, Source::Text, &first_words, move |dir| std::fs::write(dir.join("story.txt"), &t).map_err(err)).await
        }
        (None, Some(p)) => {
            let p = PathBuf::from(p);
            let ext = p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
            if !["wav", "mp3", "m4a", "flac", "ogg"].contains(&ext.as_str()) {
                return Err("the audio file must be wav, mp3, m4a, flac or ogg".into());
            }
            if !p.is_file() {
                return Err("the audio file cannot be found".into());
            }
            make_book(&state, &title, &style, pages, Source::Audio, "Spoken story", move |dir| {
                // always store a checked 16 kHz mono WAV, whatever the file was
                let out = dir.join("audio.wav");
                picturebook_core::audio::convert_with_ffmpeg(&p, &out, std::time::Duration::from_secs(180)).map(|_| ()).map_err(err)
            })
            .await
        }
        _ => Err("give either a typed story or an audio file".into()),
    }
}

/// A recording made in the app window: the raw WAV bytes are the request body, the title, style and pages are in the headers
/// (`x-title` percent-encoded). The bytes are validated before a book folder is made.
#[tauri::command]
async fn create_book_from_recording(request: tauri::ipc::Request<'_>, state: State<'_, AppState>) -> Result<BookSummary, String> {
    let tauri::ipc::InvokeBody::Raw(bytes) = request.body() else { return Err("no recording was sent".into()) };
    picturebook_core::audio::validate_wav(bytes).map_err(err)?;
    let header = |n: &str| request.headers().get(n).and_then(|v| v.to_str().ok()).map(str::to_owned).unwrap_or_default();
    let title = percent_encoding::percent_decode_str(&header("x-title")).decode_utf8_lossy().chars().take(80).collect::<String>();
    let pages = header("x-pages").parse::<u32>().ok();
    let bytes = bytes.clone();
    make_book(&state, &title, &header("x-style"), pages, Source::Audio, "Spoken story", move |dir| std::fs::write(dir.join("audio.wav"), &bytes).map_err(err)).await
}

/// Start a job in the sidecar and forward its events; when it ends, store the outcome in `book.json`.
async fn start_job(app: &AppHandle, state: &AppState, book_id: &str, kind: JobKind, label: &'static str, begin: impl std::future::Future<Output = Result<String, picturebook_core::sidecar::SidecarError>>, sidecar: Arc<Sidecar>) -> Result<String, String> {
    let job_id = begin.await.map_err(err)?;
    state.jobs.lock().await.insert(job_id.clone(), RunningJob { book_id: book_id.to_string() });
    let (app, id, book) = (app.clone(), job_id.clone(), book_id.to_string());
    tauri::async_runtime::spawn(async move {
        let mut last = String::new();
        let res = sidecar
            .follow_events(&id, |ev| {
                let data = serde_json::from_str(&ev.data).unwrap_or(serde_json::Value::String(ev.data.clone()));
                last = ev.event.clone();
                let _ = app.emit("job-event", JobEvent { job_id: id.clone(), book_id: book.clone(), kind: label, event: ev.event, data });
            })
            .await;
        if !is_final(&last) {
            // the stream broke or the sidecar died before the job said how it ended: that is a failure
            let message = res.err().map(|e| e.to_string()).unwrap_or_else(|| "the sidecar stopped before the job finished".into());
            last = "error".into();
            let _ = app.emit("job-event", JobEvent { job_id: id.clone(), book_id: book.clone(), kind: label, event: "error".into(), data: serde_json::json!({"code": "sidecar_lost", "message": message}) });
        }
        let state = app.state::<AppState>();
        state.jobs.lock().await.remove(&id);
        if let Some(status) = status_after(kind, &last) {
            let _ = state.repo.update(&book, None, Some(status));
            if matches!(status, BookStatus::Review | BookStatus::Planned) {
                adopt_plan_title(&state.repo, &book);
            }
        } else {
            let _ = state.repo.update(&book, None, None); // touches updated_at so the redrawn book moves to the top
        }
        let _ = app.emit("books-changed", ());
    });
    Ok(job_id)
}

/// A book whose title was made from the first words of the story takes the title the planner chose.
fn adopt_plan_title(repo: &BookRepository, id: &str) {
    if let Ok(d) = repo.detail(id, false) {
        if d.meta.extra.get("title_auto").and_then(|v| v.as_bool()) == Some(true) {
            if let Some(t) = std::fs::read_to_string(d.dir.join("plan.json")).ok().and_then(|t| serde_json::from_str::<serde_json::Value>(&t).ok()).and_then(|v| v["title"].as_str().map(str::to_owned)) {
                let _ = repo.update(id, Some(&t), None);
                let _ = repo.set_extra(id, "title_auto", serde_json::json!(false));
            }
        }
    }
}

#[tauri::command]
async fn start_generation(app: AppHandle, state: State<'_, AppState>, id: String) -> Result<String, String> {
    if running_ids(&state).await.contains(&id) {
        return Err("this book is already being generated".into());
    }
    let sidecar = ready_sidecar(&state).await?;
    let d = state.repo.detail(&id, false).map_err(err)?;
    let input = ["story.txt", "audio.wav", "audio.mp3", "audio.m4a", "audio.flac", "audio.ogg"].into_iter().find(|n| d.dir.join(n).is_file()).ok_or("this book has no story or audio file")?;
    state.repo.update(&id, None, Some(BookStatus::Generating)).map_err(err)?;
    let (dir, style, pages, keep) = (d.dir.clone(), d.meta.style.clone(), d.meta.pages, state.settings.lock().await.keep_recordings);
    let s2 = Arc::clone(&sidecar);
    let begin = async move { s2.start_generate(&dir, input, &style, pages, keep).await };
    match start_job(&app, &state, &id, JobKind::Generate, "generate", begin, sidecar).await {
        Ok(job) => {
            let _ = app.emit("books-changed", ());
            Ok(job)
        }
        Err(e) => {
            let _ = state.repo.update(&id, None, Some(d.meta.status)); // the sidecar refused: put the old status back
            Err(e)
        }
    }
}

/// What "Make the book" does: with approval on (the default) only the plan is made and the parent looks at the characters first;
/// with approval off the whole book is made in one go.
#[tauri::command]
async fn begin_book(app: AppHandle, state: State<'_, AppState>, id: String) -> Result<String, String> {
    if state.settings.lock().await.approve_first {
        start_step(app, state, id, "plan".into(), None).await
    } else {
        start_generation(app, state, id).await
    }
}

/// One step of the approval flow: `plan`, `assets` (optionally just one character or place again) or `pages`.
#[tauri::command]
async fn start_step(app: AppHandle, state: State<'_, AppState>, id: String, step: String, only: Option<String>) -> Result<String, String> {
    let (kind, label) = match step.as_str() {
        "plan" => (JobKind::Plan, "plan"),
        "assets" => (JobKind::Assets, "assets"),
        "pages" => (JobKind::Pages, "pages"),
        _ => return Err("unknown step".into()),
    };
    if running_ids(&state).await.contains(&id) {
        return Err("this book is already being worked on".into());
    }
    let sidecar = ready_sidecar(&state).await?;
    let d = state.repo.detail(&id, false).map_err(err)?;
    let input = ["story.txt", "audio.wav", "audio.mp3", "audio.m4a", "audio.flac", "audio.ogg"].into_iter().find(|n| d.dir.join(n).is_file());
    if step == "plan" && input.is_none() {
        return Err("this book has no story or audio file".into());
    }
    if step != "plan" && !d.has_plan {
        return Err("the plan is not made yet".into());
    }
    state.repo.update(&id, None, Some(BookStatus::Generating)).map_err(err)?;
    let (dir, style, pages, s2, keep) = (d.dir.clone(), d.meta.style.clone(), d.meta.pages, Arc::clone(&sidecar), state.settings.lock().await.keep_recordings);
    let input = input.unwrap_or("story.txt");
    let begin = async move { s2.start_step(&dir, &picturebook_core::sidecar::StepRequest { step: &step, input, style: &style, pages, only: only.as_deref(), keep_audio: keep }).await };
    match start_job(&app, &state, &id, kind, label, begin, sidecar).await {
        Ok(job) => {
            let _ = app.emit("books-changed", ());
            Ok(job)
        }
        Err(e) => {
            let _ = state.repo.update(&id, None, Some(d.meta.status)); // the sidecar refused: put the old status back
            Err(e)
        }
    }
}

#[tauri::command]
async fn get_plan(state: State<'_, AppState>, id: String) -> Result<PlanSummary, String> {
    state.repo.plan_summary(&id).map_err(err)
}

#[tauri::command]
async fn plan_options(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    ready_sidecar(&state).await?.plan_options().await.map_err(err)
}

/// Save changes to one character (`kind` = "character") or place ("place"); refused with a reason while a job runs or once pages exist.
#[tauri::command]
async fn save_plan_item(state: State<'_, AppState>, id: String, kind: String, name: String, fields: serde_json::Value) -> Result<serde_json::Value, String> {
    let d = state.repo.detail(&id, false).map_err(err)?;
    ready_sidecar(&state).await?.save_plan_item(&d.dir, &kind, &name, &fields).await.map_err(err)
}

#[tauri::command]
async fn regen_pages(app: AppHandle, state: State<'_, AppState>, id: String, pages: Vec<u32>) -> Result<String, String> {
    let sidecar = ready_sidecar(&state).await?;
    let d = state.repo.detail(&id, false).map_err(err)?;
    let (dir, s2) = (d.dir.clone(), Arc::clone(&sidecar));
    start_job(&app, &state, &id, JobKind::Redraw, "regen", async move { s2.start_regen(&dir, &pages).await }, sidecar).await
}

#[tauri::command]
async fn undo_page(app: AppHandle, state: State<'_, AppState>, id: String, page: u32) -> Result<String, String> {
    let sidecar = ready_sidecar(&state).await?;
    let d = state.repo.detail(&id, false).map_err(err)?;
    let (dir, s2) = (d.dir.clone(), Arc::clone(&sidecar));
    start_job(&app, &state, &id, JobKind::Redraw, "undo", async move { s2.start_undo(&dir, page).await }, sidecar).await
}

#[tauri::command]
async fn cancel_job(state: State<'_, AppState>, job_id: String) -> Result<bool, String> {
    ready_sidecar(&state).await?.cancel_job(&job_id).await.map_err(err)
}

#[tauri::command]
async fn delete_book(app: AppHandle, state: State<'_, AppState>, id: String) -> Result<(), String> {
    if running_ids(&state).await.contains(&id) {
        return Err("stop the running job first".into());
    }
    state.repo.delete(&id).map_err(err)?;
    let _ = app.emit("books-changed", ());
    Ok(())
}

#[tauri::command]
async fn delete_damaged(app: AppHandle, state: State<'_, AppState>, folder_name: String) -> Result<(), String> {
    state.repo.delete_damaged(&folder_name).map_err(err)?;
    let _ = app.emit("books-changed", ());
    Ok(())
}

fn open_with_desktop(path: &Path) -> Result<(), String> {
    std::process::Command::new("xdg-open").arg(path).stdin(std::process::Stdio::null()).stdout(std::process::Stdio::null()).stderr(std::process::Stdio::null()).spawn().map(|_| ()).map_err(|e| format!("could not open {}: {e}", path.display()))
}

/// Open the book's folder (`what` = "folder") or its PDF (`what` = "pdf") with the desktop's default program.
#[tauri::command]
async fn open_book(state: State<'_, AppState>, id: String, what: String) -> Result<(), String> {
    let d = state.repo.detail(&id, false).map_err(err)?;
    match what.as_str() {
        "folder" => open_with_desktop(&d.dir),
        "pdf" => open_with_desktop(&d.pdf.ok_or("the PDF has not been made yet")?),
        _ => Err("unknown target".into()),
    }
}

#[tauri::command]
async fn get_settings(state: State<'_, AppState>) -> Result<Settings, String> {
    Ok(state.settings.lock().await.clone())
}

/// Takes effect for new books at once; a changed library folder takes effect after the app is restarted.
#[tauri::command]
async fn set_settings(state: State<'_, AppState>, settings: Settings) -> Result<Settings, String> {
    let s = settings.sanitised();
    s.save(&state.settings_path).map_err(err)?;
    *state.settings.lock().await = s.clone();
    Ok(s)
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        // The app window may use the microphone (recording a story) and nothing else: camera, location, screen capture and notifications are refused.
        .on_permission_request(|_, kind| match kind {
            tauri::webview::PermissionKind::Microphone => tauri::webview::PermissionResponse::Allow,
            _ => tauri::webview::PermissionResponse::Deny,
        })
        .setup(|app| {
            let config_dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
            let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
            let settings_path = config_dir.join("settings.json");
            let settings = Settings::load(&settings_path);
            let library = settings.library_path(&data_dir);
            let repo = Arc::new(BookRepository::new(&library).map_err(|e| format!("cannot open the library folder {}: {e}", library.display()))?);
            // pictures are shown through the asset protocol; its scope is the library folder only
            app.asset_protocol_scope().allow_directory(&library, true).map_err(|e| e.to_string())?;
            app.manage(AppState { sidecar: Mutex::new(Slot::Starting), repo, settings_path, settings: Mutex::new(settings), jobs: Mutex::new(HashMap::new()) });
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let slot = match sidecar_python() {
                    Err(e) => Slot::Failed(e),
                    Ok(py) => {
                        let mut cfg = SidecarConfig::python_module(py, "picturebook_sidecar");
                        cfg.env = vec![
                            ("PICTUREBOOK_LIBRARY".into(), library.display().to_string()),
                            ("PICTUREBOOK_SCRIPTS".into(), scripts_dir().display().to_string()),
                            ("PATH".into(), path_with_local_bin()),
                        ];
                        match Sidecar::spawn(cfg).await {
                            Ok(s) => Slot::Ready(Arc::new(s)),
                            Err(e) => Slot::Failed(e.to_string()),
                        }
                    }
                };
                let state = handle.state::<AppState>();
                *state.sidecar.lock().await = slot;
                let dto = status_of(&state).await;
                let _ = handle.emit("sidecar-state", dto);
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_status, first_run_check, library_info, list_books, get_book, create_book, create_book_from_recording, start_generation, begin_book, start_step, get_plan, plan_options, save_plan_item, regen_pages, undo_page, cancel_job, delete_book, delete_damaged, open_book, get_settings, set_settings
        ])
        .build(tauri::generate_context!())
        .expect("error while building the Tauri application");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            // Ask the sidecar to stop (it also kills a running pipeline job); if that fails, dropping the handle (kill_on_drop)
            // and the closed stdin pipe still end it.
            let state = handle.state::<AppState>();
            tauri::async_runtime::block_on(async {
                if let Slot::Ready(s) = &*state.sidecar.lock().await {
                    s.request_shutdown().await;
                }
            });
        }
    });
}

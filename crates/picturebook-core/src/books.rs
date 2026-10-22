//! The book library: **the folders are the only source of truth** (there is no index of paths that could go stale).
//!
//! Layout under the library root (`<data-dir>/books`):
//!
//! ```text
//! <any folder name>/book.json      {"id", "title", "status", "style", "pages", "source", "created_at", "updated_at"}
//! <any folder name>/plan.json      written by the pipeline (stage `plan`)
//! <any folder name>/pages/page_03.png, page_03_v1.png ...   current picture and earlier versions
//! <any folder name>/regen_log.json, checks/report.json, book.pdf
//! ```
//!
//! A book is identified by the `id` **inside** `book.json`, never by its folder name or path, so the user may rename a
//! folder. Every path handed to the UI is computed from the folder found by a fresh scan plus a fixed relative name; no
//! absolute path is ever stored. Missing or damaged files are reported, not hidden.

use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum BookError {
    #[error("no book with id {0}")]
    NotFound(String),
    #[error("not a valid book id: {0:?}")]
    BadId(String),
    #[error("refusing to touch {0}: {1}")]
    Refused(PathBuf, &'static str),
    #[error("i/o error: {0}")]
    Io(#[from] io::Error),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("could not generate a random id: {0}")]
    Random(String),
}

pub type Result<T> = std::result::Result<T, BookError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BookStatus {
    Draft,
    /// The plan exists; the parent looks at the characters and places before the pictures are drawn.
    Planned,
    Generating,
    Review,
    Failed,
    /// Only produced by [`effective_status`]: the folder says `generating` but no job is running (the app was closed).
    Interrupted,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Text,
    Audio,
}

/// The contents of `book.json`. Unknown fields written by a newer version or by the user are kept on every rewrite.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BookMeta {
    pub id: String,
    pub title: String,
    pub status: BookStatus,
    #[serde(default = "default_style")]
    pub style: String,
    /// Number of pages requested; `None` = the default.
    #[serde(default)]
    pub pages: Option<u32>,
    pub source: Source,
    /// Seconds since the Unix epoch.
    pub created_at: u64,
    pub updated_at: u64,
    #[serde(flatten)]
    pub extra: BTreeMap<String, serde_json::Value>,
}

fn default_style() -> String {
    "crayon".into()
}

/// A book found by a scan. `dir` is only valid until the next scan.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct BookSummary {
    pub meta: BookMeta,
    pub dir: PathBuf,
    /// Status as shown to the user (`generating` without a running job becomes `interrupted`).
    pub status: BookStatus,
    /// Pages found in `plan.json` (0 until the plan stage has run).
    pub page_count: u32,
    /// `pages/page_01.png` if it exists.
    pub cover: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum LibraryEntry {
    Book(Box<BookSummary>),
    /// A folder under the library root that cannot be used as a book (still listed so the user can open or delete it).
    Damaged { dir: PathBuf, folder_name: String, reason: String },
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct PageDetail {
    pub index: u32,
    pub text: String,
    /// The current picture; `None` when the file is missing (the UI shows a placeholder and a Redraw button).
    pub image: Option<PathBuf>,
    /// Earlier pictures kept by a redraw, oldest first (`page_NN_v1.png`, ...).
    pub versions: Vec<PathBuf>,
    pub redrawn: u32,
    /// Warning notes for the human reviewer (`checks/report.json`); never an automatic action.
    pub hints: Vec<String>,
    /// False when the notes belong to an earlier drawing (the page was redrawn or restored since): the UI says "not checked".
    pub checked: bool,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct BookDetail {
    pub meta: BookMeta,
    pub dir: PathBuf,
    pub status: BookStatus,
    pub pages: Vec<PageDetail>,
    pub pdf: Option<PathBuf>,
    /// Plain-language problems found in the folder (unreadable plan, missing pictures ...).
    pub problems: Vec<String>,
    /// plan.json exists and lists at least one character.
    pub has_plan: bool,
}

/// One character or place on the approval screen.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct PlanItem {
    pub name: String,
    /// The full spec as stored in plan.json (the UI edits it field by field; the sidecar validates every save).
    pub spec: serde_json::Value,
    /// The chosen picture (`assets/ref_<slug>.png` or `assets/plate_<slug>.png`); `None` until it is drawn.
    pub image: Option<PathBuf>,
    /// Fields the planner had to invent because the story did not say them.
    pub guessed: Vec<String>,
    /// How many times this item has been drawn again by the parent.
    pub draws: u32,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct PlanSummary {
    pub title: String,
    pub characters: Vec<PlanItem>,
    pub places: Vec<PlanItem>,
    /// False once any page picture exists: characters and places can no longer be changed.
    pub editable: bool,
    /// Every character and place has its picture.
    pub all_drawn: bool,
}

/// File-name friendly version of a character or place name; MUST equal `slug` in scripts/rules.py (parity cases are tested on both sides).
pub fn slug_name(name: &str) -> String {
    let mut out = String::new();
    for c in name.to_lowercase().chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            out.push(c);
        } else if !out.ends_with('_') {
            out.push('_');
        }
    }
    out.trim_matches('_').to_string()
}

pub fn now_secs() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// `generating` in `book.json` with no running job means the app was closed during generation.
pub fn effective_status(stored: BookStatus, job_running: bool) -> BookStatus {
    if stored == BookStatus::Generating && !job_running { BookStatus::Interrupted } else { stored }
}

fn valid_id(id: &str) -> bool {
    id.len() == 32 && id.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn random_id() -> Result<String> {
    let mut bytes = [0u8; 16];
    getrandom::fill(&mut bytes).map_err(|e| BookError::Random(e.to_string()))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

/// Folder-name friendly version of a title: ASCII lowercase letters and digits joined by `-`, at most 40 characters.
pub fn slug(title: &str) -> String {
    let mut out = String::new();
    for c in title.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
        } else if !out.ends_with('-') && !out.is_empty() {
            out.push('-');
        }
        if out.len() >= 40 {
            break;
        }
    }
    let out = out.trim_matches('-').to_string();
    if out.is_empty() { "book".into() } else { out }
}

/// Write a file so that readers see either the old or the new content, never a half-written file.
fn write_atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let tmp = path.with_extension(format!("tmp-{}", &random_id()?[..8]));
    fs::write(&tmp, bytes)?;
    fs::rename(&tmp, path).inspect_err(|_| {
        let _ = fs::remove_file(&tmp);
    })?;
    Ok(())
}

fn read_json(path: &Path) -> std::result::Result<serde_json::Value, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

pub struct BookRepository {
    root: PathBuf,
}

impl BookRepository {
    /// `root` is the folder that contains one folder per book. It is created if missing.
    pub fn new(root: impl Into<PathBuf>) -> Result<Self> {
        let root = root.into();
        fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Read the library from disk. Newest books first; damaged folders last. `running` holds the ids of books with a running job.
    pub fn scan(&self, running: &HashSet<String>) -> Result<Vec<LibraryEntry>> {
        let mut books: Vec<BookSummary> = Vec::new();
        let mut damaged: Vec<LibraryEntry> = Vec::new();
        let mut seen: BTreeMap<String, PathBuf> = BTreeMap::new();
        let mut dirs: Vec<PathBuf> = fs::read_dir(&self.root)?
            .filter_map(|e| e.ok())
            .filter(|e| !e.file_name().to_string_lossy().starts_with('.'))
            .filter(|e| e.file_type().map(|t| t.is_dir()).unwrap_or(false)) // symlinks and stray files are ignored
            .map(|e| e.path())
            .collect();
        dirs.sort();
        for dir in dirs {
            let folder_name = dir.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
            match read_meta(&dir) {
                Err(reason) => damaged.push(LibraryEntry::Damaged { dir, folder_name, reason }),
                Ok(meta) => {
                    if let Some(first) = seen.get(&meta.id) {
                        let reason = format!("has the same id as the folder {:?} (was a book folder copied?)", first.file_name().unwrap_or_default());
                        damaged.push(LibraryEntry::Damaged { dir, folder_name, reason });
                        continue;
                    }
                    seen.insert(meta.id.clone(), dir.clone());
                    let status = effective_status(meta.status, running.contains(&meta.id));
                    let page_count = plan_pages(&dir).map(|p| p.len() as u32).unwrap_or(0);
                    let cover = Some(dir.join("pages").join("page_01.png")).filter(|p| p.is_file());
                    books.push(BookSummary { meta, dir, status, page_count, cover });
                }
            }
        }
        books.sort_by(|a, b| b.meta.updated_at.cmp(&a.meta.updated_at).then_with(|| a.meta.title.cmp(&b.meta.title)));
        let mut out: Vec<LibraryEntry> = books.into_iter().map(|b| LibraryEntry::Book(Box::new(b))).collect();
        out.extend(damaged);
        Ok(out)
    }

    /// Folder of the book with this id, found by a fresh scan (so renamed folders are found; nothing is cached).
    pub fn dir_of(&self, id: &str) -> Result<PathBuf> {
        if !valid_id(id) {
            return Err(BookError::BadId(id.to_string()));
        }
        for e in self.scan(&HashSet::new())? {
            if let LibraryEntry::Book(b) = e {
                if b.meta.id == id {
                    return Ok(b.dir);
                }
            }
        }
        Err(BookError::NotFound(id.to_string()))
    }

    /// Create `<root>/<slug>-<id prefix>/book.json` with status `draft`.
    pub fn create(&self, title: &str, style: &str, pages: Option<u32>, source: Source) -> Result<BookSummary> {
        let id = random_id()?;
        let title = { let t = title.trim(); if t.is_empty() { "Untitled book" } else { t } };
        let dir = self.root.join(format!("{}-{}", slug(title), &id[..8]));
        fs::create_dir(&dir)?;
        let now = now_secs();
        let meta = BookMeta { id, title: title.to_string(), status: BookStatus::Draft, style: style.to_string(), pages, source, created_at: now, updated_at: now, extra: BTreeMap::new() };
        write_meta(&dir, &meta)?;
        Ok(BookSummary { status: meta.status, meta, dir, page_count: 0, cover: None })
    }

    /// Change the stored title and/or status of a book (other fields, including unknown ones, are kept).
    pub fn update(&self, id: &str, title: Option<&str>, status: Option<BookStatus>) -> Result<BookMeta> {
        let dir = self.dir_of(id)?;
        let mut meta = read_meta(&dir).map_err(|e| BookError::Io(io::Error::new(io::ErrorKind::InvalidData, e)))?;
        if let Some(t) = title.map(str::trim).filter(|t| !t.is_empty()) {
            meta.title = t.to_string();
        }
        if let Some(s) = status {
            meta.status = s;
        }
        meta.updated_at = now_secs();
        write_meta(&dir, &meta)?;
        Ok(meta)
    }

    /// Store one extra field in `book.json` (for flags such as `title_auto`); everything else is kept as it is.
    pub fn set_extra(&self, id: &str, key: &str, value: serde_json::Value) -> Result<()> {
        let dir = self.dir_of(id)?;
        let mut meta = read_meta(&dir).map_err(|e| BookError::Io(io::Error::new(io::ErrorKind::InvalidData, e)))?;
        if ["id", "title", "status", "style", "pages", "source", "created_at", "updated_at"].contains(&key) {
            return Err(BookError::Refused(dir, "that name is a regular field of book.json"));
        }
        meta.extra.insert(key.to_string(), value);
        write_meta(&dir, &meta)
    }

    /// Everything the review screen needs. Problems are listed in `problems`, never raised as errors.
    pub fn detail(&self, id: &str, job_running: bool) -> Result<BookDetail> {
        let dir = self.dir_of(id)?;
        let meta = read_meta(&dir).map_err(|e| BookError::Io(io::Error::new(io::ErrorKind::InvalidData, e)))?;
        let mut problems = Vec::new();
        let plan = match plan_pages(&dir) {
            Ok(p) => p,
            Err(e) => {
                if meta.status == BookStatus::Review {
                    problems.push(format!("plan.json is not usable ({e}); generate the book again"));
                }
                Vec::new()
            }
        };
        let log = read_json(&dir.join("regen_log.json")).unwrap_or(serde_json::Value::Null);
        let report = read_json(&dir.join("checks").join("report.json")).unwrap_or(serde_json::Value::Null);
        let mut pages = Vec::new();
        for (index, text) in plan {
            let name = format!("page_{index:02}");
            let image = Some(dir.join("pages").join(format!("{name}.png"))).filter(|p| p.is_file());
            if image.is_none() {
                problems.push(format!("the picture of page {index} is missing; press Redraw"));
            }
            let versions = page_versions(&dir.join("pages"), &name);
            let redrawn = log[index.to_string()]["attempt"].as_u64().unwrap_or(0) as u32;
            let hints = report[index.to_string()]["hints"].as_array().map(|a| a.iter().filter_map(|h| h.as_str().map(str::to_owned)).collect()).unwrap_or_default();
            let checked = report[index.to_string()]["checked"].as_bool().unwrap_or(true);
            pages.push(PageDetail { index, text, image, versions, redrawn, hints, checked });
        }
        let pdf = Some(dir.join("book.pdf")).filter(|p| p.is_file());
        let status = effective_status(meta.status, job_running);
        let has_plan = read_json(&dir.join("plan.json")).ok().and_then(|v| v["characters"].as_array().map(|a| !a.is_empty())).unwrap_or(false);
        Ok(BookDetail { meta, dir, status, pages, pdf, problems, has_plan })
    }

    /// Characters and places of the plan with their pictures, for the approval screen.
    pub fn plan_summary(&self, id: &str) -> Result<PlanSummary> {
        let dir = self.dir_of(id)?;
        let plan = read_json(&dir.join("plan.json")).map_err(|e| BookError::Io(io::Error::new(io::ErrorKind::InvalidData, format!("plan.json: {e}"))))?;
        let draws: serde_json::Value = read_json(&dir.join("assets").join("draw_log.json")).unwrap_or(serde_json::Value::Null);
        let item = |spec: &serde_json::Value, prefix: &str| -> Option<PlanItem> {
            let name = spec["name"].as_str()?.to_string();
            let image = Some(dir.join("assets").join(format!("{prefix}_{}.png", slug_name(&name)))).filter(|p| p.is_file());
            let guessed = spec["inferred_fields"].as_array().map(|a| a.iter().filter_map(|x| x.as_str().map(str::to_owned)).collect()).unwrap_or_default();
            Some(PlanItem { draws: draws[&name].as_u64().unwrap_or(0) as u32, name, spec: spec.clone(), image, guessed })
        };
        let characters: Vec<PlanItem> = plan["characters"].as_array().into_iter().flatten().filter_map(|s| item(s, "ref")).collect();
        let places: Vec<PlanItem> = plan["environments"].as_array().into_iter().flatten().filter_map(|s| item(s, "plate")).collect();
        let editable = !fs::read_dir(dir.join("pages")).map(|d| d.filter_map(|e| e.ok()).any(|e| e.file_name().to_string_lossy().starts_with("page_"))).unwrap_or(false);
        let all_drawn = characters.iter().chain(places.iter()).all(|i| i.image.is_some());
        Ok(PlanSummary { title: plan["title"].as_str().unwrap_or_default().to_string(), characters, places, editable, all_drawn })
    }

    /// Delete a book folder. Only a direct child of the library root that holds a readable `book.json` with this id is ever removed.
    pub fn delete(&self, id: &str) -> Result<()> {
        let dir = self.dir_of(id)?;
        if dir.parent() != Some(self.root.as_path()) {
            return Err(BookError::Refused(dir, "not directly inside the library folder"));
        }
        if fs::symlink_metadata(&dir)?.file_type().is_symlink() {
            return Err(BookError::Refused(dir, "is a symbolic link"));
        }
        fs::remove_dir_all(&dir)?;
        Ok(())
    }

    /// Delete a damaged folder by name (the user asked for it in the library). Same safety rules, no `book.json` needed.
    pub fn delete_damaged(&self, folder_name: &str) -> Result<()> {
        if folder_name.is_empty() || folder_name.contains(['/', '\\']) || folder_name == "." || folder_name == ".." || folder_name.starts_with('.') {
            return Err(BookError::Refused(PathBuf::from(folder_name), "not a plain folder name"));
        }
        let dir = self.root.join(folder_name);
        if !fs::symlink_metadata(&dir)?.file_type().is_dir() {
            return Err(BookError::Refused(dir, "not a folder"));
        }
        // Only folders that the library itself lists as damaged (unreadable, or a copy of another book's folder) may go this way.
        let listed = self.scan(&HashSet::new())?.into_iter().any(|e| matches!(e, LibraryEntry::Damaged { dir: d, .. } if d == dir));
        if !listed {
            return Err(BookError::Refused(dir, "is a working book, delete it by id"));
        }
        fs::remove_dir_all(&dir)?;
        Ok(())
    }
}

fn read_meta(dir: &Path) -> std::result::Result<BookMeta, String> {
    let path = dir.join("book.json");
    if !path.is_file() {
        return Err("book.json is missing".into());
    }
    let text = fs::read_to_string(&path).map_err(|e| format!("book.json cannot be read: {e}"))?;
    let meta: BookMeta = serde_json::from_str(&text).map_err(|e| format!("book.json is damaged: {e}"))?;
    if !valid_id(&meta.id) {
        return Err(format!("book.json has an invalid id {:?}", meta.id));
    }
    Ok(meta)
}

fn write_meta(dir: &Path, meta: &BookMeta) -> Result<()> {
    write_atomic(&dir.join("book.json"), serde_json::to_string_pretty(meta)?.as_bytes())
}

/// `(page index, story text)` for every page of `plan.json`.
fn plan_pages(dir: &Path) -> std::result::Result<Vec<(u32, String)>, String> {
    let plan = read_json(&dir.join("plan.json"))?;
    let pages = plan["pages"].as_array().ok_or("it has no pages")?;
    Ok(pages
        .iter()
        .enumerate()
        .map(|(i, p)| (p["index"].as_u64().map(|v| v as u32).unwrap_or(i as u32 + 1), p["story_text"].as_str().unwrap_or_default().to_string()))
        .collect())
}

/// `page_03_v1.png`, `page_03_v2.png` ... in version order.
fn page_versions(pages_dir: &Path, name: &str) -> Vec<PathBuf> {
    let prefix = format!("{name}_v");
    let mut found: Vec<(u32, PathBuf)> = fs::read_dir(pages_dir)
        .into_iter()
        .flatten()
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let file = e.file_name().to_string_lossy().into_owned();
            let n = file.strip_prefix(&prefix)?.strip_suffix(".png")?.parse::<u32>().ok()?;
            Some((n, e.path()))
        })
        .collect();
    found.sort();
    found.into_iter().map(|(_, p)| p).collect()
}

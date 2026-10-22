//! User settings in one small JSON file. A missing or damaged file never stops the app: defaults are used and the file is rewritten on the next save.

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    /// Where the books are kept; `None` = the default folder inside the app data directory.
    pub library_dir: Option<PathBuf>,
    pub style: String,
    /// Default number of pages for a new book.
    pub pages: u32,
    /// Show the characters and places for approval before the pictures are drawn (default); off = make the whole book in one go.
    pub approve_first: bool,
    /// Keep the recording of a spoken story after it was transcribed (default off: the recording is deleted, only the text stays).
    pub keep_recordings: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self { library_dir: None, style: "crayon".into(), pages: 6, approve_first: true, keep_recordings: false }
    }
}

impl Settings {
    /// Keep every value inside what the pipeline accepts.
    pub fn sanitised(mut self) -> Self {
        if !["crayon", "flat", "watercolour"].contains(&self.style.as_str()) {
            self.style = "crayon".into();
        }
        self.pages = self.pages.clamp(1, 10);
        if self.library_dir.as_ref().is_some_and(|p| p.as_os_str().is_empty() || !p.is_absolute()) {
            self.library_dir = None;
        }
        self
    }

    pub fn load(path: &Path) -> Self {
        fs::read_to_string(path).ok().and_then(|t| serde_json::from_str::<Settings>(&t).ok()).unwrap_or_default().sanitised()
    }

    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let tmp = path.with_extension("json.tmp");
        fs::write(&tmp, serde_json::to_string_pretty(&self.clone().sanitised()).map_err(std::io::Error::other)?)?;
        fs::rename(tmp, path)
    }

    /// The library folder to use, given the app data directory.
    pub fn library_path(&self, data_dir: &Path) -> PathBuf {
        self.library_dir.clone().unwrap_or_else(|| data_dir.join("books"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp(name: &str) -> PathBuf {
        let p = std::env::temp_dir().join(format!("pb-settings-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&p);
        fs::create_dir_all(&p).unwrap();
        p
    }

    #[test]
    fn missing_or_damaged_files_give_defaults() {
        let d = tmp("damaged");
        assert_eq!(Settings::load(&d.join("none.json")), Settings::default());
        fs::write(d.join("s.json"), "{ nope").unwrap();
        assert_eq!(Settings::load(&d.join("s.json")), Settings::default());
    }

    #[test]
    fn values_are_clamped_and_unknown_styles_fall_back() {
        let d = tmp("clamp");
        fs::write(d.join("s.json"), r#"{"style":"oil","pages":99,"library_dir":"relative/path"}"#).unwrap();
        let s = Settings::load(&d.join("s.json"));
        assert_eq!((s.style.as_str(), s.pages, s.library_dir), ("crayon", 10, None));
    }

    #[test]
    fn save_then_load_round_trips_and_partial_files_work() {
        let d = tmp("round");
        let s = Settings { library_dir: Some(PathBuf::from("/data/books")), style: "flat".into(), pages: 8, approve_first: false, keep_recordings: true };
        s.save(&d.join("sub/s.json")).unwrap();
        assert_eq!(Settings::load(&d.join("sub/s.json")), s);
        fs::write(d.join("p.json"), r#"{"pages":4}"#).unwrap();
        assert_eq!(Settings::load(&d.join("p.json")).pages, 4);
        assert!(Settings::load(&d.join("p.json")).approve_first, "an older settings file without the new switch keeps approval on");
        assert_eq!(Settings::default().library_path(Path::new("/app")), PathBuf::from("/app/books"));
        assert_eq!(s.library_path(Path::new("/app")), PathBuf::from("/data/books"));
    }
}

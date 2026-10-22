//! Supervisor and client for the Python inference sidecar.
//!
//! Protocol (see docs/architecture.md, section 2):
//! * the core generates a random per-launch token and passes it in `PICTUREBOOK_TOKEN`;
//! * the sidecar binds `127.0.0.1` on a free port and prints one JSON line `{"event":"ready","port":N,...}`;
//! * the core keeps the sidecar's stdin open; when the core dies the pipe closes and the sidecar exits by itself;
//! * every HTTP request carries `Authorization: Bearer <token>`.

use std::path::PathBuf;
use std::process::{ExitStatus, Stdio};
use std::time::Duration;

use futures_util::StreamExt;
use serde::Deserialize;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::time::timeout;

use crate::sse::{SseEvent, SseParser};

#[derive(Debug, thiserror::Error)]
pub enum SidecarError {
    #[error("could not start the sidecar: {0}")]
    Spawn(#[from] std::io::Error),
    #[error("the sidecar exited before announcing it was ready")]
    ExitedEarly,
    #[error("the sidecar did not become ready within {0:?}")]
    ReadyTimeout(Duration),
    #[error("could not generate a random token: {0}")]
    Random(String),
    #[error("http error: {0}")]
    Http(#[from] reqwest::Error),
    #[error("the sidecar answered with status {0}")]
    Status(u16),
    /// The sidecar refused a request (HTTP 400 or 409) and said why, in plain words.
    #[error("{0}")]
    Refused(String),
    #[error("unexpected response: {0}")]
    BadResponse(String),
}

pub type Result<T> = std::result::Result<T, SidecarError>;

#[derive(Debug, Clone)]
pub struct SidecarConfig {
    /// Program to run, e.g. `sidecar/.venv/bin/python` in development.
    pub program: PathBuf,
    /// Arguments, e.g. `["-m", "picturebook_sidecar"]`.
    pub args: Vec<String>,
    pub cwd: Option<PathBuf>,
    /// Extra environment variables (library folder, scripts folder ...). The token is added by `spawn`.
    pub env: Vec<(String, String)>,
    pub ready_timeout: Duration,
}

impl SidecarConfig {
    pub fn python_module(python: impl Into<PathBuf>, module: &str) -> Self {
        Self { program: python.into(), args: vec!["-m".into(), module.into()], cwd: None, env: Vec::new(), ready_timeout: Duration::from_secs(30) }
    }
}

#[derive(Debug, Deserialize)]
struct Ready {
    event: String,
    port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Health {
    pub status: String,
    pub version: String,
    pub gpu: Option<serde_json::Value>,
}

/// One line of the first-run check.
#[derive(Debug, Clone, Deserialize, serde::Serialize)]
pub struct DiagnosticCheck {
    pub id: String,
    pub title: String,
    /// `ok`, `warn` or `missing`.
    pub status: String,
    pub detail: String,
    pub fix: String,
    pub needed_for: String,
    pub blocking: bool,
}

#[derive(Debug, Clone, Deserialize, serde::Serialize)]
pub struct Diagnostics {
    pub checks: Vec<DiagnosticCheck>,
    pub blockers: Vec<String>,
    pub audio_ready: bool,
}

pub struct Sidecar {
    child: Child,
    _stdin: ChildStdin, // dropping it closes the pipe: the sidecar's parent-death signal
    base_url: String,
    token: String,
    client: reqwest::Client,
}

fn random_token() -> Result<String> {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).map_err(|e| SidecarError::Random(e.to_string()))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

/// What one pipeline step needs besides the book folder. `only` draws a single character or place again.
pub struct StepRequest<'a> {
    pub step: &'a str,
    pub input: &'a str,
    pub style: &'a str,
    pub pages: Option<u32>,
    pub only: Option<&'a str>,
    pub keep_audio: bool,
}

impl Sidecar {
    /// Spawn the sidecar and wait until it announces its port.
    pub async fn spawn(cfg: SidecarConfig) -> Result<Self> {
        let token = random_token()?;
        let mut cmd = Command::new(&cfg.program);
        cmd.args(&cfg.args)
            .envs(cfg.env.iter().map(|(k, v)| (k.as_str(), v.as_str())))
            .env("PICTUREBOOK_TOKEN", &token)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .kill_on_drop(true);
        if let Some(cwd) = &cfg.cwd {
            cmd.current_dir(cwd);
        }
        let mut child = cmd.spawn()?;
        let stdin = child.stdin.take().expect("stdin was piped");
        let stdout = child.stdout.take().expect("stdout was piped");
        let mut lines = BufReader::new(stdout).lines();

        let port = match timeout(cfg.ready_timeout, async {
            while let Some(line) = lines.next_line().await? {
                if let Ok(r) = serde_json::from_str::<Ready>(&line) {
                    if r.event == "ready" {
                        return Ok::<Option<u16>, std::io::Error>(Some(r.port));
                    }
                }
                eprintln!("[sidecar] {line}");
            }
            Ok(None)
        })
        .await
        {
            Err(_) => return Err(SidecarError::ReadyTimeout(cfg.ready_timeout)),
            Ok(Err(e)) => return Err(SidecarError::Spawn(e)),
            Ok(Ok(None)) => return Err(SidecarError::ExitedEarly),
            Ok(Ok(Some(p))) => p,
        };
        // Keep draining stdout so the pipe never fills up and blocks the sidecar.
        tokio::spawn(async move {
            while let Ok(Some(line)) = lines.next_line().await {
                eprintln!("[sidecar] {line}");
            }
        });
        // `no_proxy`: a system proxy must never see loopback traffic that carries the token.
        let client = reqwest::Client::builder().no_proxy().build()?;
        Ok(Self { child, _stdin: stdin, base_url: format!("http://127.0.0.1:{port}"), token, client })
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn pid(&self) -> Option<u32> {
        self.child.id()
    }

    fn get(&self, path: &str) -> reqwest::RequestBuilder {
        self.client.get(format!("{}{path}", self.base_url)).bearer_auth(&self.token)
    }

    fn post(&self, path: &str) -> reqwest::RequestBuilder {
        self.client.post(format!("{}{path}", self.base_url)).bearer_auth(&self.token)
    }

    pub async fn health(&self) -> Result<Health> {
        let r = self.get("/health").timeout(Duration::from_secs(10)).send().await?;
        check(&r)?;
        Ok(r.json().await?)
    }

    /// First-run check: what is present or missing on this machine (nothing is changed or downloaded).
    pub async fn diagnostics(&self) -> Result<Diagnostics> {
        let r = self.get("/diagnostics").timeout(Duration::from_secs(120)).send().await?;
        check(&r)?;
        Ok(r.json().await?)
    }

    pub async fn start_demo_job(&self, steps: u32, delay_ms: u32) -> Result<String> {
        let r = self.post("/jobs/demo").timeout(Duration::from_secs(10)).json(&serde_json::json!({"steps": steps, "delay_ms": delay_ms})).send().await?;
        check(&r)?;
        let v: serde_json::Value = r.json().await?;
        v["job_id"].as_str().map(str::to_owned).ok_or_else(|| SidecarError::BadResponse(v.to_string()))
    }

    async fn post_job(&self, path: &str, body: serde_json::Value) -> Result<String> {
        let r = self.post(path).timeout(Duration::from_secs(10)).json(&body).send().await?;
        if matches!(r.status().as_u16(), 400 | 409) {
            let detail = r.json::<serde_json::Value>().await.ok().and_then(|v| v["detail"].as_str().map(str::to_owned));
            return Err(SidecarError::Refused(detail.unwrap_or_else(|| "the request was refused".into())));
        }
        check(&r)?;
        let v: serde_json::Value = r.json().await?;
        v["job_id"].as_str().map(str::to_owned).ok_or_else(|| SidecarError::BadResponse(v.to_string()))
    }

    /// Generate a whole book in `book_dir` from `input` (`story.txt` or `audio.<ext>` inside that folder). Returns the job id.
    pub async fn start_generate(&self, book_dir: &std::path::Path, input: &str, style: &str, pages: Option<u32>, keep_audio: bool) -> Result<String> {
        self.post_job("/jobs/generate", serde_json::json!({"book_dir": book_dir, "input": input, "style": style, "pages": pages, "keep_audio": keep_audio})).await
    }

    /// One of the three pipeline steps (`plan`, `assets`, `pages`).
    pub async fn start_step(&self, book_dir: &std::path::Path, step: &StepRequest<'_>) -> Result<String> {
        self.post_job("/jobs/step", serde_json::json!({"book_dir": book_dir, "step": step.step, "input": step.input, "style": step.style, "pages": step.pages, "only": step.only, "keep_audio": step.keep_audio})).await
    }

    /// Change fields of a character (`kind` = "character") or place ("place"); the sidecar validates them and returns the saved spec.
    pub async fn save_plan_item(&self, book_dir: &std::path::Path, kind: &str, name: &str, fields: &serde_json::Value) -> Result<serde_json::Value> {
        let r = self.post(&format!("/plan/{kind}")).timeout(Duration::from_secs(20)).json(&serde_json::json!({"book_dir": book_dir, "name": name, "fields": fields})).send().await?;
        if matches!(r.status().as_u16(), 400 | 409) {
            let detail = r.json::<serde_json::Value>().await.ok().and_then(|v| v["detail"].as_str().map(str::to_owned));
            return Err(SidecarError::Refused(detail.unwrap_or_else(|| "the change was refused".into())));
        }
        check(&r)?;
        Ok(r.json::<serde_json::Value>().await?["spec"].clone())
    }

    /// The allowed values of every drop-down on the characters screen.
    pub async fn plan_options(&self) -> Result<serde_json::Value> {
        let r = self.get("/plan/options").timeout(Duration::from_secs(10)).send().await?;
        check(&r)?;
        Ok(r.json().await?)
    }

    /// Redraw these pages (new random seed; earlier pictures are kept).
    pub async fn start_regen(&self, book_dir: &std::path::Path, pages: &[u32]) -> Result<String> {
        self.post_job("/jobs/regen", serde_json::json!({"book_dir": book_dir, "pages": pages})).await
    }

    /// Put the previous picture of a page back.
    pub async fn start_undo(&self, book_dir: &std::path::Path, page: u32) -> Result<String> {
        self.post_job("/jobs/undo", serde_json::json!({"book_dir": book_dir, "page": page})).await
    }

    /// Stop a running job. Returns false when it was not running any more.
    pub async fn cancel_job(&self, job_id: &str) -> Result<bool> {
        let r = self.post(&format!("/jobs/{job_id}/cancel")).timeout(Duration::from_secs(20)).send().await?;
        check(&r)?;
        Ok(r.json::<serde_json::Value>().await?["cancelled"].as_bool().unwrap_or(false))
    }

    /// Follow a job's Server-Sent Events, calling `on_event` for each one until the stream ends.
    pub async fn follow_events(&self, job_id: &str, mut on_event: impl FnMut(SseEvent)) -> Result<()> {
        let r = self.get(&format!("/events/{job_id}")).send().await?;
        check(&r)?;
        let mut parser = SseParser::new();
        let mut stream = r.bytes_stream();
        while let Some(chunk) = stream.next().await {
            for ev in parser.push(&chunk?) {
                on_event(ev);
            }
        }
        Ok(())
    }

    /// Ask the sidecar to stop without consuming the handle (used on app exit; dropping the handle kills the process anyway).
    pub async fn request_shutdown(&self) {
        let _ = self.post("/shutdown").timeout(Duration::from_secs(2)).send().await;
    }

    /// Ask the sidecar to stop, wait up to `grace`, then kill it.
    pub async fn shutdown(mut self, grace: Duration) -> Result<ExitStatus> {
        let _ = self.post("/shutdown").timeout(Duration::from_secs(5)).send().await;
        match timeout(grace, self.child.wait()).await {
            Ok(status) => Ok(status?),
            Err(_) => {
                self.child.kill().await?;
                Ok(self.child.wait().await?)
            }
        }
    }
}

fn check(r: &reqwest::Response) -> Result<()> {
    if r.status().is_success() { Ok(()) } else { Err(SidecarError::Status(r.status().as_u16())) }
}

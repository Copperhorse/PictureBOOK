//! End-to-end tests against the real Python sidecar (needs `uv sync` in `sidecar/`; skipped when the venv is missing).
use std::path::PathBuf;
use std::time::Duration;

use picturebook_core::sidecar::{Sidecar, SidecarConfig, SidecarError};

fn python() -> Option<PathBuf> {
    let p = std::env::var_os("PICTUREBOOK_SIDECAR_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../sidecar/.venv/bin/python"));
    p.exists().then_some(p)
}

macro_rules! sidecar_or_skip {
    () => {{
        let Some(py) = python() else {
            eprintln!("skipped: sidecar venv not found (run `uv sync` in sidecar/)");
            return;
        };
        Sidecar::spawn(SidecarConfig::python_module(py, "picturebook_sidecar")).await.expect("sidecar starts")
    }};
}

#[tokio::test]
async fn health_requires_the_token_and_succeeds_with_it() {
    let s = sidecar_or_skip!();
    let h = s.health().await.expect("authorised health");
    assert_eq!(h.status, "ok");
    // A request without the token is refused.
    let r = reqwest::Client::builder().no_proxy().build().unwrap().get(format!("{}/health", s.base_url())).send().await.unwrap();
    assert_eq!(r.status().as_u16(), 401);
    s.shutdown(Duration::from_secs(5)).await.unwrap();
}

#[tokio::test]
async fn demo_job_progress_arrives_in_order() {
    let s = sidecar_or_skip!();
    let id = s.start_demo_job(4, 20).await.unwrap();
    let mut seen = Vec::new();
    s.follow_events(&id, |ev| seen.push((ev.event, ev.data))).await.unwrap();
    let names: Vec<&str> = seen.iter().map(|(n, _)| n.as_str()).collect();
    assert_eq!(names, ["progress", "progress", "progress", "progress", "done"]);
    assert!(seen[3].1.contains("\"fraction\": 1.0"));
    s.shutdown(Duration::from_secs(5)).await.unwrap();
}

#[tokio::test]
async fn shutdown_stops_the_process_cleanly() {
    let s = sidecar_or_skip!();
    let pid = s.pid().unwrap();
    let status = s.shutdown(Duration::from_secs(5)).await.unwrap();
    assert!(status.success());
    assert!(!PathBuf::from(format!("/proc/{pid}")).exists());
}

#[tokio::test]
async fn dropping_the_handle_kills_the_sidecar() {
    let s = sidecar_or_skip!();
    let pid = s.pid().unwrap();
    drop(s);
    for _ in 0..50 {
        if !PathBuf::from(format!("/proc/{pid}")).exists() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
    panic!("sidecar {pid} still running after the handle was dropped");
}

#[tokio::test]
async fn a_program_that_never_announces_readiness_times_out() {
    let mut cfg = SidecarConfig { program: "sleep".into(), args: vec!["30".into()], cwd: None, env: vec![], ready_timeout: Duration::from_millis(300) };
    cfg.ready_timeout = Duration::from_millis(300);
    let err = Sidecar::spawn(cfg).await.err().expect("must fail");
    assert!(err.to_string().contains("did not become ready"), "{err}");
}

#[tokio::test]
async fn a_program_that_exits_immediately_is_reported() {
    let cfg = SidecarConfig { program: "true".into(), args: vec![], cwd: None, env: vec![], ready_timeout: Duration::from_secs(5) };
    let err = Sidecar::spawn(cfg).await.err().expect("must fail");
    assert!(err.to_string().contains("exited before"), "{err}");
}

// ---------------------------------------------------------------- job endpoints through the real sidecar, with fake stage scripts
mod jobs {
    use super::*;
    use std::fs;

    const RUN_ALL: &str = r#"
import json, os, sys, time
story, rd = sys.argv[1], sys.argv[2]
def ev(**k): print("@@pb " + json.dumps(k), flush=True)
text = open(story).read()
for st in ["transcribe", "plan", "assets"]:
    ev(stage=st, state="start")
    if "SLOW" in text and st == "assets": time.sleep(60)
    ev(stage=st, state="done", seconds=0.1)
open(os.path.join(rd, "book.pdf"), "w").write("pdf")
"#;

    fn setup() -> Option<(std::path::PathBuf, std::path::PathBuf, std::path::PathBuf, SidecarConfig)> {
        let py = python()?;
        let mut r = [0u8; 6];
        getrandom::fill(&mut r).unwrap();
        let tmp = std::env::temp_dir().join(format!("pb-e2e-{}", r.iter().map(|b| format!("{b:02x}")).collect::<String>()));
        let lib = tmp.join("books");
        let book = lib.join("one-1234abcd");
        let scripts = tmp.join("scripts");
        fs::create_dir_all(&book).unwrap();
        fs::create_dir_all(&scripts).unwrap();
        fs::write(book.join("book.json"), "{}").unwrap();
        fs::write(scripts.join("run_all.py"), RUN_ALL).unwrap();
        fs::write(scripts.join("regen.py"), "print('@@pb {\"stage\": \"render\", \"state\": \"done\"}')").unwrap();
        let mut cfg = SidecarConfig::python_module(py, "picturebook_sidecar");
        cfg.env = vec![("PICTUREBOOK_LIBRARY".into(), lib.display().to_string()), ("PICTUREBOOK_SCRIPTS".into(), scripts.display().to_string())];
        Some((tmp, lib, book, cfg))
    }

    async fn last_event(s: &Sidecar, id: &str) -> (String, serde_json::Value) {
        let mut last = (String::new(), serde_json::Value::Null);
        s.follow_events(id, |ev| last = (ev.event, serde_json::from_str(&ev.data).unwrap_or_default())).await.unwrap();
        last
    }

    #[tokio::test]
    async fn generate_runs_the_scripts_and_reports_done() {
        let Some((tmp, _lib, book, cfg)) = setup() else { return eprintln!("skipped: no venv") };
        let s = Sidecar::spawn(cfg).await.unwrap();
        fs::write(book.join("story.txt"), "A story.").unwrap();
        let id = s.start_generate(&book, "story.txt", "crayon", Some(4), false).await.unwrap();
        let (event, data) = last_event(&s, &id).await;
        assert_eq!(event, "done", "{data}");
        assert!(book.join("book.pdf").is_file());
        let id = s.start_regen(&book, &[2, 3]).await.unwrap();
        assert_eq!(last_event(&s, &id).await.0, "done");
        let _ = fs::remove_dir_all(tmp);
    }

    #[tokio::test]
    async fn refusals_carry_the_reason_and_cancel_stops_a_slow_job() {
        let Some((tmp, lib, book, cfg)) = setup() else { return eprintln!("skipped: no venv") };
        let s = Sidecar::spawn(cfg).await.unwrap();
        // a folder outside the library is refused, with the sidecar's own words
        let outside = tmp.join("elsewhere");
        fs::create_dir_all(&outside).unwrap();
        fs::write(outside.join("book.json"), "{}").unwrap();
        match s.start_regen(&outside, &[1]).await {
            Err(SidecarError::Refused(why)) => assert!(why.contains("directly inside the library"), "{why}"),
            other => panic!("expected a refusal, got {other:?}"),
        }
        assert!(matches!(s.start_generate(&book, "../x.txt", "crayon", None, false).await, Err(SidecarError::Status(422)) | Err(SidecarError::Refused(_))));
        // one job at a time
        fs::write(book.join("story.txt"), "SLOW story").unwrap();
        let id = s.start_generate(&book, "story.txt", "crayon", None, false).await.unwrap();
        match s.start_regen(&book, &[1]).await {
            Err(SidecarError::Refused(why)) => assert!(why.contains("another job is running"), "{why}"),
            other => panic!("expected 409, got {other:?}"),
        }
        assert!(s.cancel_job(&id).await.unwrap());
        assert_eq!(last_event(&s, &id).await.0, "cancelled");
        assert!(!s.cancel_job(&id).await.unwrap(), "nothing left to cancel");
        let _ = (lib, fs::remove_dir_all(tmp));
    }
}

#[tokio::test]
async fn first_run_check_reports_the_machine_through_the_real_sidecar() {
    let Some(py) = python() else { return eprintln!("skipped: no venv") };
    let mut cfg = SidecarConfig::python_module(py, "picturebook_sidecar");
    cfg.env = vec![("PICTUREBOOK_SCRIPTS".into(), concat!(env!("CARGO_MANIFEST_DIR"), "/../../scripts").into())];
    let s = Sidecar::spawn(cfg).await.unwrap();
    let d = s.diagnostics().await.unwrap();
    let ids: Vec<&str> = d.checks.iter().map(|c| c.id.as_str()).collect();
    for want in ["gpu", "torch", "llama", "gemma", "klein", "whisper", "ffmpeg", "microphone", "memory_cap", "disk", "ram"] {
        assert!(ids.contains(&want), "{want} missing from {ids:?}");
    }
    assert!(d.checks.iter().all(|c| ["ok", "warn", "missing"].contains(&c.status.as_str())));
    // the blockers listed are exactly the blocking checks
    let mut blocking: Vec<String> = d.checks.iter().filter(|c| c.blocking).map(|c| c.id.clone()).collect();
    let mut listed = d.blockers.clone();
    blocking.sort();
    listed.sort();
    assert_eq!(blocking, listed);
}

#[tokio::test]
async fn plan_edits_are_validated_by_the_real_sidecar_and_refusals_carry_the_reason() {
    let Some(py) = python() else { return eprintln!("skipped: no venv") };
    let mut r = [0u8; 6];
    getrandom::fill(&mut r).unwrap();
    let tmp = std::env::temp_dir().join(format!("pb-e2e-plan-{}", r.iter().map(|b| format!("{b:02x}")).collect::<String>()));
    let book = tmp.join("books").join("one-1234abcd");
    std::fs::create_dir_all(book.join("assets")).unwrap();
    std::fs::write(book.join("book.json"), "{}").unwrap();
    let ch = serde_json::json!({"name": "Mira", "species": "human", "age_group": "child", "build": "average", "height_relative": "average", "hair": "brown", "hair_style": "braids", "headwear": "None", "eyewear": "None",
        "face": "None", "skin_colour": "fair", "outfit": [{"item": "coat", "colour": "yellow", "detail": "None"}], "accessories": "None", "distinguishing_marks": "None", "inferred_fields": ["hair"]});
    std::fs::write(book.join("plan.json"), serde_json::json!({"title": "T", "characters": [ch], "environments": [], "pages": []}).to_string()).unwrap();
    std::fs::write(book.join("assets/ref_mira.png"), b"png").unwrap();
    let mut cfg = SidecarConfig::python_module(py, "picturebook_sidecar");
    cfg.env = vec![("PICTUREBOOK_LIBRARY".into(), tmp.join("books").display().to_string()), ("PICTUREBOOK_SCRIPTS".into(), concat!(env!("CARGO_MANIFEST_DIR"), "/../../scripts").into())];
    let s = Sidecar::spawn(cfg).await.unwrap();
    let opts = s.plan_options().await.unwrap();
    assert!(opts["hair_style"].as_array().unwrap().iter().any(|v| v == "ponytail"));
    let saved = s.save_plan_item(&book, "character", "Mira", &serde_json::json!({"hair": "black"})).await.unwrap();
    assert_eq!(saved["hair"], "black");
    assert!(!book.join("assets/ref_mira.png").exists(), "the old picture of the edited character is gone");
    match s.save_plan_item(&book, "character", "Mira", &serde_json::json!({"age_group": "wizard"})).await {
        Err(SidecarError::Refused(why)) => assert!(why.contains("age_group"), "{why}"),
        other => panic!("expected a refusal, got {other:?}"),
    }
    let _ = std::fs::remove_dir_all(tmp);
}

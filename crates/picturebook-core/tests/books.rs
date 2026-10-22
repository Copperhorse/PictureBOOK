//! Library behaviour on a real temporary directory, including what a user can do to the folders by hand.
use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use picturebook_core::books::*;

struct Tmp(PathBuf);
impl Tmp {
    fn new(name: &str) -> Self {
        let mut r = [0u8; 6];
        getrandom::fill(&mut r).unwrap();
        let p = std::env::temp_dir().join(format!("pb-test-{name}-{}", r.iter().map(|b| format!("{b:02x}")).collect::<String>()));
        fs::create_dir_all(&p).unwrap();
        Tmp(p)
    }
    fn books(&self) -> PathBuf {
        self.0.join("books")
    }
}
impl Drop for Tmp {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn none() -> HashSet<String> {
    HashSet::new()
}
fn books_of(repo: &BookRepository) -> Vec<BookSummary> {
    repo.scan(&none()).unwrap().into_iter().filter_map(|e| if let LibraryEntry::Book(b) = e { Some(*b) } else { None }).collect()
}
fn damaged_of(repo: &BookRepository) -> Vec<(String, String)> {
    repo.scan(&none()).unwrap().into_iter().filter_map(|e| if let LibraryEntry::Damaged { folder_name, reason, .. } = e { Some((folder_name, reason)) } else { None }).collect()
}
fn write_plan(dir: &Path, n: u32) {
    let pages: Vec<_> = (1..=n).map(|i| serde_json::json!({"index": i, "story_text": format!("Sentence {i}.")})).collect();
    fs::write(dir.join("plan.json"), serde_json::json!({"title": "T", "pages": pages}).to_string()).unwrap();
}
fn touch_png(dir: &Path, name: &str) {
    fs::create_dir_all(dir.join("pages")).unwrap();
    fs::write(dir.join("pages").join(name), b"png").unwrap();
}

#[test]
fn create_then_scan_finds_the_book_with_a_readable_folder_name() {
    let t = Tmp::new("create");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("The Little Fox & the Lantern!", "flat", Some(6), Source::Text).unwrap();
    let name = b.dir.file_name().unwrap().to_string_lossy().into_owned();
    assert!(name.starts_with("the-little-fox-the-lantern-"), "{name}");
    let found = books_of(&repo);
    assert_eq!(found.len(), 1);
    assert_eq!(found[0].meta.title, "The Little Fox & the Lantern!");
    assert_eq!((found[0].meta.style.as_str(), found[0].meta.pages, found[0].status), ("flat", Some(6), BookStatus::Draft));
    // two books with the same title get different folders
    let b2 = repo.create("The Little Fox & the Lantern!", "crayon", None, Source::Audio).unwrap();
    assert_ne!(b.dir, b2.dir);
    assert_eq!(books_of(&repo).len(), 2);
}

#[test]
fn an_empty_title_gets_a_name_and_no_stray_temp_file_is_left() {
    let t = Tmp::new("empty");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("   ", "crayon", None, Source::Text).unwrap();
    assert_eq!(b.meta.title, "Untitled book");
    repo.update(&b.meta.id, Some("New title"), Some(BookStatus::Review)).unwrap();
    let files: Vec<_> = fs::read_dir(&b.dir).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).collect();
    assert_eq!(files, vec!["book.json"], "{files:?}");
}

#[test]
fn renaming_the_folder_by_hand_does_not_lose_the_book() {
    let t = Tmp::new("rename");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Mira", "crayon", None, Source::Text).unwrap();
    write_plan(&b.dir, 3);
    touch_png(&b.dir, "page_01.png");
    let renamed = t.books().join("my favourite story");
    fs::rename(&b.dir, &renamed).unwrap();
    // same id, new path; every path is recomputed from the fresh scan
    assert_eq!(repo.dir_of(&b.meta.id).unwrap(), renamed);
    let d = repo.detail(&b.meta.id, false).unwrap();
    assert_eq!(d.dir, renamed);
    assert_eq!(d.pages[0].image.as_deref(), Some(renamed.join("pages/page_01.png").as_path()));
    assert_eq!(books_of(&repo)[0].cover.as_deref(), Some(renamed.join("pages/page_01.png").as_path()));
    // status updates and delete work on the renamed folder
    repo.update(&b.meta.id, None, Some(BookStatus::Review)).unwrap();
    assert!(renamed.join("book.json").is_file());
    repo.delete(&b.meta.id).unwrap();
    assert!(!renamed.exists() && books_of(&repo).is_empty());
}

#[test]
fn moving_a_folder_out_of_the_library_removes_it_and_moving_it_back_restores_it() {
    let t = Tmp::new("move");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Boat", "crayon", None, Source::Text).unwrap();
    let outside = t.0.join("elsewhere");
    fs::rename(&b.dir, &outside).unwrap();
    assert!(books_of(&repo).is_empty());
    assert!(matches!(repo.dir_of(&b.meta.id), Err(BookError::NotFound(_))));
    fs::rename(&outside, t.books().join("back")).unwrap();
    assert_eq!(books_of(&repo)[0].meta.id, b.meta.id);
}

#[test]
fn damaged_folders_are_listed_and_do_not_hide_the_good_books() {
    let t = Tmp::new("damaged");
    let repo = BookRepository::new(t.books()).unwrap();
    let good = repo.create("Good", "crayon", None, Source::Text).unwrap();
    fs::create_dir(t.books().join("no-json")).unwrap();
    let corrupt = t.books().join("corrupt");
    fs::create_dir(&corrupt).unwrap();
    fs::write(corrupt.join("book.json"), "{ this is not json").unwrap();
    let badid = t.books().join("badid");
    fs::create_dir(&badid).unwrap();
    fs::write(badid.join("book.json"), r#"{"id":"../../etc","title":"x","status":"draft","source":"text","created_at":1,"updated_at":1}"#).unwrap();
    fs::write(t.books().join("stray-file.txt"), "x").unwrap(); // a file, not a folder: ignored
    fs::create_dir(t.books().join(".hidden")).unwrap(); // hidden folders are ignored
    assert_eq!(books_of(&repo).len(), 1);
    let d = damaged_of(&repo);
    let names: Vec<_> = d.iter().map(|(n, _)| n.as_str()).collect();
    assert_eq!(names, vec!["badid", "corrupt", "no-json"]);
    assert!(d[1].1.contains("damaged") && d[2].1.contains("missing") && d[0].1.contains("invalid id"), "{d:?}");
    assert_eq!(books_of(&repo)[0].meta.id, good.meta.id);
}

#[test]
fn a_copied_book_folder_is_reported_once_as_a_duplicate() {
    let t = Tmp::new("dup");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Original", "crayon", None, Source::Text).unwrap();
    let copy = t.books().join("zz-copy");
    fs::create_dir(&copy).unwrap();
    fs::copy(b.dir.join("book.json"), copy.join("book.json")).unwrap();
    assert_eq!(books_of(&repo).len(), 1);
    let d = damaged_of(&repo);
    assert_eq!(d.len(), 1);
    assert!(d[0].1.contains("same id"), "{d:?}");
    // the damaged copy can be deleted by name; the real book cannot be deleted that way
    assert!(repo.delete_damaged(&b.dir.file_name().unwrap().to_string_lossy()).is_err());
    repo.delete_damaged("zz-copy").unwrap();
    assert!(damaged_of(&repo).is_empty() && b.dir.exists());
}

#[test]
fn detail_reports_missing_pictures_versions_hints_and_redraw_counts() {
    let t = Tmp::new("detail");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Story", "crayon", None, Source::Text).unwrap();
    repo.update(&b.meta.id, None, Some(BookStatus::Review)).unwrap();
    write_plan(&b.dir, 3);
    touch_png(&b.dir, "page_01.png");
    touch_png(&b.dir, "page_03.png");
    touch_png(&b.dir, "page_03_v2.png");
    touch_png(&b.dir, "page_03_v1.png");
    touch_png(&b.dir, "page_03_v10.png");
    touch_png(&b.dir, "page_03_discarded_a1.png"); // not a version
    fs::write(b.dir.join("regen_log.json"), r#"{"3":{"attempt":3,"archive":["page_03_v1.png"]}}"#).unwrap();
    fs::create_dir_all(b.dir.join("checks")).unwrap();
    fs::write(b.dir.join("checks/report.json"), r#"{"1":{"hints":["Mira may be floating"],"redrawn":0,"checked":true},"2":{"hints":[],"redrawn":0},"3":{"hints":[],"redrawn":3,"checked":false}}"#).unwrap();
    let d = repo.detail(&b.meta.id, false).unwrap();
    assert_eq!(d.pages.len(), 3);
    assert!(d.pages[1].image.is_none(), "page 2 has no picture");
    assert!(d.problems.iter().any(|p| p.contains("page 2")), "{:?}", d.problems);
    assert_eq!(d.pages[0].hints, vec!["Mira may be floating"]);
    assert!(d.pages[0].checked && d.pages[1].checked, "a report without the flag counts as checked");
    assert!(!d.pages[2].checked, "notes made for an earlier drawing are flagged");
    assert_eq!(d.pages[2].redrawn, 3);
    let v: Vec<_> = d.pages[2].versions.iter().map(|p| p.file_name().unwrap().to_string_lossy().into_owned()).collect();
    assert_eq!(v, vec!["page_03_v1.png", "page_03_v2.png", "page_03_v10.png"], "numeric order, not text order");
    assert_eq!(d.pages[1].text, "Sentence 2.");
    assert!(d.pdf.is_none());
    fs::write(b.dir.join("book.pdf"), b"pdf").unwrap();
    assert!(repo.detail(&b.meta.id, false).unwrap().pdf.is_some());
}

#[test]
fn a_book_without_a_usable_plan_still_opens() {
    let t = Tmp::new("noplan");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Fresh", "crayon", None, Source::Text).unwrap();
    assert!(repo.detail(&b.meta.id, false).unwrap().pages.is_empty());
    repo.update(&b.meta.id, None, Some(BookStatus::Review)).unwrap();
    fs::write(b.dir.join("plan.json"), "garbage").unwrap();
    let d = repo.detail(&b.meta.id, false).unwrap();
    assert!(d.pages.is_empty() && d.problems.iter().any(|p| p.contains("plan.json")), "{:?}", d.problems);
}

#[test]
fn a_generating_book_without_a_running_job_is_shown_as_interrupted() {
    let t = Tmp::new("interrupted");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Long", "crayon", None, Source::Audio).unwrap();
    repo.update(&b.meta.id, None, Some(BookStatus::Generating)).unwrap();
    assert_eq!(books_of(&repo)[0].status, BookStatus::Interrupted);
    let mut running = HashSet::new();
    running.insert(b.meta.id.clone());
    match &repo.scan(&running).unwrap()[0] {
        LibraryEntry::Book(s) => assert_eq!(s.status, BookStatus::Generating),
        _ => panic!(),
    }
    assert_eq!(repo.detail(&b.meta.id, true).unwrap().status, BookStatus::Generating);
    assert_eq!(repo.detail(&b.meta.id, false).unwrap().status, BookStatus::Interrupted);
    assert_eq!(effective_status(BookStatus::Review, false), BookStatus::Review);
}

#[test]
fn unknown_fields_written_by_a_newer_version_or_the_user_survive_an_update() {
    let t = Tmp::new("extra");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Keep", "crayon", None, Source::Text).unwrap();
    let mut v: serde_json::Value = serde_json::from_str(&fs::read_to_string(b.dir.join("book.json")).unwrap()).unwrap();
    v["notes"] = serde_json::json!("for Grandma");
    fs::write(b.dir.join("book.json"), v.to_string()).unwrap();
    repo.update(&b.meta.id, Some("Renamed"), None).unwrap();
    let after: serde_json::Value = serde_json::from_str(&fs::read_to_string(b.dir.join("book.json")).unwrap()).unwrap();
    assert_eq!((after["notes"].as_str(), after["title"].as_str()), (Some("for Grandma"), Some("Renamed")));
}

#[test]
fn delete_refuses_bad_ids_symlinks_and_anything_that_is_not_a_book_folder() {
    let t = Tmp::new("delete");
    let repo = BookRepository::new(t.books()).unwrap();
    let victim = t.0.join("important");
    fs::create_dir(&victim).unwrap();
    fs::write(victim.join("keep.txt"), "x").unwrap();
    // ids that are paths or have the wrong shape never reach the file system
    for bad in ["../important", "..", "", "ABCDEF0123456789ABCDEF0123456789", "short"] {
        assert!(matches!(repo.delete(bad), Err(BookError::BadId(_))), "{bad}");
    }
    // a symlink inside the library is ignored by scans, so it can neither be listed nor deleted
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(&victim, t.books().join("link")).unwrap();
        assert!(books_of(&repo).is_empty() && damaged_of(&repo).is_empty());
        assert!(repo.delete_damaged("link").is_err());
    }
    for bad in ["../important", "a/b", "..", ".", ".hidden", ""] {
        assert!(repo.delete_damaged(bad).is_err(), "{bad}");
    }
    assert!(victim.join("keep.txt").exists());
    assert!(matches!(repo.delete("0123456789abcdef0123456789abcdef"), Err(BookError::NotFound(_))));
}

#[test]
fn slug_is_ascii_short_and_never_empty() {
    assert_eq!(slug("Goldilocks and the Three Bears"), "goldilocks-and-the-three-bears");
    assert_eq!(slug("  ¡Hola, señor!  "), "hola-se-or");
    assert_eq!(slug("日本語"), "book");
    assert!(slug(&"x".repeat(200)).len() <= 40);
}

#[test]
fn newest_book_first() {
    let t = Tmp::new("order");
    let repo = BookRepository::new(t.books()).unwrap();
    let a = repo.create("A", "crayon", None, Source::Text).unwrap();
    let b = repo.create("B", "crayon", None, Source::Text).unwrap();
    // make A newer by hand-editing its timestamp, as a user or another tool might
    let mut v: serde_json::Value = serde_json::from_str(&fs::read_to_string(a.dir.join("book.json")).unwrap()).unwrap();
    v["updated_at"] = serde_json::json!(b.meta.updated_at + 100);
    fs::write(a.dir.join("book.json"), v.to_string()).unwrap();
    let titles: Vec<_> = books_of(&repo).into_iter().map(|b| b.meta.title).collect();
    assert_eq!(titles, vec!["A", "B"]);
}

#[test]
fn extra_flags_can_be_stored_but_regular_fields_cannot_be_overwritten_that_way() {
    let t = Tmp::new("setextra");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Flag", "crayon", None, Source::Text).unwrap();
    repo.set_extra(&b.meta.id, "title_auto", serde_json::json!(true)).unwrap();
    assert_eq!(repo.detail(&b.meta.id, false).unwrap().meta.extra["title_auto"], serde_json::json!(true));
    for key in ["id", "status", "title"] {
        assert!(repo.set_extra(&b.meta.id, key, serde_json::json!("x")).is_err(), "{key}");
    }
    assert_eq!(books_of(&repo)[0].meta.title, "Flag");
}

// ---------------------------------------------------------------- the approval screen's view of a plan
fn plan_json(dir: &Path) {
    let ch = |n: &str| serde_json::json!({"name": n, "species": "bear", "inferred_fields": ["hair", "build"]});
    let plan = serde_json::json!({"title": "The Bears", "characters": [ch("Papa Bear"), ch("Isla's Mirror")], "environments": [{"name": "Quiet Blue Lake", "inferred_fields": []}], "pages": []});
    fs::write(dir.join("plan.json"), plan.to_string()).unwrap();
}

#[test]
fn slug_names_match_the_python_side() {
    // the same cases are asserted in scripts/tests/test_rules.py (test_slug_examples_shared_with_the_rust_side) and sidecar/tests
    for (name, want) in [("Papa Bear", "papa_bear"), ("  Isla's Mirror!! ", "isla_s_mirror"), ("Seventh Prince", "seventh_prince"), ("Éclair", "clair"), ("日本", ""), ("a--b__c", "a_b_c"), ("Quiet Blue Lake", "quiet_blue_lake")] {
        assert_eq!(slug_name(name), want, "{name}");
    }
}

#[test]
fn the_plan_summary_lists_characters_places_pictures_and_guesses() {
    let t = Tmp::new("plansummary");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Bears", "crayon", None, Source::Text).unwrap();
    assert!(repo.plan_summary(&b.meta.id).is_err(), "no plan yet");
    assert!(!repo.detail(&b.meta.id, false).unwrap().has_plan);
    plan_json(&b.dir);
    assert!(repo.detail(&b.meta.id, false).unwrap().has_plan);
    let s = repo.plan_summary(&b.meta.id).unwrap();
    assert_eq!((s.title.as_str(), s.characters.len(), s.places.len()), ("The Bears", 2, 1));
    assert!(s.editable && !s.all_drawn && s.characters[0].image.is_none() && s.characters[0].guessed == vec!["hair", "build"]);
    fs::create_dir_all(b.dir.join("assets")).unwrap();
    for f in ["ref_papa_bear.png", "ref_isla_s_mirror.png", "plate_quiet_blue_lake.png", "ref_papa_bear_c1.png"] {
        fs::write(b.dir.join("assets").join(f), b"png").unwrap();
    }
    fs::write(b.dir.join("assets/draw_log.json"), r#"{"Papa Bear": 2}"#).unwrap();
    let s = repo.plan_summary(&b.meta.id).unwrap();
    assert!(s.all_drawn, "every item has its chosen picture; candidates do not count on their own");
    assert_eq!((s.characters[0].draws, s.characters[1].draws), (2, 0));
    assert_eq!(s.characters[0].image.as_deref(), Some(b.dir.join("assets/ref_papa_bear.png").as_path()));
    // pages drawn: the plan can no longer be edited
    touch_png(&b.dir, "page_01.png");
    assert!(!repo.plan_summary(&b.meta.id).unwrap().editable);
}

#[test]
fn a_candidate_alone_is_not_a_finished_picture_and_a_broken_plan_is_an_error_not_a_crash() {
    let t = Tmp::new("plansummary2");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("Bears", "crayon", None, Source::Text).unwrap();
    plan_json(&b.dir);
    fs::create_dir_all(b.dir.join("assets")).unwrap();
    fs::write(b.dir.join("assets/ref_papa_bear_c1.png"), b"png").unwrap();
    let s = repo.plan_summary(&b.meta.id).unwrap();
    assert!(s.characters[0].image.is_none() && !s.all_drawn);
    fs::write(b.dir.join("plan.json"), "{ nope").unwrap();
    assert!(repo.plan_summary(&b.meta.id).is_err());
    assert!(!repo.detail(&b.meta.id, false).unwrap().has_plan);
}

#[test]
fn a_planned_book_is_listed_as_planned_and_survives_a_missing_status_roundtrip() {
    let t = Tmp::new("planned");
    let repo = BookRepository::new(t.books()).unwrap();
    let b = repo.create("P", "crayon", None, Source::Text).unwrap();
    repo.update(&b.meta.id, None, Some(BookStatus::Planned)).unwrap();
    assert_eq!(books_of(&repo)[0].status, BookStatus::Planned);
    assert!(fs::read_to_string(b.dir.join("book.json")).unwrap().contains("\"planned\""));
}

//! What a finished job means for the book that owns it (pure rules, tested without a GUI).

use crate::books::BookStatus;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobKind {
    /// A whole book from a story or audio file in one go.
    Generate,
    /// Step 1 of the approval flow: read the story and plan characters, places and pages.
    Plan,
    /// Step 2: draw the characters and places (or just one of them again).
    Assets,
    /// Step 3: draw the pages and make the PDF.
    Pages,
    /// Redraw pages, or put an earlier picture back.
    Redraw,
}

/// The status to store in `book.json` when a job emits its last event (`done`, `error` or `cancelled`), or `None` to leave it as it is.
/// A redraw never changes the status. A step that fails after the plan exists leaves the book in `planned`, where the parent can try again.
pub fn status_after(kind: JobKind, final_event: &str) -> Option<BookStatus> {
    match (kind, final_event) {
        (JobKind::Generate, "done") => Some(BookStatus::Review),
        (JobKind::Generate, "cancelled") => Some(BookStatus::Draft),
        (JobKind::Generate, _) => Some(BookStatus::Failed),
        (JobKind::Plan, "done") => Some(BookStatus::Planned),
        (JobKind::Plan, "cancelled") => Some(BookStatus::Draft),
        (JobKind::Plan, _) => Some(BookStatus::Failed),
        (JobKind::Assets, _) => Some(BookStatus::Planned),
        (JobKind::Pages, "done") => Some(BookStatus::Review),
        (JobKind::Pages, _) => Some(BookStatus::Planned),
        (JobKind::Redraw, _) => None,
    }
}

/// Is this the last event of a job?
pub fn is_final(event: &str) -> bool {
    matches!(event, "done" | "error" | "cancelled")
}

#[cfg(test)]
mod tests {
    use super::*;
    use BookStatus::*;

    #[test]
    fn one_go_generation_outcomes() {
        assert_eq!(status_after(JobKind::Generate, "done"), Some(Review));
        assert_eq!(status_after(JobKind::Generate, "error"), Some(Failed));
        assert_eq!(status_after(JobKind::Generate, "cancelled"), Some(Draft));
        assert_eq!(status_after(JobKind::Generate, "something-else"), Some(Failed)); // an unknown ending is a failure, never a success
    }

    #[test]
    fn the_approval_flow_moves_a_book_draft_planned_review() {
        assert_eq!(status_after(JobKind::Plan, "done"), Some(Planned));
        assert_eq!(status_after(JobKind::Plan, "error"), Some(Failed));
        assert_eq!(status_after(JobKind::Plan, "cancelled"), Some(Draft));
        for e in ["done", "error", "cancelled", "weird"] {
            assert_eq!(status_after(JobKind::Assets, e), Some(Planned), "drawing characters never ends anywhere but planned: {e}");
        }
        assert_eq!(status_after(JobKind::Pages, "done"), Some(Review));
        for e in ["error", "cancelled", "weird"] {
            assert_eq!(status_after(JobKind::Pages, e), Some(Planned), "a failed page stage lets the parent try again from the characters screen: {e}");
        }
    }

    #[test]
    fn a_redraw_never_changes_the_status() {
        for e in ["done", "error", "cancelled"] {
            assert_eq!(status_after(JobKind::Redraw, e), None);
        }
    }

    #[test]
    fn only_three_events_end_a_job() {
        assert!(is_final("done") && is_final("error") && is_final("cancelled"));
        assert!(!is_final("progress") && !is_final(""));
    }
}

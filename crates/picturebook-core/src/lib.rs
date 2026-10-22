//! PictureBOOK core logic that does not depend on the UI shell.
//!
//! * [`audio`] checks recordings and converts imported audio files (strict WAV validation, ffmpeg with a time limit).
//! * [`books`] is the book library: the folders are the only source of truth (no path index that could go stale).
//! * [`sidecar`] spawns and supervises the Python inference sidecar (random loopback port, per-launch bearer token,
//!   stdin kept open as a parent-death signal) and talks to it over HTTP + Server-Sent Events.
//! * [`sse`] is a small incremental Server-Sent-Events parser.

pub mod audio;
pub mod books;
pub mod jobs;
pub mod settings;
pub mod sidecar;
pub mod sse;

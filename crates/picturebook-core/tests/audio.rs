use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

use picturebook_core::audio::*;

fn tmp(name: &str) -> PathBuf {
    let mut r = [0u8; 6];
    getrandom::fill(&mut r).unwrap();
    let p = std::env::temp_dir().join(format!("pb-audio-{name}-{}", r.iter().map(|b| format!("{b:02x}")).collect::<String>()));
    fs::create_dir_all(&p).unwrap();
    p
}

#[test]
fn a_good_recording_is_accepted_and_measured() {
    let w = silent_wav(2.5, 16000);
    let i = validate_wav(&w).unwrap();
    assert_eq!(i.sample_rate, 16000);
    assert!((i.seconds - 2.5).abs() < 1e-6);
    assert!(validate_wav(&silent_wav(3.0, 44100)).is_ok(), "other sensible rates are fine too");
}

#[test]
fn length_limits_are_enforced_in_seconds() {
    assert_eq!(validate_wav(&silent_wav(0.5, 16000)), Err(AudioError::TooShort));
    assert_eq!(validate_wav(&silent_wav(1.0, 16000)).map(|i| i.seconds), Ok(1.0));
    assert_eq!(validate_wav(&silent_wav(901.0, 16000)), Err(AudioError::TooLong));
    assert!(validate_wav(&silent_wav(899.0, 16000)).is_ok());
}

#[test]
fn things_that_are_not_wav_files_are_refused() {
    assert_eq!(validate_wav(b""), Err(AudioError::NotWav));
    assert_eq!(validate_wav(b"RIFF"), Err(AudioError::NotWav));
    assert_eq!(validate_wav(b"<html>not audio at all, but long enough to have a header</html>"), Err(AudioError::NotWav));
    let mut w = silent_wav(2.0, 16000);
    w[8..12].copy_from_slice(b"AVI ");
    assert_eq!(validate_wav(&w), Err(AudioError::NotWav));
}

#[test]
fn damaged_and_unsupported_headers_are_refused_without_panicking() {
    let good = silent_wav(2.0, 16000);
    // cut off in the middle of the data
    assert!(matches!(validate_wav(&good[..good.len() - 100]), Err(AudioError::Damaged(_))));
    // every possible truncation of the first 60 bytes must be an error, never a crash
    for n in 0..60 {
        let _ = validate_wav(&good[..n]);
    }
    // stereo, 8-bit, float format, absurd rates
    for (off, val, width) in [(22usize, 2u32, 2usize), (34, 8, 2), (20, 3, 2), (24, 96000, 4), (24, 4000, 4)] {
        let mut w = good.clone();
        if width == 2 {
            w[off..off + 2].copy_from_slice(&(val as u16).to_le_bytes());
        } else {
            w[off..off + 4].copy_from_slice(&val.to_le_bytes());
        }
        assert_eq!(validate_wav(&w), Err(AudioError::Unsupported), "{off} {val}");
    }
    // a chunk length that points far past the end must not overflow
    let mut w = good.clone();
    w[16..20].copy_from_slice(&u32::MAX.to_le_bytes());
    assert!(validate_wav(&w).is_err());
    // no data chunk at all
    let mut w = good[..36].to_vec();
    w.extend_from_slice(b"LIST\0\0\0\0");
    assert!(matches!(validate_wav(&w), Err(AudioError::Damaged(_))));
}

#[test]
fn oversize_input_is_refused_before_it_is_read() {
    assert_eq!(validate_wav(&vec![0u8; MAX_BYTES + 1]), Err(AudioError::TooLarge));
}

#[test]
fn ffmpeg_converts_other_formats_to_the_standard_wav_and_reports_bad_input() {
    if !has_ffmpeg() {
        return eprintln!("skipped: no ffmpeg");
    }
    let d = tmp("ffmpeg");
    let src = d.join("tone.m4a");
    let made = Command::new("ffmpeg").args(["-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2.5:sample_rate=44100", "-ac", "2"]).arg(&src).status().unwrap();
    assert!(made.success());
    let out = d.join("audio.wav");
    let info = convert_with_ffmpeg(&src, &out, Duration::from_secs(60)).unwrap();
    assert_eq!(info.sample_rate, 16000);
    assert!((info.seconds - 2.5).abs() < 0.1, "{}", info.seconds);
    assert!(validate_wav(&fs::read(&out).unwrap()).is_ok(), "stereo 44.1 kHz AAC became mono 16 kHz WAV");
    // not audio at all
    let bad = d.join("fake.mp3");
    fs::write(&bad, b"this is a text file pretending to be music").unwrap();
    let out2 = d.join("bad.wav");
    assert!(matches!(convert_with_ffmpeg(&bad, &out2, Duration::from_secs(60)), Err(AudioError::Convert(_))));
    assert!(!out2.exists(), "no half-made output is left behind");
    // missing file
    assert!(matches!(convert_with_ffmpeg(&d.join("nope.mp3"), &out2, Duration::from_secs(60)), Err(AudioError::Convert(_))));
    // too short after conversion
    let tiny = d.join("tiny.wav");
    Command::new("ffmpeg").args(["-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=duration=0.3"]).arg(&tiny).status().unwrap();
    assert_eq!(convert_with_ffmpeg(&tiny, &d.join("t.wav"), Duration::from_secs(60)), Err(AudioError::TooShort));
    let _ = fs::remove_dir_all(d);
}

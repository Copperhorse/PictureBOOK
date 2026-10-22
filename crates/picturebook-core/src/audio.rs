//! Audio that comes into a book: recordings made in the app window and imported files.
//! Everything that reaches the speech stage is a mono 16-bit WAV that this module has looked at first.

use std::io;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

pub const MAX_SECONDS: f64 = 15.0 * 60.0;
pub const MIN_SECONDS: f64 = 1.0;
/// 15 minutes of 16 kHz mono 16-bit audio is 28.8 MB; allow room for other common rates, never more than this.
pub const MAX_BYTES: usize = 64 * 1024 * 1024;

#[derive(Debug, thiserror::Error, PartialEq)]
pub enum AudioError {
    #[error("that is not a WAV recording")]
    NotWav,
    #[error("the recording is damaged ({0})")]
    Damaged(&'static str),
    #[error("only mono 16-bit recordings are accepted")]
    Unsupported,
    #[error("the recording is too short (at least one second is needed)")]
    TooShort,
    #[error("the recording is too long (at most 15 minutes)")]
    TooLong,
    #[error("the recording is too large")]
    TooLarge,
    #[error("ffmpeg could not convert the file: {0}")]
    Convert(String),
    #[error("ffmpeg was not found, so this kind of audio file cannot be converted (install ffmpeg or use a WAV file)")]
    NoFfmpeg,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct WavInfo {
    pub sample_rate: u32,
    pub seconds: f64,
}

fn u16le(b: &[u8], o: usize) -> u16 {
    u16::from_le_bytes([b[o], b[o + 1]])
}
fn u32le(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}

/// Check a WAV file's header and sizes. Accepts exactly what the app's recorder writes (and any mono 16-bit PCM WAV of a sensible rate).
pub fn validate_wav(bytes: &[u8]) -> Result<WavInfo, AudioError> {
    if bytes.len() > MAX_BYTES {
        return Err(AudioError::TooLarge);
    }
    if bytes.len() < 12 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err(AudioError::NotWav);
    }
    // walk the chunks: a 'fmt ' chunk, then a 'data' chunk
    let (mut o, mut fmt, mut data_len) = (12usize, None, None);
    while o + 8 <= bytes.len() {
        let id = &bytes[o..o + 4];
        let len = u32le(bytes, o + 4) as usize;
        let body = o + 8;
        if id == b"fmt " {
            if len < 16 || body + 16 > bytes.len() {
                return Err(AudioError::Damaged("format chunk"));
            }
            fmt = Some((u16le(bytes, body), u16le(bytes, body + 2), u32le(bytes, body + 4), u16le(bytes, body + 14)));
        } else if id == b"data" {
            if body + len > bytes.len() {
                return Err(AudioError::Damaged("the data is cut off"));
            }
            data_len = Some(len);
            break;
        }
        o = body.checked_add(len + (len & 1)).ok_or(AudioError::Damaged("chunk size"))?;
    }
    let (format, channels, rate, bits) = fmt.ok_or(AudioError::Damaged("no format chunk"))?;
    let data_len = data_len.ok_or(AudioError::Damaged("no audio data"))?;
    if format != 1 || channels != 1 || bits != 16 {
        return Err(AudioError::Unsupported);
    }
    if !(8000..=48000).contains(&rate) {
        return Err(AudioError::Unsupported);
    }
    let seconds = data_len as f64 / 2.0 / rate as f64;
    if seconds < MIN_SECONDS {
        return Err(AudioError::TooShort);
    }
    if seconds > MAX_SECONDS {
        return Err(AudioError::TooLong);
    }
    Ok(WavInfo { sample_rate: rate, seconds })
}

pub fn has_ffmpeg() -> bool {
    Command::new("ffmpeg").arg("-version").stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null()).status().map(|s| s.success()).unwrap_or(false)
}

/// Convert any audio file ffmpeg understands to a 16 kHz mono 16-bit WAV (cut at 15 minutes), and validate the result.
/// The input is the user's own file, but it is still treated as untrusted: no shell, a time limit, a size check afterwards.
pub fn convert_with_ffmpeg(input: &Path, output: &Path, timeout: Duration) -> Result<WavInfo, AudioError> {
    let mut child = match Command::new("ffmpeg")
        .args(["-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i"])
        .arg(input)
        .args(["-vn", "-t", "900", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"])
        .arg(output)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) if e.kind() == io::ErrorKind::NotFound => return Err(AudioError::NoFfmpeg),
        Err(e) => return Err(AudioError::Convert(e.to_string())),
    };
    let start = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(s)) => break s,
            Ok(None) if start.elapsed() > timeout => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = std::fs::remove_file(output);
                return Err(AudioError::Convert("it took too long".into()));
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(50)),
            Err(e) => return Err(AudioError::Convert(e.to_string())),
        }
    };
    if !status.success() {
        let mut msg = String::new();
        if let Some(mut e) = child.stderr.take() {
            let _ = io::Read::read_to_string(&mut e, &mut msg);
        }
        let _ = std::fs::remove_file(output);
        return Err(AudioError::Convert(msg.lines().last().unwrap_or("unknown error").to_string()));
    }
    let bytes = std::fs::read(output).map_err(|e| AudioError::Convert(e.to_string()))?;
    validate_wav(&bytes).inspect_err(|_| {
        let _ = std::fs::remove_file(output);
    })
}

/// A WAV with `seconds` of silence, for tests and for callers that need a known-good file.
pub fn silent_wav(seconds: f64, rate: u32) -> Vec<u8> {
    let n = (seconds * rate as f64) as usize;
    let mut v = Vec::with_capacity(44 + n * 2);
    v.extend_from_slice(b"RIFF");
    v.extend_from_slice(&(36 + n as u32 * 2).to_le_bytes());
    v.extend_from_slice(b"WAVEfmt ");
    v.extend_from_slice(&16u32.to_le_bytes());
    v.extend_from_slice(&1u16.to_le_bytes());
    v.extend_from_slice(&1u16.to_le_bytes());
    v.extend_from_slice(&rate.to_le_bytes());
    v.extend_from_slice(&(rate * 2).to_le_bytes());
    v.extend_from_slice(&2u16.to_le_bytes());
    v.extend_from_slice(&16u16.to_le_bytes());
    v.extend_from_slice(b"data");
    v.extend_from_slice(&(n as u32 * 2).to_le_bytes());
    v.resize(44 + n * 2, 0);
    v
}

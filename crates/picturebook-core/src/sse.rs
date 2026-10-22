//! Incremental Server-Sent-Events parser. Feed arbitrary byte chunks; complete events come out.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SseEvent {
    pub event: String,
    pub data: String,
}

#[derive(Default)]
pub struct SseParser {
    buf: Vec<u8>,
}

impl SseParser {
    pub fn new() -> Self {
        Self::default()
    }

    /// Append bytes and return every event that is now complete (terminated by a blank line).
    pub fn push(&mut self, chunk: &[u8]) -> Vec<SseEvent> {
        self.buf.extend_from_slice(chunk);
        let mut out = Vec::new();
        while let Some((end, sep_len)) = find_blank_line(&self.buf) {
            let block: Vec<u8> = self.buf.drain(..end + sep_len).collect();
            if let Some(ev) = parse_block(&block[..end]) {
                out.push(ev);
            }
        }
        out
    }
}

/// Position of the first blank line (`\n\n` or `\r\n\r\n`) and its length.
fn find_blank_line(buf: &[u8]) -> Option<(usize, usize)> {
    let mut i = 0;
    while i < buf.len() {
        if buf[i..].starts_with(b"\n\n") {
            return Some((i, 2));
        }
        if buf[i..].starts_with(b"\r\n\r\n") {
            return Some((i, 4));
        }
        i += 1;
    }
    None
}

fn parse_block(block: &[u8]) -> Option<SseEvent> {
    let text = String::from_utf8_lossy(block);
    let mut event = String::from("message");
    let mut data: Vec<&str> = Vec::new();
    for line in text.lines() {
        if line.starts_with(':') || line.is_empty() {
            continue; // comment / keep-alive
        }
        let (field, value) = match line.split_once(':') {
            Some((f, v)) => (f, v.strip_prefix(' ').unwrap_or(v)),
            None => (line, ""),
        };
        match field {
            "event" => event = value.to_string(),
            "data" => data.push(value),
            _ => {}
        }
    }
    if data.is_empty() && event == "message" {
        return None;
    }
    Some(SseEvent { event, data: data.join("\n") })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_simple_event() {
        let mut p = SseParser::new();
        let evs = p.push(b"event: progress\ndata: {\"fraction\": 0.5}\n\n");
        assert_eq!(evs, vec![SseEvent { event: "progress".into(), data: "{\"fraction\": 0.5}".into() }]);
    }

    #[test]
    fn handles_chunks_split_anywhere() {
        let whole = b"event: a\ndata: 1\n\nevent: b\ndata: 2\n\n";
        for cut in 1..whole.len() {
            let mut p = SseParser::new();
            let mut evs = p.push(&whole[..cut]);
            evs.extend(p.push(&whole[cut..]));
            assert_eq!(evs.len(), 2, "cut at {cut}");
            assert_eq!((evs[0].event.as_str(), evs[1].data.as_str()), ("a", "2"));
        }
    }

    #[test]
    fn supports_crlf_comments_and_multiline_data() {
        let mut p = SseParser::new();
        let evs = p.push(b": keep-alive\r\n\r\nevent: x\r\ndata: line1\r\ndata: line2\r\n\r\n");
        assert_eq!(evs, vec![SseEvent { event: "x".into(), data: "line1\nline2".into() }]);
    }

    #[test]
    fn default_event_name_and_incomplete_tail_is_kept() {
        let mut p = SseParser::new();
        assert_eq!(p.push(b"data: hi\n\n")[0].event, "message");
        assert!(p.push(b"event: partial\ndata: no terminator").is_empty());
        assert_eq!(p.push(b"\n\n")[0].data, "no terminator");
    }
}

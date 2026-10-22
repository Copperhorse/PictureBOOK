import { convertFileSrc } from "@tauri-apps/api/core";

/**
 * Pictures live in the library folder and are read through Tauri's asset protocol. The webview's <img> cannot load that
 * scheme everywhere (it failed in WebKitGTK while fetch worked), so a picture is fetched, optionally scaled down, and shown
 * from a local blob URL. The cache is keyed by path + version, so a redrawn page (new version) is never served stale.
 */
const cache = new Map<string, Promise<string>>();       // key -> blob URL, in insertion order (oldest first)
const MAX_ENTRIES = 160;

function evict() {
  while (cache.size > MAX_ENTRIES) {
    const [oldest] = cache.keys();
    const p = cache.get(oldest)!;
    cache.delete(oldest);
    p.then((u) => URL.revokeObjectURL(u)).catch(() => {});
  }
}

async function scaled(blob: Blob, maxSide: number): Promise<Blob> {
  const bm = await createImageBitmap(blob);
  const k = Math.min(1, maxSide / Math.max(bm.width, bm.height));
  if (k >= 1) { bm.close(); return blob; }
  const c = document.createElement("canvas");
  c.width = Math.round(bm.width * k); c.height = Math.round(bm.height * k);
  c.getContext("2d")!.drawImage(bm, 0, 0, c.width, c.height);
  bm.close();
  return await new Promise<Blob>((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error("could not scale the picture"))), "image/jpeg", 0.88));
}

/** A URL the <img> can show for the file at `path`. `maxSide` > 0 makes a smaller copy (covers, thumbnails). */
export function pictureUrl(path: string, version: string | number = 0, maxSide = 0): Promise<string> {
  const key = `${path}|${version}|${maxSide}`;
  let hit = cache.get(key);
  if (hit) { cache.delete(key); cache.set(key, hit); return hit; }     // refresh its position
  hit = (async () => {
    const r = await fetch(convertFileSrc(path));
    if (!r.ok) throw new Error(`the picture could not be read (${r.status})`);
    let blob = await r.blob();
    if (maxSide > 0) blob = await scaled(blob, maxSide);
    return URL.createObjectURL(blob);
  })();
  hit.catch(() => cache.delete(key));                                    // a failed load may be retried
  cache.set(key, hit);
  evict();
  return hit;
}

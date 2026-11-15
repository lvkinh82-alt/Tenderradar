import type { Segment } from "./store";

const pad = (n: number, w = 2) => String(n).padStart(w, "0");
const srtTime = (ms: number) => {
  ms = Math.max(0, ms);
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`;
};

export function toTxt(segs: Segment[]) {
  return segs
    .map((s) => `[${new Date(s.t).toLocaleTimeString()}]${s.speaker ? " " + s.speaker : ""}\n${s.src}\n${s.tgt}\n`)
    .join("\n");
}

export function toSrt(segs: Segment[]) {
  const t0 = segs[0]?.t ?? 0;
  return segs
    .map((s, i) => {
      const start = s.t - t0;
      const next = segs[i + 1] ? segs[i + 1].t - t0 : start + 4000;
      return `${i + 1}\n${srtTime(start)} --> ${srtTime(Math.max(next - 100, start + 800))}\n${s.tgt}\n`;
    })
    .join("\n");
}

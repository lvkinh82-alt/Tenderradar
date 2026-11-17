// Reproduces "two-person conversation" rounds: A taps, speaks, taps stop; B taps, speaks, taps stop; repeat.
// FINAL_AFTER_STOP=1  -> recognizer only delivers the final text after stop()  (iPhone Safari behaviour)
// DROP_TTS_END=n      -> the n-th spoken utterance never fires onend          (iPhone sometimes does this)
// EARLY_B=1           -> B taps and starts talking before A's translation has arrived
const { chromium, devices } = require('playwright');
const FINAL_AFTER_STOP = process.env.FINAL_AFTER_STOP === '1', DROP = +(process.env.DROP_TTS_END || 0), EARLY_B = process.env.EARLY_B === '1';
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ...devices['iPhone 13'] });
  await ctx.addInitScript(({ FINAL_AFTER_STOP, DROP }) => {
    localStorage.setItem('ll_src', '"zh-HK"'); localStorage.setItem('ll_tgt', '"en-US"');
    window.__log = []; const log = (x) => window.__log.push(x); let n = 0;
    window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.volume = 1; } };
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: { getVoices() { return []; }, resume() {},
      cancel() { log('tts:cancel'); }, speak(u) { if (u.volume === 0) return; n++; log(`🔊 ${u.text}`);
        if (n !== DROP) setTimeout(() => u.onend && u.onend(), 300); else log('   (this utterance never fires onend)'); } } });
    window.__say = null; // text the current speaker is saying
    class FakeSR {
      start() { if (this.on) throw new Error('already started'); this.on = true; this.sent = false; log(`🎙 start ${this.lang}`);
        clearInterval(this.t); this.t = setInterval(() => this.tick(), 120); }
      tick() { if (!this.on || !window.__say || this.sent) return;
        const r = [{ transcript: window.__say }]; r.isFinal = !FINAL_AFTER_STOP;
        this.onresult && this.onresult({ resultIndex: 0, results: [r] }); if (r.isFinal) { this.sent = true; window.__say = null; } }
      stop() { if (!this.on) return; this.on = false; clearInterval(this.t); log(`🎙 stop ${this.lang}`);
        setTimeout(() => { if (FINAL_AFTER_STOP && window.__say && !this.sent) { const r = [{ transcript: window.__say }]; r.isFinal = true; this.onresult && this.onresult({ resultIndex: 0, results: [r] }); window.__say = null; }
          this.onend && this.onend(); }, 150); }
      abort() { if (!this.on) return; this.on = false; clearInterval(this.t); log(`🎙 abort ${this.lang}`); setTimeout(() => this.onend && this.onend(), 30); }
    }
    for (const k of ['SpeechRecognition', 'webkitSpeechRecognition']) Object.defineProperty(window, k, { configurable: true, writable: true, value: FakeSR });
  }, { FINAL_AFTER_STOP, DROP });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://localhost:8765/#convo'); await p.waitForTimeout(400);
  const turn = async (who, text) => {
    await p.click(who === 'A' ? '#talkA' : '#talkB'); await p.waitForTimeout(200);
    await p.evaluate((t) => window.__say = t, text); await p.waitForTimeout(600);
    await p.click(who === 'A' ? '#talkA' : '#talkB');                    // tap again = stop
    await p.waitForTimeout(EARLY_B ? 100 : 2000);
  };
  const lines = [['A', '你好'], ['B', 'Hello there'], ['A', '你食咗飯未'], ['B', 'Not yet'], ['A', '一齊去食啦'], ['B', 'Sounds good']];
  for (const [w, t] of lines) await turn(w, t);
  await p.waitForTimeout(2500);
  const got = await p.$$eval('#feed .card', e => e.map(c => c.querySelector('.src').textContent + ' => ' + c.querySelector('.tgt').textContent).reverse());
  const ok = lines.every(([, t]) => got.some(g => g.startsWith(t + ' => ') && /(EN|中)<.+>$/.test(g)));
  const spoken = (await p.evaluate(() => window.__log)).filter(x => x.startsWith('🔊')).length;
  // every translation must be read aloud, except one that arrives while someone is already talking (EARLY_B)
  const spokeOk = EARLY_B ? spoken >= 1 : spoken === lines.length;
  const pass = ok && spokeOk;
  console.log(`FINAL_AFTER_STOP=${+FINAL_AFTER_STOP} DROP_TTS_END=${DROP} EARLY_B=${+EARLY_B}  →  ${pass ? 'PASS' : 'FAIL'}  (${got.filter(g => /(EN|中)<.+>$/.test(g)).length}/${lines.length} translated, ${spoken} read aloud)`);
  if (!pass && !process.env.VERBOSE) { got.forEach(g => console.log('   ', g)); console.log('   log:', (await p.evaluate(() => window.__log)).join(' | ')); }
  if (process.env.VERBOSE) { got.forEach(g => console.log('   ', g)); console.log('   log:', (await p.evaluate(() => window.__log)).join(' | ')); }
  if (errs.length) console.log('   errors', errs);
  await b.close();
})();

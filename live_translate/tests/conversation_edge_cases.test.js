const { chromium, devices } = require('playwright');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext({ ...devices['iPhone 13'] });
  await ctx.addInitScript(() => {
    localStorage.setItem('ll_src', '"zh-HK"'); localStorage.setItem('ll_tgt', '"en-US"');
    window.__log = []; const log = (x) => window.__log.push(x);
    window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; this.volume = 1; } };
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: { getVoices() { return []; }, resume() {}, cancel() {},
      speak(u) { if (u.volume === 0) return; log(`🔊 ${u.text}`); setTimeout(() => u.onend && u.onend(), 300); } } });
    window.__say = null; window.__active = 0;
    class FakeSR { // iPhone-like: final text only after stop(); complains if two run at once
      start() { if (this.on) throw new Error('already started'); window.__active++; if (window.__active > 1) log('‼ two recognizers at once'); this.on = true; log(`🎙 start ${this.lang}`); }
      stop() { if (!this.on) return; this.on = false; window.__active--; const said = window.__say; window.__say = null;
        setTimeout(() => { if (said) { const r = [{ transcript: said }]; r.isFinal = true; this.onresult && this.onresult({ resultIndex: 0, results: [r] }); } this.onend && this.onend(); }, 300); }
      abort() { if (!this.on) return; this.on = false; window.__active--; window.__say = null; setTimeout(() => this.onend && this.onend(), 30); }
    }
    for (const k of ['SpeechRecognition', 'webkitSpeechRecognition']) Object.defineProperty(window, k, { configurable: true, writable: true, value: FakeSR });
  });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  const cards = () => p.$$eval('#feed .card', e => e.map(c => c.querySelector('.src').textContent + ' => ' + c.querySelector('.tgt').textContent).reverse());
  await p.goto('http://localhost:8765/#convo'); await p.waitForTimeout(300);
  // 1) hand over without stopping: A talks, B taps B straight away
  await p.click('#talkA'); await p.evaluate(() => window.__say = '你好呀'); await p.waitForTimeout(300);
  await p.click('#talkB'); await p.waitForTimeout(150); await p.evaluate(() => window.__say = 'Hi, nice to meet you'); await p.waitForTimeout(400);
  await p.click('#talkB'); await p.waitForTimeout(2500);
  console.log('1) hand-over:', JSON.stringify(await cards()));
  // 2) tap and stop without saying anything
  const before = (await cards()).length;
  await p.click('#talkA'); await p.waitForTimeout(200); await p.click('#talkA'); await p.waitForTimeout(800);
  console.log('2) empty tap adds no card:', (await cards()).length === before);
  // 3) button labels are back to idle
  console.log('3) idle buttons:', (await p.innerText('#talkA')).split('\n')[0], '|', (await p.innerText('#talkB')).split('\n')[0]);
  // 4) leave the screen mid-sentence: nothing stray appears
  await p.click('#talkA'); await p.evaluate(() => window.__say = '唔好翻譯呢句'); await p.waitForTimeout(200);
  await p.goto('http://localhost:8765/#'); await p.waitForTimeout(800); await p.goto('http://localhost:8765/#convo'); await p.waitForTimeout(500);
  console.log('4) no stray card after leaving:', !(await cards()).some(c => c.startsWith('唔好翻譯')));
  // 5) many quick rounds
  for (let i = 0; i < 5; i++) for (const [w, t] of [['A', `第${i}句`], ['B', `Reply ${i}`]]) {
    await p.click(w === 'A' ? '#talkA' : '#talkB'); await p.waitForTimeout(150);
    await p.evaluate((t) => window.__say = t, t); await p.waitForTimeout(250);
    await p.click(w === 'A' ? '#talkA' : '#talkB'); await p.waitForTimeout(1600);
  }
  await p.waitForTimeout(1500);
  const all = await cards(); const okRounds = [0,1,2,3,4].every(i => all.some(c => c.startsWith(`第${i}句 => EN<`)) && all.some(c => c.startsWith(`Reply ${i} => 中<`)));
  console.log('5) 10 quick turns all translated:', okRounds);
  const log = await p.evaluate(() => window.__log);
  console.log('   never two recognizers at once:', !log.some(x => x.startsWith('‼')), '| read aloud:', log.filter(x => x.startsWith('🔊')).length);
  console.log('errors', errs); await b.close();
})();

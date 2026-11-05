// Synthesised sound effects and a gentle generative music loop (Web Audio, no asset files).
(function () {
  let ctx = null, master = null, musicGain = null, sfxGain = null, musicOn = true, sfxOn = true, musicTimer = null, step = 0;

  function init() {
    if (ctx) return;
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain(); master.gain.value = 0.6; master.connect(ctx.destination);
    sfxGain = ctx.createGain(); sfxGain.gain.value = 0.8; sfxGain.connect(master);
    musicGain = ctx.createGain(); musicGain.gain.value = 0.16; musicGain.connect(master);
    if (musicOn) startMusic();
  }

  function tone(freq, dur, type = 'sine', vol = 0.3, when = 0, dest = null, slide = 0) {
    if (!ctx) return;
    const t = ctx.currentTime + when;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.setValueAtTime(freq, t);
    if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(30, freq + slide), t + dur);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest || sfxGain);
    o.start(t); o.stop(t + dur + 0.05);
  }

  function noise(dur, vol = 0.2, when = 0, hp = 1000) {
    if (!ctx) return;
    const t = ctx.currentTime + when;
    const buf = ctx.createBuffer(1, ctx.sampleRate * dur, ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
    const s = ctx.createBufferSource(); s.buffer = buf;
    const f = ctx.createBiquadFilter(); f.type = 'highpass'; f.frequency.value = hp;
    const g = ctx.createGain(); g.gain.value = vol;
    s.connect(f); f.connect(g); g.connect(sfxGain); s.start(t);
  }

  const FX = {
    click: () => tone(660, 0.05, 'triangle', 0.12),
    hover: () => tone(880, 0.03, 'sine', 0.04),
    cash: () => { noise(0.08, 0.25, 0, 3000); tone(1318, 0.18, 'triangle', 0.18, 0.05); tone(1760, 0.3, 'triangle', 0.15, 0.12); },
    sale: () => { [784, 988, 1175, 1568].forEach((f, i) => tone(f, 0.22, 'triangle', 0.16, i * 0.06)); },
    coin: () => { tone(1568, 0.08, 'square', 0.06); tone(2093, 0.2, 'square', 0.05, 0.06); },
    bad: () => { tone(220, 0.25, 'sawtooth', 0.12, 0, null, -80); tone(160, 0.3, 'sawtooth', 0.1, 0.12, null, -60); },
    warn: () => { tone(440, 0.12, 'square', 0.07); tone(370, 0.15, 'square', 0.07, 0.12); },
    door: () => { tone(1568, 0.5, 'sine', 0.08); tone(1976, 0.6, 'sine', 0.06, 0.08); },
    bid: () => { noise(0.05, 0.2, 0, 1500); tone(520, 0.08, 'triangle', 0.14); },
    outbid: () => { tone(600, 0.1, 'square', 0.08); tone(450, 0.15, 'square', 0.08, 0.1); },
    gavel: () => { noise(0.12, 0.5, 0, 200); tone(120, 0.2, 'sine', 0.4, 0, null, -40); noise(0.1, 0.4, 0.22, 200); tone(110, 0.2, 'sine', 0.35, 0.22, null, -40); },
    scan: () => { tone(400, 0.35, 'sine', 0.08, 0, null, 900); tone(1200, 0.08, 'sine', 0.1, 0.38); },
    reveal: () => { [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.4, 'triangle', 0.13, i * 0.08)); },
    day: () => { [392, 523, 659, 784].forEach((f, i) => tone(f, 0.5, 'sine', 0.12, i * 0.12)); },
    tick: () => tone(1000, 0.03, 'square', 0.04),
    win: () => { [523, 659, 784, 1047, 784, 1047, 1319].forEach((f, i) => tone(f, 0.35, 'triangle', 0.14, i * 0.13)); },
  };

  function play(name) { if (!sfxOn) return; try { init(); FX[name] && FX[name](); } catch (e) { } }

  // Mellow lounge loop: ii-V-I-vi in C with a walking bass.
  const CHORDS = [[293.7, 349.2, 440, 523.3], [196, 246.9, 349.2, 392], [261.6, 329.6, 392, 493.9], [220, 261.6, 329.6, 392]];
  const BASS = [[73.4, 87.3, 110, 98], [98, 123.5, 146.8, 123.5], [65.4, 82.4, 98, 110], [110, 98, 87.3, 82.4]];
  function startMusic() {
    if (!ctx || musicTimer) return;
    const beat = 0.62;
    musicTimer = setInterval(() => {
      const bar = Math.floor(step / 4) % 4, b = step % 4;
      if (b === 0) CHORDS[bar].forEach((f) => tone(f, beat * 3.6, 'sine', 0.05, 0, musicGain));
      if (b === 2) CHORDS[bar].slice(1).forEach((f) => tone(f * 2, beat * 0.5, 'triangle', 0.018, 0, musicGain));
      tone(BASS[bar][b], beat * 0.9, 'triangle', 0.12, 0, musicGain);
      if (Math.random() < 0.25) tone(CHORDS[bar][Math.floor(Math.random() * 4)] * 2, beat * 0.4, 'sine', 0.03, beat * 0.5, musicGain);
      step++;
    }, beat * 1000);
  }
  function stopMusic() { clearInterval(musicTimer); musicTimer = null; }

  window.SFX = {
    play, init,
    setMusic(on) { musicOn = on; if (on) { init(); startMusic(); } else stopMusic(); },
    setSfx(on) { sfxOn = on; },
    setVolume(v) { init(); master.gain.value = v; },
    get music() { return musicOn; }, get sfx() { return sfxOn; },
  };
})();

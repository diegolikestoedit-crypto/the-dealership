// The Dealership — client. Renders server state and sends player intents. No game rules live here.
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = (n) => (n < 0 ? '-' : '') + '$' + Math.abs(Math.round(n || 0)).toLocaleString('en-US');
  const nice = (v) => { v = Math.max(1, Math.round(v)); const s = v < 50 ? 1 : v < 300 ? 5 : v < 1500 ? 10 : v < 6000 ? 25 : 50; return Math.max(s, Math.round(v / s) * s); };
  const LOCAL = location.origin;
  // Each browser keeps its own profile & solo save on whichever computer hosts the game.
  let PROFILE = '';
  try { PROFILE = localStorage.getItem('dealer_profile_id') || ''; if (!PROFILE) { PROFILE = 'p' + Math.random().toString(36).slice(2, 12) + Date.now().toString(36); localStorage.setItem('dealer_profile_id', PROFILE); } } catch (e) { PROFILE = 'p' + Math.random().toString(36).slice(2, 14); }
  const ONLINE = !/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);
  const COLORS = ['#e5b84b', '#6cc3ff', '#5fd38d', '#ff6b6b', '#c39bff', '#ffb547', '#4dd0e1', '#f48fb1'];
  const DECOR = { plant: '🪴', cat: '🐈', aquarium: '🐠', chandelier: '🕯️', trophy: '🏆', jukebox: '📻', statue: '🗿' };
  const ROLE_ICON = { appraiser: '🔍', sales: '🤝', security: '🛡️', negotiator: '💬', researcher: '📊' };
  const UP_ICON = { showroom: '🏬', storage: '📦', lab: '🔬', cases: '💎', ads: '📣', service: '🛋️', security: '🔒', specialty: '⭐' };

  const S = {
    screen: 'menu', base: LOCAL, sess: null, v: null, profile: null, tab: 'floor',
    draft: { offer: {}, price: {}, bid: '', spec: '', joinType: 'general', solo: { bots: 4, days: 7, pace: 'normal', space: false, type: 'general', rivals: 'mix' }, host: { days: 7, pace: 'normal', max: 6, public: true, name: '', rule: 'free', type: 'general' }, joinAddr: LOCAL, code: '' },
    sel: new Set(), seenNote: -1, phaseTotal: 1, lastPhase: null, lastLot: null, lastBid: 0, lastCust: null, awarded: {}, award: null,
    rooms: [], save: null, info: null, errCount: 0, lastCash: null, types: null,
  };
  try { S.sess = JSON.parse(localStorage.getItem('dealer_session') || 'null'); S.awarded = JSON.parse(localStorage.getItem('dealer_awarded') || '{}'); } catch (e) { }

  // ------------------------------------------------------------------ network
  async function post(path, body, base = S.base) {
    try {
      const r = await fetch(base + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return await r.json();
    } catch (e) { return { ok: false, error: 'Cannot reach the game server at ' + base }; }
  }
  async function get(path, base = S.base) {
    try { const r = await fetch(base + path); return await r.json(); } catch (e) { return { error: 'Cannot reach ' + base }; }
  }
  let nonceN = 0;
  async function act(action, args = {}) {
    if (!S.sess) return {};
    const nonce = S.sess.pid + '-' + Date.now().toString(36) + '-' + (nonceN++);
    const r = await post('/api/action', { room: S.sess.room, token: S.sess.token, action, args, nonce }, S.sess.base);
    if (!r.ok) { toast(r.error || 'Action failed', 'bad'); SFX.play('warn'); }
    return r;
  }
  function saveSess(s) { S.sess = s; try { s ? localStorage.setItem('dealer_session', JSON.stringify(s)) : localStorage.removeItem('dealer_session'); } catch (e) { } }

  let es = null;
  function connect() {
    if (es) es.close();
    const { base, room, token } = S.sess;
    S.seenNote = -1;
    es = new EventSource(`${base}/api/stream?room=${encodeURIComponent(room)}&token=${encodeURIComponent(token)}`);
    es.onmessage = (ev) => {
      S.errCount = 0;
      const v = JSON.parse(ev.data);
      if (v.kicked) return leaveLocal('You were removed from the room.');
      onView(v);
    };
    es.onerror = async () => {
      S.errCount++;
      renderConn();
      if (S.errCount === 3 || S.errCount % 10 === 0) {
        const r = await post('/api/rejoin', { room, token }, base);
        if (r && r.ok === false && /not found|expired/i.test(r.error || '')) leaveLocal('That match no longer exists.');
      }
    };
  }
  function leaveLocal(msg) {
    if (es) es.close(); es = null;
    saveSess(null); S.v = null; S.screen = 'menu'; S.tab = 'floor';
    if (msg) toast(msg, 'warn');
    loadMenuData(); render();
  }
  function renderConn() {
    let el = $('#conn');
    if (S.errCount > 1 && S.sess) {
      if (!el) { el = document.createElement('div'); el.id = 'conn'; el.className = 'toast warn'; el.style.cssText = 'position:fixed;top:66px;left:50%;transform:translateX(-50%);z-index:80;animation:none'; document.body.appendChild(el); }
      el.textContent = 'Connection lost — reconnecting… (your shop is on autopilot after 20s)';
    } else if (el) el.remove();
  }

  // ------------------------------------------------------------------ view updates & feedback
  function onView(v) {
    const prev = S.v;
    S.v = v;
    renderConn();
    S.screen = v.phase === 'lobby' ? 'lobby' : 'game';
    if (v.me) {
      const notes = v.me.notes || [];
      const maxN = notes.length ? notes[notes.length - 1].n : 0;
      if (S.seenNote < 0) S.seenNote = maxN;
      for (const n of notes) if (n.n > S.seenNote) {
        toast(n.text, n.kind);
        SFX.play({ sale: 'sale', bad: 'bad', good: 'cash', warn: 'warn' }[n.kind] || 'coin');
      }
      S.seenNote = Math.max(S.seenNote, maxN);
      if (S.lastCash != null && v.me.cash > S.lastCash) coinFx('+' + fmt(v.me.cash - S.lastCash));
      S.lastCash = v.me.cash;
      const cid = v.me.active && v.me.active.id;
      if (cid && cid !== S.lastCust) { SFX.play('door'); if (S.tab !== 'floor' && v.phase === 'shop') flashTab('floor'); }
      S.lastCust = cid;
    }
    if (v.phase !== S.lastPhase) {
      S.phaseTotal = Math.max(1, v.left || 1);
      if (S.lastPhase !== null || v.phase !== 'lobby') {
        SFX.play({ morning: 'day', shop: 'door', auction: 'gavel', report: 'coin', final: 'win' }[v.phase] || 'click');
      }
      if (v.phase === 'morning') S.tab = 'brief';
      if (v.phase === 'shop') S.tab = 'floor';
      S.lastPhase = v.phase;
    }
    if (v.auction && v.auction.lot) {
      const lot = v.auction.lot;
      if (lot.id !== S.lastLot) { S.lastLot = lot.id; S.lastBid = 0; S.draft.bid = ''; }
      if (lot.bid !== S.lastBid && lot.bid > 0) {
        if (prev && prev.auction && prev.auction.lot && prev.auction.lot.bidder === v.you && lot.bidder !== v.you) SFX.play('outbid'); else SFX.play('bid');
        S.lastBid = lot.bid;
      }
      if (lot.closed && !(prev && prev.auction && prev.auction.lot && prev.auction.lot.closed && prev.auction.lot.id === lot.id)) SFX.play('gavel');
    }
    if (v.final && S.sess && !S.awarded[S.sess.room + S.sess.pid]) awardProfile(v);
    maybeIntro(v);
    if (v.final && S.sess && !S.award) { try { S.award = JSON.parse(localStorage.getItem('dealer_award_' + S.sess.room + S.sess.pid) || 'null'); } catch (e) { } }
    render();
  }

  async function awardProfile(v) {
    const key = S.sess.room + S.sess.pid;
    S.awarded[key] = true;
    try { localStorage.setItem('dealer_awarded', JSON.stringify(S.awarded)); } catch (e) { }
    const row = v.final.rows.find((r) => r.id === v.you);
    if (!row) return;
    const r = await post('/api/profile/award', { profile: PROFILE, host: S.sess.base, room: S.sess.room, pid: v.you, row, players: v.final.rows.length }, LOCAL);
    if (r && r.profile) {
      S.profile = r.profile; S.award = r;
      try { localStorage.setItem('dealer_award_' + key, JSON.stringify({ gained: r.gained, new: r.new, levelUp: r.levelUp, level: r.level })); } catch (e) { }
      render(); if (r.levelUp) { SFX.play('reveal'); toast('LEVEL UP! You reached level ' + r.level, 'good'); } }
  }

  function toast(text, kind = 'info') {
    const d = document.createElement('div');
    d.className = 'toast ' + kind; d.textContent = text;
    $('#toasts').appendChild(d);
    setTimeout(() => d.remove(), 4800);
    while ($('#toasts').children.length > 5) $('#toasts').firstChild.remove();
  }
  function coinFx(text) {
    const anchor = $('#stat-cash'); if (!anchor) return;
    const r = anchor.getBoundingClientRect();
    const d = document.createElement('div'); d.className = 'coinfx'; d.textContent = text;
    d.style.left = r.left + 'px'; d.style.top = (r.top + 30) + 'px';
    document.body.appendChild(d); setTimeout(() => d.remove(), 1300);
  }
  function flashTab(t) { const el = document.querySelector(`[data-a="tab"][data-t="${t}"]`); if (el) { el.animate([{ background: '#e5b84b55' }, { background: 'transparent' }], { duration: 900, iterations: 2 }); } }

  // Only touch the DOM when markup really changed, and keep focus/caret in inputs.
  function patch(el, html) {
    if (!el || el._h === html) return false;
    const a = document.activeElement;
    let keep = null;
    if (a && el.contains(a) && a.id) keep = { id: a.id, v: a.value, s: a.selectionStart, e: a.selectionEnd };
    el.innerHTML = html; el._h = html;
    if (keep) { const n = document.getElementById(keep.id); if (n) { n.focus(); if (n.value !== keep.v) n.value = keep.v; try { n.setSelectionRange(keep.s, keep.e); } catch (e) { } } }
    return true;
  }
  function ensure(el, key, html) { if (el._k !== key) { el.innerHTML = html; el._k = key; el._h = null; return true; } return false; }

  // ------------------------------------------------------------------ menu screens
  async function loadMenuData() {
    const [p, s, inf] = await Promise.all([get('/api/profile?profile=' + PROFILE, LOCAL), get('/api/save?profile=' + PROFILE, LOCAL), get('/api/info', LOCAL)]);
    if (inf && inf.types) S.types = inf.types;
    if (p && !p.error) {
      S.profile = p;
      SFX.setMusic(!!p.settings.music); SFX.setSfx(p.settings.sfx !== false);
      if (!S.draft.host.name) S.draft.host.name = p.name + "'s Match";
    }
    S.save = s && s.exists ? s : null;
    if (S.screen === 'menu') render();
  }

  function menuBG() {
    const kinds = ['watch', 'guitar', 'vase', 'coin', 'camera', 'painting', 'ring', 'globe', 'robot', 'helmet', 'sax', 'card'];
    const floats = kinds.map((k, i) => `<div class="float" style="left:${(i * 8.3 + 2) % 96}%;animation-delay:-${i * 1.6}s;animation-duration:${16 + (i % 5) * 3}s">${ART.item({ kind: k, variant: 'abcd'[i % 4], condIdx: 1 }, 64 + (i % 3) * 32)}</div>`).join('');
    const shops = ['#c0392b', '#2e86c1', '#239b56', '#8e44ad', '#d35400'].map((a, i) => `<div class="shopfront" style="--a:${a};height:${180 + (i % 3) * 40}px;background:linear-gradient(${['#3b2b20', '#2b3440', '#2e3b2c', '#3a2b3e', '#40302a'][i]},#1b140f)"><div class="awning"></div><div class="win"></div></div>`).join('');
    return floats + `<div class="street">${shops}</div>`;
  }

  function menuScreen() {
    const p = S.profile;
    return `<div class="menu">${menuBG()}<div class="menu-box">
      <div class="logo"><small>THE</small>DEALERSHIP</div>
      <div class="tagline">Buy low. Sell high. Outsmart every dealer on the street.</div>
      <div class="menu-btns">
        ${S.save ? `<button class="btn primary" data-a="continue">Continue Solo Match <span class="dim">· Day ${S.save.day}/${S.save.days}</span></button>` : ''}
        <button class="btn ${S.save ? '' : 'primary'}" data-a="go" data-s="solo">Solo vs AI Dealers</button>
        <button class="btn" data-a="go" data-s="host">Host Multiplayer (LAN)</button>
        <button class="btn" data-a="go" data-s="join">Join Multiplayer</button>
        <div class="row"><button class="btn grow" data-a="go" data-s="profile">Profile & Cosmetics</button><button class="btn grow" data-a="go" data-s="howto">How to Play</button><button class="btn" data-a="go" data-s="settings">⚙</button></div>
        ${ONLINE ? '' : '<button class="btn ghost" data-a="quit">Quit Game</button>'}
      </div>
      <div class="menu-foot">${p ? `${esc(p.name)} · Level ${p.level} · ${p.wins} wins · ${esc(p.selected.title)}` : 'Loading profile…'}</div>
    </div></div>`;
  }

  function wrapForm(title, inner) {
    return `<div class="menu">${menuBG()}<div class="menu-box form panel scroll" style="width:720px;max-height:94vh">
      <div class="row"><h2>${title}</h2><button class="btn ghost right" data-a="go" data-s="menu">← Back</button></div>${inner}</div></div>`;
  }
  const sel = (id, val, opts) => `<select id="${id}" data-in="${id}">${opts.map(([v, l]) => `<option value="${v}" ${String(v) === String(val) ? 'selected' : ''}>${l}</option>`).join('')}</select>`;
  const paceOpts = [['quick', 'Quick (~20 min)'], ['normal', 'Normal (~30 min)'], ['relaxed', 'Relaxed (~45 min)']];

  const T = (k) => ((S.v && S.v.types) || S.types || {})[k] || { name: k, icon: '🏪', desc: '', cats: null };
  function typePicker(cur, act) {
    const types = (S.v && S.v.types) || S.types || {};
    return `<div class="type-grid">${Object.entries(types).map(([k, t]) => `<div class="tpick ${cur === k ? 'on' : ''}" data-a="${act}" data-k="${k}">
      <div class="ticon">${t.icon}</div><b>${esc(t.name)}</b><div class="dim" style="font-size:11px">${esc(t.desc)}</div><div class="tnote">${esc(t.note || '')}</div></div>`).join('')}</div>`;
  }
  const ruleOpts = () => [['free', 'Each dealer chooses'], ...Object.entries((S.v && S.v.types) || S.types || {}).map(([k, t]) => [k, 'Everyone: ' + t.name])];

  function soloScreen() {
    const d = S.draft.solo, p = S.profile;
    const spaceOk = p && p.expansions.find((x) => x.key === 'space' && x.unlocked);
    return wrapForm('Solo Match', `
      <h3 style="margin-top:6px">Your dealership</h3>${typePicker(d.type, 'solo-type')}
      <label>AI rivals' dealerships ${sel('solo-rivals', d.rivals, [['mix', 'Random mix of types'], ['same', 'Same type as me (' + esc(T(d.type).name) + ')'], ['general', 'General dealers']])}</label>
      <label>Rival AI dealers ${sel('solo-bots', d.bots, [1, 2, 3, 4, 5, 6, 7].map((n) => [n, n + ' rival' + (n > 1 ? 's' : '')]))}</label>
      <label>Business days ${sel('solo-days', d.days, [[5, '5 days'], [7, '7 days'], [10, '10 days'], [12, '12 days']])}</label>
      <label>Pace ${sel('solo-pace', d.pace, paceOpts)}</label>
      <label>Space Memorabilia expansion <input type="checkbox" data-in="solo-space" ${d.space ? 'checked' : ''} ${spaceOk ? '' : 'disabled'}> ${spaceOk ? '' : '<span class="dim">unlocks at level 4</span>'}</label>
      <p class="muted">Everyone starts with $25,000. Highest net worth after the final day wins. Solo matches can be paused and auto-save every morning.</p>
      <button class="btn primary lg" style="width:100%" data-a="solo-start">Open for Business</button>`);
  }

  function hostScreen() {
    const d = S.draft.host;
    return wrapForm('Host a LAN Match', `
      <label>Dealership rule ${sel('host-rule', d.rule, ruleOpts())}</label>
      ${d.rule === 'free' ? `<h3>Your dealership</h3>${typePicker(d.type, 'host-type')}` : ''}
      <label>Match name <input type="text" id="host-name" data-in="host-name" value="${esc(d.name)}" maxlength="40"></label>
      <label>Max players ${sel('host-max', d.max, [2, 3, 4, 5, 6, 7, 8].map((n) => [n, n + ' dealers']))}</label>
      <label>Business days ${sel('host-days', d.days, [[5, '5 days'], [7, '7 days'], [10, '10 days']])}</label>
      <label>Pace ${sel('host-pace', d.pace, paceOpts)}</label>
      <label>List in room browser <input type="checkbox" data-in="host-public" ${d.public ? 'checked' : ''}></label>
      <p class="muted">Players on the same network join from their own copy of the game (or a browser) using your address and room code. Empty seats can be filled with AI dealers in the lobby.</p>
      <button class="btn primary lg" style="width:100%" data-a="host-create">Create Lobby</button>`);
  }

  function joinScreen() {
    const rooms = S.rooms.length ? S.rooms.map((r) => `<div class="card row" style="margin-bottom:6px"><div class="grow"><b>${esc(r.name)}</b><div class="muted" style="font-size:12px">Host ${esc(r.host)} · ${r.players}/${r.max} dealers · ${r.days} days · code <b>${r.code}</b></div></div><button class="btn primary sm" data-a="join-room" data-code="${r.code}" ${r.players >= r.max ? 'disabled' : ''}>Join</button></div>`).join('')
      : `<p class="dim">No open public lobbies found on this server.</p>`;
    return wrapForm('Join a Match', `
      <label>Server address <input type="text" id="join-addr" data-in="join-addr" value="${esc(S.draft.joinAddr)}" style="width:280px" placeholder="http://192.168.1.20:8642"></label>
      <div class="row" style="margin:10px 0"><h3 class="grow" style="margin:0">Open lobbies</h3><button class="btn sm" data-a="join-refresh">↻ Refresh</button></div>
      <div class="scroll" style="max-height:240px">${rooms}</div>
      <h3 style="margin-top:10px">Your dealership <span class="dim" style="font-family:var(--sans);font-size:12px">· used if the host lets everyone choose (you can change it in the lobby)</span></h3>${typePicker(S.draft.joinType, 'join-type')}
      <label style="margin-top:8px">Room code <input type="text" id="join-code" data-in="join-code" value="${esc(S.draft.code)}" maxlength="4" style="width:100px;text-transform:uppercase;letter-spacing:.2em"></label>
      <button class="btn primary lg" style="width:100%" data-a="join-code">Join with Code</button>`);
  }

  function settingsScreen() {
    const s = (S.profile && S.profile.settings) || { music: true, sfx: true, volume: 0.6 };
    return wrapForm('Settings', `
      <label>Music <input type="checkbox" data-in="set-music" ${s.music ? 'checked' : ''}></label>
      <label>Sound effects <input type="checkbox" data-in="set-sfx" ${s.sfx !== false ? 'checked' : ''}></label>
      <label>Master volume <input type="range" min="0" max="1" step="0.05" value="${s.volume}" data-in="set-volume"></label>
      <p class="muted">Saves and profile are stored on this computer. Delete the TheDealership folder in your application data to reset.</p>`);
  }

  function howtoScreen() {
    const demo = { settings: { solo: true, days: 7, type_rule: 'free' }, days: 7, startCash: 25000, types: S.types, lobby: [], you: null };
    const solo = introPages(demo), mp = introPages(Object.assign({}, demo, { settings: { solo: false, days: 7, type_rule: 'free' } }));
    const pages = solo.map((p, i) => `<section class="hsec"><h2>${p.title}</h2>${i === 0 ? p.body.replace(/<p class="tip">.*?<\/p>/s, '') : p.body}</section>`).join('');
    return wrapForm('How to Play', `<div class="howto scroll intro" style="max-height:70vh;max-width:none">
      <section class="hsec"><h2>Playing solo</h2><ol class="ilist"><li>Main menu → <b>Solo vs AI Dealers</b>.</li><li>Pick <b>your dealership</b> and how your AI rivals are set up, how many rivals, and how many days.</li><li>Press <b>Open for Business</b>. The instructions appear and the clock waits until you press <b>Start Day 1</b>.</li><li>Pause any time. The game saves every morning — pick <b>Continue</b> on the main menu to resume.</li></ol></section>
      <section class="hsec"><h2>Playing with friends</h2><ol class="ilist"><li><b>Host:</b> Main menu → <b>Host Multiplayer</b> → pick a rule (everyone chooses their own dealership, or one type for all) → <b>Create Lobby</b>.</li><li>The lobby shows a <b>room code</b> and a <b>link</b>. Send both to your friends.</li><li><b>Friends:</b> open the link in any browser → <b>Join Multiplayer</b> → choose a dealership → type the code → <b>Join</b>.</li><li>Everyone picks their dealership in the lobby. The host can add AI dealers to fill seats, then presses <b>Start Match</b>.</li><li>Day 1 gives everyone 3 minutes to read the instructions; it starts early once all players press <b>Open the doors</b>.</li></ol></section>
      ${pages}${mp[5] ? `<p class="tip">${mp[5].body.match(/autopilot.*?control\./s) ? 'If your connection drops in multiplayer, your shop goes on <b>autopilot</b> after 20 seconds. Reopen the same link in the same browser to take back control.' : ''}</p>` : ''}</div>`);
  }

  function profileScreen() {
    const p = S.profile;
    if (!p) return wrapForm('Profile', '<p>Loading…</p>');
    const pct = Math.min(100, Math.round(100 * (p.xp - p.cur_xp) / Math.max(1, p.next_xp - p.cur_xp)));
    const themes = p.themes.map((t) => `<div class="pick theme-${t.key} ${p.selected.theme === t.key ? 'on' : ''} ${t.unlocked ? '' : 'lock'}" data-a="${t.unlocked ? 'p-theme' : ''}" data-k="${t.key}"><div class="mini-scene"></div>${esc(t.name)}${t.unlocked ? '' : `<div class="dim">Lv ${t.level}</div>`}</div>`).join('');
    const titles = p.titles.map((t) => `<div class="pick ${p.selected.title === t.name ? 'on' : ''} ${t.unlocked ? '' : 'lock'}" data-a="${t.unlocked ? 'p-title' : ''}" data-k="${esc(t.name)}">${esc(t.name)}${t.unlocked ? '' : `<div class="dim">Lv ${t.level}</div>`}</div>`).join('');
    const decor = p.decor.map((t) => `<div class="pick ${p.selected.decor.includes(t.key) ? 'on' : ''} ${t.unlocked ? '' : 'lock'}" data-a="${t.unlocked ? 'p-decor' : ''}" data-k="${t.key}"><div style="font-size:26px">${t.key === 'sign' ? '<span style="color:#ff4fd8;text-shadow:0 0 8px #ff4fd8;font-weight:900;font-size:16px">OPEN</span>' : DECOR[t.key] || '✨'}</div>${esc(t.name)}${t.unlocked ? '' : `<div class="dim">Lv ${t.level}</div>`}</div>`).join('');
    const ach = Object.entries(p.achievement_defs).map(([k, [n, d]]) => `<div class="a ${p.achievements.includes(k) ? 'on' : ''}"><b>${p.achievements.includes(k) ? '🏅' : '🔒'} ${esc(n)}</b><div class="dim" style="font-size:12px">${esc(d)}</div></div>`).join('');
    const tro = p.trophies.length ? p.trophies.slice().reverse().map((t) => `<span class="chip" title="${t.players} players">${t.name === 'Gold Ledger' ? '🥇' : t.name === 'Silver Scale' ? '🥈' : '🥉'} ${esc(t.name)} · ${fmt(t.nw)}</span>`).join(' ') : '<span class="dim">Finish in the top 3 of a 3+ dealer match to earn trophies.</span>';
    return `<div class="menu" style="align-items:stretch;padding:30px">${menuBG()}<div class="panel scroll" style="position:relative;z-index:2;width:min(1000px,100%);margin:auto;max-height:100%">
      <div class="row"><h2>Dealer Profile</h2><button class="btn ghost right" data-a="go" data-s="menu">← Back</button></div>
      <div class="row" style="gap:20px;margin-bottom:12px">
        <label class="row">Name <input type="text" id="p-name" data-in="p-name" value="${esc(p.name)}" maxlength="20"></label>
        <div class="grow"><div class="row"><b>Level ${p.level}</b><span class="dim right">${p.xp} / ${p.next_xp} XP</span></div><div class="xpbar"><i style="width:${pct}%"></i></div></div>
        <div class="stat"><b>${p.matches}</b><span>Matches</span></div><div class="stat"><b>${p.wins}</b><span>Wins</span></div><div class="stat"><b>${fmt(p.best_nw)}</b><span>Best net worth</span></div>
      </div>
      <p class="dim" style="margin-top:0">Progression is cosmetic only — every match starts perfectly even.</p>
      <h3>Store theme</h3><div class="pick-grid">${themes}</div>
      <h3 style="margin-top:14px">Title</h3><div class="pick-grid">${titles}</div>
      <h3 style="margin-top:14px">Decorations (up to 4)</h3><div class="pick-grid">${decor}</div>
      <h3 style="margin-top:14px">Trophies</h3><div class="row wrap">${tro}</div>
      <h3 style="margin-top:14px">Achievements</h3><div class="achv">${ach}</div></div></div>`;
  }

  function lobbyScreen() {
    const v = S.v, isHost = v.host === v.you, st = v.settings;
    const addr = ONLINE ? location.origin : S.info ? `http://${S.info.ip}:${S.info.port}` : S.sess.base;
    const players = v.lobby.map((p, i) => `<div class="card row" style="margin-bottom:6px"><span class="swatch" style="background:${COLORS[i % 8]}"></span>
      <div class="grow"><b>${esc(p.name)}</b> ${isHost && p.is_ai && st.type_rule === 'free' ? '' : `<span class="chip">${T(st.type_rule === 'free' ? p.dtype : st.type_rule).icon} ${esc(T(st.type_rule === 'free' ? p.dtype : st.type_rule).name)}</span>`} ${p.is_ai ? '<span class="chip">AI</span>' : ''} ${p.id === v.host ? '<span class="chip gold">Host</span>' : ''} ${p.id === v.you ? '<span class="chip verified">You</span>' : ''}<div class="dim" style="font-size:12px">${esc(p.title)} · ${esc(p.theme)} store</div></div>
      ${isHost && p.is_ai && st.type_rule === 'free' ? `<select data-in="ai-type" data-pid="${p.id}">${Object.entries(v.types).map(([k, t]) => `<option value="${k}" ${p.dtype === k ? 'selected' : ''}>${t.icon} ${esc(t.name)}</option>`).join('')}</select>` : ''}
      ${isHost && p.id !== v.you ? `<button class="btn sm red" data-a="lobby-remove" data-pid="${p.id}">Remove</button>` : ''}</div>`).join('');
    const mine = v.lobby.find((p) => p.id === v.you);
    const ctl = (id, val, opts) => isHost ? sel(id, val, opts) : `<b>${esc(opts.find((o) => String(o[0]) === String(val))?.[1] || val)}</b>`;
    return `<div class="menu">${menuBG()}<div class="menu-box panel scroll" style="width:860px;max-height:94vh;text-align:left">
      <div class="row"><h2>${esc(st.name)}</h2><button class="btn right" data-a="intro-show">📖 How to play</button><button class="btn ghost" data-a="leave">Leave</button></div>
      ${st.type_rule === 'free' && mine ? `<h3>Choose your dealership <span class="dim" style="font-family:var(--sans);font-size:12px">· every player picks their own</span></h3>${typePicker(mine.dtype, 'lobby-type')}` : `<p class="banner">The host set every shop to <b>${T(st.type_rule).icon} ${esc(T(st.type_rule).name)}</b> for this match.</p>`}
      <div class="cols2">
        <div><h3>Dealers (${v.lobby.length}/${st.max_players})</h3><div class="scroll" style="max-height:320px">${players}</div>
          ${isHost ? `<button class="btn" data-a="lobby-bot" ${v.lobby.length >= st.max_players ? 'disabled' : ''}>+ Add AI dealer</button>` : '<p class="muted">Waiting for the host to start…</p>'}</div>
        <div><h3>Invite players</h3>
          <div class="card"><div class="dim" style="font-size:12px">Room code</div><div style="font-family:var(--serif);font-size:40px;letter-spacing:.2em;color:var(--gold)">${esc(v.room)}</div>
          <div class="dim" style="font-size:12px">${ONLINE ? 'Send friends this link' : 'Friends on the same Wi-Fi open this in their browser'} → <b>Join Multiplayer</b> → enter the code</div><b style="user-select:text;font-size:15px">${esc(addr)}</b> <button class="btn sm" data-a="copy" data-t="${esc(addr)}">Copy</button></div>
          <h3 style="margin-top:12px">Settings</h3>
          <div class="form" style="width:auto">
            <label>Dealerships ${ctl('lob-rule', st.type_rule, ruleOpts())}</label>
            <label>Days ${ctl('lob-days', st.days, [[5, '5 days'], [7, '7 days'], [10, '10 days']])}</label>
            <label>Pace ${ctl('lob-pace', st.pace, paceOpts)}</label>
            <label>Max players ${ctl('lob-max', st.max_players, [2, 3, 4, 5, 6, 7, 8].map((n) => [n, String(n)]))}</label>
          </div>
          ${isHost ? `<button class="btn primary lg" style="width:100%;margin-top:10px" data-a="lobby-start" ${v.lobby.length < 2 ? 'disabled' : ''}>Start Match</button>` : ''}
        </div></div>
        </div></div>`;
  }

  // ------------------------------------------------------------------ game screen
  function gameSkeleton() {
    return `<div class="game"><header class="topbar" id="g-top"></header>
      <div class="main"><nav class="tabs" id="g-tabs"></nav><section class="content scroll" id="g-content"></section></div>
      <aside class="side"><div class="board" id="g-board"></div><div class="feed scroll" id="g-feed"></div></aside></div>
      <div class="popups" id="g-pops"></div>`;
  }

  const PHASE_LABEL = { morning: 'Morning — Planning', shop: 'Shop Hours', auction: 'Auction House', report: 'End of Day', final: 'Final Results' };

  function topHTML(v) {
    const me = v.me;
    const repStars = '★'.repeat(Math.round(me.rep / 20)) + '☆'.repeat(5 - Math.round(me.rep / 20));
    return `<div class="brand" title="The Dealership">$</div>
      <div class="stat" title="${esc(T(me.dtype).name)} — ${esc(T(me.dtype).desc)}"><b>Day ${v.day}/${v.days}</b><span>${T(me.dtype).icon} ${esc(T(me.dtype).name)}</span></div>
      <div class="flow" id="g-flow"></div>
      <div class="phasebox" id="g-phase"></div>
      <div class="stat" id="stat-cash"><b class="gold money">${fmt(me.cash)}</b><span>Cash</span></div>
      <div class="stat"><b class="money">${fmt(me.netWorth)}</b><span>Net worth</span></div>
      <div class="stat" title="Reputation ${me.rep}/100"><b class="gold" style="font-size:14px">${repStars}</b><span>Reputation ${Math.round(me.rep)}</span></div>
      ${me.loan ? `<div class="stat"><b class="bad money">${fmt(me.loan)}</b><span>Loan</span></div>` : ''}
      ${me.autopilot ? '<span class="chip warn">AUTOPILOT</span>' : ''}
      <div class="row right">
        ${v.settings.solo && v.phase !== 'final' ? `<button class="btn sm" data-a="pause">${v.paused ? '▶ Resume' : '❚❚ Pause'}</button>` : ''}
        <button class="btn sm" data-a="intro-show" title="Instructions">?</button>
        <button class="btn sm" data-a="music" title="Music">${SFX.music ? '♫' : '♫̸'}</button>
        <button class="btn sm" data-a="sfx" title="Sound effects">${SFX.sfx ? '🔊' : '🔈'}</button>
        <button class="btn sm" data-a="leave-ask">Menu</button></div>`;
  }

  function tabsFor(v) {
    if (v.phase === 'auction') return [['auction', '🔨 Auction'], ['inventory', 'Inventory'], ['market', 'Market']];
    if (v.phase === 'report') return [['report', 'Day Report'], ['inventory', 'Inventory'], ['staff', '👥 Staff'], ['business', 'Business'], ['market', 'Market']];
    if (v.phase === 'final') return [['final', '🏆 Results']];
    const t = [];
    if (v.phase === 'morning') t.push(['brief', '☀ Briefing']);
    t.push(['floor', 'Shop Floor'], ['inventory', 'Inventory'], ['street', 'Market Street'], ['staff', '👥 Staff'], ['business', 'Business'], ['market', 'Market & News']);
    return t;
  }

  function tabsHTML(v, tabs) {
    const inv = v.me.inventory.length;
    return tabs.map(([k, l]) => `<div class="tab ${S.tab === k ? 'on' : ''}" data-a="tab" data-t="${k}">${l}${k === 'inventory' ? ` <span class="dim">${inv}/${v.me.storage}</span>` : ''}${k === 'floor' && v.me.active && S.tab !== 'floor' ? '<span class="badge">!</span>' : ''}</div>`).join('');
  }

  function boardHTML(v) {
    if (v.final) {
      return `<h3>Final standings <span class="dim" style="font-size:11px;font-family:var(--sans)">true values</span></h3>` + v.final.rows.map((r) => `<div class="lb-row ${r.id === v.you ? 'me' : ''}"><div class="rank">${r.place}</div>
        <div style="min-width:0"><div class="nm">${esc(r.name)} ${r.is_ai ? '<span class="chip">AI</span>' : ''}</div><div class="sub">${fmt(r.cash)} cash · ${fmt(r.inventory)} stock</div></div>
        <div class="money gold" style="font-weight:700">${fmt(r.net_worth)}</div></div>`).join('');
    }
    const rows = v.leaderboard.map((r, i) => `<div class="lb-row ${r.id === v.you ? 'me' : ''}">
      <div class="rank">${i + 1}</div>
      <div style="min-width:0"><div class="nm"><span title="${esc(T(r.dtype).name)}">${T(r.dtype).icon}</span> ${esc(r.name)} ${r.is_ai ? '<span class="chip">AI</span>' : ''}${!r.connected ? ' <span class="chip warn">offline</span>' : r.autopilot ? ' <span class="chip warn">auto</span>' : ''}${(v.phase === 'morning' || v.phase === 'report') && r.ready && !r.is_ai ? ' ✓' : ''}</div>
        <div class="sub">${fmt(r.cash)} cash · ${fmt(r.inventory)} stock · ${r.items} items · rep ${r.rep}</div></div>
      <div class="money gold" style="font-weight:700">${fmt(r.net_worth)}</div></div>`).join('');
    return `<h3>Leaderboard <span class="dim" style="font-size:11px;font-family:var(--sans)">net worth</span></h3>${rows}`;
  }
  function feedHTML(v) { return v.feed.slice().reverse().map((f) => `<div class="${f.kind}">${f.day ? `<span class="dim">D${f.day}</span> ` : ''}${esc(f.text)}</div>`).join(''); }

  function renderGame() {
    const v = S.v, app = $('#app');
    if (ensure(app, 'game', gameSkeleton())) { S.lastTabKey = null; }
    const tabs = tabsFor(v);
    if (!tabs.find((t) => t[0] === S.tab)) S.tab = tabs[0][0];
    patch($('#g-top'), topHTML(v));
    const pct = v.left != null ? Math.max(0, Math.min(100, 100 * v.left / S.phaseTotal)) : 100;
    const steps = [['morning', '☀ Plan'], ['shop', '🏪 Trade'], ['auction', '🔨 Auction'], ['report', '📒 Report']];
    const curI = steps.findIndex((x) => x[0] === v.phase);
    patch($('#g-flow'), v.phase === 'final' ? '<span class="fstep on">🏆 Final results</span>' : steps.map(([k, l], i) => `<span class="fstep ${i === curI ? 'on' : i < curI ? 'done' : ''}">${l}</span>`).join('<span class="farrow">›</span>'));
    patch($('#g-phase'), `<div class="row"><b>${PHASE_LABEL[v.phase] || v.phase}</b>${v.left != null ? `<span class="right money ${v.left < 10 ? 'warn' : 'muted'}">${Math.ceil(v.left)}s</span>` : ''}${v.paused ? '<span class="chip warn">PAUSED</span>' : ''}</div><div class="phasebar"><i style="width:${pct}%"></i></div>`);
    patch($('#g-tabs'), tabsHTML(v, tabs));
    patch($('#g-board'), boardHTML(v));
    patch($('#g-feed'), feedHTML(v));
    patch($('#g-pops'), popsHTML(v));
    const c = $('#g-content');
    const r = { brief: briefTab, floor: floorTab, inventory: invTab, street: streetTab, business: bizTab, staff: staffTab, market: marketTab, auction: auctionTab, report: reportTab, final: finalTab }[S.tab];
    r(v, c);
  }

  // ---------- shop floor
  function suggestPrice(it) { return S.draft.price[it.id] ?? (it.listed ? it.price : nice(it.likely * 1.2)); }
  function canList(v, it) { return v.me.cats.includes(it.cat); }

  // What should the player do right now? One clear sentence.
  function nextHint(v) {
    const me = v.me, c = me.active;
    const freeSlots = me.display - me.inventory.filter((i) => i.listed).length;
    const unlisted = me.inventory.filter((i) => !i.listed && canList(v, i)).length;
    if (me.buyerOffers.length) return ['💬', 'A buyer made you an offer — answer it in the bottom-right corner.'];
    if (c) {
      const it = c.item;
      if (!it.cond && it.likely > 120) return ['🔎', `Look before you pay: inspect the ${esc(it.name)} (press I) or scan it for fakes (S).`];
      if (it.fakeable && it.status === 'unverified' && it.likely > 400) return ['🧪', 'This kind of item is often faked. A scan (S) could save you a fortune.'];
      if (!c.lastOffer) return ['💵', `Make an offer below the ask — sellers rarely expect their first price. Your estimate: <b>${fmt(it.likely)}</b>.`];
      if (c.final) return ['⚖️', `That's their final price. Accept <b>${fmt(c.ask)}</b> (A) or walk away (W).`];
      return ['🤝', 'Counter again, try persuading, or walk away — some sellers call you back.'];
    }
    if (unlisted && freeSlots > 0) return ['🏷️', `You have ${unlisted} item${unlisted > 1 ? 's' : ''} not on display. List them below so buyers can find them (L lists all).`];
    if (me.inventory.length >= me.storage) return ['📦', 'Storage is full — sell something or upgrade your back room.'];
    return ['⏳', me.queue.length ? 'Next seller is on the way…' : 'Waiting for the next seller. Check Market Street to see what rivals charge.'];
  }

  function floorTab(v, c) {
    if (v.phase !== 'shop') {
      ensure(c, 'floor-closed', '');
      return patch(c, `<div class="panel center" style="padding:60px"><h2>The doors are closed</h2><p class="muted">${v.phase === 'morning' ? 'Shop hours start after the morning briefing. Use this time to price your stock, hire staff and plan upgrades.' : 'Come back tomorrow.'}</p>${v.phase === 'morning' ? '<button class="btn primary lg" data-a="ready">Open the doors now →</button>' : ''}</div>`);
    }
    ensure(c, 'floor', `<div class="floor2"><div class="hintbar" id="fl-hint"></div>
      <div class="scene" id="sc"><div class="wallpaper"></div><div class="lamp" style="left:10%"></div><div class="lamp" style="left:60%"></div>
      <div class="sign" id="sc-sign"></div><div class="shelves" id="sc-shelves"></div><div id="sc-decor"></div><div class="counter"></div><div class="register"></div>
      <div id="sc-cust"></div><div id="sc-item"></div><div id="sc-bubble"></div><div class="queue" id="sc-queue"></div></div>
      <div class="nego panel scroll" id="ng"></div>
      <div class="stock panel" id="fl-stock"><div class="row" id="fl-stock-head"></div><div class="strip" id="fl-strip"></div></div></div>`);
    const me = v.me, cust = me.active;
    const [hi, ht] = nextHint(v);
    patch($('#fl-hint'), `<span class="hicon">${hi}</span><span>${ht}</span>`);
    $('#sc').className = 'scene theme-' + (me.theme || 'classic') + (me.dtype === 'cars' ? ' showroom' : '');
    patch($('#sc-sign'), esc((v.leaderboard.find((r) => r.id === v.you) || {}).name || 'My Shop').toUpperCase() + "'S " + esc(T(me.dtype).sign || ''));
    const listed = me.inventory.filter((i) => i.listed);
    let slots = '';
    for (let i = 0; i < 10; i++) {
      const it = listed[i];
      if (i >= me.display) slots += `<div class="slot locked"></div>`;
      else if (it) slots += `<div class="slot glow-${glowLevel(it)}" title="${esc(it.name)} — ${fmt(it.price)}">${ART.item(it, 64)}<span class="tag">${fmt(it.price)}</span><span class="snm">${esc(it.name)}</span></div>`;
      else slots += `<div class="slot empty"></div>`;
    }
    patch($('#sc-shelves'), slots);
    const decor = (me.decor || []).map((d, i) => d === 'sign' ? `<div class="decor" style="top:${120 + i * 10}px;right:14px;font:900 18px var(--sans);color:#ff4fd8;text-shadow:0 0 10px #ff4fd8;transform:rotate(-4deg)">OPEN</div>` : `<div class="decor" style="bottom:${31}%;left:${[4, 86, 16, 76][i % 4]}%">${DECOR[d] || ''}</div>`).join('');
    patch($('#sc-decor'), decor);
    if (cust) {
      const scc = $('#sc-cust'), same = scc._cid === cust.id;
      scc._cid = cust.id;
      patch(scc, `<div class="customer ${same ? 'stay' : ''} ${cust.mood < 25 ? 'mood-angry' : ''}">${ART.person(cust.look, cust.mood, 200)}</div>`);
      patch($('#sc-item'), `<div class="counter-item ${same ? 'stay' : ''} glow-${glowLevel(cust.item)}">${ART.item(cust.item, 128)}<div class="plate">${esc(cust.item.name)}<small>${esc(cust.item.catName)}</small></div></div>`);
      const last = cust.lines.filter((l) => l.who === 'them').slice(-1)[0];
      patch($('#sc-bubble'), last ? `<div class="bubble">${esc(last.text)}</div>` : '');
    } else {
      patch($('#sc-cust'), `<div class="empty-msg">${me.queue.length ? 'Next customer coming up…' : 'Waiting for customers…'}</div>`);
      $('#sc-cust')._cid = null;
      patch($('#sc-item'), ''); patch($('#sc-bubble'), '');
    }
    patch($('#sc-queue'), me.queue.length ? `<span class="qlabel">${me.queue.length} waiting</span>` + me.queue.map((q) => `<div class="q">${ART.person(q.look, 60, 48)}</div>`).join('') : '');
    negoPanel(v, $('#ng'));
    stockStrip(v);
  }

  // Bottom strip: everything you own, listable in one click without leaving the counter.
  function stockStrip(v) {
    const me = v.me;
    const listedN = me.inventory.filter((i) => i.listed).length;
    const unlisted = me.inventory.filter((i) => !i.listed && canList(v, i));
    patch($('#fl-stock-head'), `<h3 style="margin:0">Your stock</h3><span class="chip">${me.inventory.length}/${me.storage} stored</span><span class="chip">${listedN}/${me.display} on display</span>
      <span class="right"></span>${unlisted.length && listedN < me.display ? `<button class="btn sm primary" data-a="list-all">🏷️ List all (${Math.min(unlisted.length, me.display - listedN)}) <kbd>L</kbd></button>` : ''}
      <button class="btn sm" data-a="tab" data-t="inventory">Manage inventory →</button>`);
    const items = me.inventory.length ? me.inventory : [{ id: '__empty' }];
    patchList($('#fl-strip'), items, (it) => it.id, (it) => {
      if (it.id === '__empty') return `<div class="scard empty dim">Nothing in stock yet — buy from the seller at the counter.</div>`;
      const ok = canList(v, it);
      const action = it.repair ? `<div class="warn" style="font-size:11px">🔧 Workshop · ready day ${it.repair.until}</div>` : it.listed
        ? `<div class="good" style="font-weight:700">${fmt(it.price)} <span style="font-weight:400;font-size:11px">on sale</span></div><button class="btn sm ghost" data-a="unlist" data-id="${it.id}">Take down</button>`
        : !ok ? `<div class="warn" style="font-size:11px">Not your trade</div><button class="btn sm" data-a="bulk-one" data-id="${it.id}">Wholesale</button>`
        : listedN >= me.display ? `<div class="dim" style="font-size:11px">Display full</div>`
        : `<button class="btn sm primary" data-a="list" data-id="${it.id}">List ${fmt(suggestPrice(it))}</button>`;
      return `<div class="scard ${it.listed ? 'listed' : ''}"><div class="glow-${glowLevel(it)}">${ART.item(it, 48)}</div>
        <div class="scard-nm" title="${esc(it.name)}">${esc(it.name)}</div><div class="dim" style="font-size:10px">paid ${fmt(it.paid)} · est ${fmt(it.likely)}</div>${action}</div>`;
    });
  }

  function glowLevel(it) { return it.editionIdx >= 2 || it.rarity >= 5 ? 3 : it.editionIdx >= 1 || it.rarity >= 4 ? 2 : 1; }

  function negoPanel(v, el) {
    const me = v.me, c = me.active;
    if (!c) {
      ensure(el, 'idle', '<div id="ng-idle"></div>');
      const lc = me.lastCustomer;
      return patch($('#ng-idle'), `<h2>The counter</h2><p class="muted">Sellers walk in one at a time. Every dealer of your type meets the same sellers today — make the most of each one.</p>
        ${lc ? `<div class="card"><div class="dim" style="font-size:12px">Last customer: ${esc(lc.name)} ${lc.deal ? `— <span class="good">you bought it for ${fmt(lc.deal)}</span>` : ''}</div>${lc.lines.map((l) => `<div class="line ${l.who}" style="margin-top:4px">${esc(l.text)}</div>`).join('')}</div>` : ''}
        <div class="keys"><b>Shortcuts</b> <kbd>I</kbd> inspect <kbd>S</kbd> scan <kbd>E</kbd> expert <kbd>O</kbd> offer box <kbd>Enter</kbd> send offer <kbd>A</kbd> accept <kbd>W</kbd> walk away <kbd>L</kbd> list all <kbd>1</kbd>–<kbd>6</kbd> tabs</div>`);
    }
    const key = 'c-' + c.id;
    if (ensure(el, key, `<div id="ng-head"></div><div id="ng-meters"></div><div class="dialog" id="ng-dialog"></div>
        <div class="step"><div class="step-h"><span class="num">1</span>Look it over</div><div id="ng-item"></div><div class="tools" id="ng-tools"></div></div>
        <div class="step"><div class="step-h"><span class="num">2</span>Negotiate</div><div id="ng-offer"></div><div id="ng-persuade"></div></div>
        <div class="step decide"><div class="step-h"><span class="num">3</span>Decide</div><div id="ng-actions"></div></div>`)) {
      if (S.draft.offer[c.id] == null) S.draft.offer[c.id] = nice(c.item.likely * 0.55);
    }
    patch($('#ng-head'), `<div class="cust-head"><div class="grow"><div class="nm">${esc(c.name)}</div><div class="row wrap"><span class="chip">${esc(c.vibe)}</span>${c.persona ? `<span class="chip ed">${esc(c.persona)}</span>` : ''}${c.flagged ? '<span class="chip replica">⚠ Security: seems dishonest</span>' : ''}${c.lying ? '<span class="chip replica">⚠ Lying about condition</span>' : ''}${c.final ? '<span class="chip warn">Final offer</span>' : ''}</div>
      ${c.floor ? `<div class="mind">🔮 Your mentalist senses they'd go as low as <b>${fmt(c.floor[0])}–${fmt(c.floor[1])}</b></div>` : ''}</div>
      <div class="center"><div class="dim" style="font-size:11px">Asking</div><div style="font-family:var(--serif);font-size:30px;color:var(--bad)" class="money">${fmt(c.ask)}</div></div></div>`);
    const mood = c.mood, moodC = mood > 60 ? 'var(--good)' : mood > 30 ? 'var(--warn)' : 'var(--bad)';
    const pat = 100 * c.patience / c.patienceMax;
    patch($('#ng-meters'), `<div class="cols2" style="gap:10px"><div><div class="row" style="font-size:11px"><span class="muted">Mood</span><span class="right">${mood > 60 ? '😊' : mood > 30 ? '😐' : '😠'} ${c.moodExact ? mood : ''}</span></div><div class="meter"><i style="width:${Math.max(0, mood)}%;background:${moodC}"></i></div></div>
      <div><div class="row" style="font-size:11px"><span class="muted">Patience</span><span class="right">${Math.ceil(c.patience)}s</span></div><div class="meter"><i style="width:${Math.max(0, pat)}%;background:${pat > 40 ? 'var(--info)' : 'var(--bad)'}"></i></div></div></div>`);
    if (patch($('#ng-dialog'), c.lines.map((l) => `<div class="line ${l.who}">${esc(l.text)}</div>`).join(''))) { const d = $('#ng-dialog'); d.scrollTop = d.scrollHeight; }
    patch($('#ng-item'), itemDetail(c.item, c.ask, c.lastOffer));
    const t = me.tools, it = c.item;
    const known = { inspect: !!it.cond, scan: it.status !== 'unverified', expert: it.expert };
    const keyOf = { inspect: 'I', scan: 'S', expert: 'E' };
    const hasExpert = me.staff.some((x) => x.role === 'expert');
    const expBtn = hasExpert ? `<button class="btn exp" data-a="opinion" data-target="counter" ${it.opinion || it.expert || !me.expertLeft ? 'disabled' : ''} title="Free and instant. Can be wrong about very rare items.">🎓 Ask your expert <kbd>X</kbd><small>${it.opinion ? 'done ✓' : me.expertLeft > 100 ? 'free · unlimited' : 'free · ' + me.expertLeft + ' left today'}</small></button>` : '';
    patch($('#ng-tools'), expBtn + ['inspect', 'scan', 'expert'].map((k) => `<button class="btn" data-a="tool" data-tool="${k}" data-target="counter" ${known[k] ? 'disabled' : ''} title="${esc(t[k].desc)}">${{ inspect: '🔎', scan: '🧪', expert: '🎓' }[k]} ${t[k].name.split(' ')[0]} <kbd>${keyOf[k]}</kbd><small>${known[k] ? 'done ✓' : fmt(t[k].cost) + ' · ' + t[k].time + 's of patience'}</small></button>`).join(''));
    const off = S.draft.offer[c.id];
    const max = Math.max(c.ask, 10);
    patch($('#ng-offer'), `<div class="offerbox"><input type="number" id="offer-in" data-in="offer" data-cid="${c.id}" value="${off}" min="1"><button class="btn primary" data-a="offer">Send offer <kbd>Enter</kbd></button></div>
      <input type="range" id="offer-range" data-in="offer-range" data-cid="${c.id}" min="0" max="${max}" step="${max > 2000 ? 25 : 5}" value="${Math.min(off, max)}" style="width:100%">
      <div class="quick">${[0.4, 0.55, 0.7, 0.85].map((p) => `<button class="btn sm" data-a="offer-pct" data-p="${p}">${Math.round(p * 100)}% of est.</button>`).join('')}<button class="btn sm" data-a="offer-step" data-p="-0.05">−5%</button><button class="btn sm" data-a="offer-step" data-p="0.05">+5%</button></div>`);
    patch($('#ng-persuade'), `<div class="persuade">${Object.entries(v.persuade).map(([k, p]) => `<button class="btn sm" data-a="persuade" data-k="${k}" title="${esc(p.desc)}" ${c.persuaded.includes(k) ? 'disabled' : ''}>${esc(p.name)}</button>`).join('')}</div>`);
    const margin = it.likely - c.ask;
    patch($('#ng-actions'), `<div class="row"><button class="btn green grow" data-a="accept" ${c.ask > me.cash ? 'disabled' : ''}>Buy for ${fmt(c.ask)} <kbd>A</kbd></button><button class="btn red" data-a="walk">Walk away <kbd>W</kbd></button></div>
      <div style="font-size:12px;margin-top:6px" class="${margin > 0 ? 'good' : 'bad'}">At this price your estimated margin is ${margin >= 0 ? '+' : ''}${fmt(margin)} (${c.ask ? Math.round(100 * margin / c.ask) : 0}%).</div>
      ${me.inventory.length >= me.storage ? '<p class="bad">Storage full — you can’t buy until you sell or upgrade.</p>' : ''}`);
  }

  // Keyed list update: only changed entries are replaced, so lists don't flicker or lose input focus.
  function patchList(el, items, keyFn, htmlFn) {
    if (!el) return;
    const existing = new Map([...el.children].map((ch) => [ch.dataset.key, ch]));
    let prev = null;
    const firstRender = !el.children.length;
    for (const it of items) {
      const k = String(keyFn(it)), h = htmlFn(it);
      let node = existing.get(k);
      if (node) {
        existing.delete(k);
        const ae = document.activeElement;
        const typing = ae && /INPUT|SELECT|TEXTAREA/.test(ae.tagName) && ae.type !== 'checkbox' && node.contains(ae);
        if (node._h !== h && !typing) {
          const t = document.createElement('template'); t.innerHTML = h.trim();
          const nn = t.content.firstElementChild; nn.dataset.key = k; nn._h = h; nn.classList.add('noanim');
          node.replaceWith(nn); node = nn;
        }
      } else {
        const t = document.createElement('template'); t.innerHTML = h.trim();
        node = t.content.firstElementChild; node.dataset.key = k; node._h = h;
        if (firstRender) node.classList.add('noanim'); else node.classList.add('arrive');
      }
      const want = prev ? prev.nextElementSibling : el.firstElementChild;
      if (node !== want) el.insertBefore(node, want);
      prev = node;
    }
    existing.forEach((n) => n.remove());
  }

  function itemDetail(it, ask, offer) {
    const top = Math.max(it.high, ask || 0) * 1.08 || 1;
    const pos = (x) => (100 * x / top).toFixed(1) + '%';
    const cond = it.cond ? `<span class="good">${esc(it.cond)}</span> ✓` : `${esc(it.claimed)} <span class="warn">(claimed)</span>`;
    const auth = it.status === 'verified' ? '<span class="chip verified">✓ Authentic</span>' : it.status === 'replica' ? '<span class="chip replica">✗ Counterfeit</span>' : it.fakeable ? '<span class="chip unverified">? Unverified</span>' : '<span class="chip">Not usually faked</span>';
    const ed = it.edition ? `<span class="chip ed">${esc(it.edition)}</span>` : '<span class="dim">Unknown</span>';
    return `<div class="itemcard"><div class="pic glow-${glowLevel(it)}">${ART.item(it, 80)}</div><div>
      <div style="font-weight:700;font-size:16px">${esc(it.name)}</div><div class="muted" style="font-size:12px">${esc(it.catName)} · <span class="rar${it.rarity}">${'◆'.repeat(it.rarity)}</span></div>
      <dl class="facts" style="margin:6px 0 0"><dt>Condition</dt><dd>${cond}</dd><dt>Authenticity</dt><dd>${auth}</dd><dt>Edition</dt><dd>${ed}</dd>${it.modified != null ? `<dt>Modified</dt><dd>${it.modified ? '<span class="bad">Yes — aftermarket parts</span>' : 'No'}</dd>` : ''}</dl>
      ${it.hints.map((h) => `<div class="hint">“${esc(h)}”</div>`).join('')}
      ${it.opinion ? `<div class="hint" style="border-color:var(--info)">🎓 Your expert: “I'd say it's worth about <b>${fmt(it.opinion)}</b>.” <span class="dim">(experts can misjudge very rare pieces)</span></div>` : ''}</div></div>
      <div class="range"><div class="bar" style="left:${pos(it.low)};width:calc(${pos(it.high)} - ${pos(it.low)})"></div>
        <div class="mk li" style="left:${pos(it.likely)}"><span>likely ${fmt(it.likely)}</span></div>
        ${ask ? `<div class="mk ask" style="left:${pos(ask)}"><span>ask ${fmt(ask)}</span></div>` : ''}
        ${offer ? `<div class="mk off" style="left:${pos(offer)}"><span>you ${fmt(offer)}</span></div>` : ''}
        <div class="ends" style="left:${pos(it.low)}">${fmt(it.low)}</div><div class="ends" style="left:calc(${pos(it.high)} - 30px)">${fmt(it.high)}</div></div>
      <div class="dim" style="font-size:11px">Your estimate of resale value ${it.expert ? '(expert appraisal: ±8%)' : '— narrows as you investigate'}.</div>`;
  }

  // ---------- inventory
  function invTab(v, c) {
    ensure(c, 'inv', '<div id="inv-head"></div><div class="grid" id="inv-grid"></div>');
    const me = v.me, canSell = v.phase === 'morning' || v.phase === 'shop' || v.phase === 'report';
    const selIds = [...S.sel].filter((id) => me.inventory.find((i) => i.id === id));
    S.sel = new Set(selIds);
    const listedN = me.inventory.filter((i) => i.listed).length;
    patch($('#inv-head'), `<div class="row wrap" style="margin-bottom:12px"><h2 style="margin:0">Inventory</h2>
      <span class="chip">Display ${listedN}/${me.display}</span><span class="chip">Storage ${me.inventory.length}/${me.storage}</span>
      <span class="right"></span>${selIds.length ? `<span class="muted">${selIds.length} selected</span><button class="btn sm" data-a="sel-none">Clear</button>` : ''}
      <button class="btn sm" data-a="bulk" ${selIds.length && canSell ? '' : 'disabled'} title="The wholesaler inspects and pays ~45% of true value instantly">📦 Sell selected to wholesaler</button></div>
      ${!me.inventory.length ? '<div class="panel center muted" style="padding:40px">Nothing in stock yet. Buy items from sellers on the shop floor, private offers or at auction.</div>' : ''}`);
    const t = me.tools;
    const okCat = (it) => me.cats.includes(it.cat);
    patchList($('#inv-grid'), me.inventory, (it) => it.id, (it) => {
      const off = !okCat(it);
      const pd = S.draft.price[it.id] ?? (it.listed ? it.price : nice(it.likely * 1.2));
      const profit = (it.listed ? it.price : pd) - it.paid;
      return `<div class="icard ${it.listed ? 'listed' : ''} ${S.sel.has(it.id) ? 'sel' : ''}">
        <input type="checkbox" class="pick" data-in="sel" data-id="${it.id}" ${S.sel.has(it.id) ? 'checked' : ''}>
        <div class="top"><div class="pic glow-${glowLevel(it)}">${ART.item(it, 64)}</div><div>
          <div class="nm">${esc(it.name)}</div><div class="meta">${esc(it.catName)} · <span class="rar${it.rarity}">${'◆'.repeat(it.rarity)}</span> · ${it.days}d held</div>
          <div class="row wrap" style="gap:4px;margin-top:3px"><span class="chip ${it.status}">${it.status}</span><span class="chip">${esc(it.cond || it.claimed + '?')}</span>${it.edition && it.editionIdx > 0 ? `<span class="chip ed">${esc(it.edition)}</span>` : ''}</div></div></div>
        <div class="est"><span>Est. <b>${fmt(it.likely)}</b> <span class="dim">(${fmt(it.low)}–${fmt(it.high)})</span></span><span class="dim">Paid ${fmt(it.paid)}</span></div>
        <div class="row"><input type="number" id="price-${it.id}" data-in="price" data-id="${it.id}" value="${pd}" style="width:96px">
          <button class="btn sm ${it.listed ? '' : 'primary'}" data-a="list" data-id="${it.id}" ${canSell && !off ? '' : 'disabled'} title="${off ? 'Outside your dealership type' : ''}">${it.listed ? 'Update' : 'List'}</button>
          ${it.listed ? `<button class="btn sm" data-a="unlist" data-id="${it.id}">Unlist</button>` : ''}
          <span class="right ${profit >= 0 ? 'good' : 'bad'}" style="font-size:12px">${profit >= 0 ? '+' : ''}${fmt(profit)}</span></div>
        <div class="row wrap" style="gap:4px">${[1.0, 1.15, 1.3, 1.5].map((m) => `<button class="btn sm ghost" data-a="price-chip" data-id="${it.id}" data-m="${m}">×${m}</button>`).join('')}</div>
        <div class="row wrap" style="gap:4px">${!it.cond ? `<button class="btn sm" data-a="tool" data-tool="inspect" data-target="${it.id}" ${canSell ? '' : 'disabled'}>🔎 ${fmt(t.inspect.cost)}</button>` : ''}
          ${it.status === 'unverified' ? `<button class="btn sm" data-a="tool" data-tool="scan" data-target="${it.id}" ${canSell ? '' : 'disabled'}>🧪 ${fmt(t.scan.cost)}</button>` : ''}
          ${!it.expert ? `<button class="btn sm" data-a="tool" data-tool="expert" data-target="${it.id}" ${canSell ? '' : 'disabled'}>🎓 ${fmt(t.expert.cost)}</button>` : ''}
          ${it.repairQuote && !it.repair ? `<button class="btn sm" data-a="repair" data-id="${it.id}" ${canSell ? '' : 'disabled'} title="Restore to ${esc(it.repairQuote.toLabel)} in ${it.repairQuote.days} day(s)">🔧 Repair ${fmt(it.repairQuote.cost)} · ${it.repairQuote.days}d</button>` : ''}
          ${me.staff.some((x) => x.role === 'expert') && !it.opinion && !it.expert ? `<button class="btn sm" data-a="opinion" data-target="${it.id}" ${canSell && me.expertLeft ? '' : 'disabled'}>🎓 Ask expert</button>` : ''}
          ${(v.phase === 'morning' || v.phase === 'shop') && !me.consigned ? `<button class="btn sm" data-a="consign" data-id="${it.id}" title="Sell at tonight's auction to rivals (10% fee). Starting bid = the price box.">🔨 Consign</button>` : ''}</div>
        ${it.repair ? `<div class="chip unverified" style="align-self:flex-start">🔧 In the workshop → ${esc(['Brand New', 'Excellent', 'Good'][it.repair.to])} on day ${it.repair.until}</div>` : ''}
        ${it.opinion ? `<div style="font-size:11px" class="muted">🎓 Expert says ≈ ${fmt(it.opinion)}</div>` : ''}
        ${off ? `<div class="warn" style="font-size:11px">Not your trade (${esc(it.catName)}) — wholesale it or consign it to the auction.</div>` : ''}
        <div class="dim" style="font-size:11px">${esc(it.source)}</div></div>`;
    });
  }

  // ---------- market street
  function streetTab(v, c) {
    ensure(c, 'street', '<div id="st"></div>');
    if (v.phase !== 'shop') return patch($('#st'), '<div class="panel center muted" style="padding:40px">Rival shops are closed until shop hours.</div>');
    patch($('#st'), `<h2>Market Street</h2><p class="muted">Every rival's display, live. Buyers compare these prices with yours — and you can buy any listed item outright.</p>` +
      (v.street || []).map((s) => {
        const idx = v.leaderboard.findIndex((r) => r.id === s.id);
        return `<div class="street-store panel"><div class="row"><span class="swatch theme-${s.theme}" style="background:var(--wall)"></span><h3 style="margin:0">${esc(s.name)}</h3><span class="chip">${T(s.dtype).icon} ${esc(T(s.dtype).name)}</span><span class="dim">#${idx + 1} · ${s.items.length} on display</span></div>
        <div class="street-items" style="margin-top:8px">${s.items.length ? s.items.map((it) => `<div class="sitem"><div class="glow-${glowLevel(it)}">${ART.item(it, 48)}</div><div style="min-width:0">
          <div style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(it.name)}</div>
          <div style="font-size:11px" class="muted">${esc(it.cond || it.claimed + '?')} · <span class="chip ${it.status}" style="padding:0 5px">${it.status}</span></div>
          <div class="row" style="margin-top:4px"><b class="gold">${fmt(it.price)}</b><span class="dim" style="font-size:10px">est ${fmt(it.likely)}</span><button class="btn sm right" data-a="buy-rival" data-owner="${s.id}" data-id="${it.id}" ${it.price > v.me.cash || !v.me.cats.includes(it.cat) ? 'disabled' : ''} title="${v.me.cats.includes(it.cat) ? '' : 'Outside your trade'}">Buy</button></div></div></div>`).join('') : '<span class="dim">Empty shelves.</span>'}</div></div>`;
      }).join(''));
  }

  // ---------- business
  function bizTab(v, c) {
    ensure(c, 'biz', '<div id="biz"></div>');
    const me = v.me, open = v.phase !== 'auction' && v.phase !== 'final';
    const ups = Object.entries(v.upgrades).map(([k, u]) => {
      const lvl = me.upgrades[k], maxed = lvl >= u.costs.length, cost = u.costs[lvl];
      return `<div class="card upg"><div class="row"><span style="font-size:22px">${UP_ICON[k]}</span><b class="grow">${esc(u.name)}</b><div class="pips">${u.costs.map((_, i) => `<i class="${i < lvl ? 'on' : ''}"></i>`).join('')}</div></div>
        <div class="muted" style="font-size:12px">${esc(u.desc)}</div>
        ${k === 'specialty' && !maxed ? sel('spec', S.draft.spec, [['', 'Choose category…'], ...Object.entries(v.market).filter(([ck]) => me.cats.includes(ck)).map(([ck, m]) => [ck, m.name])]) : ''}
        ${k === 'specialty' && me.specialty ? `<div class="gold">Specialty: ${esc(v.market[me.specialty].name)}</div>` : ''}
        <button class="btn ${maxed ? '' : 'primary'} sm" data-a="upgrade" data-k="${k}" ${maxed || !open || cost > me.cash ? 'disabled' : ''}>${maxed ? 'Max level' : 'Upgrade · ' + fmt(cost)}</button></div>`;
    }).join('');
    patch($('#biz'), `<div class="cols2"><div><h2>Upgrades</h2><div class="ugrid">${ups}</div></div>
      <div class="col"><div class="panel"><h3>Staff</h3><p class="muted" style="margin:0">${me.staff.length}/${me.maxStaff} specialists employed. <a class="gold" data-a="tab" data-t="staff" style="cursor:pointer">Manage staff →</a></p></div>
      <div class="panel"><h3>Finance</h3><div class="row wrap"><span>Loan: <b class="${me.loan ? 'bad' : ''}">${fmt(me.loan)}</b> / ${fmt(me.maxLoan)} · 4% interest per day</span></div>
        <div class="row wrap" style="margin-top:8px">${[5000, 10000, 20000].map((a) => `<button class="btn sm" data-a="loan" data-amt="${a}" ${!open || me.loan + a > me.maxLoan ? 'disabled' : ''}>Borrow ${fmt(a)}</button>`).join('')}
        <button class="btn sm green" data-a="repay" data-amt="${me.loan}" ${!open || !me.loan || !me.cash ? 'disabled' : ''}>Repay all</button></div></div>
      <div class="panel"><h3>Today so far</h3><table class="t">${dayRows(me.day)}</table></div></div></div>`);
  }
  function staffTab(v, c) {
    ensure(c, 'staff', '<div id="stf"></div>');
    const me = v.me, open = v.phase !== 'auction' && v.phase !== 'final';
    const wl = v.weekDaysLeft, full = me.staff.length >= me.maxStaff;
    const weekly = me.staff.reduce((a, s) => a + v.wages[s.stars], 0);
    const cards = Object.entries(v.employees).map(([role, e]) => {
      const cur = me.staff.find((s) => s.role === role);
      const tiers = [1, 2, 3].map((st) => {
        const due = nice((v.wages[st] - (cur ? v.wages[cur.stars] : 0)) * wl / 7);
        let btn;
        if (cur && cur.stars >= st) btn = `<span class="chip verified">${cur.stars === st ? 'Current' : '✓'}</span>`;
        else if (!cur && full) btn = `<span class="dim" style="font-size:11px">Staff full</span>`;
        else btn = `<button class="btn sm ${cur ? '' : 'primary'}" data-a="hire" data-role="${role}" data-stars="${st}" ${!open || due > me.cash ? 'disabled' : ''} title="Pay ${fmt(due)} now for the rest of this week">${cur ? 'Promote' : 'Hire'} · ${fmt(due)}</button>`;
        return `<div class="tier ${cur && cur.stars >= st ? 'on' : ''}"><span class="stars">${'★'.repeat(st)}<span class="dim">${'★'.repeat(3 - st)}</span></span>
          <div class="grow"><b>${fmt(v.wages[st])}</b><span class="dim">/week</span><div class="dim" style="font-size:11px">${esc(e.stars[st - 1])}</div></div>${btn}</div>`;
      }).join('');
      return `<div class="card emp ${cur ? 'hired' : ''}"><div class="row"><span style="font-size:26px">${e.icon}</span><div class="grow"><b>${esc(e.name)}</b>
          ${cur ? `<div class="good" style="font-size:12px">${esc(cur.name)} · ${'★'.repeat(cur.stars)}</div>` : ''}</div>
          ${cur ? `<button class="btn sm red" data-a="fire" data-id="${cur.id}" ${open ? '' : 'disabled'}>Let go</button>` : ''}</div>
        <div class="muted" style="font-size:12px;margin:4px 0 6px">${esc(e.desc)}</div>${tiers}</div>`;
    }).join('');
    patch($('#stf'), `<div class="banner"><span style="font-size:26px">👥</span><div class="grow"><b style="font-family:var(--serif);font-size:18px">Hire specialists — up to ${me.maxStaff}</b>
        <div class="muted">${me.staff.length}/${me.maxStaff} employed · weekly wages ${fmt(weekly)} · paid every 7 days (day 1, 8, 15…). This week has <b>${wl}</b> day${wl > 1 ? 's' : ''} left, so hiring now costs ${wl}/7 of a week's wage.</div></div></div>
      <div class="egrid">${cards}</div>`);
  }
  function lookFrom(name) {
    let h = 0; for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    const pick = (a) => a[(h = (h * 1103515245 + 12345) >>> 0) % a.length];
    return { skin: pick(['#f5d0b5', '#e8b48f', '#c98d63', '#a46a43', '#7a4a2a']), hair: pick(['#1b1b1b', '#3b2a1a', '#6b4423', '#d8b25a', '#9e9e9e']), style: h % 6, shirt: pick(['#1e88e5', '#43a047', '#8e24aa', '#e53935', '#00897b']), glasses: h % 3 === 0, beard: h % 5 === 0 };
  }
  function dayRows(d) {
    const r = [['Sales revenue', d.revenue, 'good'], ['Purchases', -d.spent, 'bad'], ['Tools & research', -d.tools, 'bad'], ['Wages & hiring', -d.wages, 'bad'], ['Upgrades', -d.upgrades, 'bad'], ['Loan interest', -d.interest, 'bad'], ['Refunds', -d.refunds, 'bad']];
    return r.filter((x) => x[1]).map(([l, n, c]) => `<tr><td>${l}</td><td class="${c}" style="text-align:right">${fmt(n)}</td></tr>`).join('') || '<tr><td class="dim">No activity yet.</td></tr>';
  }

  // ---------- market & news
  function marketTab(v, c) {
    ensure(c, 'market', '<div id="mk"></div>');
    const r = v.me.research;
    const rows = Object.entries(v.market).sort((a, b) => b[1].mult - a[1].mult).map(([k, m]) => {
      const d = m.mult - m.prev, w = Math.min(100, m.mult / 2 * 100);
      const fc = r && r.tomorrow ? r.tomorrow[k] : null;
      return `<div class="mrow"><span><span class="swatch" style="background:${m.color}"></span> ${esc(m.name)}</span>
        <div class="mbar"><i style="width:${w}%;background:${m.color}"></i><span class="mid"></span></div>
        <span class="money" style="text-align:right"><b>${m.mult.toFixed(2)}×</b> <span class="${d > 0.005 ? 'good' : d < -0.005 ? 'bad' : 'dim'}">${d > 0.005 ? '▲' : d < -0.005 ? '▼' : '•'}</span>${fc != null ? `<div class="${fc > m.mult ? 'good' : 'bad'}" style="font-size:10px">→ ${fc.toFixed(2)}${r.exact ? '' : '?'}</div>` : ''}</span></div>`;
    }).join('');
    patch($('#mk'), `<div class="cols2"><div class="panel"><h2>Demand index</h2><p class="muted" style="margin-top:0">1.00× is normal. Prices for every item in a category scale with its demand. Each sale nudges demand down a little.</p>${rows}
      <div class="row" style="margin-top:10px"><button class="btn sm primary" data-a="research" ${r && r.exact || v.phase === 'auction' ? 'disabled' : ''}>📊 Buy market research · $800</button><span class="dim" style="font-size:12px">Exact forecast for tomorrow.</span></div></div>
      <div class="col"><div class="panel"><h3>Today's news</h3>${v.events.length ? v.events.map((e) => `<div class="news"><b>${esc(e.name)}</b><div class="muted">${esc(e.desc)}</div></div>`).join('') : '<p class="dim">A quiet day on the market.</p>'}
        <h3 style="margin-top:10px">Word on the street</h3>${v.rumors.length ? v.rumors.map((x) => `<div class="news rumor">${esc(x)}</div>`).join('') : '<p class="dim">No rumors about tomorrow.</p>'}
        ${r && r.events && r.events.length ? `<div class="news"><b>Research:</b> tomorrow brings ${r.events.map(esc).join(', ')}.</div>` : ''}</div>
      <div class="panel chart"><h3>Net worth race</h3>${nwChart(v)}</div></div></div>`);
  }
  function nwChart(v) {
    const ids = v.leaderboard.map((r) => r.id);
    const series = ids.map((id) => [v.startCash || 25000, ...v.history.map((h) => h.nw[id] ?? 0), v.leaderboard.find((r) => r.id === id).net_worth]);
    const n = series[0].length, all = series.flat(), mx = Math.max(...all, (v.startCash || 25000) * 1.2), mn = Math.min(...all, 0);
    const X = (i) => 40 + (i / Math.max(1, n - 1)) * 540, Y = (y) => 190 - (y - mn) / (mx - mn) * 170;
    const order = v.leaderboard.map((r) => r.id);
    // end labels: keep them at least 12px apart so close races stay readable
    const ly = series.map((s, k) => [k, Y(s[n - 1])]).sort((a, b) => a[1] - b[1]);
    for (let i = 1; i < ly.length; i++) ly[i][1] = Math.max(ly[i][1], ly[i - 1][1] + 12);
    const labelY = {}; ly.forEach(([k, y]) => labelY[k] = y);
    const lines = series.map((s, k) => { const r = v.leaderboard[k]; const col = COLORS[k % 8]; return `<polyline fill="none" stroke="${col}" stroke-width="${r.id === v.you ? 3.5 : 2}" points="${s.map((y, i) => X(i) + ',' + Y(y)).join(' ')}" opacity="${r.id === v.you ? 1 : .75}"/><text x="${X(n - 1) + 4}" y="${labelY[k] + 4}" fill="${col}" font-size="11" font-weight="${r.id === v.you ? 700 : 400}">${esc(r.name.split(' ').slice(-1)[0])}</text>`; }).join('');
    const grid = [0, 0.5, 1].map((t) => { const y = mn + (mx - mn) * t; return `<line x1="40" x2="580" y1="${Y(y)}" y2="${Y(y)}" stroke="#ffffff14"/><text x="2" y="${Y(y) + 4}" fill="#7d6f5d" font-size="10">${fmt(y)}</text>`; }).join('');
    void order;
    return `<svg viewBox="0 0 650 230">${grid}${lines}<text x="40" y="206" fill="#7d6f5d" font-size="10">Start</text><text x="560" y="206" fill="#7d6f5d" font-size="10">Now</text></svg>`;
  }

  // ---------- morning briefing
  function briefTab(v, c) {
    ensure(c, 'brief', '<div id="br"></div>');
    const me = v.me, r = me.research;
    const movers = Object.entries(v.market).map(([k, m]) => [m.name, m.mult - m.prev, m.mult]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 4);
    patch($('#br'), `<div class="banner"><span style="font-size:30px">☀</span><div class="grow"><b style="font-family:var(--serif);font-size:20px">Good morning — Day ${v.day} of ${v.days}</b><div class="muted">Price your stock, hire staff and upgrade before the doors open. ${v.days - v.day === 0 ? '<b class="warn">This is the final day!</b>' : ''}</div></div>
      <button class="btn primary lg" data-a="ready" ${me.ready ? 'disabled' : ''}>${me.ready ? 'Waiting for others…' : 'Open the doors →'}</button></div>
      <div class="cols3"><div class="panel"><h3>Headlines</h3>${v.events.length ? v.events.map((e) => `<div class="news"><b>${esc(e.name)}</b><div class="muted">${esc(e.desc)}</div></div>`).join('') : '<p class="dim">No major news today.</p>'}
        <h3 style="margin-top:10px">Rumors for tomorrow</h3>${v.rumors.length ? v.rumors.map((x) => `<div class="news rumor">${esc(x)}</div>`).join('') : '<p class="dim">Nothing on the grapevine.</p>'}</div>
      <div class="panel"><h3>Market movers</h3>${movers.map(([n, d, m]) => `<div class="row"><span class="grow">${esc(n)}</span><b>${m.toFixed(2)}×</b><span class="${d > 0 ? 'good' : 'bad'}" style="width:60px;text-align:right">${d > 0 ? '▲' : '▼'} ${Math.abs(d * 100).toFixed(0)}%</span></div>`).join('')}
        ${r ? `<div class="news" style="margin-top:10px"><b>${r.exact ? 'Research report' : 'Researcher’s hunch'}</b><div class="muted">Tomorrow: ${Object.entries(r.tomorrow).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, x]) => `${esc(v.market[k].name)} ${x.toFixed(2)}×`).join(', ')}${r.events.length ? ' · Event: ' + r.events.map(esc).join(', ') : ''}</div></div>` : `<button class="btn sm" style="margin-top:10px" data-a="research">📊 Buy research · $800</button>`}</div>
      <div class="panel"><h3>Your shop</h3><table class="t"><tr><td>Cash</td><td class="gold">${fmt(me.cash)}</td></tr><tr><td>On display</td><td>${me.inventory.filter((i) => i.listed).length}/${me.display}</td></tr><tr><td>Stock</td><td>${me.inventory.length}/${me.storage}</td></tr><tr><td>Staff wages</td><td>${fmt(me.staff.reduce((a, s) => a + v.wages[s.stars], 0))}/week</td></tr><tr><td>Staff</td><td>${me.staff.length}/${me.maxStaff} <a class="gold" data-a="tab" data-t="staff" style="cursor:pointer">hire →</a></td></tr></table>
        ${me.inventory.some((i) => !i.listed) && me.inventory.filter((i) => i.listed).length < me.display ? '<p class="warn">You have empty display slots and unlisted stock.</p>' : ''}</div></div>`);
  }

  // ---------- auction
  function auctionTab(v, c) {
    ensure(c, 'auction', `<div class="hall"><div class="stage" id="au-stage"></div><div class="bidbox"><div class="panel" id="au-bid"></div><div class="panel" id="au-info"></div><div class="panel" id="au-hist"></div></div></div>`);
    const a = v.auction;
    if (!a) return;
    const lot = a.lot;
    if (!lot) {
      ensure($('#au-stage'), 'nolot', `<div class="curtain l"></div><div class="curtain r"></div><div class="lot-title">The auctioneer takes the stand…</div><div class="pedestal"></div>`);
      patch($('#au-bid'), `<h2>Tonight: ${a.count} lots</h2>${a.upcoming.map((t, i) => `<div>${i + 1}. ${esc(t)}</div>`).join('')}`);
      patch($('#au-info'), ''); patch($('#au-hist'), '');
      return;
    }
    const lb = v.leaderboard;
    const paddles = lb.map((r, i) => `<div class="paddle ${lot.bidder === r.id ? 'up' : ''}"><b style="${r.id === v.you ? 'border-color:var(--gold)' : ''}">${i + 1}</b><span>${esc(r.name.split(' ')[0])}</span></div>`).join('');
    const stg = $('#au-stage');
    ensure(stg, 'lot-' + lot.id, `<div class="curtain l"></div><div class="curtain r"></div><div class="lot-title"></div><div class="lot-items"></div><div class="pedestal"></div><div class="paddles"></div><div class="au-sold"></div>`);
    patch($('.lot-title', stg), `Lot ${a.index + 1}/${a.count}: ${esc(lot.title)}`);
    patch($('.lot-items', stg), lot.items.map((it) => `<div class="glow-${glowLevel(it)}">${ART.item(it, lot.items.length > 1 ? 96 : 192)}</div>`).join(''));
    patch($('.paddles', stg), paddles);
    patch($('.au-sold', stg), lot.closed ? `<div class="sold"><h1>${lot.result && lot.result.winner ? 'SOLD!' : 'NO SALE'}</h1>${lot.result && lot.result.winner ? `<div style="font-size:20px">to <b class="gold">${esc(lot.result.winner)}</b> for ${fmt(lot.result.amount)}</div>` : ''}</div>` : '');
    const mine = lot.bidder === v.you, own = lot.seller === v.you || !lot.items.some((it) => v.me.cats.includes(it.cat));
    const offType = lot.seller !== v.you && own;
    const minB = lot.minBid, left = lot.left, R = 30, circ = 2 * Math.PI * R;
    const frac = Math.min(1, left / 18);
    const bidDraft = S.draft.bid || '';
    patch($('#au-bid'), `<div class="row"><div class="grow"><div class="dim" style="font-size:12px">${lot.bidder ? 'Current bid' : 'Starting bid'}</div>
        <div class="bignum ${lot.bid ? 'bump' : ''}">${fmt(lot.bid || lot.start)}</div>
        <div>${lot.bidder ? (mine ? '<b class="good">You are the highest bidder!</b>' : `High bidder: <b>${esc(lot.bidderName)}</b>`) : '<span class="muted">No bids yet</span>'}</div></div>
        <div class="timer" id="au-timer"></div></div>
      ${offType ? `<p class="warn">Outside your trade (${T(v.me.dtype).icon} ${esc(T(v.me.dtype).name)}) — you can watch, but not bid.</p>` : own ? '<p class="warn">This is your consigned lot — you receive the winning bid minus a 10% fee.</p>' : ''}
      <div class="row" style="margin-top:10px"><button class="btn primary lg grow" data-a="bid" data-amt="${minB}" ${lot.closed || mine || own || minB > v.me.cash ? 'disabled' : ''}>Bid ${fmt(minB)}</button>
        <button class="btn" data-a="bid" data-amt="${nice(minB * 1.15)}" ${lot.closed || mine || own || nice(minB * 1.15) > v.me.cash ? 'disabled' : ''}>${fmt(nice(minB * 1.15))}</button></div>
      <div class="row" style="margin-top:6px"><input type="number" id="bid-in" data-in="bid" value="${esc(bidDraft)}" placeholder="Custom bid" style="flex:1"><button class="btn" data-a="bid-custom" ${lot.closed || mine || own ? 'disabled' : ''}>Bid</button></div>
      <div class="dim" style="font-size:11px;margin-top:6px">You have ${fmt(v.me.cash)} · late bids extend the clock to 5s · storage ${v.me.inventory.length}/${v.me.storage}</div>`);
    patch($('#au-timer'), `<svg width="74" height="74"><circle cx="37" cy="37" r="${R}" stroke="#ffffff18" stroke-width="6" fill="none"/><circle cx="37" cy="37" r="${R}" stroke="${left < 5 ? '#ff6b6b' : '#e5b84b'}" stroke-width="6" fill="none" stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - frac)}" stroke-linecap="round"/></svg><b>${lot.closed ? '—' : Math.ceil(left)}</b>`);
    patch($('#au-info'), `<h3>Catalogue ${lot.scouted ? `<span class="chip verified" style="font-family:var(--sans)">🔭 Scout report (${'★'.repeat(lot.scouted)})</span>` : ''}</h3><div class="row"><span>Estimate</span><b class="right">${fmt(lot.low)} – ${fmt(lot.high)}</b></div>${lot.sellerName ? `<div class="muted">Consigned by ${esc(lot.sellerName)}</div>` : ''}
      ${lot.items.map((it) => `<div class="row" style="margin-top:6px;font-size:12px"><b class="grow">${esc(it.name)}</b><span class="chip">${esc(it.cond || it.claimed + '?')}</span><span class="chip ${it.status}">${it.status}</span>${it.edition ? `<span class="chip ed">${esc(it.edition)}</span>` : '<span class="chip">edition ?</span>'}</div>${it.hints.map((h) => `<div class="hint">“${esc(h)}”</div>`).join('')}`).join('')}`);
    patch($('#au-hist'), `<h3>Bids</h3><div class="bids">${lot.bids.slice().reverse().map((b) => `<div><b class="${b.pid === v.you ? 'gold' : ''}">${esc(b.name)}</b> <span class="right">${fmt(b.amount)}</span></div>`).join('') || '<span class="dim">—</span>'}</div>
      ${a.results.length ? `<h3 style="margin-top:10px">Results</h3>${a.results.map((r) => `<div style="font-size:12px">${esc(r.title)}: ${r.result.winner ? `<b>${esc(r.result.winner)}</b> ${fmt(r.result.amount)}` : '<span class="dim">no sale</span>'}</div>`).join('')}` : ''}
      ${a.upcoming.length ? `<h3 style="margin-top:10px">Coming up</h3>${a.upcoming.map((t) => `<div class="dim" style="font-size:12px">${esc(t)}</div>`).join('')}` : ''}`);
  }

  // ---------- report & final
  function reportTab(v, c) {
    ensure(c, 'report', '<div id="rp"></div>');
    const r = v.report || {}, me = v.me;
    const delta = (r.end_nw || 0) - (r.start_nw || 0);
    patch($('#rp'), `<div class="banner"><span style="font-size:28px">📒</span><div class="grow"><b style="font-family:var(--serif);font-size:20px">Day ${v.day} closed</b><div class="muted">Net worth ${fmt(r.start_nw)} → <b>${fmt(r.end_nw)}</b> <span class="${delta >= 0 ? 'good' : 'bad'}">(${delta >= 0 ? '+' : ''}${fmt(delta)})</span></div></div>
      <button class="btn primary lg" data-a="ready" ${me.ready ? 'disabled' : ''}>${me.ready ? 'Waiting for others…' : 'Next day →'}</button></div>
      <div class="cols2"><div class="panel"><h3>Profit & loss</h3><table class="t">${dayRows(r)}<tr><td>Items bought / sold</td><td style="text-align:right">${r.bought || 0} / ${r.sold || 0}</td></tr><tr><td>Reputation</td><td style="text-align:right">${r.rep}</td></tr></table></div>
      <div class="panel chart"><h3>Net worth race</h3>${nwChart(v)}</div></div>`);
  }

  function finalTab(v, c) {
    ensure(c, 'final', '<div id="fn"></div>');
    const f = v.final; if (!f) return;
    const rows = f.rows, me = rows.find((r) => r.id === v.you);
    const top = [rows[1], rows[0], rows[2]].filter(Boolean);
    const H = { 1: 150, 2: 110, 3: 80 }, CL = { 1: 'linear-gradient(#ffe7a3,#e5b84b)', 2: 'linear-gradient(#eceff1,#b0bec5)', 3: 'linear-gradient(#e6b48a,#b07d4c)' };
    const aw = S.award;
    patch($('#fn'), `<div class="center"><h1 style="font-size:40px">${me && me.place === 1 ? '🏆 You win!' : 'Final results'}</h1><p class="muted">True values of every item are now revealed. Inventory counts at 80% (liquidation).</p></div>
      <div class="podium">${top.map((r) => `<div class="pl"><div style="font-weight:700">${esc(r.name)}</div><div class="gold">${fmt(r.net_worth)}</div><div class="blk" style="height:${H[r.place]}px;background:${CL[r.place]}">${r.place}</div></div>`).join('')}</div>
      <div class="cols2"><div class="panel"><table class="t"><tr><th>#</th><th>Dealer</th><th>Cash</th><th>Stock (true)</th><th>Assets</th><th>Loan</th><th>Net worth</th></tr>
        ${rows.map((r) => `<tr style="${r.id === v.you ? 'background:#e5b84b18' : ''}"><td>${r.place}</td><td>${T(r.dtype).icon} ${esc(r.name)}${r.is_ai ? ' <span class="chip">AI</span>' : ''}</td><td>${fmt(r.cash)}</td><td>${fmt(r.inventory)} <span class="${r.inventory >= r.book * 0.8 ? 'good' : 'bad'}" style="font-size:10px">(book ${fmt(r.book * 0.8)})</span></td><td>${fmt(r.assets)}</td><td class="bad">${r.loan ? fmt(-r.loan) : ''}</td><td class="gold"><b>${fmt(r.net_worth)}</b></td></tr>`).join('')}</table></div>
      <div class="col"><div class="panel"><h3>Awards</h3>${f.awards.map((a) => `<div class="row"><b class="grow">${esc(a.title)}</b><span>${esc(a.name)}</span><span class="dim">${esc(a.value)}</span></div>`).join('') || '<span class="dim">—</span>'}</div>
        ${me ? `<div class="panel"><h3>Your match</h3><table class="t"><tr><td>Items bought / sold</td><td>${me.stats.bought} / ${me.stats.sold}</td></tr><tr><td>Fakes caught / bought</td><td>${me.stats.fakes_caught} / ${me.stats.fakes_bought}</td></tr><tr><td>Auction wins</td><td>${me.stats.auction_wins}</td></tr><tr><td>Best flip</td><td>${fmt(me.stats.best_flip)} ${esc(me.stats.best_flip_name)}</td></tr></table>
          ${aw ? `<p class="gold">+${aw.gained} XP${aw.levelUp ? ` · LEVEL UP → ${aw.level}` : ''}</p>${aw.new.length ? `<p>New achievements: ${aw.new.map((n) => `<span class="chip ed">🏅 ${esc(n)}</span>`).join(' ')}</p>` : ''}` : `<p class="dim">${S.sess && S.awarded[S.sess.room + S.sess.pid] ? 'Progress saved to your profile.' : 'Saving progress…'}</p>`}</div>` : ''}
        <div class="panel chart"><h3>Net worth race</h3>${nwChart(v)}</div>
        <button class="btn primary lg" data-a="final-menu">Back to main menu</button></div></div>`);
  }

  // ---------- popups
  function popsHTML(v) {
    let h = '';
    const po = v.privateOffer;
    if (po && v.phase === 'shop') {
      const it = po.item;
      h += `<div class="pop private"><div class="row"><b class="grow" style="color:var(--purple)">💌 PRIVATE OFFER</b><span class="warn">${Math.ceil(po.left)}s</span></div>
        <div class="row" style="margin-top:6px"><div class="glow-${glowLevel(it)}">${ART.item(it, 64)}</div><div class="grow"><b>${esc(it.name)}</b><div class="dim" style="font-size:12px">${esc(it.cond || it.claimed)} · ${it.status} · est ${fmt(it.low)}–${fmt(it.high)}</div></div></div>
        <div class="row" style="margin-top:6px"><span class="dim" style="font-size:12px">First dealer to claim wins.</span>${v.me.cats.includes(it.cat) ? `<button class="btn primary right" data-a="claim" data-id="${po.id}" ${po.price > v.me.cash ? 'disabled' : ''}>Claim · ${fmt(po.price)}</button>` : '<span class="right dim">Not your trade</span>'}</div></div>`;
    }
    for (const o of (v.me && v.me.buyerOffers) || []) {
      h += `<div class="pop"><div class="row"><div class="avatar">${ART.person(o.look, 70, 40)}</div><div class="grow"><b>${esc(o.name)}</b> <span class="dim">wants your</span> <b>${esc(o.itemName)}</b><div style="font-size:12px">Listed ${fmt(o.price)} · offers <b class="gold">${fmt(o.offer)}</b></div></div><span class="warn">${Math.ceil(o.left)}s</span></div>
        <div class="row" style="margin-top:6px"><button class="btn green grow" data-a="buyer" data-id="${o.id}" data-yes="1">Sell for ${fmt(o.offer)}</button><button class="btn" data-a="buyer" data-id="${o.id}" data-yes="0">Decline</button></div></div>`;
    }
    if (v.paused) h += `<div class="pop"><b>Game paused.</b> <button class="btn sm primary" data-a="pause">Resume</button></div>`;
    return h;
  }

  // ------------------------------------------------------------------ pre-game instructions
  function introPages(v) {
    const solo = v.settings.solo, me = v.me || (v.lobby || []).find((p) => p.id === v.you) || {};
    const t = T((v.settings.type_rule !== 'free' ? v.settings.type_rule : me.dtype) || 'general');
    const start = fmt(v.startCash || 25000), days = v.days || v.settings.days;
    const art = (k, i) => ART.item({ kind: k, variant: 'abcd'[i % 4], condIdx: 1 }, 48);
    return [
      { title: 'Welcome to The Dealership', body: `
        <div class="intro-art">${['watch', 'guitar', 'sedan', 'painting', 'coin', 'amphora'].map(art).join('')}</div>
        <p class="lead">You run a second-hand <b>${t.icon} ${esc(t.name)}</b>. Buy things from people who walk in, sell them to buyers for more, and finish with the <b>highest net worth</b>.</p>
        <ul class="ilist"><li>Everyone starts with <b>${start}</b> and the same chances.</li>
        <li>The match lasts <b>${days} business days</b>.</li>
        <li><b>Net worth</b> = cash + your stock (at 80% of its true value) + 40% of what you spent on upgrades − loans.</li>
        <li>True item values are only revealed at the very end — until then, you only know what you've investigated.</li></ul>
        ${solo ? '<p class="tip">🧑 <b>Solo match:</b> your rivals are AI dealers. The clock is stopped until you press <b>Start</b>, and you can pause any time.</p>'
               : '<p class="tip">👥 <b>Multiplayer:</b> every player shares one clock. Day 1 morning gives everyone 3 minutes to read this and set up; the day starts early when all players press <b>Open the doors</b>.</p>'}` },
      { title: 'How a day works', body: `
        <div class="daysteps">
          <div><span>☀</span><b>1 · Plan</b><p>Read the news and rumors, hire staff, buy upgrades, price your stock. Press <b>Open the doors</b> when ready.</p></div>
          <div><span>🏪</span><b>2 · Trade</b><p>Sellers come to your counter one at a time. Buyers browse every shop on the street.</p></div>
          <div><span>🔨</span><b>3 · Auction</b><p>A few valuable lots go under the hammer. Everyone bids live.</p></div>
          <div><span>📒</span><b>4 · Report</b><p>See your profit and the race. Wages, loan interest and refunds are settled.</p></div></div>
        <p class="tip">The bar at the top always shows which step you're in, and the gold <b>hint bar</b> on the Shop Floor tells you what to do next.</p>` },
      { title: 'Buying from sellers', body: `
        <div class="three"><div><b>① Look it over</b><p>You see an <b>estimate range</b>, not the real value. Use <b>🔎 Inspect</b> (true condition), <b>🧪 Scan</b> (catches fakes) or <b>Lab certification</b> (everything). Tools cost money <i>and</i> the seller's patience.</p></div>
        <div><b>② Negotiate</b><p>Offer below their ask — they rarely expect their first price. They counter. Lowball too hard and they get angry and leave. Try a persuasion tactic: <b>"Point out flaws"</b> only works if you really found one.</p></div>
        <div><b>③ Decide</b><p>Buy, or walk away. Walking away sometimes makes them call you back with a better price.</p></div></div>
        <ul class="ilist"><li><b>Read the seller:</b> anxious people need cash fast; confident ones know the value; "friendly" smooth-talkers may be selling fakes.</li>
        <li><b>Watch the clues</b> in italics — "the logo font looks off" can mean a fake; "an unusual marking" can mean a rare edition worth many times more.</li>
        <li>Every dealer of your type meets the <b>same sellers in the same order</b> — your decisions make the difference.</li></ul>` },
      { title: 'Selling', body: `
        <ul class="ilist"><li>Bought items appear in <b>Your stock</b> at the bottom of the Shop Floor. Click <b>List</b> to put one on display (or press <b>L</b> to list everything).</li>
        <li>Buyers walk the whole street and pick the <b>best value across all shops</b>. Price too high and they buy from a rival; too low and you leave money on the table. Check <b>Market Street</b> to see rivals' prices.</li>
        <li>Sometimes a buyer makes you an offer — answer it in the bottom-right corner before they leave.</li>
        <li><b>Verified</b> items sell for more. Selling an unverified fake can get you exposed or hit with a refund later.</li>
        <li>Need cash fast? The <b>wholesaler</b> buys anything instantly at ~45% of its value. Or consign an item to tonight's auction.</li>
        <li>Demand per category moves with the news. Tomorrow's events are hinted at as <b>rumors</b> each morning.</li></ul>` },
      { title: 'Auctions, rivals and staff', body: `
        <ul class="ilist"><li><b>Auctions:</b> bid against everyone in real time. A late bid adds time to the clock, so there's no sniping. Catalogue info can be incomplete — that's the gamble.</li>
        <li><b>Private offers</b> pop up during the day: the first dealer to click <b>Claim</b> gets the item.</li>
        <li><b>Market Street:</b> you can buy any rival's listed item — snap up the underpriced ones.</li>
        <li><b>👥 Staff tab:</b> hire up to <b>4</b> of 10 specialists — Mechanic (repairs items over a few days), Mentalist (persuasion + reads their lowest price), Lucky Kid, Appraisal Expert (free instant values, but can misjudge very rare pieces), Negotiator, Salesperson, Security Guard, Market Analyst, Auction Scout and Marketer. Each has 1–3 stars costing <b>$2,000 / $10,000 / $50,000 per week</b>.</li>
        <li><b>Business tab:</b> upgrades (more display space, storage, lab, advertising…) and loans (4% interest per day).</li></ul>` },
      { title: 'Controls', body: `
        <div class="keys" style="font-size:14px;line-height:2.2"><kbd>I</kbd> Inspect · <kbd>S</kbd> Scan · <kbd>E</kbd> Lab certification · <kbd>X</kbd> Ask your expert<br>
        <kbd>O</kbd> jump to the offer box · <kbd>Enter</kbd> send offer · <kbd>A</kbd> accept their price · <kbd>W</kbd> walk away<br>
        <kbd>L</kbd> list all stock · <kbd>B</kbd> bid at the auction · <kbd>1</kbd>–<kbd>6</kbd> switch tabs · <kbd>Esc</kbd> close a window</div>
        ${solo ? '<p class="tip">Your solo match <b>saves automatically</b> every morning. Use <b>Pause</b> in the top bar anytime, and <b>Continue</b> from the main menu next time.</p>'
               : '<p class="tip">If your connection drops, your shop goes on <b>autopilot</b> after 20 seconds. Just reopen the same link in the same browser to take back control.</p>'}
        <p class="muted">You can reread these instructions any time from <b>How to Play</b> on the main menu, or the <b>?</b> button in the top bar.</p>` },
    ];
  }
  function showIntro(v, page = 0) {
    const pages = introPages(v), p = pages[page], last = page === pages.length - 1;
    const solo = v.settings.solo && v.phase !== 'lobby';
    modal(`<div class="intro"><div class="row"><span class="dim">Before you start · ${page + 1}/${pages.length}</span><div class="dots right">${pages.map((_, i) => `<i class="${i === page ? 'on' : ''}" data-a="intro-go" data-p="${i}"></i>`).join('')}</div></div>
      <h2 style="font-size:28px;margin-top:8px">${p.title}</h2>${p.body}
      <div class="row" style="margin-top:16px">${page ? `<button class="btn" data-a="intro-go" data-p="${page - 1}">← Back</button>` : ''}
        <button class="btn ghost" data-a="intro-done">Skip</button>
        <button class="btn primary lg right" data-a="${last ? 'intro-done' : 'intro-go'}" data-p="${page + 1}">${last ? (solo ? 'Start Day 1 ▶' : 'Got it — let\'s play') : 'Next →'}</button></div></div>`);
    S.introOpen = true;
  }
  function maybeIntro(v) {
    if (!S.sess || S.introOpen) return;
    const key = 'dealer_intro_' + S.sess.room + '_' + S.sess.pid;
    let seen = false; try { seen = !!localStorage.getItem(key); } catch (e) { }
    if (!seen && (v.phase === 'lobby' || v.phase === 'morning' || (v.settings.solo && v.paused))) showIntro(v, 0);
  }

  // ------------------------------------------------------------------ main render
  function render() {
    const app = $('#app');
    if (S.screen === 'game' && S.v && S.v.me) return renderGame();
    if (S.screen === 'lobby' && S.v && S.v.lobby) { app._k = null; return patch(app, lobbyScreen()); }
    app._k = null;
    const fn = { menu: menuScreen, solo: soloScreen, host: hostScreen, join: joinScreen, profile: profileScreen, howto: howtoScreen, settings: settingsScreen }[S.screen] || menuScreen;
    patch(app, fn());
  }

  function modal(html) { $('#modal').innerHTML = html ? `<div class="panel">${html}</div>` : ''; }

  // ------------------------------------------------------------------ input handling
  async function startSession(r, base) {
    if (!r.ok) { toast(r.error || 'Could not connect', 'bad'); SFX.play('bad'); return; }
    saveSess({ base, room: r.room, token: r.token, pid: r.pid });
    S.v = null; S.lastPhase = null; S.lastCash = null; S.tab = 'floor'; S.award = null;
    S.info = await get('/api/info', base);
    connect();
  }
  function cosmetics() { const p = S.profile; return p ? p.selected : {}; }
  function profName() { return (S.profile && S.profile.name) || 'Player'; }
  async function updProfile(ch) { const r = await post('/api/profile', Object.assign({ profile: PROFILE }, ch), LOCAL); if (r && !r.error && !r.ok === false) { S.profile = r; } render(); }

  const H = {
    go: (d) => { S.screen = d.s; if (d.s === 'join') H['join-refresh'](); if (d.s === 'menu') loadMenuData(); render(); },
    continue: async () => startSession(await post('/api/resume', { profile: PROFILE }, LOCAL), LOCAL),
    'solo-start': async () => {
      const d = S.draft.solo; SFX.init();
      startSession(await post('/api/create', { profile: PROFILE, name: profName(), cosmetics: cosmetics(), settings: { solo: true, bots: +d.bots, days: +d.days, pace: d.pace, expansion_space: d.space, max_players: 8, my_type: d.type, rivals: d.rivals } }, LOCAL), LOCAL);
    },
    'host-create': async () => {
      const d = S.draft.host; SFX.init();
      startSession(await post('/api/create', { profile: PROFILE, name: profName(), cosmetics: cosmetics(), settings: { name: d.name || 'Dealership Match', days: +d.days, pace: d.pace, max_players: +d.max, public: d.public, type_rule: d.rule, my_type: d.type } }, LOCAL), LOCAL);
    },
    'join-refresh': async () => { const base = normBase(S.draft.joinAddr); const r = await get('/api/rooms', base); S.rooms = (r && r.rooms) || []; if (r.error) toast(r.error, 'bad'); render(); },
    'join-room': async (d) => { SFX.init(); const base = normBase(S.draft.joinAddr); startSession(await post('/api/join', { room: d.code, name: profName(), cosmetics: cosmetics(), my_type: S.draft.joinType }, base), base); },
    'join-code': async () => { SFX.init(); const base = normBase(S.draft.joinAddr); startSession(await post('/api/join', { room: S.draft.code.toUpperCase(), name: profName(), cosmetics: cosmetics(), my_type: S.draft.joinType }, base), base); },
    'join-type': (d) => { S.draft.joinType = d.k; render(); },
    'solo-type': (d) => { S.draft.solo.type = d.k; render(); },
    'host-type': (d) => { S.draft.host.type = d.k; render(); },
    'lobby-type': (d) => post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'set_type', dtype: d.k }, S.sess.base).then(errT),
    'lobby-bot': () => post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'add_bot' }, S.sess.base).then(errT),
    'lobby-remove': (d) => post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'remove', pid: d.pid }, S.sess.base).then(errT),
    'lobby-start': () => post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'start' }, S.sess.base).then(errT),
    leave: async () => { if (S.sess) await post('/api/leave', { room: S.sess.room, token: S.sess.token }, S.sess.base); leaveLocal(); },
    'leave-ask': () => modal(`<h2>Leave the match?</h2><p class="muted">${S.v.settings.solo ? 'Your solo match is saved — continue it from the main menu.' : 'Your shop will be run by autopilot. You can rejoin with the same session while the match is running.'}</p><div class="row"><button class="btn red" data-a="leave-yes">Leave</button><button class="btn right" data-a="modal-close">Stay</button></div>`),
    'leave-yes': async () => { modal(''); if (S.sess) await post('/api/leave', { room: S.sess.room, token: S.sess.token }, S.sess.base); leaveLocal(); },
    'modal-close': () => modal(''),
    copy: (d) => { try { navigator.clipboard.writeText(d.t); toast('Copied ' + d.t, 'good'); } catch (e) { toast(d.t); } },
    'intro-go': (d) => showIntro(S.v, +d.p),
    'intro-done': () => {
      try { localStorage.setItem('dealer_intro_' + S.sess.room + '_' + S.sess.pid, '1'); } catch (e) { }
      S.introOpen = false; modal('');
      if (S.v && S.v.settings.solo && S.v.paused && S.v.phase !== 'lobby') post('/api/pause', { room: S.sess.room, token: S.sess.token, paused: false }, S.sess.base).then(errT);
    },
    'intro-show': () => S.v && showIntro(S.v, 0),
    quit: async () => { await post('/api/quit', {}, LOCAL); document.body.innerHTML = '<div style="height:100%;display:flex;align-items:center;justify-content:center;font:20px Georgia;color:#e5b84b">Thanks for playing The Dealership. You can close this window.</div>'; setTimeout(() => window.close(), 400); },
    'final-menu': () => leaveLocal(),
    tab: (d) => { S.tab = d.t; render(); },
    pause: () => post('/api/pause', { room: S.sess.room, token: S.sess.token, paused: !S.v.paused }, S.sess.base).then(errT),
    music: () => { SFX.setMusic(!SFX.music); updProfile({ settings: { music: SFX.music } }); },
    sfx: () => { SFX.setSfx(!SFX.sfx); updProfile({ settings: { sfx: SFX.sfx } }); },
    ready: () => act('ready'),
    offer: () => { const c = S.v.me.active; if (!c) return; act('offer', { amount: +S.draft.offer[c.id] || 0 }); },
    'offer-pct': (d) => { const c = S.v.me.active; if (!c) return; setOffer(c, nice(c.item.likely * +d.p)); },
    'offer-step': (d) => { const c = S.v.me.active; if (!c) return; setOffer(c, nice((+S.draft.offer[c.id] || 0) * (1 + +d.p))); },
    accept: () => act('accept_ask'),
    walk: () => act('walk'),
    persuade: (d) => act('persuade', { kind: d.k }),
    tool: async (d) => { SFX.play('scan'); const r = await act('tool', { tool: d.tool, target: d.target }); if (r.ok && /COUNTERFEIT|counterfeit/.test(r.res.result)) SFX.play('bad'); else if (r.ok && /Anniversary|Unique|Prototype|Developer|Royal|Historic|Master|Museum|Error|One of|Studio|Lost|Tour|Legend|Signed Maker|Palace|Expedition|National|Atelier|Haute|Flown|Moon/.test(r.res.result)) SFX.play('reveal'); },
    list: (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); const p = +(S.draft.price[d.id] ?? (it && (it.price || nice(it.likely * 1.2)))); act('list', { item: d.id, price: p }).then((r) => { if (r.ok) { delete S.draft.price[d.id]; } }); },
    unlist: (d) => act('unlist', { item: d.id }),
    'list-all': async () => {
      const me = S.v.me; let free = me.display - me.inventory.filter((i) => i.listed).length;
      for (const it of me.inventory) {
        if (free <= 0) break;
        if (it.listed || !me.cats.includes(it.cat)) continue;
        const r = await act('list', { item: it.id, price: suggestPrice(it) });
        if (r.ok) free--;
      }
    },
    'bulk-one': (d) => act('bulk_sell', { items: [d.id] }),
    'price-chip': (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); if (!it) return; S.draft.price[d.id] = nice(it.likely * +d.m); render(); },
    'sel-none': () => { S.sel.clear(); render(); },
    bulk: () => { const ids = [...S.sel]; const tot = ids.length; modal(`<h2>Sell ${tot} item(s) to the wholesaler?</h2><p class="muted">The wholesaler inspects everything and pays about 45% of true value, instantly. Good for clearing storage — bad for profit.</p><div class="row"><button class="btn primary" data-a="bulk-yes">Sell</button><button class="btn right" data-a="modal-close">Cancel</button></div>`); },
    'bulk-yes': () => { modal(''); act('bulk_sell', { items: [...S.sel] }).then((r) => { if (r.ok) S.sel.clear(); }); },
    consign: (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); const start = +(S.draft.price[d.id] ?? nice(it.likely * 0.4)); modal(`<h2>Consign ${esc(it.name)}?</h2><p class="muted">It goes to tonight's auction with a starting bid of <b>${fmt(start)}</b> (edit the price box to change). Rivals bid against each other; you get the winning bid minus 10%. Unsold lots come back to you. One consignment per day.</p><div class="row"><button class="btn primary" data-a="consign-yes" data-id="${d.id}" data-start="${start}">Consign</button><button class="btn right" data-a="modal-close">Cancel</button></div>`); },
    'consign-yes': (d) => { modal(''); act('consign', { item: d.id, start: +d.start }); },
    'buy-rival': (d) => act('buy_rival', { owner: d.owner, item: d.id }),
    buyer: (d) => act('buyer_reply', { offer: d.id, accept: d.yes === '1' }),
    claim: (d) => act('claim', { offer: d.id }),
    bid: (d) => act('bid', { amount: +d.amt }),
    'bid-custom': () => { const a = +S.draft.bid; if (!a) return toast('Enter a bid amount', 'warn'); act('bid', { amount: a }).then((r) => { if (r.ok) S.draft.bid = ''; }); },
    upgrade: (d) => { if (d.k === 'specialty' && !S.draft.spec) return toast('Choose a specialty category first', 'warn'); act('upgrade', { key: d.k, specialty: S.draft.spec }); },
    hire: (d) => act('hire', { role: d.role, stars: +d.stars }),
    repair: (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); const q = it && it.repairQuote; if (!q) return; modal(`<h2>Repair ${esc(it.name)}?</h2><p class="muted">Your mechanic will restore it to <b>${esc(q.toLabel)}</b> for <b>${fmt(q.cost)}</b>. It will be in the workshop for <b>${q.days} day${q.days > 1 ? 's' : ''}</b> (ready on day ${S.v.day + q.days}) and can't be sold meanwhile.</p><div class="row"><button class="btn primary" data-a="repair-yes" data-id="${d.id}">Start repair</button><button class="btn right" data-a="modal-close">Cancel</button></div>`); },
    'repair-yes': (d) => { modal(''); act('repair', { item: d.id }); },
    opinion: (d) => act('opinion', { target: d.target }),
    fire: (d) => act('fire', { staff: d.id }),
    loan: (d) => act('loan', { amount: +d.amt }),
    repay: (d) => act('repay', { amount: +d.amt }),
    research: () => act('research'),
    'p-theme': (d) => updProfile({ selected: { theme: d.k } }),
    'p-title': (d) => updProfile({ selected: { title: d.k } }),
    'p-decor': (d) => { const cur = S.profile.selected.decor.slice(); const i = cur.indexOf(d.k); i >= 0 ? cur.splice(i, 1) : cur.push(d.k); updProfile({ selected: { decor: cur.slice(-4) } }); },
  };
  function errT(r) { if (r && r.ok === false) { toast(r.error, 'bad'); SFX.play('warn'); } }
  // Turn what the player typed into a server address. Only a bare LAN address ("192.168.1.20")
  // gets the desktop game's default port; web addresses (https://….onrender.com) are used as-is.
  function normBase(s) {
    s = (s || '').trim().replace(/\/+$/, '');
    if (!s) return LOCAL;
    const typedScheme = /^https?:\/\//.test(s);
    if (!typedScheme) s = (/^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?$/.test(s) ? 'http://' : 'https://') + s;
    try {
      const u = new URL(s);
      if (!u.port && u.protocol === 'http:' && /^(localhost|\d{1,3}(\.\d{1,3}){3})$/.test(u.hostname)) u.port = '8642';
      return u.origin;
    } catch (e) { return s; }
  }
  function setOffer(c, val) {
    S.draft.offer[c.id] = val;
    const a = $('#offer-in'), b = $('#offer-range');
    if (a) a.value = val; if (b) b.value = val;
  }

  // Fire on pointer-down: the UI re-renders several times a second, and a button replaced
  // between mouse-down and mouse-up would otherwise swallow the click.
  document.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    const b = e.target.closest('[data-a]');
    if (!b || b.disabled || !b.dataset.a) return;
    SFX.init(); SFX.play('click');
    const fn = H[b.dataset.a];
    if (fn) fn(b.dataset, b, e);
  });
  const INPUTS = {
    'solo-bots': (v) => S.draft.solo.bots = v, 'solo-days': (v) => S.draft.solo.days = v, 'solo-pace': (v) => S.draft.solo.pace = v, 'solo-space': (v, el) => S.draft.solo.space = el.checked,
    'host-name': (v) => S.draft.host.name = v, 'host-max': (v) => S.draft.host.max = v, 'host-days': (v) => S.draft.host.days = v, 'host-pace': (v) => S.draft.host.pace = v, 'host-public': (v, el) => S.draft.host.public = el.checked,
    'join-addr': (v) => S.draft.joinAddr = v, 'join-code': (v) => S.draft.code = v,
    'lob-days': (v) => lobbySet({ days: +v }), 'lob-rule': (v) => lobbySet({ type_rule: v }),
    'solo-rivals': (v) => S.draft.solo.rivals = v, 'host-rule': (v) => { S.draft.host.rule = v; render(); },
    'ai-type': (v, el) => post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'set_type', pid: el.dataset.pid, dtype: v }, S.sess.base).then(errT), 'lob-pace': (v) => lobbySet({ pace: v }), 'lob-max': (v) => lobbySet({ max_players: +v }),
    offer: (v, el) => { S.draft.offer[el.dataset.cid] = +v; const r = $('#offer-range'); if (r) r.value = v; },
    'offer-range': (v, el) => { S.draft.offer[el.dataset.cid] = +v; const a = $('#offer-in'); if (a) a.value = v; },
    price: (v, el) => S.draft.price[el.dataset.id] = +v,
    sel: (v, el) => { el.checked ? S.sel.add(el.dataset.id) : S.sel.delete(el.dataset.id); render(); },
    bid: (v) => S.draft.bid = v,
    spec: (v) => S.draft.spec = v,
    'p-name': (v) => { clearTimeout(S._nt); S._nt = setTimeout(() => updProfile({ name: v }), 600); },
    'set-music': (v, el) => { SFX.setMusic(el.checked); updProfile({ settings: { music: el.checked } }); },
    'set-sfx': (v, el) => { SFX.setSfx(el.checked); updProfile({ settings: { sfx: el.checked } }); },
    'set-volume': (v) => { SFX.setVolume(+v); clearTimeout(S._vt); S._vt = setTimeout(() => updProfile({ settings: { volume: +v } }), 400); },
  };
  function lobbySet(s) { post('/api/lobby', { room: S.sess.room, token: S.sess.token, op: 'settings', settings: s }, S.sess.base).then(errT); }
  const onInput = (e) => { const k = e.target.dataset && e.target.dataset.in; if (k && INPUTS[k]) INPUTS[k](e.target.value, e.target); };
  document.addEventListener('input', (e) => { if (e.target.type !== 'checkbox' && e.target.tagName !== 'SELECT') onInput(e); });
  document.addEventListener('change', (e) => { if (e.target.type === 'checkbox' || e.target.tagName === 'SELECT') onInput(e); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { if (S.introOpen) H['intro-done'](); else modal(''); }
    const typing = /INPUT|SELECT|TEXTAREA/.test(e.target.tagName);
    if (!typing && S.screen === 'game' && S.v && S.v.me && !e.metaKey && !e.ctrlKey) {
      const c = S.v.me.active, k = e.key.toLowerCase();
      const tool = { i: 'inspect', s: 'scan', e: 'expert' }[k];
      if (tool && c && S.v.phase === 'shop') { H.tool({ tool, target: 'counter' }); return; }
      if (k === 'a' && c) { SFX.play('click'); H.accept(); return; }
      if (k === 'x' && c) { SFX.play('click'); H.opinion({ target: 'counter' }); return; }
      if (k === 'w' && c) { SFX.play('click'); H.walk(); return; }
      if (k === 'o' && c) { const el = $('#offer-in'); if (el) { el.focus(); el.select(); e.preventDefault(); } return; }
      if (k === 'l' && S.v.phase !== 'auction') { H['list-all'](); return; }
      if (k === 'b' && S.v.phase === 'auction') { const b = document.querySelector('[data-a="bid"]:not([disabled])'); if (b) H.bid(b.dataset); return; }
      if (/^[1-6]$/.test(k)) { const tabs = tabsFor(S.v); const t = tabs[+k - 1]; if (t) { S.tab = t[0]; render(); } return; }
    }
    if (e.key === 'Enter' && e.target.id === 'offer-in') H.offer();
    if (e.key === 'Enter' && e.target.id === 'bid-in') H['bid-custom']();
    if (e.key === 'Enter' && e.target.dataset && e.target.dataset.in === 'price') H.list({ id: e.target.dataset.id });
  });
  document.addEventListener('mouseover', (e) => { const b = e.target.closest('.btn'); if (b && b !== S._hov && !b.disabled) { S._hov = b; SFX.play('hover'); } });

  // ------------------------------------------------------------------ boot
  ART.onReady(() => render());
  (async () => {
    ART.preload(ART.kinds()).then(() => render());
    await loadMenuData();
    if (S.sess) {
      const r = await post('/api/rejoin', { room: S.sess.room, token: S.sess.token }, S.sess.base);
      if (r.ok) { S.info = await get('/api/info', S.sess.base); connect(); } else { saveSess(null); }
    }
    render();
  })();
  window.__DEALER = S; // debugging aid
})();

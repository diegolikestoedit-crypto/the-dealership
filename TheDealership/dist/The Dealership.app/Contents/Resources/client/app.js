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
    screen: 'menu', base: LOCAL, sess: null, v: null, profile: null, tab: 'counter',
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
    saveSess(null); S.v = null; S.screen = 'menu'; S.tab = 'counter';
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
        const k = n.kind.replace('quiet-', '');
        if (!n.kind.startsWith('quiet-')) toast(n.text, n.kind);  // counter results already show in the result card
        SFX.play({ sale: 'sale', bad: 'bad', good: 'cash', warn: 'warn' }[k] || (n.kind.startsWith('quiet-') ? 'click' : 'coin'));
      }
      S.seenNote = Math.max(S.seenNote, maxN);
      if (S.lastCash != null && v.me.cash > S.lastCash) coinFx('+' + fmt(v.me.cash - S.lastCash));
      S.lastCash = v.me.cash;
      const cid = v.me.visitor && v.me.visitor.id;
      if (cid && cid !== S.lastCust) SFX.play('door');
      S.lastCust = cid;
    }
    if (v.phase !== S.lastPhase) {
      S.phaseTotal = Math.max(1, v.left || 1);
      if (S.lastPhase !== null || v.phase !== 'lobby') {
        SFX.play({ shop: 'day', auction: 'gavel', evening: 'coin', final: 'win' }[v.phase] || 'click');
      }
      S.tab = { shop: 'main', auction: 'auction', evening: 'main', final: 'final' }[v.phase] || 'main';
      if (v.phase === 'shop' && S.lastPhase !== null) {
        const n = v.catNames || {};
        toast(`Day ${v.day} — ${v.hot ? '🔥 ' + (n[v.hot] || v.hot) + ' are hot today' : 'a calm market'}${v.cold ? ' · ❄ ' + (n[v.cold] || v.cold) + ' are cold' : ''}`, 'good');
      }
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
      <section class="hsec"><h2>Playing with friends</h2><ol class="ilist"><li><b>Host:</b> Main menu → <b>Host Multiplayer</b> → pick a rule (everyone chooses their own dealership, or one type for all) → <b>Create Lobby</b>.</li><li>The lobby shows a <b>room code</b> and a <b>link</b>. Send both to your friends.</li><li><b>Friends:</b> open the link in any browser → <b>Join Multiplayer</b> → choose a dealership → type the code → <b>Join</b>.</li><li>Everyone picks their dealership in the lobby. The host can add AI dealers to fill seats, then presses <b>Start Match</b>.</li><li>Everyone serves their own visitors at the counter. When all players are done, you meet at the auction, then plan your evening.</li></ol></section>
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

  // ------------------------------------------------------------------ game screen (minimal)
  // One screen: your shop with the customer in it, and a small deal card. Stock and "Improve shop"
  // open as full pages with a Back button. Everything else stays out of the way.
  function gameSkeleton() {
    return `<div class="g2"><header class="bar2" id="g-top"></header><main class="stage2" id="g-content"></main></div>`;
  }

  function myRank(v) { return v.leaderboard.findIndex((r) => r.id === v.you) + 1; }

  function topHTML(v) {
    const me = v.me, page = S.tab;
    const label = { shop: 'Open', auction: 'Auction', evening: 'Evening', final: 'Results' }[v.phase] || '';
    return `<div class="brand" title="The Dealership">$</div>
      <div class="b2 day"><b>Day ${v.day}</b><span>of ${v.days} · ${label}</span></div>
      <div class="b2 cash"><b class="money">${fmt(me.cash)}</b><span>cash</span></div>
      ${v.phase !== 'final' ? `<button class="b2 rank" data-a="rivals" title="See your rivals"><b>#${myRank(v)}</b><span>of ${v.leaderboard.length}</span></button>` : ''}
      <div class="grow"></div>
      ${v.phase === 'shop' || v.phase === 'evening' ? `
        <button class="btn nav ${page === 'stock' ? 'on' : ''}" data-a="page" data-t="stock">📦 Stock <b>${me.inventory.length}</b></button>
        <button class="btn nav ${page === 'improve' ? 'on' : ''}" data-a="page" data-t="improve">🏗 Improve shop</button>` : ''}
      ${v.paused ? '<span class="chip warn">PAUSED</span>' : ''}
      <button class="btn sm ghost" data-a="menu2" title="Menu">☰</button>`;
  }

  function renderGame() {
    const v = S.v, app = $('#app');
    ensure(app, 'game', gameSkeleton());
    if (v.phase === 'auction' || v.phase === 'final') S.tab = v.phase;
    else if (!['stock', 'improve', 'main'].includes(S.tab)) S.tab = 'main';
    patch($('#g-top'), topHTML(v));
    const c = $('#g-content');
    const page = S.tab === 'stock' ? stockPage : S.tab === 'improve' ? improvePage : v.phase === 'auction' ? auctionPage
      : v.phase === 'final' ? finalPage : v.phase === 'evening' ? eveningPage : counterPage;
    page(v, c);
  }

  function glowLevel(it) { return it.editionIdx >= 2 || it.rarity >= 5 ? 3 : it.editionIdx >= 1 || it.rarity >= 4 ? 2 : 1; }
  const known = (it) => it.cond && it.status !== 'unverified';
  const worthText = (it) => it.opinion ? fmt(it.opinion) : known(it) ? fmt(it.likely) : `≈ ${fmt(it.likely)}?`;

  // ---------- the counter
  function counterPage(v, c) {
    ensure(c, 'counter', `<div class="scene full" id="sc"><div class="wallpaper"></div><div class="lamp" style="left:8%"></div><div class="lamp" style="left:45%"></div>
      <div class="sign" id="sc-sign"></div><div class="shelves" id="sc-shelves"></div><div class="counter"></div><div class="register"></div>
      <div id="sc-cust"></div><div id="sc-item"></div><div id="sc-bubble"></div></div><div class="card2" id="deal"></div>`);
    const me = v.me, vis = me.visitor;
    $('#sc').className = 'scene full theme-' + (me.theme || 'classic') + (me.dtype === 'cars' ? ' showroom' : '');
    patch($('#sc-sign'), esc(((v.leaderboard.find((r) => r.id === v.you) || {}).name || 'My Shop').toUpperCase()) + "'S " + esc(T(me.dtype).sign || ''));
    let slots = '';
    for (let i = 0; i < 8; i++) {
      const it = me.inventory[i];
      slots += it ? `<div class="slot glow-${glowLevel(it)}" title="${esc(it.name)}">${ART.item(it, 56)}</div>` : `<div class="slot empty"></div>`;
    }
    patch($('#sc-shelves'), slots);
    const scc = $('#sc-cust');
    if (vis) {
      const same = scc._cid === vis.id;
      scc._cid = vis.id;
      patch(scc, `<div class="customer ${same ? 'stay' : ''} ${vis.mood < 25 ? 'mood-angry' : ''}">${ART.person(vis.look, vis.mood, 220)}</div>`);
      patch($('#sc-item'), vis.item ? `<div class="counter-item ${same ? 'stay' : ''} glow-${glowLevel(vis.item)}">${ART.item(vis.item, 128)}</div>` : '');
      const last = vis.lines.filter((l) => l.who === 'them').slice(-1)[0];
      const face = vis.mood > 60 ? '😊' : vis.mood > 30 ? '😐' : '😠';
      patch($('#sc-bubble'), last ? `<div class="bubble"><span class="face">${face}</span>${esc(last.text)}</div>` : '');
    } else {
      scc._cid = null;
      patch(scc, ''); patch($('#sc-item'), '');
      const L = me.last;
      patch($('#sc-bubble'), L && L.lines && L.lines.length ? `<div class="bubble fade">${esc(L.lines.filter((l) => l.who === 'them').slice(-1)[0]?.text || '')}</div>` : '');
    }
    dealCard(v, $('#deal'));
  }

  function dealCard(v, el) {
    const me = v.me, vis = me.visitor;
    if (!vis) {
      ensure(el, 'idle', '<div id="idle"></div>');
      const L = me.last;
      const icon = L ? { good: '🤝', sale: '💰', bad: '😠', info: '👋' }[L.outcome] || '👋' : '';
      const left = me.visitors - me.vidx;
      if (me.done) {
        return patch($('#idle'), `${L ? `<div class="res2 ${L.outcome}">${icon} ${esc(L.text)}</div>` : ''}
          <div class="idle2"><div style="font-size:40px">🌙</div><h2>Closed for today</h2>
          <p class="muted">${v.waiting && v.waiting.length ? 'Waiting for ' + v.waiting.map(esc).join(', ') + '…' : 'Off to the auction…'}</p></div>`);
      }
      return patch($('#idle'), `${L ? `<div class="res2 ${L.outcome}">${icon} ${esc(L.text)}</div>` : ''}
        <div class="idle2"><div class="dim">${me.vidx === 0 ? `${me.visitors} customers today` : `${left} customer${left === 1 ? '' : 's'} left`}</div>
        <button class="btn primary xl" data-a="next">${me.vidx === 0 ? 'Open the shop' : 'Next customer'} ▶</button>
        <div class="dim" style="font-size:12px;margin-top:8px">or press Space</div>
        ${me.vidx > 0 ? `<button class="btn ghost sm" style="margin-top:14px" data-a="close-early">Close early</button>` : ''}</div>`);
    }
    const seller = vis.kind === 'seller', it = vis.item;
    if (ensure(el, 'v-' + vis.id, `<div id="d-top"></div><div id="d-price"></div><div id="d-acts"></div><div id="d-extra"></div>`)) {
      S.draft.offer[vis.id] = seller ? nice((it.opinion || it.likely) * 0.6) : nice(Math.max(vis.offer * 1.2, (it.opinion || it.likely) * 1.1));
    }
    const warn = it.status === 'replica' ? '<div class="warn2 bad">✗ This is a FAKE</div>'
      : vis.flagged ? '<div class="warn2">⚠ Your guard says: this person seems dishonest</div>'
      : vis.lying ? '<div class="warn2">⚠ Your guard says: it\'s in worse shape than they claim</div>' : '';
    patch($('#d-top'), `<div class="who">${esc(vis.name)} ${seller ? 'wants to <b class="sellc">sell</b>' : 'wants to <b class="buyc">buy</b>'}</div>
      <div class="iname">${esc(it.name)} ${it.hot ? '<span title="Hot today">🔥</span>' : it.cold ? '<span title="Cold today">❄</span>' : ''}${it.editionIdx > 0 && it.edition ? ` <span class="chip ed">${esc(it.edition)}</span>` : ''}</div>
      ${warn}
      <div class="nums">
        <div><span>${seller ? 'They want' : 'They offer'}</span><b class="${seller ? 'bad' : 'good'}">${fmt(seller ? vis.ask : vis.offer)}</b></div>
        <div title="${known(it) ? '' : 'Range: ' + fmt(it.low) + ' – ' + fmt(it.high) + '. Check it to be sure.'}"><span>${known(it) || it.opinion ? 'Worth about' : 'Probably worth'}</span><b>${worthText(it)}</b></div>
        ${!seller ? `<div><span>You paid</span><b>${fmt(vis.paid)}</b></div>` : ''}
      </div>
      ${known(it) ? `<div class="checked ${it.status === 'replica' ? 'bad' : 'good'}">${it.status === 'replica' ? '✗ Fake' : '✓ Genuine'} · ${esc(it.cond)} condition</div>` : ''}
      ${!known(it) && !it.opinion ? `<button class="btn check" data-a="examine">🔍 Check it — ${me.examineFee ? fmt(me.examineFee) : 'free'}</button>` : ''}
      ${it.hints.length ? `<div class="hint">“${esc(it.hints[0])}”</div>` : ''}
      ${vis.limit ? `<div class="mind">🔮 Their limit is about ${fmt(vis.limit[0])}–${fmt(vis.limit[1])}</div>` : ''}`);
    const off = S.draft.offer[vis.id], max = Math.max(seller ? vis.ask : (it.high || vis.offer * 2), 100);
    patch($('#d-price'), `<div class="pr2"><button class="btn" data-a="step" data-p="-0.05">−</button><input type="number" id="offer-in" data-in="offer" data-cid="${vis.id}" value="${off}"><button class="btn" data-a="step" data-p="0.05">+</button></div>
      <input type="range" id="offer-range" data-in="offer-range" data-cid="${vis.id}" min="0" max="${max}" step="${max > 20000 ? 100 : 10}" value="${Math.min(off, max)}">`);
    patch($('#d-acts'), `<div class="acts2">
      <button class="btn primary" data-a="offer">${seller ? 'Offer' : 'Ask'} ${fmt(off)}</button>
      <button class="btn green" data-a="accept" ${seller && vis.ask > me.cash ? 'disabled' : ''}>${seller ? 'Buy' : 'Sell'} ${fmt(seller ? vis.ask : vis.offer)}</button>
      <button class="btn red" data-a="pass">No</button></div>`);
    const hasExpert = me.staff.some((x) => x.role === 'expert');
    patch($('#d-extra'), `<div class="extra2"><span class="pat" title="How many more offers they'll listen to">Patience ${'●'.repeat(vis.rounds)}<span class="dim">${'●'.repeat(Math.max(0, vis.roundsMax - vis.rounds))}</span></span>
      ${hasExpert && !it.opinion && me.expertLeft ? '<button class="btn sm ghost" data-a="opinion">🎓 Ask expert</button>' : ''}</div>`);
  }

  // Keyed list update: only changed entries are replaced, so lists don't flicker.
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
        if (node._h !== h) {
          const t = document.createElement('template'); t.innerHTML = h.trim();
          const nn = t.content.firstElementChild; nn.dataset.key = k; nn._h = h; nn.classList.add('noanim');
          node.replaceWith(nn); node = nn;
        }
      } else {
        const t = document.createElement('template'); t.innerHTML = h.trim();
        node = t.content.firstElementChild; node.dataset.key = k; node._h = h;
        node.classList.add(firstRender ? 'noanim' : 'arrive');
      }
      const want = prev ? prev.nextElementSibling : el.firstElementChild;
      if (node !== want) el.insertBefore(node, want);
      prev = node;
    }
    existing.forEach((n) => n.remove());
  }

  const backBtn = (v) => `<button class="btn" data-a="page" data-t="main">← Back to ${v.phase === 'evening' ? 'the evening' : 'the counter'}</button>`;

  // ---------- stock (simple list)
  function stockPage(v, c) {
    ensure(c, 'stock', '<div class="page2"><div id="st-head"></div><div class="rows2" id="st-list"></div></div>');
    const me = v.me, hasExpert = me.staff.some((x) => x.role === 'expert');
    patch($('#st-head'), `<div class="row">${backBtn(v)}<h2 style="margin:0 0 0 10px">Your stock</h2><span class="dim right">${me.inventory.length} of ${me.storage} spaces · buyers choose from these</span></div>
      ${!me.inventory.length ? '<div class="empty2">Nothing yet. Buy things from sellers at the counter.</div>' : ''}`);
    patchList($('#st-list'), me.inventory, (it) => it.id, (it) => `<div class="srow">
        <div class="glow-${glowLevel(it)}">${ART.item(it, 48)}</div>
        <div class="grow"><b>${esc(it.name)}</b> ${it.status === 'replica' ? '<span class="chip replica">fake</span>' : ''}${it.repair ? `<span class="chip unverified">🔧 ready day ${it.repair.until}</span>` : ''}${!it.canSell ? '<span class="chip warn">not your trade</span>' : ''}
          <div class="dim" style="font-size:12px">${esc(it.cond || it.claimed + '?')} · worth ${worthText(it)} · you paid ${fmt(it.paid)}</div></div>
        <div class="row" style="gap:4px">
          ${!known(it) ? `<button class="btn sm" data-a="examine" data-target="${it.id}">🔍 Check ${me.examineFee ? fmt(me.examineFee) : ''}</button>` : ''}
          ${hasExpert && !it.opinion && me.expertLeft ? `<button class="btn sm" data-a="opinion" data-target="${it.id}">🎓</button>` : ''}
          ${it.repairQuote && !it.repair ? `<button class="btn sm" data-a="repair" data-id="${it.id}">🔧 Fix ${fmt(it.repairQuote.cost)}</button>` : ''}
          ${!it.repair ? `<button class="btn sm ghost" data-a="quick" data-id="${it.id}" title="Instant cash at about 45% of its value">Pawn</button>` : ''}</div></div>`);
  }

  // ---------- improve shop: upgrades + staff on one page
  function improvePage(v, c) {
    ensure(c, 'improve', '<div class="page2" id="imp"></div>');
    const me = v.me, wl = v.weekDaysLeft, full = me.staff.length >= me.maxStaff;
    const ups = Object.entries(v.upgrades).map(([k, u]) => {
      const lvl = me.upgrades[k], maxed = lvl >= u.costs.length, cost = u.costs[lvl];
      return `<div class="srow"><span style="font-size:26px">${u.icon}</span><div class="grow"><b>${esc(u.name)}</b> <span class="stars">${'★'.repeat(lvl)}<span class="dim">${'★'.repeat(u.costs.length - lvl)}</span></span><div class="dim" style="font-size:12px">${esc(u.desc)}</div></div>
        <button class="btn sm ${maxed ? '' : 'primary'}" data-a="upgrade" data-k="${k}" ${maxed || cost > me.cash ? 'disabled' : ''}>${maxed ? 'Maxed' : fmt(cost)}</button></div>`;
    }).join('');
    const staff = Object.entries(v.employees).map(([role, e]) => {
      const cur = me.staff.find((s) => s.role === role);
      const btns = [1, 2, 3].map((st) => {
        if (cur && cur.stars >= st) return `<span class="starbtn on">${'★'.repeat(st)}</span>`;
        const due = nice((v.wages[st] - (cur ? v.wages[cur.stars] : 0)) * wl / 7);
        const dis = (!cur && full) || due > me.cash;
        return `<button class="btn sm starbtn" data-a="hire" data-role="${role}" data-stars="${st}" ${dis ? 'disabled' : ''} title="${esc(e.stars[st - 1])} — ${fmt(v.wages[st])}/week">${'★'.repeat(st)} ${fmt(v.wages[st])}</button>`;
      }).join('');
      return `<div class="srow ${cur ? 'hired' : ''}"><span style="font-size:24px">${e.icon}</span><div class="grow"><b>${esc(e.name)}</b>${cur ? ` <span class="good" style="font-size:12px">· ${esc(cur.name)}</span>` : ''}<div class="dim" style="font-size:12px">${esc(e.desc)}</div></div>
        <div class="row" style="gap:4px">${btns}${cur ? `<button class="btn sm ghost" data-a="fire" data-id="${cur.id}" title="Let go">✕</button>` : ''}</div></div>`;
    }).join('');
    patch($('#imp'), `<div class="row">${backBtn(v)}<h2 style="margin:0 0 0 10px">Improve your shop</h2><span class="dim right">You have ${fmt(me.cash)}</span></div>
      <h3 style="margin-top:14px">Upgrades</h3><div class="rows2">${ups}</div>
      <h3 style="margin-top:16px">Staff <span class="dim" style="font-family:var(--sans);font-size:12px">· ${me.staff.length} of ${me.maxStaff} hired · paid weekly (this week: ${wl} day${wl > 1 ? 's' : ''} left)</span></h3><div class="rows2">${staff}</div>`);
  }

  // ---------- evening
  function eveningPage(v, c) {
    ensure(c, 'evening', '<div class="page2 center2" id="ev"></div>');
    const r = v.report || {}, me = v.me, delta = (r.end_nw || 0) - (r.start_nw || 0), f = me.forecast, n = v.catNames || {};
    patch($('#ev'), `<div class="evcard"><div style="font-size:46px">🌙</div><h1>Day ${v.day} is over</h1>
      <div class="bigdelta ${delta >= 0 ? 'good' : 'bad'}">${delta >= 0 ? '+' : ''}${fmt(delta)}</div>
      <div class="muted">You bought ${r.bought || 0} and sold ${r.sold || 0} item${r.sold === 1 ? '' : 's'} today · you're <b>#${myRank(v)} of ${v.leaderboard.length}</b></div>
      ${r.stolen ? `<div class="bad" style="margin-top:6px">😱 Burglars stole ${r.stolen} item${r.stolen > 1 ? 's' : ''} last night</div>` : ''}
      ${f && f.hot ? `<div style="margin-top:8px">📊 Your analyst: tomorrow <b class="good">${esc(n[f.hot] || f.hot)}</b> will be hot.</div>` : ''}
      <div class="row" style="justify-content:center;margin-top:20px;gap:10px">
        <button class="btn lg" data-a="page" data-t="improve">🏗 Improve shop</button>
        <button class="btn primary lg" data-a="ready" ${me.ready ? 'disabled' : ''}>${me.ready ? 'Waiting for others…' : `Start day ${v.day + 1} ▶`}</button></div>
      ${me.ready && v.waiting && v.waiting.length ? `<p class="dim">Waiting for ${v.waiting.map(esc).join(', ')}</p>` : ''}</div>`);
  }

  function nwChart(v) {
    const ids = v.leaderboard.map((r) => r.id);
    const series = ids.map((id) => [v.startCash || 25000, ...v.history.map((h) => h.nw[id] ?? 0), v.leaderboard.find((r) => r.id === id).net_worth]);
    const n = series[0].length, all = series.flat(), mx = Math.max(...all, (v.startCash || 25000) * 1.2), mn = Math.min(...all, 0);
    const X = (i) => 40 + (i / Math.max(1, n - 1)) * 540, Y = (y) => 190 - (y - mn) / (mx - mn) * 170;
    const ly = series.map((s, k) => [k, Y(s[n - 1])]).sort((a, b) => a[1] - b[1]);
    for (let i = 1; i < ly.length; i++) ly[i][1] = Math.max(ly[i][1], ly[i - 1][1] + 12);
    const labelY = {}; ly.forEach(([k, y]) => labelY[k] = y);
    const lines = series.map((s, k) => { const r = v.leaderboard[k]; const col = COLORS[k % 8]; return `<polyline fill="none" stroke="${col}" stroke-width="${r.id === v.you ? 3.5 : 2}" points="${s.map((y, i) => X(i) + ',' + Y(y)).join(' ')}" opacity="${r.id === v.you ? 1 : .75}"/><text x="${X(n - 1) + 4}" y="${labelY[k] + 4}" fill="${col}" font-size="11" font-weight="${r.id === v.you ? 700 : 400}">${esc(r.name.split(' ').slice(-1)[0])}</text>`; }).join('');
    return `<svg viewBox="0 0 650 210">${lines}</svg>`;
  }

  function rivalsModal() {
    const v = S.v;
    modal(`<div class="row"><h2 class="grow">Rivals</h2><button class="btn sm" data-a="modal-close">Close</button></div>
      ${v.leaderboard.map((r, i) => `<div class="lb-row ${r.id === v.you ? 'me' : ''}"><div class="rank">${i + 1}</div>
        <div><div class="nm">${T(r.dtype).icon} ${esc(r.name)}${r.is_ai ? ' <span class="chip">AI</span>' : ''}</div><div class="sub">${esc(T(r.dtype).name)} · ${r.items} items</div></div>
        <div class="money gold" style="font-weight:700">${fmt(r.net_worth)}</div></div>`).join('')}
      <div class="chart" style="margin-top:10px">${nwChart(v)}</div>`);
  }

  // ---------- auction (just the lot, the price, the clock)
  function auctionPage(v, c) {
    ensure(c, 'auction', `<div class="stage au2" id="au-stage"></div>`);
    const a = v.auction, stg = $('#au-stage');
    if (!a) return;
    const lot = a.lot;
    if (!lot) {
      ensure(stg, 'nolot', `<div class="curtain l"></div><div class="curtain r"></div><div class="lot-title">The auction is about to start…</div><div class="pedestal"></div>`);
      return;
    }
    ensure(stg, 'lot-' + lot.id, `<div class="curtain l"></div><div class="curtain r"></div><div class="lot-title"></div><div class="lot-items"></div><div class="pedestal"></div><div class="aucard" id="au-card"></div><div class="au-sold"></div>`);
    patch($('.lot-title', stg), `Lot ${a.index + 1} of ${a.count}: ${esc(lot.title)}`);
    patch($('.lot-items', stg), lot.items.map((it) => `<div class="glow-${glowLevel(it)}">${ART.item(it, lot.items.length > 1 ? 96 : 176)}</div>`).join(''));
    patch($('.au-sold', stg), lot.closed ? `<div class="sold"><h1>${lot.result && lot.result.winner ? 'SOLD!' : 'NO SALE'}</h1>${lot.result && lot.result.winner ? `<div style="font-size:20px">to <b class="gold">${esc(lot.result.winner)}</b> for ${fmt(lot.result.amount)}</div>` : ''}</div>` : '');
    const mine = lot.bidder === v.you, minB = lot.minBid;
    patch($('#au-card'), `<div class="row"><div class="grow"><div class="dim" style="font-size:12px">${lot.bidder ? (mine ? 'You lead with' : esc(lot.bidderName) + ' leads with') : 'Starting price'}</div>
        <div class="bignum ${mine ? 'good' : ''}">${fmt(lot.bid || lot.start)}</div>
        <div class="dim" style="font-size:12px">Probably worth ${fmt(lot.low)} – ${fmt(lot.high)}${lot.scouted ? ' · 🔭 scouted' : ''}</div></div>
        <div class="clock2 ${lot.left < 5 ? 'bad' : ''}">${lot.closed ? '—' : Math.ceil(lot.left)}</div></div>
      ${!lot.allowed ? '<div class="warn2">Not your trade — you can only watch this one.</div>'
        : mine ? '<div class="good" style="margin-top:8px">You\'re winning! Wait for the clock…</div>'
        : `<button class="btn primary lg" style="width:100%;margin-top:8px" data-a="bid" data-amt="${minB}" ${lot.closed || minB > v.me.cash ? 'disabled' : ''}>Bid ${fmt(minB)}</button>`}`);
  }

  // ---------- final
  function finalPage(v, c) {
    ensure(c, 'final', '<div class="page2" id="fn"></div>');
    const f = v.final; if (!f) return;
    const rows = f.rows, me = rows.find((r) => r.id === v.you), aw = S.award;
    const top = [rows[1], rows[0], rows[2]].filter(Boolean);
    const Hh = { 1: 150, 2: 110, 3: 80 }, CL = { 1: 'linear-gradient(#ffe7a3,#e5b84b)', 2: 'linear-gradient(#eceff1,#b0bec5)', 3: 'linear-gradient(#e6b48a,#b07d4c)' };
    patch($('#fn'), `<div class="center"><h1 style="font-size:40px">${me && me.place === 1 ? '🏆 You win!' : `You finished #${me ? me.place : '?'}`}</h1></div>
      <div class="podium">${top.map((r) => `<div class="pl"><div style="font-weight:700">${esc(r.name)}</div><div class="gold">${fmt(r.net_worth)}</div><div class="blk" style="height:${Hh[r.place]}px;background:${CL[r.place]}">${r.place}</div></div>`).join('')}</div>
      <div class="rows2" style="max-width:640px;margin:0 auto">${rows.map((r) => `<div class="srow ${r.id === v.you ? 'hired' : ''}"><b style="width:24px">${r.place}</b><div class="grow">${T(r.dtype).icon} ${esc(r.name)}</div><b class="gold">${fmt(r.net_worth)}</b></div>`).join('')}</div>
      <div class="center" style="margin-top:14px">${aw ? `<p class="gold">+${aw.gained} XP${aw.levelUp ? ` · LEVEL UP → ${aw.level}` : ''}</p>` : ''}
        <button class="btn primary lg" data-a="final-menu">Back to main menu</button></div>`);
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
        <p class="lead">You run a second-hand <b>${t.icon} ${esc(t.name)}</b>. <b>Buy low</b> from people who want to sell, <b>sell high</b> to people who want to buy — and finish with more money than your rivals.</p>
        <ul class="ilist"><li>Everyone starts with <b>${start}</b>. The match lasts <b>${days} days</b>.</li>
        <li>Your score is your <b>net worth</b>: cash + your stock + part of what you spent on upgrades.</li></ul>
        ${solo ? '<p class="tip">🧑 <b>Solo:</b> your rivals are AI dealers. There is no timer at your counter — take your time. You can pause any time.</p>'
               : '<p class="tip">👥 <b>Multiplayer:</b> everyone serves their own visitors at their own pace. When everyone is done, you all meet at the auction.</p>'}` },
      { title: 'Every day has 3 steps', body: `
        <div class="daysteps three-steps">
          <div><span>🏪</span><b>1 · The counter</b><p>Visitors come in one at a time. Some want to <b>sell</b> you something, others want to <b>buy</b> something you own. Make a deal or say no, then press <b>Next visitor</b>.</p></div>
          <div><span>🔨</span><b>2 · The auction</b><p>A few special items go under the hammer. Bid if you want one — or just watch.</p></div>
          <div><span>🌙</span><b>3 · The evening</b><p>See how you did. Hire staff, buy upgrades, then start the next day.</p></div></div>
        <p class="tip">The bar at the top of the screen always shows which step you're in.</p>` },
      { title: 'How to make a deal', body: `
        <div class="three"><div><b>Look</b><p>The coloured bar shows what the item is <b>probably worth</b>. Press <b>🔍 Examine</b> to check its real condition and whether it's a <b>fake</b>.</p></div>
        <div><b>Haggle</b><p>Type a price (or tap a % button) and press <b>Offer</b>. They'll answer with a counter-offer. Each person has limited <b>patience</b> — the dots show how many offers you have left.</p></div>
        <div><b>Decide</b><p><b>Buy/Sell</b> at their price, or <b>No deal</b>. Saying no sometimes makes a seller call you back cheaper!</p></div></div>
        <ul class="ilist"><li>Offer too little and they get <b>angry</b> and leave. Watch the mood face.</li>
        <li><b>🔥 Hot</b> categories sell for more today; <b>❄ cold</b> ones for less. They're shown at the top.</li>
        <li>Clues in <i>italics</i> matter: "the logo looks off" may mean a fake; "an unusual marking" may mean a rare, very valuable piece.</li></ul>` },
      { title: 'Staff, upgrades & keys', body: `
        <ul class="ilist"><li><b>👥 Staff:</b> hire up to 4 specialists — e.g. an <b>Expert</b> who tells you what things are worth, a <b>Mechanic</b> who repairs items, a <b>Mentalist</b> who senses people's limits. They cost $2,000 / $10,000 / $50,000 a week for 1/2/3 stars.</li>
        <li><b>🏗 Upgrades:</b> a bigger shop brings more visitors; the back room holds more stock; display cases make buyers pay more.</li>
        <li><b>📦 Stock:</b> everything you own. Buyers pick from it. Need quick cash? The pawn broker buys anything instantly — for less.</li></ul>
        <div class="keys" style="font-size:14px;line-height:2.2"><kbd>Space</kbd> next visitor · <kbd>Enter</kbd> make offer · <kbd>A</kbd> accept · <kbd>N</kbd> no deal · <kbd>E</kbd> examine · <kbd>X</kbd> ask expert · <kbd>B</kbd> bid · <kbd>1</kbd>–<kbd>4</kbd> tabs</div>
        ${solo ? '<p class="tip">Your solo game <b>saves automatically</b> every day — choose <b>Continue</b> on the main menu next time.</p>'
               : '<p class="tip">If your connection drops, the computer runs your shop until you reopen the link in the same browser.</p>'}` },
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
    S.v = null; S.lastPhase = null; S.lastCash = null; S.tab = 'main'; S.award = null;
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
    page: (d) => { S.tab = d.t; render(); },
    rivals: () => rivalsModal(),
    menu2: () => {
      const v = S.v;
      modal(`<div class="row"><h2 class="grow">Menu</h2><button class="btn sm" data-a="modal-close">Close</button></div><div class="col" style="margin-top:8px">
        ${v.settings.solo && v.phase !== 'final' ? `<button class="btn lg" data-a="pause-m">${v.paused ? '▶ Resume game' : '❚❚ Pause game'}</button>` : ''}
        <button class="btn lg" data-a="intro-show-m">📖 How to play</button>
        <button class="btn lg" data-a="music-m">${SFX.music ? '♫ Music: on' : '♫ Music: off'}</button>
        <button class="btn lg" data-a="sfx-m">${SFX.sfx ? '🔊 Sound: on' : '🔈 Sound: off'}</button>
        <button class="btn lg red" data-a="leave-ask">Leave match</button></div>`);
    },
    'pause-m': () => { modal(''); H.pause(); },
    'intro-show-m': () => { modal(''); H['intro-show'](); },
    'music-m': () => { H.music(); H.menu2(); },
    'sfx-m': () => { H.sfx(); H.menu2(); },
    pause: () => post('/api/pause', { room: S.sess.room, token: S.sess.token, paused: !S.v.paused }, S.sess.base).then(errT),
    music: () => { SFX.setMusic(!SFX.music); updProfile({ settings: { music: SFX.music } }); },
    sfx: () => { SFX.setSfx(!SFX.sfx); updProfile({ settings: { sfx: SFX.sfx } }); },
    ready: () => act('ready'),
    next: () => act('next'),
    'close-early': () => modal(`<h2>Close the shop early?</h2><p class="muted">The rest of today's visitors will go home. You'll go straight to waiting for the auction.</p><div class="row"><button class="btn primary" data-a="close-yes">Close for today</button><button class="btn right" data-a="modal-close">Keep serving</button></div>`),
    'close-yes': () => { modal(''); act('ready'); },
    offer: () => { const v = S.v.me.visitor; if (!v) return; act('offer', { amount: +S.draft.offer[v.id] || 0 }); },
    pct: (d) => { const v = S.v.me.visitor; if (!v) return; setOffer(v, nice(v.item.likely * +d.p)); },
    step: (d) => { const v = S.v.me.visitor; if (!v) return; setOffer(v, nice((+S.draft.offer[v.id] || 0) * (1 + +d.p))); },
    accept: () => act('accept'),
    pass: () => act('pass'),
    examine: async (d) => { SFX.play('scan'); const r = await act('examine', { target: d.target || 'counter' }); if (r.ok && r.res.fake) SFX.play('bad'); },
    opinion: (d) => act('opinion', { target: d.target || 'counter' }),
    quick: (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); if (!it) return; modal(`<h2>Sell ${esc(it.name)} to the pawn broker?</h2><p class="muted">Instant cash, no haggling — but the pawn broker only pays about <b>45% of what it's really worth</b>. Better to wait for a buyer at your counter unless you need the space or the money.</p><div class="row"><button class="btn primary" data-a="quick-yes" data-id="${d.id}">Sell it</button><button class="btn right" data-a="modal-close">Keep it</button></div>`); },
    'quick-yes': (d) => { modal(''); act('quick_sell', { item: d.id }); },
    bid: (d) => act('bid', { amount: +d.amt }),
    upgrade: (d) => act('upgrade', { key: d.k }),
    hire: (d) => act('hire', { role: d.role, stars: +d.stars }),
    fire: (d) => act('fire', { staff: d.id }),
    repair: (d) => { const it = S.v.me.inventory.find((i) => i.id === d.id); const q = it && it.repairQuote; if (!q) return; modal(`<h2>Repair ${esc(it.name)}?</h2><p class="muted">Your mechanic will restore it to <b>${esc(q.toLabel)}</b> for <b>${fmt(q.cost)}</b>. It will be in the workshop for <b>${q.days} day${q.days > 1 ? 's' : ''}</b> (ready on day ${S.v.day + q.days}) and buyers can't buy it meanwhile.</p><div class="row"><button class="btn primary" data-a="repair-yes" data-id="${d.id}">Start repair</button><button class="btn right" data-a="modal-close">Cancel</button></div>`); },
    'repair-yes': (d) => { modal(''); act('repair', { item: d.id }); },
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
    if (!typing && S.screen === 'game' && S.v && S.v.me && !e.metaKey && !e.ctrlKey && !S.introOpen && !$('#modal').innerHTML) {
      const v = S.v.me.visitor, k = e.key.toLowerCase(), shop = S.v.phase === 'shop';
      if (shop && !v && !S.v.me.done && (k === ' ' || k === 'enter')) { e.preventDefault(); SFX.play('click'); H.next(); return; }
      if (shop && v) {
        if (k === 'enter') { e.preventDefault(); SFX.play('click'); H.offer(); return; }
        if (k === 'a') { SFX.play('click'); H.accept(); return; }
        if (k === 'n') { SFX.play('click'); H.pass(); return; }
        if (k === 'e') { H.examine({}); return; }
        if (k === 'x') { SFX.play('click'); H.opinion({}); return; }
      }
      if (k === 'b' && S.v.phase === 'auction') { const b = document.querySelector('[data-a="bid"]:not([disabled])'); if (b) H.bid(b.dataset); return; }
      if (k === 'escape' && S.tab !== 'main') { S.tab = 'main'; render(); return; }
    }
    if (e.key === 'Enter' && e.target.id === 'offer-in') H.offer();
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

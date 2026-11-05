// Procedural vector art for items, people and store scenes. Everything is drawn in code.
(function () {
  const PAL = {
    a: { m: '#c0392b', d: '#7b1e16', l: '#f1948a', x: '#f4d03f' },
    b: { m: '#2e86c1', d: '#1b4f72', l: '#85c1e9', x: '#f8f9f9' },
    c: { m: '#239b56', d: '#145a32', l: '#82e0aa', x: '#f5cba7' },
    d: { m: '#2c2c34', d: '#111116', l: '#5d6d7e', x: '#e5b84b' },
  };
  const GOLD = '#e5b84b', GOLDD = '#a67c1d', SILV = '#cfd8dc', SILVD = '#8a9ba3', WOOD = '#8d5a35', WOODD = '#5b3720',
    GLASS = '#bfe9ff', BRASS = '#d4a645', DARK = '#23232b', CREAM = '#f3ead7', MARBLE = '#ecebe6';

  const R = (x, y, w, h, f, rx = 0, extra = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${f}" ${extra}/>`;
  const C = (x, y, r, f, extra = '') => `<circle cx="${x}" cy="${y}" r="${r}" fill="${f}" ${extra}/>`;
  const E = (x, y, rx, ry, f, extra = '') => `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="${f}" ${extra}/>`;
  const P = (d, f, extra = '') => `<path d="${d}" fill="${f}" ${extra}/>`;
  const L = (x1, y1, x2, y2, s, w = 2, extra = '') => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${s}" stroke-width="${w}" stroke-linecap="round" ${extra}/>`;
  const S = (d, s, w = 2, extra = '') => `<path d="${d}" fill="none" stroke="${s}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;

  const K = {
    phone: (p) => R(34, 14, 32, 72, p.d, 6) + R(37, 20, 26, 56, GLASS, 2) + R(41, 26, 18, 3, '#fff', 1, 'opacity=".6"') + C(50, 81, 2.5, p.l),
    laptop: (p) => P('M22 30h56v38H22z', p.d) + R(26, 34, 48, 30, '#1e3a5f') + R(30, 38, 20, 3, '#5dade2') + R(30, 44, 30, 2, '#5dade2', 0, 'opacity=".6"') + P('M12 68h76l-6 10H18z', SILV) + R(42, 70, 16, 2, SILVD, 1),
    camera: (p) => R(16, 34, 68, 40, p.d, 6) + R(22, 28, 18, 8, p.d, 2) + C(54, 54, 16, DARK) + C(54, 54, 12, '#34495e') + C(54, 54, 7, '#5dade2', 'opacity=".8"') + C(51, 51, 2.5, '#fff', 'opacity=".8"') + R(70, 38, 8, 5, SILV, 1) + R(16, 46, 68, 4, p.l, 0, 'opacity=".4"'),
    console: (p) => R(14, 40, 72, 30, p.m === '#2c2c34' ? '#7f8c8d' : CREAM, 8) + R(20, 46, 18, 18, DARK, 3) + R(26, 52, 6, 6, '#555') + C(68, 52, 4, p.m) + C(76, 58, 4, p.l) + R(44, 54, 10, 3, '#888', 1),
    headphones: (p) => S('M24 58 Q24 18 50 18 Q76 18 76 58', p.d, 7) + R(16, 52, 16, 26, p.m, 6) + R(68, 52, 16, 26, p.m, 6) + R(20, 56, 8, 18, p.d, 3) + R(72, 56, 8, 18, p.d, 3),
    radio: (p) => R(16, 30, 68, 46, WOOD, 10) + R(16, 30, 68, 8, WOODD, 4) + R(22, 42, 34, 28, CREAM, 4) + S('M24 48h30M24 54h30M24 60h30M24 66h30', WOODD, 1.5) + C(68, 50, 6, GOLD) + C(68, 66, 5, GOLD) + L(40, 30, 54, 14, SILVD, 2),
    tv: (p) => R(14, 22, 72, 56, WOOD, 6) + R(20, 28, 46, 40, '#2d3436', 8) + R(24, 32, 38, 32, '#74b9ff', 10, 'opacity=".5"') + C(74, 36, 4, GOLD) + C(74, 48, 4, GOLD) + L(30, 78, 26, 88, WOODD, 4) + L(70, 78, 74, 88, WOODD, 4) + L(44, 22, 34, 8, SILVD, 1.5) + L(56, 22, 66, 8, SILVD, 1.5),
    drone: (p) => R(36, 44, 28, 14, p.m, 5) + L(36, 48, 18, 38, DARK, 3) + L(64, 48, 82, 38, DARK, 3) + E(18, 36, 12, 3, '#888', 'opacity=".7"') + E(82, 36, 12, 3, '#888', 'opacity=".7"') + C(50, 62, 5, DARK) + C(50, 62, 2.5, '#5dade2'),
    watch: (p) => R(40, 6, 20, 26, p.d, 4) + R(40, 68, 20, 26, p.d, 4) + C(50, 50, 22, p.x === '#e5b84b' ? GOLD : SILV) + C(50, 50, 18, p.m === '#2c2c34' ? '#111' : p.l) + L(50, 50, 50, 38, '#fff', 2) + L(50, 50, 59, 53, '#fff', 2) + C(50, 50, 2, GOLD) + R(71, 47, 5, 6, SILVD, 1) + [0, 90, 180, 270].map(a => { const r = a * Math.PI / 180; return C(50 + Math.sin(r) * 14, 50 - Math.cos(r) * 14, 1.4, '#fff'); }).join(''),
    pocketwatch: (p) => S('M50 22 Q30 6 60 8', GOLDD, 2) + C(50, 22, 5, 'none', `stroke="${GOLD}" stroke-width="3"`) + C(50, 56, 28, GOLD) + C(50, 56, 23, CREAM) + L(50, 56, 50, 40, DARK, 2) + L(50, 56, 61, 60, DARK, 1.5) + C(50, 56, 2, DARK) + C(50, 70, 6, 'none', `stroke="${SILVD}" stroke-width="1"`),
    ring: (p) => E(50, 62, 24, 22, 'none', `stroke="${GOLD}" stroke-width="7"`) + P('M40 36 L50 22 L60 36 L50 44Z', p.l) + P('M40 36 L50 22 L50 44Z', '#fff', 'opacity=".5"') + R(44, 38, 12, 6, GOLDD, 2),
    necklace: (p) => S('M18 16 Q50 74 82 16', GOLD, 3) + [0, 1, 2, 3, 4, 5, 6].map(i => { const t = (i + 1) / 8; const x = 18 + 64 * t; const y = 16 + 58 * 4 * t * (1 - t) * 0.5 * 2 * 0.5; return C(x, y + 8, 3.5, p.x === '#f8f9f9' ? '#fff' : CREAM); }).join('') + P('M50 66 L60 78 L50 92 L40 78Z', p.m) + P('M50 66 L50 92 L40 78Z', '#fff', 'opacity=".3"'),
    earrings: (p) => [34, 66].map(x => L(x, 18, x, 34, GOLD, 2) + C(x, 18, 3, GOLD) + P(`M${x} 34 L${x + 9} 50 L${x} 72 L${x - 9} 50Z`, p.m) + P(`M${x} 34 L${x} 72 L${x - 9} 50Z`, '#fff', 'opacity=".35"')).join(''),
    brooch: (p) => C(50, 50, 30, GOLD) + C(50, 50, 24, GOLDD) + P('M50 30 Q66 40 58 54 Q70 66 50 72 Q30 66 42 54 Q34 40 50 30Z', p.m) + C(50, 52, 6, p.l) + [0, 60, 120, 180, 240, 300].map(a => { const r = a * Math.PI / 180; return C(50 + Math.cos(r) * 27, 50 + Math.sin(r) * 27, 2.5, '#fff'); }).join(''),
    crown: (p) => P('M16 70 L20 30 L36 50 L50 22 L64 50 L80 30 L84 70Z', SILV) + R(16, 66, 68, 12, SILVD, 2) + C(50, 22, 4, p.m) + C(20, 30, 3, p.m) + C(80, 30, 3, p.m) + C(50, 56, 6, p.l) + C(32, 70, 3, p.m) + C(68, 70, 3, p.m),
    vase: (p) => P('M38 14h24l-4 12 Q78 40 70 70 Q64 88 50 88 Q36 88 30 70 Q22 40 42 26Z', CREAM) + S('M34 50 Q50 40 66 50', p.m, 4) + S('M32 62 Q50 72 68 62', p.m, 3) + C(50, 56, 5, p.m, 'opacity=".7"') + R(36, 12, 28, 5, p.d, 2),
    clock: (p) => P('M20 84 V44 Q20 16 50 16 Q80 16 80 44 V84Z', WOOD) + C(50, 44, 20, CREAM) + C(50, 44, 20, 'none', `stroke="${GOLD}" stroke-width="3"`) + L(50, 44, 50, 31, DARK, 2) + L(50, 44, 59, 48, DARK, 2) + R(30, 68, 40, 10, WOODD, 2) + R(16, 82, 68, 6, WOODD, 2),
    lamp: (p) => P('M18 50 Q50 6 82 50Z', p.m) + S('M30 40 L50 14 L70 40 M24 48 Q50 30 76 48', GOLD, 1.5) + P('M26 48 Q50 38 74 48 L60 50 Q50 45 40 50Z', p.x, 'opacity=".7"') + R(46, 50, 8, 30, BRASS) + E(50, 84, 18, 5, BRASS),
    teapot: (p) => E(50, 58, 28, 22, SILV) + E(50, 58, 28, 22, 'none', `stroke="${SILVD}" stroke-width="2"`) + P('M22 52 Q6 44 10 30 L16 32 Q14 44 26 48Z', SILV) + S('M76 46 Q92 50 80 72', SILVD, 5) + E(50, 36, 14, 4, SILVD) + C(50, 31, 4, SILVD) + E(42, 52, 6, 10, '#fff', 'opacity=".35"'),
    globe: (p) => C(50, 44, 28, p.b ? p.l : '#5dade2') + C(50, 44, 28, '#6fb7e0') + P('M36 28 Q44 22 52 30 Q48 40 40 38Z M56 46 Q66 40 70 52 Q62 64 56 56Z M30 50 Q38 50 40 60 Q32 62 30 50Z', '#c5a46d') + S('M18 44 A32 32 0 0 0 82 44', BRASS, 3) + R(46, 74, 8, 8, WOOD) + E(50, 86, 20, 5, WOODD),
    gramophone: (p) => R(18, 62, 52, 22, WOOD, 3) + E(44, 62, 22, 4, DARK) + L(60, 60, 64, 40, BRASS, 3) + P('M62 42 Q60 14 90 8 Q88 34 66 46Z', BRASS) + P('M64 40 Q66 20 86 12 Q84 30 66 42Z', GOLDD, 'opacity=".5"'),
    musicbox: (p) => R(18, 46, 64, 36, WOOD, 4) + P('M18 46 L26 24 H74 L82 46Z', WOODD) + R(18, 58, 64, 4, GOLD) + C(50, 70, 5, GOLD) + S('M84 58 q6 0 6 6 t-6 6', GOLD, 2),
    card: (p) => R(26, 10, 48, 80, GOLD, 4) + R(30, 14, 40, 72, p.m, 3) + R(34, 20, 32, 30, p.l) + C(50, 35, 9, p.x) + R(34, 54, 32, 4, '#fff', 1, 'opacity=".8"') + R(34, 62, 24, 3, '#fff', 1, 'opacity=".6"') + P('M26 10 L74 90', 'none', 'stroke="#fff" stroke-width="10" opacity=".18"'),
    comic: (p) => R(22, 10, 56, 80, '#fffbea', 2) + R(22, 10, 56, 16, p.m, 2) + `<text x="50" y="23" text-anchor="middle" font-size="11" font-weight="900" fill="#fff" font-family="Impact,sans-serif">POW!</text>` + C(50, 54, 16, p.l) + P('M38 44 L50 30 L62 44 L56 70 H44Z', p.d) + P('M28 76 L40 66 L46 82Z', p.x),
    coin: (p) => C(50, 50, 34, GOLDD) + C(50, 50, 30, GOLD) + C(50, 50, 24, 'none', `stroke="${GOLDD}" stroke-width="1.5"`) + P('M44 36 Q56 34 58 46 Q60 58 50 64 Q42 60 42 50 Q40 42 44 36Z', GOLDD) + E(40, 38, 6, 10, '#fff', 'opacity=".4"'),
    robot: (p) => R(34, 14, 32, 26, SILV, 3) + C(44, 26, 4, p.m) + C(56, 26, 4, p.m) + R(44, 33, 12, 3, DARK) + L(50, 14, 50, 6, SILVD, 2) + C(50, 5, 3, p.m) + R(30, 42, 40, 30, p.m, 3) + R(38, 48, 24, 12, SILV, 2) + R(20, 44, 8, 22, SILVD, 3) + R(72, 44, 8, 22, SILVD, 3) + R(34, 72, 12, 18, SILVD) + R(54, 72, 12, 18, SILVD),
    vinyl: (p) => R(10, 14, 64, 72, p.m, 2) + R(14, 18, 56, 64, p.l, 1, 'opacity=".4"') + C(62, 50, 32, '#111') + C(62, 50, 26, 'none', 'stroke="#333" stroke-width="1"') + C(62, 50, 18, 'none', 'stroke="#333" stroke-width="1"') + C(62, 50, 9, p.x) + C(62, 50, 2, '#111'),
    figure: (p) => R(26, 8, 48, 84, p.d, 3) + R(30, 18, 40, 64, GLASS, 2, 'opacity=".55"') + C(50, 32, 7, '#f5cba7') + R(42, 40, 16, 22, p.m, 3) + R(42, 62, 6, 14, p.d) + R(52, 62, 6, 14, p.d) + R(36, 42, 6, 16, p.m, 2) + R(58, 42, 6, 16, p.m, 2) + R(26, 8, 48, 8, p.x, 2),
    book: (p) => R(20, 14, 58, 74, p.d, 3) + R(24, 14, 54, 74, p.m, 3) + R(74, 18, 6, 66, CREAM) + R(32, 26, 36, 22, 'none', 0, `stroke="${GOLD}" stroke-width="2"`) + C(50, 37, 6, GOLD) + R(34, 60, 32, 3, GOLD) + R(24, 14, 4, 74, p.l, 0, 'opacity=".3"'),
    jersey: (p) => P('M30 16 L42 12 Q50 20 58 12 L70 16 L88 34 L76 44 L70 38 V88 H30 V38 L24 44 L12 34Z', p.m) + `<text x="50" y="64" text-anchor="middle" font-size="24" font-weight="900" fill="${p.x}" font-family="Impact,sans-serif">23</text>` + S('M36 76 q8 -8 14 0 t14 -2', DARK, 1.5),
    painting: (p) => R(10, 14, 80, 66, GOLD, 2) + R(16, 20, 68, 54, GOLDD) + R(18, 22, 64, 50, '#a9cce3') + P('M18 56 L36 40 L52 54 L64 44 L82 58 V72 H18Z', p.c ? '#27ae60' : '#5d8a4c') + C(68, 34, 6, '#f9e79f') + P('M18 64 Q50 56 82 66 V72 H18Z', p.m, 'opacity=".55"'),
    abstract: (p) => R(14, 10, 72, 80, '#fafafa', 1) + R(14, 10, 72, 80, 'none', 0, 'stroke="#333" stroke-width="2"') + C(38, 36, 14, p.m) + R(50, 44, 28, 36, p.d) + P('M20 82 L44 52 L56 82Z', p.x) + S('M20 26 Q50 60 82 20', p.l, 4),
    sketch: (p) => R(16, 10, 68, 80, CREAM, 1) + S('M36 70 Q30 46 42 32 Q52 22 62 32 Q72 48 62 70', '#444', 1.5) + S('M42 44 q3 -3 6 0 M54 44 q3 -3 6 0 M46 56 q4 4 8 0', '#444', 1.2) + S('M30 80 Q50 72 70 80', '#666', 1) + R(16, 10, 68, 80, 'none', 0, `stroke="${WOOD}" stroke-width="3"`),
    bust: (p) => P('M34 30 Q34 10 50 10 Q66 10 66 30 Q66 48 56 54 L58 62 Q78 66 80 80 H20 Q22 66 42 62 L44 54 Q34 48 34 30Z', MARBLE) + S('M40 30 q3 -2 6 0 M54 30 q3 -2 6 0 M47 44 q3 2 6 0', '#a0a09a', 1.5) + R(28, 80, 44, 10, '#d0cfc8', 1) + E(42, 24, 4, 8, '#fff', 'opacity=".5"'),
    statue: (p) => C(50, 18, 8, '#b07d3c') + P('M42 28 H58 L62 54 L56 56 L58 80 H42 L44 56 L38 54Z', '#b07d3c') + L(58, 32, 72, 16, '#b07d3c', 5) + R(32, 80, 36, 10, '#4b3621', 1) + E(46, 40, 3, 10, '#e0b070', 'opacity=".5"'),
    guitar: (p) => R(46, 4, 8, 44, WOODD) + R(43, 2, 14, 8, DARK, 2) + P('M50 44 Q70 40 70 56 Q64 64 72 74 Q72 94 50 94 Q28 94 28 74 Q36 64 30 56 Q30 40 50 44Z', p.m) + C(50, 72, 6, DARK) + R(40, 82, 20, 4, DARK) + S('M48 10 V84 M52 10 V84', '#eee', 0.7),
    acoustic: (p) => R(46, 4, 8, 42, WOODD) + R(43, 2, 14, 8, WOODD, 2) + P('M50 40 Q66 38 66 54 Q60 62 68 72 Q68 94 50 94 Q32 94 32 72 Q40 62 34 54 Q34 38 50 40Z', '#d4a065') + C(50, 66, 8, '#3e2a1a') + R(42, 80, 16, 3, WOODD) + S('M48 10 V80 M52 10 V80', '#eee', 0.6),
    violin: (p) => P('M50 30 Q62 28 62 40 Q58 48 64 56 Q66 76 50 78 Q34 76 36 56 Q42 48 38 40 Q38 28 50 30Z', '#a04000') + R(47, 4, 6, 28, DARK) + C(50, 6, 4, DARK) + S('M44 50 q-3 4 0 8 M56 50 q3 4 0 8', DARK, 1.5) + R(46, 64, 8, 3, DARK) + L(20, 90, 84, 30, '#d7ccc8', 2),
    trumpet: (p) => S('M14 54 H64', BRASS, 6) + P('M62 54 L86 36 V72Z', BRASS) + E(86, 54, 5, 18, GOLDD) + S('M28 54 V40 h20 V54', BRASS, 4) + [32, 38, 44].map(x => R(x - 2, 32, 4, 10, SILV, 1)).join('') + C(14, 54, 4, SILVD),
    synth: (p) => R(8, 30, 84, 44, WOOD, 4) + R(12, 34, 76, 16, DARK, 2) + [20, 30, 40, 50, 60, 70, 80].map((x, i) => C(x, 42, 3, i % 2 ? p.m : SILV)).join('') + R(12, 54, 76, 16, '#fff') + [16, 26, 36, 46, 56, 66, 76].map(x => R(x, 54, 4, 10, DARK)).join(''),
    sax: (p) => S('M58 8 Q58 20 54 24 V70 Q54 86 40 86 Q26 86 28 70', BRASS, 9) + P('M20 64 Q22 54 36 58 L32 74Z', BRASS) + [32, 42, 52, 62].map(y => C(60, y, 3, GOLDD)).join('') + L(58, 8, 70, 4, DARK, 3),
    chair: (p) => P('M24 20 Q22 12 30 12 H70 Q78 12 76 20 L72 54 H28Z', p.m) + R(20, 52, 60, 14, p.d, 5) + L(28, 66, 22, 90, WOODD, 4) + L(72, 66, 78, 90, WOODD, 4) + L(40, 66, 38, 88, WOODD, 3) + L(60, 66, 62, 88, WOODD, 3),
    cabinet: (p) => R(18, 8, 64, 84, WOOD, 3) + R(24, 14, 24, 52, GLASS, 1, 'opacity=".6"') + R(52, 14, 24, 52, GLASS, 1, 'opacity=".6"') + L(24, 40, 48, 40, WOODD, 2) + L(52, 40, 76, 40, WOODD, 2) + R(24, 70, 52, 16, WOODD, 2) + C(46, 78, 2, GOLD) + C(54, 78, 2, GOLD) + C(36, 30, 4, p.m) + R(60, 26, 8, 12, p.l),
    rug: (p) => R(10, 22, 80, 56, p.m, 2) + R(16, 28, 68, 44, 'none', 0, `stroke="${p.x}" stroke-width="3"`) + P('M50 34 L66 50 L50 66 L34 50Z', p.d) + P('M50 42 L58 50 L50 58 L42 50Z', p.x) + [14, 22, 30, 38, 46, 54, 62, 70, 78, 86].map(x => L(x, 18, x, 22, CREAM, 1.5) + L(x, 78, x, 82, CREAM, 1.5)).join(''),
    stool: (p) => E(50, 24, 22, 7, p.m) + R(28, 24, 44, 5, p.d) + L(32, 28, 24, 90, DARK, 4) + L(68, 28, 76, 90, DARK, 4) + L(50, 28, 50, 88, DARK, 3) + E(50, 62, 18, 3, 'none', `stroke="${DARK}" stroke-width="2.5"`),
    mirror: (p) => E(50, 50, 30, 40, GOLD) + E(50, 50, 24, 34, '#cfe8f3') + P('M36 30 L44 26 L34 60 L30 56Z', '#fff', 'opacity=".55"') + C(50, 10, 5, GOLD) + C(50, 90, 5, GOLD),
    sword: (p) => P('M48 8 L52 8 L54 64 H46Z', SILV) + L(50, 12, 50, 60, '#fff', 1, 'opacity=".7"') + R(32, 62, 36, 6, GOLD, 2) + R(47, 68, 6, 18, WOODD, 1) + C(50, 90, 5, GOLD) + S('M34 66 Q30 76 42 80', GOLD, 2),
    helmet: (p) => P('M24 60 Q22 14 50 12 Q78 14 76 60 L72 80 H28Z', SILV) + R(32, 42, 36, 6, DARK, 2) + [38, 46, 54, 62].map(x => R(x - 1, 52, 2.5, 14, SILVD)).join('') + L(50, 12, 50, 40, SILVD, 3) + P('M50 12 Q56 2 70 4 Q60 8 52 14Z', p.m),
    map: (p) => P('M10 20 L36 14 L64 20 L90 14 V80 L64 86 L36 80 L10 86Z', '#ead7a6') + S('M36 14 V80 M64 20 V86', '#c9b27a', 1) + P('M22 40 Q30 30 44 38 Q50 50 38 56 Q26 56 22 40Z', '#9ab973') + S('M48 62 l6 6 m0 -6 l-6 6', '#c0392b', 2.5) + S('M28 58 Q40 70 50 64', '#c0392b', 1.2, 'stroke-dasharray="2 3"') + C(76, 36, 7, 'none', 'stroke="#7a5c2e" stroke-width="1.2"'),
    medal: (p) => P('M36 8 H48 L54 40 H42Z', p.m) + P('M52 8 H64 L58 40 H46Z', p.l) + C(50, 62, 22, GOLD) + C(50, 62, 16, GOLDD) + P('M50 50 l4 8 9 1 -7 6 2 9 -8 -5 -8 5 2 -9 -7 -6 9 -1z', GOLD),
    compass: (p) => C(50, 50, 34, BRASS) + C(50, 50, 28, CREAM) + P('M50 26 L55 50 L50 74 L45 50Z', '#c0392b') + P('M50 50 L55 50 L50 74 L45 50Z', DARK) + C(50, 50, 3, BRASS) + `<text x="50" y="22" text-anchor="middle" font-size="7" font-weight="700" fill="#555">N</text>` + C(50, 14, 4, 'none', `stroke="${BRASS}" stroke-width="2"`),
    handbag: (p) => S('M34 38 Q34 14 50 14 Q66 14 66 38', p.d, 4) + P('M18 38 H82 L76 86 H24Z', p.m) + R(18, 38, 64, 10, p.d) + R(44, 46, 12, 10, GOLD, 2) + S('M24 70 H76', p.d, 1, 'stroke-dasharray="3 2"'),
    sunglasses: (p) => E(30, 50, 16, 12, '#111') + E(70, 50, 16, 12, '#111') + S('M46 48 Q50 44 54 48', p.x === '#e5b84b' ? GOLD : SILV, 3) + L(14, 46, 6, 40, p.x === '#e5b84b' ? GOLD : SILV, 3) + L(86, 46, 94, 40, p.x === '#e5b84b' ? GOLD : SILV, 3) + E(25, 46, 5, 3, '#fff', 'opacity=".4"') + E(65, 46, 5, 3, '#fff', 'opacity=".4"'),
    pen: (p) => P('M24 80 L70 20 L80 28 L34 88Z', p.d) + P('M70 20 L80 28 L84 22 L76 14Z', GOLD) + P('M24 80 L34 88 L18 94Z', GOLD) + L(60, 32, 68, 26, GOLD, 3),
    perfume: (p) => R(42, 14, 16, 12, GOLD, 2) + R(46, 24, 8, 8, GOLDD) + P('M26 40 Q26 32 34 32 H66 Q74 32 74 40 V80 Q74 88 66 88 H34 Q26 88 26 80Z', p.l, 'opacity=".9"') + R(32, 52, 36, 18, p.m, 2, 'opacity=".75"') + E(36, 44, 4, 8, '#fff', 'opacity=".55"'),
    lighter: (p) => R(32, 34, 36, 54, p.m, 4) + R(32, 22, 36, 14, SILV, 3) + [38, 44, 50, 56, 62].map(x => C(x, 29, 1.5, SILVD)).join('') + P('M48 20 Q44 10 50 4 Q56 12 52 20Z', '#f39c12') + R(38, 46, 24, 30, p.l, 2, 'opacity=".35"'),
    scarf: (p) => P('M20 20 Q50 34 80 20 L76 40 Q50 54 24 40Z', p.m) + P('M56 40 L70 86 L58 88 L48 46Z', p.m) + P('M36 42 L28 84 L40 86 L46 46Z', p.d) + S('M28 30 Q50 40 72 30', p.x, 2) + S('M60 60 l6 20', p.x, 1.5),
    meteor: (p) => P('M26 40 Q30 18 54 20 Q78 22 80 46 Q84 72 58 80 Q30 86 22 64 Q18 52 26 40Z', '#5d5550') + C(40, 40, 6, '#4a433f') + C(60, 58, 8, '#4a433f') + C(64, 34, 4, '#4a433f') + S('M30 66 Q44 70 52 62', '#9e9890', 2) + E(48, 30, 8, 4, '#a39e98', 'opacity=".5"'),
    patch: (p) => C(50, 50, 36, p.d) + C(50, 50, 31, '#0b1d3a') + C(50, 50, 36, 'none', `stroke="${GOLD}" stroke-width="3"`) + P('M50 26 L56 56 H44Z', SILV) + P('M44 56 L40 64 H60 L56 56Z', '#c0392b') + C(66, 36, 3, '#fff') + C(34, 64, 2, '#fff') + C(70, 60, 1.5, '#fff') + E(50, 70, 20, 4, 'none', `stroke="${p.l}" stroke-width="1.5"`),
    visor: (p) => P('M18 56 Q18 14 50 14 Q82 14 82 56 Q82 84 50 86 Q18 84 18 56Z', '#ecf0f1') + P('M26 52 Q26 26 50 26 Q74 26 74 52 Q74 70 50 72 Q26 70 26 52Z', GOLD) + P('M30 46 Q36 30 52 30 Q40 40 36 54Z', '#fff', 'opacity=".45"') + R(40, 80, 20, 8, SILVD, 2),
    rocket: (p) => P('M50 6 Q66 24 64 62 H36 Q34 24 50 6Z', '#ecf0f1') + C(50, 36, 7, '#5dade2') + C(50, 36, 7, 'none', `stroke="${SILVD}" stroke-width="2"`) + P('M36 50 L22 72 L36 66Z', p.m) + P('M64 50 L78 72 L64 66Z', p.m) + R(40, 62, 20, 6, SILVD) + P('M42 68 Q50 96 58 68Z', '#f39c12'),
    amphora: (p) => P('M40 10h20v8 Q72 26 70 52 Q66 80 50 90 Q34 80 30 52 Q28 26 40 18Z', '#c0703a') + S('M40 20 Q24 22 26 40 M60 20 Q76 22 74 40', '#a0582a', 4) + S('M33 46 H67 M32 56 H68', '#2b1d12', 2) + P('M40 47 l4 8 4 -8 4 8 4 -8 4 8', 'none', 'stroke="#2b1d12" stroke-width="1.5"') + R(40, 8, 20, 4, '#8a4a20', 1),
    fossil: (p) => C(50, 50, 34, '#b8a88a') + S('M50 50 m0 -4 a4 4 0 1 1 -4 4 a8 8 0 1 1 8 8 a12 12 0 1 1 -12 -12 a18 18 0 1 1 18 18 a24 24 0 1 1 -24 -24', '#7d6b4f', 3) + E(40, 36, 8, 4, '#fff', 'opacity=".25"'),
    scroll: (p) => R(24, 18, 52, 64, '#efe0b8') + R(18, 12, 64, 10, '#8a5a2b', 5) + R(18, 78, 64, 10, '#8a5a2b', 5) + R(32, 28, 36, 14, p.m, 2, 'opacity=".75"') + C(50, 35, 4, GOLD) + S('M32 50h36M32 56h30M32 62h34M32 68h26', '#6d5a3a', 1.6),
    chest: (p) => R(14, 40, 72, 44, WOOD, 3) + P('M14 42 Q14 18 50 18 Q86 18 86 42Z', WOODD) + R(14, 38, 72, 6, '#555') + [26, 50, 74].map((x) => R(x - 3, 18, 6, 66, '#5a5a5a')).join('') + R(44, 48, 12, 12, GOLD, 2) + C(50, 54, 2, DARK),
    arcade: (p) => P('M26 8 H74 L70 30 L78 62 V92 H22 V62 L30 30Z', p.m) + R(32, 14, 36, 8, p.x, 1) + R(32, 30, 36, 26, '#111', 2) + R(35, 33, 30, 20, '#2ecc71', 1, 'opacity=".5"') + P('M22 62 L30 56 H70 L78 62Z', p.d) + C(38, 60, 3, '#e74c3c') + C(58, 60, 2.5, '#f1c40f') + C(64, 60, 2.5, '#3498db') + R(40, 72, 20, 10, '#111', 1),
    drum: (p) => E(50, 70, 26, 8, '#ddd') + R(24, 50, 52, 20, p.m) + E(50, 50, 26, 8, '#f5f5f5') + E(50, 50, 26, 8, 'none', `stroke="${SILVD}" stroke-width="2"`) + E(22, 30, 14, 4, GOLD) + L(22, 30, 22, 86, SILVD, 2) + E(80, 34, 12, 4, GOLD) + L(80, 34, 80, 86, SILVD, 2) + L(40, 30, 62, 46, WOODD, 2.5) + L(66, 26, 58, 46, WOODD, 2.5),
    piano: (p) => R(12, 14, 76, 56, p.d === '#111116' ? '#111' : '#3b2416', 4) + R(16, 18, 68, 20, '#00000033', 2) + R(14, 52, 72, 14, '#fff') + [18, 26, 34, 46, 54, 62, 70, 78].map((x) => R(x, 52, 4, 8, '#111')).join('') + L(20, 70, 20, 90, '#3b2416', 4) + L(80, 70, 80, 90, '#3b2416', 4) + R(36, 24, 28, 10, CREAM, 1, 'opacity=".7"'),
  };

  // Vehicles: shared side-view builder (body path, cabin, wheels)
  const WHEEL = (x, y, r) => C(x, y, r, '#151515') + C(x, y, r * 0.55, '#9aa5ab') + C(x, y, r * 0.18, '#333');
  const CAR = (body, glass, wheels, extra = '') => (p) => P(body, p.m) + P(body, 'none', `stroke="${p.d}" stroke-width="1.5"`) + P(glass, '#bfe9ff', 'opacity=".85"') + extra + wheels.map(([x, y, r]) => WHEEL(x, y, r)).join('') + E(50, 92, 44, 3, '#000', 'opacity=".25"');
  Object.assign(K, {
    hatchback: CAR('M8 70 V58 Q10 50 20 48 L34 34 H62 Q70 34 76 46 L88 50 Q94 52 94 60 V70Z', 'M37 38 H60 Q66 38 70 47 H30Z', [[26, 72, 10], [76, 72, 10]], R(10, 62, 8, 4, '#f1c40f', 1) + S('M48 38 V48', '#555', 1.5) + C(40, 56, 2, '#6d4c41', 'opacity=".6"') + C(64, 60, 3, '#6d4c41', 'opacity=".5"')),
    sedan: CAR('M4 70 V60 Q6 52 18 50 L32 36 H66 L80 50 Q94 52 96 60 V70Z', 'M35 40 H64 L74 50 H26Z', [[24, 72, 10], [78, 72, 10]], S('M50 40 V50', '#555', 1.5) + R(90, 58, 6, 4, '#f39c12', 1)),
    muscle: CAR('M2 70 V60 Q4 54 16 52 L36 40 H64 L76 52 Q96 52 98 60 V70Z', 'M39 43 H62 L70 52 H32Z', [[22, 72, 11], [80, 72, 11]], R(6, 58, 90, 3, '#fff', 0, 'opacity=".8"') + R(6, 63, 90, 2, '#fff', 0, 'opacity=".6"')),
    roadster: CAR('M4 70 V62 Q6 54 20 54 Q30 46 40 52 L56 52 Q70 44 80 52 Q96 54 96 62 V70Z', 'M44 52 L52 42 L54 52Z', [[24, 72, 11], [78, 72, 11]], C(14, 60, 3, '#fff8d0') + S('M20 54 Q30 48 40 52', SILV, 2)),
    pickup: CAR('M4 72 V56 Q4 50 12 50 L22 34 H48 V50 H96 V72Z', 'M25 38 H44 V49 H17Z', [[24, 74, 10], [78, 74, 10]], R(52, 50, 42, 4, '#00000044') + R(4, 64, 92, 2, '#00000033')),
    jeep: CAR('M6 72 V48 H22 L28 30 H72 V48 H94 V72Z', 'M31 34 H48 V46 H26Z M52 34 H68 V46 H52Z', [[26, 74, 12], [76, 74, 12]], R(92, 50, 6, 16, '#222', 2) + R(4, 46, 94, 3, '#333')),
    van: CAR('M6 72 V36 Q6 24 18 24 H80 Q94 24 94 40 V72Z', 'M12 30 H30 V44 H10Z M36 30 H56 V44 H36Z M62 30 H82 Q88 30 89 44 H62Z', [[24, 74, 10], [76, 74, 10]], R(6, 52, 88, 6, '#fff', 0, 'opacity=".85"') + R(40, 24, 20, 4, '#e0e0e0', 1)),
    motorcycle: (p) => WHEEL(22, 72, 15) + WHEEL(80, 72, 15) + P('M30 62 L46 46 H66 L76 58 L60 66 H40Z', p.m) + R(46, 40, 20, 8, '#222', 3) + L(76, 58, 80, 72, SILV, 3) + L(70, 48, 78, 32, SILV, 3) + L(74, 32, 84, 30, '#222', 3) + L(30, 62, 22, 72, SILV, 3) + S('M40 68 H62', '#888', 4) + E(50, 92, 40, 3, '#000', 'opacity=".25"'),
    scooter: (p) => WHEEL(22, 76, 11) + WHEEL(78, 76, 11) + P('M14 70 Q14 56 30 56 H52 L60 70Z', p.m) + P('M60 70 L70 30 H76 L70 70Z', p.m) + R(26, 48, 26, 8, '#3b2416', 4) + L(68, 28, 82, 26, '#222', 3) + C(78, 40, 4, '#fff8d0') + E(50, 92, 36, 3, '#000', 'opacity=".25"'),
  });
  K.supercar = CAR('M2 70 V64 Q4 58 18 56 L40 44 Q52 40 64 46 L84 54 Q98 56 98 64 V70Z', 'M42 47 Q52 43 62 48 L72 55 H34Z', [[22, 72, 10], [80, 72, 10]], P('M84 54 L98 50 V56Z', '#111') + R(4, 62, 10, 3, '#f1c40f', 1));

  function itemSVG(it, opts = {}) {
    const p = PAL[it.variant] || PAL.a;
    const fn = K[it.kind] || ((pp) => C(50, 50, 30, pp.m));
    const cond = it.condIdx ?? 2;
    let overlay = '';
    if (cond >= 4) {
      overlay += S('M30 20 L44 42 L36 54 L52 78', '#2b1d12', 4) + S('M70 30 L60 46 L68 58', '#2b1d12', 3.5);
    }
    if (cond >= 3) overlay += C(64, 70, 6, '#6d4c41', 'opacity=".45"') + C(32, 30, 4, '#6d4c41', 'opacity=".4"');
    const size = opts.size || 72;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="${size}" height="${size}">${fn(p)}${overlay}</svg>`;
  }

  function personSVG(look, mood = 60, size = 180) {
    const skin = look.skin, hair = look.hair, shirt = look.shirt;
    const st = look.style % 6;
    let hairBack = '', hairFront = '';
    if (st === 0) hairFront = P('M30 40 Q30 14 50 14 Q70 14 70 40 Q66 26 50 26 Q34 26 30 40Z', hair);
    if (st === 1) { hairBack = P('M26 44 Q24 12 50 12 Q76 12 74 44 L76 78 H24Z', hair); hairFront = P('M30 38 Q34 18 50 18 Q66 18 70 38 Q60 28 50 30 Q40 28 30 38Z', hair); }
    if (st === 2) hairFront = P('M30 36 Q32 16 50 16 Q68 16 70 36 L66 30 L60 34 L54 28 L48 34 L42 28 L36 34Z', hair);
    if (st === 3) hairFront = '';
    if (st === 4) { hairBack = C(50, 30, 22, hair); hairFront = P('M30 36 Q30 16 50 14 Q70 16 70 36 Q60 24 50 24 Q40 24 30 36Z', hair); }
    if (st === 5) { hairBack = P('M28 40 Q26 12 50 12 Q74 12 72 40 L70 56 H30Z', hair); hairFront = P('M30 36 Q40 18 64 22 Q56 30 30 36Z', hair); }
    const happy = mood > 60, angry = mood < 30;
    const mouth = happy ? S('M42 52 Q50 59 58 52', '#5a2a1a', 2.2) : angry ? S('M42 56 Q50 50 58 56', '#5a2a1a', 2.2) : L(43, 54, 57, 54, '#5a2a1a', 2.2);
    const brows = angry ? L(38, 34, 46, 37, '#3a2a1a', 2.2) + L(62, 34, 54, 37, '#3a2a1a', 2.2) : L(38, 35, 46, 34, '#3a2a1a', 1.8) + L(54, 34, 62, 35, '#3a2a1a', 1.8);
    const eyes = C(43, 41, 2.4, '#222') + C(57, 41, 2.4, '#222');
    const glasses = look.glasses ? C(43, 41, 6, 'none', 'stroke="#222" stroke-width="1.8"') + C(57, 41, 6, 'none', 'stroke="#222" stroke-width="1.8"') + L(49, 41, 51, 41, '#222', 1.8) : '';
    const beard = look.beard ? P('M33 46 Q34 66 50 68 Q66 66 67 46 Q62 58 50 58 Q38 58 33 46Z', hair, 'opacity=".9"') : '';
    const hat = look.hat ? (look.persona === 'wealthy' ? R(30, 4, 40, 18, '#1b1b1b', 2) + R(22, 20, 56, 5, '#1b1b1b', 2) + R(30, 16, 40, 4, '#8e2b2b')
      : P('M28 26 Q30 8 50 8 Q70 8 72 26Z', look.persona === 'crook' ? '#333' : shirt) + R(24, 24, 52, 5, look.persona === 'crook' ? '#222' : '#00000055', 2)) : '';
    const tie = look.persona === 'wealthy' || look.persona === 'shark' ? P('M48 78 L52 78 L55 96 L50 102 L45 96Z', '#8e2b2b') : '';
    const blush = mood < 20 ? E(38, 48, 4, 2, '#e74c3c', 'opacity=".5"') + E(62, 48, 4, 2, '#e74c3c', 'opacity=".5"') : '';
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120" width="${size}" height="${size * 1.2}">
      ${hairBack}
      ${P('M14 120 Q14 82 50 78 Q86 82 86 120Z', shirt)}
      ${P('M42 78 L50 92 L58 78Z', '#ffffff33')}${tie}
      ${R(44, 62, 12, 18, skin, 4)}
      ${E(50, 42, 20, 24, skin)}
      ${E(30, 44, 3, 5, skin)}${E(70, 44, 3, 5, skin)}
      ${beard}${hairFront}${brows}${eyes}${glasses}${mouth}${blush}${hat}
    </svg>`;
  }

  // ---------------------------------------------------------------- pixel-art pipeline
  // Vector drawings are the source; each is rasterised onto a tiny grid, hard-edged,
  // colour-reduced and outlined, then shown upscaled with crisp (nearest-neighbour) pixels.
  const cache = new Map(), pending = new Map();
  const BLANK = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==';
  let readyCb = null, readyTimer = null;

  function process(img, w, h, cond, crop) {
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d');
    if (crop) {
      // trim empty space so every object fills its tile (keeps aspect, 1px margin for the outline)
      const big = document.createElement('canvas'); big.width = big.height = 200;
      const bx = big.getContext('2d'); bx.drawImage(img, 0, 0, 200, 200);
      const bd = bx.getImageData(0, 0, 200, 200).data;
      let x0 = 200, y0 = 200, x1 = -1, y1 = -1;
      for (let y = 0; y < 200; y++) for (let x = 0; x < 200; x++) if (bd[(y * 200 + x) * 4 + 3] > 60) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      if (x1 >= x0) {
        const bw = x1 - x0 + 1, bh = y1 - y0 + 1, sc = Math.min((w - 2) / bw, (h - 2) / bh);
        const dw = bw * sc, dh = bh * sc;
        ctx.drawImage(big, x0, y0, bw, bh, (w - dw) / 2, h - 1 - dh - (h - 2 - dh) / 2, dw, dh);
      }
    } else ctx.drawImage(img, 0, 0, w, h);
    const d = ctx.getImageData(0, 0, w, h), px = d.data;
    const solid = new Uint8Array(w * h);
    for (let i = 0; i < w * h; i++) {
      const o = i * 4, a = px[o + 3];
      if (a < 96) { px[o + 3] = 0; continue; }
      let r = px[o] * 255 / a, g = px[o + 1] * 255 / a, b = px[o + 2] * 255 / a; // un-premultiply edge pixels
      if (a < 255) { r = px[o]; g = px[o + 1]; b = px[o + 2]; }
      if (cond >= 4) { const l = 0.3 * r + 0.59 * g + 0.11 * b, k = cond >= 5 ? 0.7 : 0.45; r += (l - r) * k; g += (l - g) * k; b += (l - b) * k; if (cond >= 5) { r *= 0.8; g *= 0.8; b *= 0.8; } }
      const q = (v) => Math.min(255, Math.round(v / 28) * 28 + 8); // posterise for a retro palette
      px[o] = q(r); px[o + 1] = q(g); px[o + 2] = q(b); px[o + 3] = 255;
      solid[i] = 1;
    }
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (solid[i]) continue;
      const n = (x > 0 && solid[i - 1]) || (x < w - 1 && solid[i + 1]) || (y > 0 && solid[i - w]) || (y < h - 1 && solid[i + w]);
      if (n) { const o = i * 4; px[o] = 20; px[o + 1] = 14; px[o + 2] = 10; px[o + 3] = 255; }
    }
    ctx.putImageData(d, 0, 0);
    return cv.toDataURL();
  }

  function render(key, svg, w, h, cond, crop = false) {
    if (cache.has(key) || pending.has(key)) return;
    const img = new Image();
    const job = new Promise((res) => {
      img.onload = () => { try { cache.set(key, process(img, w, h, cond, crop)); } catch (e) { cache.set(key, BLANK); } res(); };
      img.onerror = () => { cache.set(key, BLANK); res(); };
    });
    pending.set(key, job);
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    job.then(() => {
      pending.delete(key);
      document.querySelectorAll(`img[data-pk="${CSS.escape(key)}"]`).forEach((el) => { el.src = cache.get(key); el.classList.remove('pending'); });
      clearTimeout(readyTimer); readyTimer = setTimeout(() => readyCb && readyCb(), 30);
    });
    return job;
  }

  const condBucket = (c) => (c == null || c <= 2 ? 1 : c);
  function itemKey(it) { return `i|${it.kind}|${it.variant || 'a'}|${condBucket(it.condIdx)}`; }

  // <img> markup for an item sprite; size in CSS pixels (multiples of 32 look sharpest)
  function item(it, size = 64, cls = '') {
    const key = itemKey(it);
    if (!cache.has(key)) render(key, itemSVG(it, { size: 100 }), 32, 32, condBucket(it.condIdx), true);
    const src = cache.get(key);
    return `<img class="px ${src ? '' : 'pending'} ${cls}" data-pk="${key}" src="${src || BLANK}" width="${size}" height="${size}" alt="${(it.name || it.kind || '').replace(/"/g, '')}" draggable="false">`;
  }

  function person(look, mood = 60, size = 120) {
    const m = mood > 60 ? 'h' : mood < 30 ? 'a' : 'n';
    const key = `p|${look.skin}|${look.hair}|${look.style}|${look.shirt}|${look.hat ? 1 : 0}|${look.glasses ? 1 : 0}|${look.beard ? 1 : 0}|${look.persona || ''}|${m}`;
    if (!cache.has(key)) render(key, personSVG(look, m === 'h' ? 80 : m === 'a' ? 10 : 50, 100), 40, 48, 0);
    const src = cache.get(key);
    return `<img class="px person ${src ? '' : 'pending'}" data-pk="${key}" src="${src || BLANK}" width="${size}" height="${Math.round(size * 1.2)}" alt="" draggable="false">`;
  }

  function preload(kinds) {
    const jobs = [];
    for (const k of kinds) for (const v of 'abcd') { const it = { kind: k, variant: v, condIdx: 1 }; const key = itemKey(it); jobs.push(render(key, itemSVG(it, { size: 100 }), 32, 32, 1, true)); }
    return Promise.all(jobs.filter(Boolean));
  }

  window.ART = { itemSVG, personSVG, PAL, item, person, preload, kinds: () => Object.keys(K), onReady: (fn) => { readyCb = fn; } };
})();

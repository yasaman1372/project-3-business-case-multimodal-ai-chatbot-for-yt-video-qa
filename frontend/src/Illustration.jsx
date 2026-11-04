// Background illustration: a cozy library at night, in a storybook style.
// Bookshelves frame the scene, an arched window shows a "play" moon, and a
// reader sits in an armchair by lamplight with a cat asleep on a book stack.
// Purely decorative: hidden from screen readers.

// Bird in flight, facing right: body, tail, two raised wings, head and beak
const BIRD_BODY = "M-20 4 C -10 -5 10 -7 22 -3 C 27 -1 30 2 31 4 C 22 10 -4 12 -20 4 Z";
const BIRD_TAIL = "M-17 3 L-36 -4 L-31 4 L-37 12 L-15 8 Z";
const BIRD_WING_BACK = "M-2 0 C -4 -16 -12 -30 -24 -40 C -6 -36 10 -22 12 -1 Z";
const BIRD_WING_FRONT = "M4 0 C 6 -20 16 -36 30 -46 C 28 -28 24 -12 18 2 Z";

const BOOK_COLORS = [
  "#c4553a", "#e8613c", "#f2b43c", "#3f7d4b", "#2f6b4f", "#6b4d7a",
  "#5a4470", "#d9a441", "#8a9a3a", "#a35a3c", "#e9dcc0", "#2b3d52", "#8c3b2e",
];

const SKIN = "#f2c9a0";
const SKIN_SHADE = "#e0a982";
const HAIR = "#4a2c1d";
const SWEATER = "#e0a53c";
const SWEATER_SHADE = "#b98128";

// Deterministic pseudo-random so the scene looks the same on every render
function seeded(n) {
  const v = Math.sin(n * 9301 + 49297) * 233280;
  return v - Math.floor(v);
}

// ---------- Books & shelves ----------

function shelfBooks(x0, x1, y, seed) {
  const books = [];
  let x = x0 + 4;
  let i = 0;
  while (x < x1 - 14) {
    const w = 12 + Math.floor(seeded(seed + i + 50) * 13);
    const h = 72 + Math.floor(seeded(seed + i + 100) * 40);
    if (x + w > x1 - 4) break;
    const leaning = seeded(seed + i) > 0.9 && x + w + 30 < x1;
    books.push({
      x, y, w, h,
      color: BOOK_COLORS[Math.floor(seeded(seed + i + 150) * BOOK_COLORS.length)],
      bands: seeded(seed + i + 200) > 0.45,
      label: seeded(seed + i + 220) > 0.6,
      youtube: w >= 15 && seeded(seed + i + 270) > 0.62,
      lean: leaning ? 14 : 0,
    });
    x += w + (leaning ? 18 : 1.5);
    if (seeded(seed + i + 250) > 0.88) x += 16;
    i += 1;
  }
  return books;
}

// Small YouTube logo on a white passe-partout: red rounded rectangle with a white play triangle
function YouTubeMark({ cx, cy, width }) {
  const h = width * 0.7;
  const pad = width * 0.2;
  return (
    <g>
      <rect x={cx - width / 2 - pad} y={cy - h / 2 - pad} width={width + pad * 2} height={h + pad * 2}
            rx={pad * 0.8} fill="#fbf6ec" stroke="rgba(0,0,0,0.15)" strokeWidth="0.6" />
      <rect x={cx - width / 2} y={cy - h / 2} width={width} height={h} rx={h * 0.28} fill="#ff0000" />
      <path d={`M${cx - width * 0.14} ${cy - h * 0.27} L${cx + width * 0.2} ${cy} L${cx - width * 0.14} ${cy + h * 0.27} Z`}
            fill="#fff" />
    </g>
  );
}

function Book({ b }) {
  return (
    <g transform={b.lean ? `rotate(${b.lean} ${b.x + b.w} ${b.y})` : undefined}>
      <rect x={b.x} y={b.y - b.h} width={b.w} height={b.h} rx="1.5" fill={b.color} />
      <rect x={b.x} y={b.y - b.h} width={b.w} height={b.h} rx="1.5" fill="url(#ill-book-shade)" />
      {b.bands && (
        <>
          <rect x={b.x + 1} y={b.y - b.h + 9} width={b.w - 2} height="2" fill="#f3d58a" opacity="0.8" />
          <rect x={b.x + 1} y={b.y - 12} width={b.w - 2} height="2" fill="#f3d58a" opacity="0.8" />
        </>
      )}
      {b.youtube ? (
        <YouTubeMark cx={b.x + b.w / 2} cy={b.y - b.h * 0.55} width={Math.min((b.w - 3) / 1.4, 12)} />
      ) : b.label && (
        <rect x={b.x + 3} y={b.y - b.h * 0.62} width={b.w - 6} height={b.h * 0.18} rx="1" fill="#f6ecd6" opacity="0.85" />
      )}
    </g>
  );
}

function Bookcase({ x, width, top, bottom, rows, seed }) {
  const step = (bottom - top) / rows;
  return (
    <g>
      {/* frame with wood grain */}
      <rect x={x} y={top - 24} width={width} height={bottom - top + 24} fill="url(#ill-wood)" />
      {[0.25, 0.5, 0.75].map((t) => (
        <path key={t} d={`M${x + 4} ${top} C ${x + 8} ${top + 200} ${x + 2} ${bottom - 300} ${x + 6} ${bottom}`}
              stroke="rgba(0,0,0,0.18)" strokeWidth="1" fill="none" transform={`translate(${t * 6} 0)`} />
      ))}
      <rect x={x + 12} y={top} width={width - 24} height={bottom - top} fill="#170f09" />
      {Array.from({ length: rows }, (_, r) => {
        const shelfY = top + step * (r + 1);
        return (
          <g key={r}>
            {/* soft shadow at the back of each shelf */}
            <rect x={x + 12} y={shelfY - step} width={width - 24} height={step} fill="url(#ill-shelf-shadow)" />
            {shelfBooks(x + 14, x + width - 14, shelfY, seed + r * 37).map((b, i) => <Book key={i} b={b} />)}
            <rect x={x + 6} y={shelfY} width={width - 12} height="13" fill="url(#ill-wood-light)" />
            <rect x={x + 6} y={shelfY} width={width - 12} height="2" fill="rgba(255,220,170,0.25)" />
            <rect x={x + 6} y={shelfY + 13} width={width - 12} height="5" fill="rgba(0,0,0,0.35)" />
          </g>
        );
      })}
      <rect x={x - 6} y={top - 40} width={width + 12} height="18" rx="2" fill="url(#ill-wood-light)" />
      <rect x={x - 6} y={top - 40} width={width + 12} height="3" fill="rgba(255,220,170,0.25)" />
    </g>
  );
}

// ---------- Small props ----------

function BirdShape({ fill }) {
  return (
    <>
      <path d={BIRD_WING_BACK} fill={fill} opacity="0.75" />
      <path d={BIRD_TAIL} fill={fill} />
      <path d={BIRD_BODY} fill={fill} />
      <circle cx="25" cy="-2" r="6" fill={fill} />
      <path d="M30 -4 L39 -1 L30 1 Z" fill="#f2a43c" />
      <g className="ill-wing">
        <path d={BIRD_WING_FRONT} fill={fill} />
      </g>
    </>
  );
}

function Bird({ x, y, scale = 1, delay = 0 }) {
  return (
    <g className="ill-bird" style={{ animationDelay: `${delay}s` }}>
      <g transform={`translate(${x} ${y}) scale(${scale})`}>
        <g filter="url(#ill-glow-strong)" opacity="0.9">
          <BirdShape fill="#ffb347" />
        </g>
        <BirdShape fill="#ffe7a8" />
        <circle cx="27" cy="-3" r="1.2" fill="#5a3a24" />
      </g>
    </g>
  );
}

function PendantLamp({ x, cordLength = 110 }) {
  const y = cordLength;
  return (
    <g>
      <polygon points={`${x - 26},${y + 30} ${x + 26},${y + 30} ${x + 230},900 ${x - 230},900`}
               fill="url(#ill-light-cone)" className="ill-lantern" />
      <line x1={x} y1="-10" x2={x} y2={y} stroke="#1a110b" strokeWidth="3" />
      <circle cx={x} cy={y + 34} r="90" fill="url(#ill-lamp-glow)" className="ill-lantern" />
      <path d={`M${x - 14} ${y} L${x + 14} ${y} L${x + 36} ${y + 32} L${x - 36} ${y + 32} Z`} fill="url(#ill-brass)" />
      <path d={`M${x - 10} ${y + 3} L${x - 26} ${y + 29}`} stroke="rgba(255,240,200,0.5)" strokeWidth="2" />
      <rect x={x - 6} y={y - 6} width="12" height="8" rx="2" fill="#8a6a2a" />
      <ellipse cx={x} cy={y + 33} rx="24" ry="6" fill="#fff4d6" />
    </g>
  );
}

// ---------- Reading corner ----------

function FloorLamp() {
  return (
    <g>
      <circle cx="62" cy="545" r="160" fill="url(#ill-lamp-glow)" className="ill-lantern" />
      <rect x="58" y="575" width="7" height="318" fill="url(#ill-brass)" />
      <ellipse cx="62" cy="893" rx="36" ry="8" fill="#2a1b12" />
      <ellipse cx="62" cy="890" rx="30" ry="5" fill="#8a6a2a" />
      <path d="M20 582 L104 582 L88 524 L36 524 Z" fill="#e8613c" />
      {[34, 46, 58, 70, 82].map((x) => (
        <line key={x} x1={x + 6} y1="526" x2={x} y2="580" stroke="rgba(0,0,0,0.12)" strokeWidth="1.2" />
      ))}
      <path d="M36 524 L88 524" stroke="#ffb27a" strokeWidth="2" />
      <ellipse cx="62" cy="582" rx="42" ry="5" fill="#ffd9a0" opacity="0.8" />
    </g>
  );
}

function Armchair({ children }) {
  return (
    <g>
      {/* back */}
      <path d="M100 840 L100 700 C 100 650 135 628 205 628 C 275 628 310 650 310 700 L310 840 Z" fill="#b8573c" />
      <path d="M100 840 L100 700 C 100 650 135 628 205 628 C 275 628 310 650 310 700 L310 840 Z" fill="url(#ill-fabric)" />
      <path d="M100 840 L100 700 C 100 650 135 628 205 628 C 275 628 310 650 310 700 L310 840 Z" fill="url(#ill-chair-shade)" />
      {[[160, 680], [205, 672], [250, 680], [182, 730], [228, 730]].map(([cx, cy], i) => (
        <g key={i}>
          <circle cx={cx} cy={cy} r="3.5" fill="#7d3524" />
          <circle cx={cx - 1} cy={cy - 1} r="1.2" fill="#e08a6a" />
        </g>
      ))}
      {/* base */}
      <rect x="104" y="836" width="202" height="54" fill="#a24c33" />
      <rect x="104" y="836" width="202" height="54" fill="url(#ill-fabric)" />
      <rect x="104" y="872" width="202" height="18" fill="rgba(0,0,0,0.2)" />
      {/* seat cushion */}
      <rect x="118" y="805" width="174" height="44" rx="14" fill="#c4613f" />
      <rect x="118" y="805" width="174" height="44" rx="14" fill="url(#ill-fabric)" />
      <rect x="124" y="808" width="162" height="6" rx="3" fill="rgba(255,200,160,0.25)" />

      {children}

      {/* arms (in front of the reader) */}
      {[[78, 140], [270, 332]].map(([x0, x1], i) => (
        <g key={i}>
          <path d={`M${x0} 890 L${x0} 790 C ${x0} 762 ${x1} 762 ${x1} 790 L${x1} 890 Z`} fill="#c4613f" />
          <path d={`M${x0} 890 L${x0} 790 C ${x0} 762 ${x1} 762 ${x1} 790 L${x1} 890 Z`} fill="url(#ill-fabric)" />
          <path d={`M${x0 + 6} 788 C ${x0 + 10} 772 ${x1 - 10} 772 ${x1 - 6} 788`} stroke="rgba(255,210,170,0.35)"
                strokeWidth="3" fill="none" strokeLinecap="round" />
          <rect x={x0} y="850" width={x1 - x0} height="40" fill="rgba(0,0,0,0.18)" />
        </g>
      ))}
      {/* wooden feet */}
      {[92, 318].map((x) => (
        <rect key={x} x={x - 7} y="888" width="14" height="10" rx="2" fill="#4a2f1c" />
      ))}
    </g>
  );
}

function Reader() {
  return (
    <g>
      {/* glow from the open book */}
      <circle cx="205" cy="790" r="72" fill="url(#ill-lamp-glow)" opacity="0.55" />

      {/* trousers: two straight legs from the sweater hem down to the ankles */}
      <rect x="178" y="810" width="25" height="70" rx="3" fill="#2b3d52" />
      <rect x="207" y="810" width="25" height="70" rx="3" fill="#26384c" />
      <rect x="181" y="812" width="3" height="66" fill="rgba(255,255,255,0.08)" />
      <path d="M190.5 818 L190.5 876 M219.5 818 L219.5 876" stroke="rgba(0,0,0,0.18)" strokeWidth="1" />
      <path d="M178 878 L203 878 M207 878 L232 878" stroke="#1f2e40" strokeWidth="2" />
      {/* socks + shoes pointing forward */}
      <rect x="182" y="879" width="17" height="6" fill="#d9a441" />
      <rect x="211" y="879" width="17" height="6" fill="#d9a441" />
      <rect x="182" y="881" width="17" height="1.6" fill="#c4553a" />
      <rect x="211" y="881" width="17" height="1.6" fill="#c4553a" />
      <path d="M178 892 C 178 884 182 883 190.5 883 C 199 883 203 884 203 892 Z" fill="#5a3a24" />
      <path d="M207 892 C 207 884 211 883 219.5 883 C 228 883 232 884 232 892 Z" fill="#5a3a24" />
      <ellipse cx="187" cy="886.5" rx="4" ry="1.4" fill="rgba(255,220,180,0.45)" />
      <ellipse cx="216" cy="886.5" rx="4" ry="1.4" fill="rgba(255,220,180,0.45)" />

      {/* torso: knitted sweater */}
      <path d="M170 816 C 167 784 168 758 184 744 L226 744 C 242 758 243 784 240 816 Z" fill={SWEATER} />
      <path d="M170 816 C 167 784 168 758 184 744 L226 744 C 242 758 243 784 240 816 Z" fill="url(#ill-knit)" />
      <path d="M170 816 C 167 784 168 758 184 744 L190 744 C 180 762 178 790 181 816 Z" fill={SWEATER_SHADE} opacity="0.55" />
      <rect x="170" y="808" width="70" height="10" rx="4" fill={SWEATER_SHADE} />
      {[176, 184, 192, 200, 208, 216, 224, 232].map((x) => (
        <line key={x} x1={x} y1="809" x2={x} y2="817" stroke="rgba(0,0,0,0.15)" strokeWidth="1.5" />
      ))}
      <path d="M194 744 L205 757 L216 744 Z" fill="#f6ecd6" />
      <path d="M194 744 L205 757 L216 744" stroke="#d8c8a8" strokeWidth="1" fill="none" />

      {/* neck + head */}
      <rect x="199" y="727" width="13" height="19" rx="5" fill={SKIN_SHADE} />
      <ellipse cx="183" cy="708" rx="5" ry="7" fill={SKIN_SHADE} />
      <ellipse cx="228" cy="708" rx="5" ry="7" fill={SKIN_SHADE} />
      <ellipse cx="205.5" cy="706" rx="23" ry="26" fill={SKIN} />
      <ellipse cx="205.5" cy="718" rx="19" ry="12" fill="#ffe0b8" opacity="0.4" />

      {/* hair: bob with fringe */}
      <path d="M181 712 C 176 678 196 668 206 668 C 222 668 238 678 231 712 C 232 724 236 730 238 734
               C 228 734 226 722 226 708 C 220 694 200 690 188 700 C 186 712 186 724 176 734 C 176 728 180 722 181 712 Z"
            fill={HAIR} />
      <path d="M188 700 C 196 686 214 684 226 700 C 222 690 212 682 204 682 C 196 682 190 690 188 700 Z" fill="#5c3826" />
      <path d="M196 676 C 204 672 216 674 222 680" stroke="#7a4e34" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M186 690 C 188 682 194 676 200 674" stroke="#7a4e34" strokeWidth="1.5" fill="none" strokeLinecap="round" />

      {/* face, looking down at the book */}
      <path d="M190 699 q 6 -3 11 0" stroke="#3a2418" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      <path d="M210 699 q 6 -3 11 0" stroke="#3a2418" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      {[196, 215].map((ex) => (
        <g key={ex}>
          <path d={`M${ex - 4.6} 709 Q ${ex} 704.6 ${ex + 4.6} 709 Q ${ex} 712.4 ${ex - 4.6} 709 Z`} fill="#fffaf2" />
          <circle cx={ex} cy="710" r="2.3" fill="#5a3522" />
          <circle cx={ex} cy="710.3" r="1.2" fill="#1f130c" />
          <circle cx={ex + 0.8} cy="709.2" r="0.6" fill="#fff" />
          <path d={`M${ex - 4.8} 709 Q ${ex} 704.4 ${ex + 4.8} 709`} stroke="#3a2418" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          <path d={`M${ex + (ex < 205 ? -4.8 : 4.8)} 709 l ${ex < 205 ? -1.8 : 1.8} -1.2`} stroke="#3a2418" strokeWidth="1.1" strokeLinecap="round" />
        </g>
      ))}
      <circle cx="196" cy="708" r="8" fill="rgba(255,240,210,0.12)" stroke="#6b4a2a" strokeWidth="1.6" />
      <circle cx="215" cy="708" r="8" fill="rgba(255,240,210,0.12)" stroke="#6b4a2a" strokeWidth="1.6" />
      <path d="M204 707 q 1.5 -2 3 0" stroke="#6b4a2a" strokeWidth="1.6" fill="none" />
      <path d="M192 704 l 3 -2" stroke="rgba(255,255,255,0.6)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M205.5 711 q 3 6 -1 8" stroke={SKIN_SHADE} strokeWidth="1.8" fill="none" strokeLinecap="round" />
      <circle cx="190" cy="719" r="4.5" fill="#ec8f78" opacity="0.45" />
      <circle cx="221" cy="719" r="4.5" fill="#ec8f78" opacity="0.45" />
      <path d="M200 724 q 5 3.5 10 0" stroke="#a8553f" strokeWidth="1.6" fill="none" strokeLinecap="round" />

      {/* arms: upper arms hang from the shoulders, elbows at the sides,
          forearms come forward to the outer edges of the book */}
      <path d="M184 752 C 174 764 168 782 167 796 C 167 803 168 807 170 810" stroke={SWEATER} strokeWidth="15"
            fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M226 752 C 236 764 242 782 243 796 C 243 803 242 807 240 810" stroke={SWEATER} strokeWidth="15"
            fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M178 762 C 172 774 168 786 167 796" stroke={SWEATER_SHADE} strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.7" />
      <path d="M232 762 C 238 774 242 786 243 796" stroke={SWEATER_SHADE} strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.7" />

      {/* open book: cover, page stacks with thickness, curved pages meeting at the spine */}
      <path d="M168 796 Q 186 790 205 798 Q 224 790 242 796 L242 820 Q 224 814 205 822 Q 186 814 168 820 Z" fill="#c4553a" />
      <path d="M171 795 Q 188 790 205 797 L205 819 Q 188 813 171 817 Z" fill="#e6d8b8" />
      <path d="M239 795 Q 222 790 205 797 L205 819 Q 222 813 239 817 Z" fill="#dccdab" />
      <path d="M171 792 Q 188 786 205 795 L205 817 Q 188 810 171 814 Z" fill="#fbf3e2" />
      <path d="M239 792 Q 222 786 205 795 L205 817 Q 222 810 239 814 Z" fill="#f3e8d0" />
      <path d="M171 815.5 Q 188 811.5 205 818 M239 815.5 Q 222 811.5 205 818" stroke="#cbb994" strokeWidth="0.8" fill="none" />
      <path d="M205 795 L205 817" stroke="#cbb994" strokeWidth="1.2" />
      <path d="M201 796 Q 203 806 201 816" stroke="rgba(0,0,0,0.08)" strokeWidth="4" fill="none" />
      <path d="M209 796 Q 207 806 209 816" stroke="rgba(0,0,0,0.08)" strokeWidth="4" fill="none" />
      {[0, 1, 2, 3].map((i) => (
        <g key={i} stroke="#b8a888" strokeWidth="1" strokeLinecap="round" fill="none">
          <path d={`M176 ${796 + i * 4.4} Q 188 ${792 + i * 4.4} 200 ${799 + i * 4.4}`} />
          <path d={`M210 ${799 + i * 4.4} Q 222 ${792 + i * 4.4} 234 ${796 + i * 4.4}`} />
        </g>
      ))}

      {/* cuffs + hands gripping the outer edges of the cover */}
      <rect x="160" y="801" width="14" height="9" rx="3" fill={SWEATER_SHADE} />
      <rect x="236" y="801" width="14" height="9" rx="3" fill={SWEATER_SHADE} />
      <path d="M161 810 C 160 804 166 802 171 805 C 174 808 174 816 170 819 C 165 821 161 816 161 810 Z" fill={SKIN} />
      <path d="M249 810 C 250 804 244 802 239 805 C 236 808 236 816 240 819 C 245 821 249 816 249 810 Z" fill={SKIN} />
      <path d="M168 806 C 171 808 171 813 169 815 M242 806 C 239 808 239 813 241 815" stroke={SKIN_SHADE} strokeWidth="1"
            fill="none" strokeLinecap="round" />
      <path d="M163 813 q 3 1 5 0 M163 816 q 3 1 5 0 M247 813 q -3 1 -5 0 M247 816 q -3 1 -5 0" stroke={SKIN_SHADE}
            strokeWidth="0.8" fill="none" strokeLinecap="round" />
    </g>
  );
}

function Mug() {
  // Sits on the flat top of the right armrest (top edge at y = 769)
  return (
    <g>
      <ellipse cx="301" cy="771" rx="17" ry="3" fill="rgba(0,0,0,0.25)" />
      <rect x="289" y="745" width="24" height="26" rx="4" fill="#e9dcc0" />
      <ellipse cx="301" cy="745.5" rx="12" ry="2.5" fill="#5a3a24" />
      <rect x="292" y="753" width="18" height="6" fill="#3f7d4b" opacity="0.8" />
      <path d="M313 751 q 10 0 10 8 q 0 8 -10 8" stroke="#e9dcc0" strokeWidth="3.5" fill="none" />
      <rect x="291" y="748" width="4" height="20" rx="2" fill="rgba(255,255,255,0.35)" />
      <g className="ill-steam" fill="none" stroke="#f3ecdc" strokeWidth="2" strokeLinecap="round" opacity="0.5">
        <path d="M297 738 q -6 -10 0 -20 q 6 -10 0 -20" />
        <path d="M306 740 q -6 -10 0 -20 q 6 -10 0 -20" />
      </g>
    </g>
  );
}

// ---------- Right corner: plant, book stack, cat ----------

function MonsteraLeaf({ angle, length, color }) {
  return (
    <g transform={`rotate(${angle})`}>
      <path d={`M0 0 L0 ${-length * 0.55}`} stroke="#2f5a3a" strokeWidth="3" />
      <g transform={`translate(0 ${-length * 0.55})`}>
        <path d={`M0 0 C ${length * 0.32} ${-length * 0.08} ${length * 0.34} ${-length * 0.4} 0 ${-length * 0.5}
                  C ${-length * 0.34} ${-length * 0.4} ${-length * 0.32} ${-length * 0.08} 0 0 Z`} fill={color} />
        <path d={`M0 -2 L0 ${-length * 0.48}`} stroke="rgba(0,0,0,0.22)" strokeWidth="2" />
        {[0.15, 0.27, 0.39].map((t) => (
          <g key={t} stroke="rgba(0,0,0,0.18)" strokeWidth="1.5">
            <line x1="0" y1={-length * t} x2={length * 0.2} y2={-length * (t + 0.06)} />
            <line x1="0" y1={-length * t} x2={-length * 0.2} y2={-length * (t + 0.06)} />
          </g>
        ))}
        <path d={`M${-length * 0.06} ${-length * 0.12} C ${-length * 0.2} ${-length * 0.2} ${-length * 0.2} ${-length * 0.32} ${-length * 0.08} ${-length * 0.42}`}
              stroke="rgba(255,255,255,0.18)" strokeWidth="2" fill="none" />
      </g>
    </g>
  );
}

function Plant() {
  return (
    <g>
      <g transform="translate(1240 812)">
        <g className="ill-sway-right">
          <MonsteraLeaf angle={-42} length={150} color="#2f6b4f" />
          <MonsteraLeaf angle={-14} length={185} color="#3f7d4b" />
          <MonsteraLeaf angle={14} length={172} color="#4c8a4f" />
          <MonsteraLeaf angle={40} length={140} color="#2f6b4f" />
        </g>
      </g>
      <path d="M1203 818 L1277 818 L1266 895 L1214 895 Z" fill="#c4613f" />
      <path d="M1210 840 L1271 840 M1212 862 L1269 862" stroke="#e8935f" strokeWidth="3" opacity="0.7" />
      <path d="M1203 818 L1215 818 L1222 895 L1214 895 Z" fill="rgba(255,220,180,0.18)" />
      <rect x="1197" y="808" width="86" height="15" rx="4" fill="#a8502f" />
      <rect x="1199" y="809" width="82" height="3" rx="1.5" fill="rgba(255,220,180,0.3)" />
    </g>
  );
}

function BookStack() {
  const stack = [
    [1105, 878, 138, "#2f6b4f"],
    [1111, 860, 124, "#d9a441"],
    [1101, 842, 132, "#6b4d7a"],
    [1114, 826, 110, "#c4553a"],
  ];
  return (
    <g>
      {stack.map(([x, y, w, c], i) => (
        <g key={i}>
          <rect x={x} y={y} width={w} height="17" rx="2.5" fill={c} />
          <rect x={x} y={y} width={w} height="17" rx="2.5" fill="url(#ill-book-shade-v)" />
          <rect x={x + w - 8} y={y + 2} width="6" height="13" fill="#f6ecd6" />
          {[4, 7, 10].map((dy) => (
            <line key={dy} x1={x + w - 8} y1={y + 2 + dy} x2={x + w - 2} y2={y + 2 + dy} stroke="#d8c8a8" strokeWidth="0.8" />
          ))}
          {i === 2 ? (
            <YouTubeMark cx={x + w * 0.42} cy={y + 8.5} width={13} />
          ) : (
            <rect x={x + 14} y={y + 6} width={w * 0.35} height="2.5" fill="#f3d58a" opacity="0.75" />
          )}
        </g>
      ))}
    </g>
  );
}

// Cat sitting upright, facing the viewer. y = 0 is the surface it sits on.
function Cat({ x, y }) {
  const fur = "#e08a48";
  const furDark = "#c4672e";
  const furLight = "#f6c08e";
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="ill-cat">
        {/* tail curling round the right side */}
        <path d="M14 -3 C 30 -2 34 -16 30 -28 C 28 -34 24 -36 22 -34" stroke={fur} strokeWidth="7"
              strokeLinecap="round" fill="none" />
        <path d="M27 -31 C 26 -34 24 -35.5 22 -34" stroke={furDark} strokeWidth="7" strokeLinecap="round" fill="none" />
        {/* body */}
        <path d="M-19 0 C -24 -18 -18 -40 0 -44 C 18 -40 24 -18 19 0 Z" fill={fur} />
        <path d="M-17 -12 q 5 -2 8 2 M-19 -22 q 5 -2 8 2 M17 -12 q -5 -2 -8 2 M19 -22 q -5 -2 -8 2" stroke={furDark}
              strokeWidth="2.4" strokeLinecap="round" fill="none" />
        <ellipse cx="0" cy="-24" rx="9" ry="15" fill={furLight} />
        {/* front legs + paws */}
        <rect x="-9.5" y="-18" width="7.5" height="18" rx="3.5" fill={fur} />
        <rect x="2" y="-18" width="7.5" height="18" rx="3.5" fill={fur} />
        <ellipse cx="-5.8" cy="-1.5" rx="5" ry="3" fill={furLight} />
        <ellipse cx="5.8" cy="-1.5" rx="5" ry="3" fill={furLight} />
        {/* ears */}
        <path d="M-16 -60 L-13 -80 L-2 -67 Z" fill={fur} />
        <path d="M16 -60 L13 -80 L2 -67 Z" fill={fur} />
        <path d="M-13.5 -63 L-12 -75 L-5.5 -67 Z" fill="#f2a7a0" />
        <path d="M13.5 -63 L12 -75 L5.5 -67 Z" fill="#f2a7a0" />
        {/* head */}
        <ellipse cx="0" cy="-56" rx="18" ry="15" fill={fur} />
        <path d="M0 -70 L0 -64 M-5 -69 L-4 -64 M5 -69 L4 -64" stroke={furDark} strokeWidth="2" strokeLinecap="round" />
        <ellipse cx="0" cy="-49" rx="9" ry="6" fill={furLight} />
        {/* green almond eyes with slit pupils */}
        {[-7, 7].map((ex) => (
          <g key={ex}>
            <path d={`M${ex - 4.5} -57 Q ${ex} -62.5 ${ex + 4.5} -57 Q ${ex} -51.5 ${ex - 4.5} -57 Z`} fill="#a6cf5e" />
            <ellipse cx={ex} cy="-57" rx="1.2" ry="3.6" fill="#1f130c" />
            <circle cx={ex + 1.4} cy="-58.6" r="0.9" fill="#fff" />
            <path d={`M${ex - 4.5} -57 Q ${ex} -62.5 ${ex + 4.5} -57`} stroke="#5a2e16" strokeWidth="1" fill="none" />
          </g>
        ))}
        {/* nose, mouth, whiskers */}
        <path d="M-2.2 -51.5 L2.2 -51.5 L0 -49 Z" fill="#d9707a" />
        <path d="M0 -49 L0 -47.5 M0 -47.5 q -2 1.6 -3.6 0 M0 -47.5 q 2 1.6 3.6 0" stroke="#5a2e16" strokeWidth="0.9"
              fill="none" strokeLinecap="round" />
        <path d="M6 -49 l 13 -2 M6 -47 l 13 1.5 M-6 -49 l -13 -2 M-6 -47 l -13 1.5" stroke="rgba(255,245,230,0.75)"
              strokeWidth="0.7" />
      </g>
    </g>
  );
}

// ---------- Scene ----------

const STARS = Array.from({ length: 26 }, (_, i) => ({
  x: 650 + seeded(i + 1) * 300,
  y: 110 + seeded(i + 101) * 420,
  r: 0.7 + seeded(i + 201) * 1.5,
  delay: seeded(i + 301) * 6,
}));

const MOTES = [
  [470, 380], [380, 520], [1140, 330], [1230, 470], [150, 520], [250, 600], [1190, 600], [520, 260],
];

export default function Illustration() {
  return (
    <svg className="illustration" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="ill-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0e2230" />
          <stop offset="70%" stopColor="#163b44" />
          <stop offset="100%" stopColor="#1b4448" />
        </linearGradient>
        <linearGradient id="ill-night" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0a1626" />
          <stop offset="100%" stopColor="#1d4a63" />
        </linearGradient>
        <linearGradient id="ill-wood" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#3a2416" />
          <stop offset="50%" stopColor="#4a2f1c" />
          <stop offset="100%" stopColor="#2e1c11" />
        </linearGradient>
        <linearGradient id="ill-wood-light" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7a5233" />
          <stop offset="100%" stopColor="#5a3a24" />
        </linearGradient>
        <linearGradient id="ill-brass" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#a8822f" />
          <stop offset="45%" stopColor="#f0cf7a" />
          <stop offset="100%" stopColor="#8a6a2a" />
        </linearGradient>
        <linearGradient id="ill-book-shade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.2" />
          <stop offset="35%" stopColor="#fff" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id="ill-book-shade-v" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.22" />
          <stop offset="40%" stopColor="#fff" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.28" />
        </linearGradient>
        <linearGradient id="ill-shelf-shadow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#000" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="ill-chair-shade" cx="30%" cy="30%" r="90%">
          <stop offset="0%" stopColor="#ffcfa0" stopOpacity="0.25" />
          <stop offset="60%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.35" />
        </radialGradient>
        <radialGradient id="ill-moon-glow">
          <stop offset="0%" stopColor="#ffe3a3" stopOpacity="0.85" />
          <stop offset="35%" stopColor="#f6b53c" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#f6b53c" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="ill-lamp-glow">
          <stop offset="0%" stopColor="#ffd27a" stopOpacity="0.75" />
          <stop offset="100%" stopColor="#ff9a3c" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ill-light-cone" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffd27a" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#ffd27a" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="ill-window-spill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#9ec7d6" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#9ec7d6" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="ill-center-shade" cx="50%" cy="52%" r="46%">
          <stop offset="0%" stopColor="#061019" stopOpacity="0.6" />
          <stop offset="60%" stopColor="#061019" stopOpacity="0.32" />
          <stop offset="100%" stopColor="#061019" stopOpacity="0" />
        </radialGradient>

        {/* Textures */}
        <pattern id="ill-fabric" width="6" height="6" patternUnits="userSpaceOnUse">
          <path d="M0 6 L6 0" stroke="rgba(0,0,0,0.12)" strokeWidth="1" />
          <path d="M0 0 L6 6" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        </pattern>
        <pattern id="ill-knit" width="6" height="7" patternUnits="userSpaceOnUse">
          <path d="M0 0 L3 4 L6 0" stroke="rgba(0,0,0,0.13)" strokeWidth="1" fill="none" />
        </pattern>
        <pattern id="ill-plaid" width="16" height="16" patternUnits="userSpaceOnUse">
          <rect width="16" height="5" fill="rgba(226,165,60,0.35)" />
          <rect width="5" height="16" fill="rgba(226,165,60,0.3)" />
          <rect y="10" width="16" height="1.5" fill="rgba(196,85,58,0.6)" />
          <rect x="10" width="1.5" height="16" fill="rgba(196,85,58,0.6)" />
        </pattern>
        <pattern id="ill-rug-dots" width="16" height="10" patternUnits="userSpaceOnUse">
          <circle cx="8" cy="5" r="2" fill="#f2b43c" opacity="0.55" />
        </pattern>

        {/* Soft brush streaks on the wall only */}
        <filter id="ill-brush" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.045 0.004" numOctaves="3" seed="4" />
          <feDisplacementMap in="SourceGraphic" scale="40" />
        </filter>
        <filter id="ill-grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <filter id="ill-glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
        <filter id="ill-glow-strong" x="-150%" y="-150%" width="400%" height="400%">
          <feGaussianBlur stdDeviation="14" />
        </filter>

        <clipPath id="ill-window-clip">
          <path d="M640 620 L640 260 A 160 160 0 0 1 960 260 L960 620 Z" />
        </clipPath>
      </defs>

      {/* Back wall */}
      <g filter="url(#ill-brush)">
        <rect x="-40" y="-40" width="1680" height="1000" fill="url(#ill-wall)" />
        {[120, 420, 560, 1040, 1180, 1480].map((x, i) => (
          <rect key={i} x={x} y="-40" width="60" height="1000" fill="#1f4d55" opacity={0.25 + (i % 3) * 0.08} />
        ))}
      </g>
      {/* wainscoting */}
      <rect x="-20" y="760" width="1640" height="130" fill="#13323a" />
      <rect x="-20" y="756" width="1640" height="8" fill="#2a1b12" />
      {Array.from({ length: 14 }, (_, i) => (
        <rect key={i} x={i * 120 + 20} y="780" width="96" height="92" rx="3" fill="none" stroke="rgba(0,0,0,0.25)" strokeWidth="2" />
      ))}

      {/* Arched window */}
      <g>
        <g clipPath="url(#ill-window-clip)">
          <rect x="630" y="90" width="340" height="540" fill="url(#ill-night)" />
          {STARS.map((s, i) => (
            <circle key={i} className="ill-star" cx={s.x} cy={s.y} r={s.r} fill="#f7ecd2"
                    style={{ animationDelay: `${s.delay}s` }} />
          ))}
          <g className="ill-moon">
            <circle cx="895" cy="190" r="120" fill="url(#ill-moon-glow)" />
            <circle cx="895" cy="190" r="38" fill="#fde9b8" />
            <circle cx="882" cy="178" r="6" fill="#efd59a" />
            <circle cx="906" cy="206" r="4" fill="#efd59a" />
            <path d="M886 176 L910 190 L886 204 Z" fill="#f2b85c" opacity="0.8" strokeLinejoin="round" />
          </g>
          <Bird x={720} y={320} scale={0.95} delay={-2} />
          <Bird x={780} y={440} scale={0.7} delay={-6} />
          <path d="M630 620 L630 560 L670 560 L670 530 L700 510 L730 530 L730 560 L790 560 L790 540 L840 540 L840 575 L900 575 L900 545 L930 520 L960 545 L960 620 Z"
                fill="#0b1c28" />
          <rect x="682" y="540" width="9" height="12" fill="#ffd27a" opacity="0.8" />
          <rect x="918" y="555" width="9" height="12" fill="#ffd27a" opacity="0.7" />
        </g>
        <path d="M640 620 L640 260 A 160 160 0 0 1 960 260 L960 620 Z" fill="none" stroke="#3e2818" strokeWidth="18" />
        <path d="M646 618 L646 262 A 154 154 0 0 1 954 262" fill="none" stroke="rgba(255,220,170,0.15)" strokeWidth="2" />
        <line x1="800" y1="100" x2="800" y2="620" stroke="#3e2818" strokeWidth="9" />
        <line x1="640" y1="400" x2="960" y2="400" stroke="#3e2818" strokeWidth="9" />
        <rect x="610" y="616" width="380" height="20" rx="4" fill="url(#ill-wood-light)" />
        <rect x="610" y="616" width="380" height="3" fill="rgba(255,220,170,0.3)" />
      </g>
      <polygon points="640,636 960,636 1120,1000 480,1000" fill="url(#ill-window-spill)" />

      {/* Floorboards with grain */}
      <rect x="-20" y="890" width="1640" height="130" fill="#3a2618" />
      {Array.from({ length: 18 }, (_, i) => (
        <line key={i} x1={i * 96 + (i % 2) * 40} y1="890" x2={i * 96 + (i % 2) * 40 - 30} y2="1000" stroke="#24170f" strokeWidth="2" />
      ))}
      {[915, 950, 985].map((y) => (
        <path key={y} d={`M-20 ${y} C 300 ${y - 4} 700 ${y + 4} 1620 ${y - 2}`} stroke="rgba(0,0,0,0.18)" strokeWidth="1" fill="none" />
      ))}

      {/* Rug with border and fringe */}
      <ellipse cx="760" cy="955" rx="470" ry="48" fill="#7a3328" />
      <ellipse cx="760" cy="955" rx="440" ry="39" fill="url(#ill-rug-dots)" />
      <ellipse cx="760" cy="955" rx="400" ry="31" fill="#5e2620" />
      <ellipse cx="760" cy="955" rx="300" ry="21" fill="none" stroke="#d9a441" strokeWidth="2" opacity="0.4" />

      {/* Bookcases */}
      <Bookcase x={10} width={300} top={90} bottom={890} rows={5} seed={3} />
      <Bookcase x={1290} width={300} top={90} bottom={890} rows={5} seed={91} />

      {/* Rolling ladder */}
      <g strokeLinecap="round">
        <line x1="1335" y1="900" x2="1395" y2="70" stroke="#7a5233" strokeWidth="8" />
        <line x1="1395" y1="900" x2="1455" y2="70" stroke="#7a5233" strokeWidth="8" />
        <line x1="1333" y1="898" x2="1393" y2="70" stroke="rgba(255,220,170,0.3)" strokeWidth="2" />
        {Array.from({ length: 9 }, (_, i) => {
          const t = (i + 1) / 10;
          const y = 900 - t * 830;
          const x = 1335 + t * 60;
          return <line key={i} x1={x} y1={y} x2={x + 60} y2={y} stroke="#8a6040" strokeWidth="6" />;
        })}
        <circle cx="1335" cy="902" r="7" fill="#1a110b" />
        <circle cx="1395" cy="902" r="7" fill="#1a110b" />
      </g>

      {/* Hanging lamps */}
      <PendantLamp x={450} cordLength={110} />
      <PendantLamp x={1150} cordLength={140} />

      {/* Reading corner */}
      <FloorLamp />
      <Armchair>
        <Reader />
      </Armchair>
      <g transform="translate(109 771) scale(0.78)">
        <Cat x={0} y={0} />
      </g>
      <Mug />

      {/* Right corner */}
      <Plant />
      <BookStack />

      {/* Glowing dust motes */}
      {MOTES.map(([x, y], i) => (
        <g key={i} className="ill-firefly" style={{ animationDelay: `${-i * 1.6}s` }}>
          <circle cx={x} cy={y} r="8" fill="#ffc768" opacity="0.35" filter="url(#ill-glow)" />
          <circle cx={x} cy={y} r="2.2" fill="#fff1c9" />
        </g>
      ))}

      {/* Calm centre + paper grain */}
      <rect width="1600" height="1000" fill="url(#ill-center-shade)" />
      <rect width="1600" height="1000" filter="url(#ill-grain)" opacity="0.12" style={{ mixBlendMode: "overlay" }} />
    </svg>
  );
}

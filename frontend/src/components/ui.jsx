// ── Stat bar ──────────────────────────────────────────────────────────────────
export function StatBar({ label, value, max = 99, color = '#22c55e' }) {
  const pct = Math.round(((value || 0) / max) * 100)
  const clr =
    pct >= 80 ? '#22c55e' : pct >= 65 ? '#eab308' : pct >= 50 ? '#f97316' : '#ef4444'
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-gray-400 w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: clr }}
        />
      </div>
      <span className="w-7 text-right font-mono text-gray-300">{value ?? '—'}</span>
    </div>
  )
}

// ── Stat pill ──────────────────────────────────────────────────────────────────
export function StatPill({ label, value }) {
  const color =
    value >= 80 ? 'bg-green-900/60 text-green-300' :
    value >= 65 ? 'bg-yellow-900/60 text-yellow-300' :
    value >= 50 ? 'bg-orange-900/60 text-orange-300' :
                  'bg-red-900/60 text-red-300'
  return (
    <div className={`rounded-lg px-3 py-2 text-center ${color}`}>
      <div className="text-lg font-bold">{value ?? '—'}</div>
      <div className="text-[10px] uppercase tracking-wide opacity-70">{label}</div>
    </div>
  )
}

// ── Position badge ─────────────────────────────────────────────────────────────
const posColors = {
  GK: 'bg-yellow-600', CB: 'bg-blue-700', FB: 'bg-blue-500',
  MID: 'bg-green-700', WIDE: 'bg-purple-700', FWD: 'bg-red-700',
}
export function PosBadge({ pos }) {
  const bg = posColors[pos] || 'bg-gray-700'
  return (
    <span className={`${bg} text-white text-[10px] font-bold px-2 py-0.5 rounded`}>
      {pos}
    </span>
  )
}

// ── Currency formatter ─────────────────────────────────────────────────────────
export function fmt(n) {
  if (!n) return '—'
  if (n >= 1_000_000) return `€${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `€${(n / 1_000).toFixed(0)}K`
  return `€${n}`
}

// ── Loading spinner ────────────────────────────────────────────────────────────
export function Spinner() {
  return (
    <div className="flex justify-center py-16">
      <div className="w-8 h-8 border-2 border-green-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

// ── Card ───────────────────────────────────────────────────────────────────────
export function Card({ children, className = '' }) {
  return (
    <div className={`bg-[#1c2a36] border border-white/10 rounded-xl p-5 ${className}`}>
      {children}
    </div>
  )
}

// ── Player card (compact) ─────────────────────────────────────────────────────
export function PlayerCard({ player, onClick, showSimilarity }) {
  return (
    <div
      onClick={onClick}
      className="bg-[#1c2a36] border border-white/10 rounded-xl p-4 cursor-pointer
                 hover:border-green-600/50 hover:bg-[#223040] transition-all group"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-white truncate group-hover:text-green-400 transition-colors">
            {player.short_name}
          </div>
          <div className="text-xs text-gray-400 truncate">{player.club_name}</div>
          <div className="text-xs text-gray-500 truncate">{player.league_name}</div>
        </div>
        <div className="text-center shrink-0">
          <div className="text-2xl font-bold text-white">{player.overall}</div>
          <PosBadge pos={player.position_group} />
        </div>
      </div>

      {/* Card stats */}
      <div className="grid grid-cols-6 gap-1 mb-3">
        {[
          ['PAC', player.pace], ['SHO', player.shooting], ['PAS', player.passing],
          ['DRI', player.dribbling], ['DEF', player.defending], ['PHY', player.physic],
        ].map(([l, v]) => (
          <div key={l} className="text-center">
            <div className={`text-xs font-bold ${
              v >= 80 ? 'text-green-400' : v >= 65 ? 'text-yellow-400' : 'text-gray-400'
            }`}>{v ?? '—'}</div>
            <div className="text-[9px] text-gray-500">{l}</div>
          </div>
        ))}
      </div>

      {/* Economic */}
      <div className="flex gap-3 text-xs text-gray-400 border-t border-white/5 pt-2">
        <span>💰 {fmt(player.value_eur)}</span>
        <span>📋 {fmt(player.wage_eur)}/wk</span>
        {player.release_clause_eur && <span>🔓 {fmt(player.release_clause_eur)}</span>}
      </div>

      {showSimilarity && player.similarity_score != null && (
        <div className="mt-2 pt-2 border-t border-white/5">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full rounded-full bg-green-500"
                style={{ width: `${Math.round(player.similarity_score * 100)}%` }}
              />
            </div>
            <span className="text-xs text-green-400 font-mono">
              {(player.similarity_score * 100).toFixed(1)}%
            </span>
          </div>
          <div className="text-[10px] text-gray-500 mt-0.5">Similarity score</div>
        </div>
      )}

      {player.uniqueness_index != null && (
        <div className="text-[10px] text-gray-500 mt-1">
          Uniqueness: <span className="text-gray-300">{(player.uniqueness_index * 100).toFixed(1)}%</span>
        </div>
      )}
    </div>
  )
}

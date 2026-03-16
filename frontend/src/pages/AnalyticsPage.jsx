import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend, Cell
} from 'recharts'
import {
  getUniquenessRankings, getReplaceability,
  getPositionUniqueness, getTemporalUniqueness
} from '../api'
import { Card, Spinner, fmt, PosBadge } from '../components/ui'

const SEASONS = ['2022/23', '2023/24', '2025/26']
const POS_COLORS = { GK: '#eab308', CB: '#3b82f6', FB: '#60a5fa', MID: '#22c55e', WIDE: '#a855f7', FWD: '#ef4444' }

export default function AnalyticsPage() {
  const navigate = useNavigate()
  const [season, setSeason] = useState('2025/26')
  const [activeSection, setActiveSection] = useState('uniqueness')

  const { data: uniqueness, isLoading: uLoading } = useQuery({
    queryKey: ['uniqueness', season],
    queryFn: () => getUniquenessRankings({ season, limit: 30 }).then(r => r.data),
  })

  const { data: replaceability, isLoading: rLoading } = useQuery({
    queryKey: ['replaceability', season],
    queryFn: () => getReplaceability({ season }).then(r => r.data),
  })

  const { data: posStats } = useQuery({
    queryKey: ['posUniqueness', season],
    queryFn: () => getPositionUniqueness(season).then(r => r.data),
  })

  const { data: temporal } = useQuery({
    queryKey: ['temporal'],
    queryFn: () => getTemporalUniqueness().then(r => r.data),
  })

  // Reshape temporal data for recharts: [{season, GK: 0.x, CB: 0.x, ...}]
  const temporalBySeason = temporal ? SEASONS.map(s => {
    const row = { season: s }
    const entries = temporal.filter(t => t.season === s)
    entries.forEach(e => { row[e.position_group] = parseFloat(e.avg_uniqueness) })
    return row
  }) : []

  const sections = ['uniqueness', 'replaceability', 'position analysis', 'temporal']

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-2">Analytics Dashboard</h1>
      <p className="text-gray-400 text-sm mb-6">
        Player Uniqueness Index · Club Replaceability Index · Temporal evolution — replicating the paper's methodology
      </p>

      {/* Season selector */}
      <div className="flex gap-2 mb-6">
        {SEASONS.map(s => (
          <button key={s} onClick={() => setSeason(s)}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${season === s ? 'bg-green-700 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
            {s}
          </button>
        ))}
      </div>

      {/* Section nav */}
      <div className="flex gap-1 mb-8 border-b border-white/10">
        {sections.map(s => (
          <button key={s} onClick={() => setActiveSection(s)}
            className={`px-4 py-2 text-sm capitalize font-medium border-b-2 -mb-px transition ${
              activeSection === s ? 'border-green-500 text-white' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {s}
          </button>
        ))}
      </div>

      {/* ── Uniqueness section ── */}
      {activeSection === 'uniqueness' && (
        <div className="space-y-6">
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Top unique players table */}
            <Card>
              <h3 className="text-sm font-semibold text-gray-300 mb-4">Top 30 Most Unique Players</h3>
              {uLoading ? <Spinner /> : (
                <div className="overflow-y-auto max-h-96">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-[#1c2a36]">
                      <tr className="text-gray-500 border-b border-white/10">
                        <th className="py-2 text-left">#</th>
                        <th className="py-2 text-left">Player</th>
                        <th className="py-2">Pos</th>
                        <th className="py-2">OVR</th>
                        <th className="py-2">Uniqueness</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(uniqueness || []).map((p, i) => (
                        <tr key={p.sofifa_id}
                          className="border-b border-white/5 hover:bg-white/5 cursor-pointer transition"
                          onClick={() => navigate(`/player/${p.sofifa_id}?season=${season}`)}>
                          <td className="py-2 text-gray-500">{i + 1}</td>
                          <td className="py-2">
                            <div className="text-white font-medium">{p.short_name}</div>
                            <div className="text-gray-500">{p.club_name}</div>
                          </td>
                          <td className="py-2 text-center"><PosBadge pos={p.position_group} /></td>
                          <td className="py-2 text-center text-gray-300">{p.overall}</td>
                          <td className="py-2">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                                <div className="h-full rounded-full bg-purple-500"
                                  style={{ width: `${(p.uniqueness_index * 100 / 0.4) * 100}%` }} />
                              </div>
                              <span className="text-purple-300 font-mono w-12 text-right">
                                {(p.uniqueness_index * 100).toFixed(1)}%
                              </span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {/* Uniqueness by position bar */}
            <Card>
              <h3 className="text-sm font-semibold text-gray-300 mb-4">Mean Uniqueness by Position</h3>
              {posStats ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={posStats} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" horizontal={false} />
                    <XAxis type="number" domain={[0, 0.25]} tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <YAxis type="category" dataKey="position_group" tick={{ fill: '#9ca3af', fontSize: 12 }} width={40} />
                    <Tooltip
                      contentStyle={{ background: '#1c2a36', border: '1px solid #ffffff20', borderRadius: 8 }}
                      formatter={(v) => [`${(v * 100).toFixed(2)}%`, 'Avg Uniqueness']}
                    />
                    <Bar dataKey="mean" radius={[0, 4, 4, 0]}>
                      {(posStats || []).map(e => (
                        <Cell key={e.position_group} fill={POS_COLORS[e.position_group] || '#6b7280'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <Spinner />}
            </Card>
          </div>

          {/* Position stats table (mirrors paper Table 1) */}
          {posStats && (
            <Card>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Uniqueness Statistics by Position (Table 1)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 border-b border-white/10">
                      {['Position', 'Count', 'Mean', 'Median', 'Std Dev', 'Min', 'P10', 'P25', 'P75', 'P90', 'Max'].map(h => (
                        <th key={h} className="py-2 text-right first:text-left px-2">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {posStats.map(r => (
                      <tr key={r.position_group} className="border-b border-white/5">
                        <td className="py-2 px-2"><PosBadge pos={r.position_group} /></td>
                        <td className="py-2 px-2 text-right text-gray-400">{r.player_count}</td>
                        {[r.mean, r.median, r.std_dev, r.min_val, r.p10, r.p25, r.p75, r.p90, r.max_val].map((v, i) => (
                          <td key={i} className="py-2 px-2 text-right text-gray-300 font-mono">
                            {v != null ? (v * 100).toFixed(2) : '—'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ── Replaceability section ── */}
      {activeSection === 'replaceability' && (
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Club Replaceability Index — {season}</h3>
            <p className="text-xs text-gray-500 mb-4">
              R_club = (1/N) × Σ(1 − U_i) — Higher = easier to replace players (more squad depth)
            </p>
            {rLoading ? <Spinner /> : (
              <div className="overflow-y-auto max-h-[500px]">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#1c2a36]">
                    <tr className="text-gray-500 border-b border-white/10">
                      <th className="py-2 text-left">#</th>
                      <th className="py-2 text-left">Club</th>
                      <th className="py-2 text-left">League</th>
                      <th className="py-2">Players</th>
                      <th className="py-2">Replaceability</th>
                      <th className="py-2">Avg Uniqueness</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(replaceability || []).map((c, i) => (
                      <tr key={c.club_name} className="border-b border-white/5 hover:bg-white/5 transition">
                        <td className="py-2 text-gray-500">{i + 1}</td>
                        <td className="py-2 font-medium text-white">{c.club_name}</td>
                        <td className="py-2 text-gray-400">{c.league_name}</td>
                        <td className="py-2 text-center text-gray-400">{c.player_count}</td>
                        <td className="py-2">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1.5 rounded-full bg-white/10 overflow-hidden">
                              <div className="h-full rounded-full bg-blue-500"
                                style={{ width: `${((c.replaceability_index - 0.7) / 0.3) * 100}%` }} />
                            </div>
                            <span className="text-blue-300 font-mono">{(c.replaceability_index * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="py-2 text-center text-purple-300 font-mono">
                          {(c.avg_uniqueness * 100).toFixed(1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Position analysis section ── */}
      {activeSection === 'position analysis' && posStats && (
        <div className="grid lg:grid-cols-2 gap-6">
          {Object.entries(POS_COLORS).map(([pos, color]) => {
            const stat = posStats.find(p => p.position_group === pos)
            if (!stat) return null
            return (
              <Card key={pos}>
                <div className="flex items-center gap-2 mb-3">
                  <PosBadge pos={pos} />
                  <span className="text-sm font-semibold text-gray-300">{pos} — Uniqueness distribution</span>
                </div>
                <div className="space-y-2 text-xs">
                  {[
                    ['Players', stat.player_count],
                    ['Mean uniqueness', `${(stat.mean * 100).toFixed(2)}%`],
                    ['Median', `${(stat.median * 100).toFixed(2)}%`],
                    ['Std deviation', `${(stat.std_dev * 100).toFixed(2)}%`],
                    ['P25 – P75', `${(stat.p25 * 100).toFixed(2)}% – ${(stat.p75 * 100).toFixed(2)}%`],
                    ['Max uniqueness', `${(stat.max_val * 100).toFixed(2)}%`],
                  ].map(([l, v]) => (
                    <div key={l} className="flex justify-between">
                      <span className="text-gray-500">{l}</span>
                      <span className="text-gray-200 font-mono">{v}</span>
                    </div>
                  ))}
                </div>
                {/* Mini distribution bar */}
                <div className="mt-3 relative h-2 rounded-full bg-white/10 overflow-hidden">
                  <div className="absolute h-full rounded-full opacity-40"
                    style={{ left: `${(stat.p25 / 0.25) * 100}%`, width: `${((stat.p75 - stat.p25) / 0.25) * 100}%`, background: color }} />
                  <div className="absolute h-full w-0.5 rounded-full"
                    style={{ left: `${(stat.median / 0.25) * 100}%`, background: color }} />
                </div>
                <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                  <span>0%</span><span>P25–P75 (IQR)</span><span>25%</span>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* ── Temporal section ── */}
      {activeSection === 'temporal' && (
        <div className="space-y-6">
          <Card>
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Temporal Evolution of Average Uniqueness by Position</h3>
            <p className="text-xs text-gray-500 mb-4">Mirrors Figure 4 from the paper — declining uniqueness reflects tactical homogenisation</p>
            {temporalBySeason.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={temporalBySeason}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                  <XAxis dataKey="season" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                  <YAxis tickFormatter={v => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#9ca3af', fontSize: 11 }} domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ background: '#1c2a36', border: '1px solid #ffffff20', borderRadius: 8 }}
                    formatter={(v, name) => [`${(v * 100).toFixed(2)}%`, name]}
                  />
                  <Legend />
                  {Object.entries(POS_COLORS).map(([pos, color]) => (
                    <Line key={pos} type="monotone" dataKey={pos} stroke={color} strokeWidth={2}
                      dot={{ fill: color, r: 4 }} connectNulls name={pos} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center text-gray-400 py-12">
                Need data from multiple seasons to show temporal trends.<br />
                Run the scraper for 2022/23 and 2023/24 as well.
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}

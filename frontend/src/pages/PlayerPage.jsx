import { useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts'
import { getPlayer, getPlayerHistory, getSimilarPlayers, getSeasons } from '../api'
import { StatBar, StatPill, PosBadge, Card, Spinner, PlayerCard, fmt } from '../components/ui'

const CARD_STATS = [
  ['PAC', 'pace'], ['SHO', 'shooting'], ['PAS', 'passing'],
  ['DRI', 'dribbling'], ['DEF', 'defending'], ['PHY', 'physic'],
]

const ATTR_GROUPS = {
  Attacking: ['attacking_crossing', 'attacking_finishing', 'attacking_heading_accuracy', 'attacking_short_passing', 'attacking_volleys'],
  Skill: ['skill_dribbling', 'skill_curve', 'skill_fk_accuracy', 'skill_long_passing', 'skill_ball_control'],
  Movement: ['movement_acceleration', 'movement_sprint_speed', 'movement_agility', 'movement_reactions', 'movement_balance'],
  Power: ['power_shot_power', 'power_jumping', 'power_stamina', 'power_strength', 'power_long_shots'],
  Mentality: ['mentality_aggression', 'mentality_interceptions', 'mentality_positioning', 'mentality_vision', 'mentality_composure'],
  Defending: ['defending_marking_awareness', 'defending_standing_tackle', 'defending_sliding_tackle'],
  Goalkeeping: ['goalkeeping_diving', 'goalkeeping_handling', 'goalkeeping_kicking', 'goalkeeping_positioning', 'goalkeeping_reflexes'],
}

const prettyAttr = (k) => k.replace(/^[a-z]+_/, '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

export default function PlayerPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [sp] = useSearchParams()
  const [season, setSeason] = useState(sp.get('season') || '2025/26')
  const [simFilters, setSimFilters] = useState({ league: '', age_min: '', age_max: '', wage_max: '', value_max: '' })
  const [activeTab, setActiveTab] = useState('overview')

  const { data: seasons } = useQuery({ queryKey: ['seasons'], queryFn: () => getSeasons().then(r => r.data) })
  const { data: player, isLoading } = useQuery({
    queryKey: ['player', id, season],
    queryFn: () => getPlayer(id, season).then(r => r.data),
  })
  const { data: history } = useQuery({
    queryKey: ['history', id],
    queryFn: () => getPlayerHistory(id).then(r => r.data),
  })
  const cleanSim = Object.fromEntries(Object.entries(simFilters).filter(([, v]) => v !== ''))
  const { data: similar, isLoading: simLoading } = useQuery({
    queryKey: ['similar', id, season, cleanSim],
    queryFn: () => getSimilarPlayers(id, { season, top_n: 12, ...cleanSim }).then(r => r.data),
    enabled: !!player,
  })

  if (isLoading) return <Spinner />
  if (!player) return <div className="text-center text-gray-400 py-20">Player not found</div>

  const tabs = ['overview', 'attributes', 'history', 'similar']

  return (
    <div>
      {/* Back */}
      <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white text-sm mb-4 flex items-center gap-1 transition">
        ← Back
      </button>

      {/* Season switcher */}
      <div className="flex gap-2 mb-6">
        {(seasons || ['2022/23', '2023/24', '2025/26']).map(s => (
          <button key={s} onClick={() => setSeason(s)}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition ${season === s ? 'bg-green-700 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
            {s}
          </button>
        ))}
      </div>

      {/* Hero card */}
      <Card className="mb-6">
        <div className="flex flex-col sm:flex-row gap-6">
          {/* Left: identity */}
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <PosBadge pos={player.position_group} />
              <span className="text-xs text-gray-500">{player.player_positions}</span>
              {player.uniqueness_index != null && (
                <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded">
                  Uniqueness {(player.uniqueness_index * 100).toFixed(1)}%
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-white mb-1">{player.long_name || player.short_name}</h1>
            <div className="text-gray-400 text-sm mb-3">{player.club_name} · {player.league_name}</div>
            <div className="flex flex-wrap gap-4 text-sm text-gray-400">
              <span>🌍 {player.nationality_name}</span>
              <span>🎂 Age {player.age}</span>
              <span>🦶 {player.preferred_foot}</span>
              {player.height_cm && <span>📏 {player.height_cm}cm</span>}
              {player.skill_moves && <span>⭐ {player.skill_moves}★ skills</span>}
            </div>
          </div>

          {/* Right: overall + card stats */}
          <div className="sm:text-right">
            <div className="text-6xl font-black text-white mb-3">{player.overall}</div>
            <div className="grid grid-cols-6 gap-2 mb-4">
              {CARD_STATS.map(([l, k]) => (
                <StatPill key={l} label={l} value={player[k]} />
              ))}
            </div>
            {/* Economic */}
            <div className="flex flex-wrap gap-3 text-sm justify-end">
              <div className="bg-green-900/30 border border-green-800/30 rounded-lg px-3 py-2">
                <div className="text-xs text-gray-400 mb-0.5">Market Value</div>
                <div className="text-green-400 font-semibold">{fmt(player.value_eur)}</div>
              </div>
              <div className="bg-blue-900/30 border border-blue-800/30 rounded-lg px-3 py-2">
                <div className="text-xs text-gray-400 mb-0.5">Weekly Wage</div>
                <div className="text-blue-400 font-semibold">{fmt(player.wage_eur)}</div>
              </div>
              {player.release_clause_eur && (
                <div className="bg-purple-900/30 border border-purple-800/30 rounded-lg px-3 py-2">
                  <div className="text-xs text-gray-400 mb-0.5">Release Clause</div>
                  <div className="text-purple-400 font-semibold">{fmt(player.release_clause_eur)}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-white/10">
        {tabs.map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={`px-4 py-2 text-sm capitalize font-medium border-b-2 transition -mb-px ${
              activeTab === t ? 'border-green-500 text-white' : 'border-transparent text-gray-400 hover:text-white'
            }`}>
            {t}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <div className="grid lg:grid-cols-2 gap-6">
          {Object.entries(ATTR_GROUPS).filter(([group]) =>
            group !== 'Goalkeeping' || player.position_group === 'GK'
          ).slice(0, 4).map(([group, attrs]) => (
            <Card key={group}>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">{group}</h3>
              <div className="space-y-2">
                {attrs.map(a => (
                  <StatBar key={a} label={prettyAttr(a)} value={player[a]} />
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Attributes tab */}
      {activeTab === 'attributes' && (
        <div className="grid lg:grid-cols-2 gap-6">
          {Object.entries(ATTR_GROUPS).filter(([group]) =>
            group !== 'Goalkeeping' || player.position_group === 'GK'
          ).map(([group, attrs]) => (
            <Card key={group}>
              <h3 className="text-sm font-semibold text-gray-300 mb-3">{group}</h3>
              <div className="space-y-2">
                {attrs.map(a => (
                  <StatBar key={a} label={prettyAttr(a)} value={player[a]} />
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* History tab */}
      {activeTab === 'history' && (
        <div className="space-y-6">
          {history && history.length > 1 ? (
            <>
              {/* Overall + market value chart */}
              <Card>
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Overall Rating & Market Value</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                    <XAxis dataKey="season" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <YAxis yAxisId="left" domain={[50, 100]} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <YAxis yAxisId="right" orientation="right" tickFormatter={v => `€${(v/1e6).toFixed(0)}M`} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#1c2a36', border: '1px solid #ffffff20', borderRadius: 8 }}
                      labelStyle={{ color: '#e5e7eb' }}
                    />
                    <Legend />
                    <Line yAxisId="left" type="monotone" dataKey="overall" stroke="#22c55e" strokeWidth={2} dot={{ fill: '#22c55e' }} name="Overall" />
                    <Line yAxisId="right" type="monotone" dataKey="value_eur" stroke="#60a5fa" strokeWidth={2} dot={{ fill: '#60a5fa' }} name="Value (€)" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              {/* Economic chart */}
              <Card>
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Economic Evolution (€/week wage, release clause)</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                    <XAxis dataKey="season" tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <YAxis tickFormatter={v => `€${(v/1000).toFixed(0)}K`} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ background: '#1c2a36', border: '1px solid #ffffff20', borderRadius: 8 }}
                      formatter={(v, name) => [fmt(v), name]}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="wage_eur" stroke="#a78bfa" strokeWidth={2} dot={{ fill: '#a78bfa' }} name="Weekly Wage" />
                    <Line type="monotone" dataKey="release_clause_eur" stroke="#f97316" strokeWidth={2} dot={{ fill: '#f97316' }} name="Release Clause" strokeDasharray="5 5" />
                  </LineChart>
                </ResponsiveContainer>
              </Card>

              {/* Season table */}
              <Card>
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Season by Season</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-500 border-b border-white/10">
                        <th className="py-2 text-left">Season</th>
                        <th className="py-2">OVR</th>
                        <th className="py-2">Club</th>
                        <th className="py-2">Value</th>
                        <th className="py-2">Wage/wk</th>
                        <th className="py-2">Release</th>
                        <th className="py-2">Uniqueness</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map(h => (
                        <tr key={h.season} className={`border-b border-white/5 ${h.season === season ? 'bg-green-900/20' : ''}`}>
                          <td className="py-2 font-medium text-white">{h.season}</td>
                          <td className="py-2 text-center text-green-400 font-bold">{h.overall}</td>
                          <td className="py-2 text-center text-gray-300">{h.club_name}</td>
                          <td className="py-2 text-center">{fmt(h.value_eur)}</td>
                          <td className="py-2 text-center">{fmt(h.wage_eur)}</td>
                          <td className="py-2 text-center">{fmt(h.release_clause_eur)}</td>
                          <td className="py-2 text-center text-purple-300">
                            {h.uniqueness_index ? `${(h.uniqueness_index * 100).toFixed(1)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          ) : (
            <div className="text-center text-gray-400 py-12">
              Historical data available for {history?.length || 0} season(s).<br />
              Scrape more seasons to see evolution.
            </div>
          )}
        </div>
      )}

      {/* Similar players tab */}
      {activeTab === 'similar' && (
        <div>
          {/* Similarity filters */}
          <Card className="mb-6">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Context Filters</h3>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {[
                ['league', 'League', 'e.g. Premier League'],
                ['age_min', 'Min age', '16'],
                ['age_max', 'Max age', '35'],
                ['wage_max', 'Max wage (€/wk)', '100000'],
                ['value_max', 'Max value (€)', '50000000'],
              ].map(([k, label, ph]) => (
                <div key={k}>
                  <label className="block text-xs text-gray-400 mb-1">{label}</label>
                  <input
                    placeholder={ph}
                    value={simFilters[k] || ''}
                    onChange={e => setSimFilters(f => ({ ...f, [k]: e.target.value }))}
                    className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white"
                  />
                </div>
              ))}
            </div>
          </Card>

          {simLoading ? <Spinner /> : (
            <>
              {similar?.similar_players?.length > 0 ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {similar.similar_players.map(p => (
                    <PlayerCard
                      key={p.sofifa_id}
                      player={p}
                      showSimilarity
                      onClick={() => navigate(`/player/${p.sofifa_id}?season=${season}`)}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-400 py-12">
                  No similar players found. Try removing filters or run the ML pipeline first.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

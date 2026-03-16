import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { searchPlayers, getSeasons, getLeagues } from '../api'
import { PlayerCard, Spinner, PosBadge } from '../components/ui'

const POSITION_GROUPS = ['GK', 'CB', 'FB', 'MID', 'WIDE', 'FWD']

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [filters, setFilters] = useState({
    q: searchParams.get('q') || '',
    season: '2025/26',
    position: '',
    league: '',
    nationality: '',
    age_min: '',
    age_max: '',
    wage_max: '',
    value_max: '',
    release_clause_max: '',
    overall_min: '',
  })
  const [page, setPage] = useState(0)
  const [showFilters, setShowFilters] = useState(false)
  const LIMIT = 24

  const { data: seasons } = useQuery({ queryKey: ['seasons'], queryFn: () => getSeasons().then(r => r.data) })
  const { data: leagues } = useQuery({
    queryKey: ['leagues', filters.season],
    queryFn: () => getLeagues(filters.season).then(r => r.data)
  })

  const cleanFilters = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '' && v !== null)
  )

  const { data, isLoading } = useQuery({
    queryKey: ['search', cleanFilters, page],
    queryFn: () => searchPlayers({ ...cleanFilters, limit: LIMIT, offset: page * LIMIT }).then(r => r.data),
    keepPreviousData: true,
  })

  const set = (k, v) => { setFilters(f => ({ ...f, [k]: v })); setPage(0) }

  const totalPages = data ? Math.ceil(data.total / LIMIT) : 0

  return (
    <div>
      {/* Search bar */}
      <div className="mb-6">
        <div className="flex gap-2 mb-3">
          <input
            value={filters.q}
            onChange={e => set('q', e.target.value)}
            placeholder="Search players by name…"
            className="flex-1 bg-[#1c2a36] border border-white/20 rounded-xl px-4 py-3 text-white
                       placeholder-gray-500 focus:outline-none focus:border-green-500"
          />
          <button
            onClick={() => setShowFilters(f => !f)}
            className={`px-4 py-3 rounded-xl border text-sm font-medium transition ${
              showFilters
                ? 'bg-green-700 border-green-600 text-white'
                : 'bg-[#1c2a36] border-white/20 text-gray-300 hover:border-white/40'
            }`}
          >
            Filters {showFilters ? '▲' : '▼'}
          </button>
        </div>

        {/* Season selector */}
        <div className="flex gap-2 flex-wrap mb-3">
          {(seasons || ['2022/23', '2023/24', '2025/26']).map(s => (
            <button
              key={s}
              onClick={() => set('season', s)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                filters.season === s
                  ? 'bg-green-700 text-white'
                  : 'bg-white/5 text-gray-400 hover:bg-white/10'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Expanded filters */}
        {showFilters && (
          <div className="bg-[#1c2a36] border border-white/10 rounded-xl p-5 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Position */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Position</label>
              <div className="flex flex-wrap gap-1">
                <button onClick={() => set('position', '')} className={`px-2 py-1 text-xs rounded ${!filters.position ? 'bg-green-700 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}>All</button>
                {POSITION_GROUPS.map(p => (
                  <button key={p} onClick={() => set('position', p)}
                    className={`px-2 py-1 text-xs rounded ${filters.position === p ? 'bg-green-700 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {/* League */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">League</label>
              <select value={filters.league} onChange={e => set('league', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white">
                <option value="">All leagues</option>
                {(leagues || []).map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>

            {/* Age */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Age range</label>
              <div className="flex gap-2">
                <input type="number" placeholder="Min" value={filters.age_min} onChange={e => set('age_min', e.target.value)}
                  className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
                <input type="number" placeholder="Max" value={filters.age_max} onChange={e => set('age_max', e.target.value)}
                  className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
              </div>
            </div>

            {/* Weekly wage */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Max weekly wage (€)</label>
              <input type="number" placeholder="e.g. 100000" value={filters.wage_max} onChange={e => set('wage_max', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
            </div>

            {/* Market value */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Max market value (€)</label>
              <input type="number" placeholder="e.g. 50000000" value={filters.value_max} onChange={e => set('value_max', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
            </div>

            {/* Release clause */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Max release clause (€)</label>
              <input type="number" placeholder="e.g. 80000000" value={filters.release_clause_max} onChange={e => set('release_clause_max', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
            </div>

            {/* Overall min */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Min overall rating</label>
              <input type="number" placeholder="e.g. 75" value={filters.overall_min} onChange={e => set('overall_min', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
            </div>

            {/* Nationality */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Nationality</label>
              <input placeholder="e.g. Spanish" value={filters.nationality} onChange={e => set('nationality', e.target.value)}
                className="w-full bg-[#0f1923] border border-white/20 rounded-lg px-3 py-2 text-sm text-white" />
            </div>

            <div className="flex items-end">
              <button onClick={() => { setFilters({ q: '', season: '2025/26', position: '', league: '', nationality: '', age_min: '', age_max: '', wage_max: '', value_max: '', release_clause_max: '', overall_min: '' }); setPage(0) }}
                className="text-xs text-gray-400 hover:text-white underline">
                Clear all filters
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Results count */}
      {data && (
        <div className="text-sm text-gray-400 mb-4">
          {data.total.toLocaleString()} players found
          {filters.season && <span className="ml-2 text-gray-500">· {filters.season}</span>}
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <Spinner />
      ) : (
        <>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-8">
            {(data?.players || []).map(p => (
              <PlayerCard
                key={p.sofifa_id}
                player={p}
                onClick={() => navigate(`/player/${p.sofifa_id}?season=${filters.season}`)}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center gap-2">
              <button disabled={page === 0} onClick={() => setPage(p => p - 1)}
                className="px-4 py-2 rounded-lg bg-[#1c2a36] border border-white/10 text-sm disabled:opacity-30 hover:border-white/30 transition">
                ← Prev
              </button>
              <span className="px-4 py-2 text-sm text-gray-400">
                Page {page + 1} of {totalPages}
              </span>
              <button disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}
                className="px-4 py-2 rounded-lg bg-[#1c2a36] border border-white/10 text-sm disabled:opacity-30 hover:border-white/30 transition">
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

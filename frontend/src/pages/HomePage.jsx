import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDataFreshness } from '../api'

export default function HomePage() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const { data: freshness } = useQuery({ queryKey: ['freshness'], queryFn: () => getDataFreshness().then(r => r.data) })

  const handleSearch = (e) => {
    e.preventDefault()
    if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`)
  }

  const completedSeasons = freshness?.filter(s => s.status === 'completed') || []

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center text-center px-4">
      {/* Hero */}
      <div className="mb-8">
        <div className="text-6xl mb-4">⚽</div>
        <h1 className="text-4xl sm:text-5xl font-bold text-white mb-3">
          Soccer<span className="text-green-400">Solver</span>
        </h1>
        <p className="text-lg text-gray-400 max-w-xl">
          Quantitative player similarity & tactical fit — find who can replace who, instantly.
        </p>
        <p className="text-sm text-gray-500 mt-2">
          Built on the MIT Sports Analytics Conference framework · PCA + K-Means + Hybrid Similarity
        </p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="w-full max-w-xl mb-10">
        <div className="flex gap-2">
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search for a player… e.g. Mbappé, Pedri, Haaland"
            className="flex-1 bg-[#1c2a36] border border-white/20 rounded-xl px-5 py-3 text-white
                       placeholder-gray-500 focus:outline-none focus:border-green-500 transition"
          />
          <button
            type="submit"
            className="bg-green-600 hover:bg-green-500 text-white font-semibold px-6 py-3 rounded-xl transition"
          >
            Search
          </button>
        </div>
      </form>

      {/* Quick nav */}
      <div className="grid sm:grid-cols-3 gap-4 w-full max-w-2xl mb-10">
        {[
          { icon: '🔍', title: 'Find Similar Players', desc: 'Search by name, filter by salary, age, league', to: '/search' },
          { icon: '📊', title: 'Analytics Dashboard', desc: 'Uniqueness index, replaceability by club & league', to: '/analytics' },
          { icon: '🧠', title: 'Tactical Fit Engine', desc: 'PCA-powered similarity with context filters', to: '/search' },
        ].map(card => (
          <button
            key={card.title}
            onClick={() => navigate(card.to)}
            className="bg-[#1c2a36] border border-white/10 rounded-xl p-5 text-left
                       hover:border-green-600/50 hover:bg-[#223040] transition-all"
          >
            <div className="text-2xl mb-2">{card.icon}</div>
            <div className="font-semibold text-white text-sm mb-1">{card.title}</div>
            <div className="text-xs text-gray-500">{card.desc}</div>
          </button>
        ))}
      </div>

      {/* Data freshness */}
      {completedSeasons.length > 0 && (
        <div className="text-xs text-gray-500 flex gap-4 flex-wrap justify-center">
          {completedSeasons.map(s => (
            <span key={s.season} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
              {s.season} · {s.total_players?.toLocaleString()} players
              {s.completed_at && ` · updated ${new Date(s.completed_at).toLocaleDateString()}`}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

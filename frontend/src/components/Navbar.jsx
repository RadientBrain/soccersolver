import { Link, useLocation } from 'react-router-dom'

export default function Navbar() {
  const { pathname } = useLocation()
  const link = (to, label) => (
    <Link
      to={to}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        pathname === to
          ? 'bg-green-700 text-white'
          : 'text-gray-400 hover:text-white hover:bg-white/10'
      }`}
    >
      {label}
    </Link>
  )

  return (
    <nav className="border-b border-white/10 bg-[#0f1923]/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="text-2xl">⚽</span>
          <span className="font-bold text-lg text-white">SoccerSolver</span>
          <span className="text-xs text-gray-500 ml-1 hidden sm:block">Scouting Intelligence</span>
        </Link>
        <div className="flex items-center gap-1">
          {link('/', 'Home')}
          {link('/search', 'Players')}
          {link('/analytics', 'Analytics')}
        </div>
      </div>
    </nav>
  )
}

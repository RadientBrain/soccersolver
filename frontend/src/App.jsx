import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import SearchPage from './pages/SearchPage'
import PlayerPage from './pages/PlayerPage'
import AnalyticsPage from './pages/AnalyticsPage'
import HomePage from './pages/HomePage'

export default function App() {
  return (
    <div className="min-h-screen bg-[#0f1923] text-gray-100">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/player/:id" element={<PlayerPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Routes>
      </main>
    </div>
  )
}

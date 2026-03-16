import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 15000,
})

export const searchPlayers = (params) => api.get('/api/players/search', { params })
export const getPlayer = (id, season) => api.get(`/api/players/${id}`, { params: { season } })
export const getPlayerHistory = (id) => api.get(`/api/players/${id}/history`)
export const getSimilarPlayers = (id, params) => api.get(`/api/players/${id}/similar`, { params })
export const getSeasons = () => api.get('/api/seasons')
export const getLeagues = (season) => api.get('/api/leagues', { params: { season } })
export const getDataFreshness = () => api.get('/api/data-freshness')
export const getUniquenessRankings = (params) => api.get('/api/analytics/uniqueness', { params })
export const getReplaceability = (params) => api.get('/api/analytics/replaceability', { params })
export const getPositionUniqueness = (season) => api.get('/api/analytics/position-uniqueness', { params: { season } })
export const getTemporalUniqueness = () => api.get('/api/analytics/temporal-uniqueness')
export const getClubPlayers = (club, season) => api.get(`/api/clubs/${encodeURIComponent(club)}/players`, { params: { season } })

export default api

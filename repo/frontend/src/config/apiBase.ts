/** Backend origin; set `VITE_API_BASE` in `.env` (e.g. `http://localhost:8000`). */
const raw = import.meta.env.VITE_API_BASE as string | undefined
export const API_BASE = (raw?.trim().replace(/\/$/, '') || 'http://localhost:8000')

import { useEffect, useState } from 'react'

interface HealthResponse {
  status: string
  database: string
}

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health/')
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`)
        }
        return res.json() as Promise<HealthResponse>
      })
      .then((data) => {
        setHealth(data)
        setLoading(false)
      })
      .catch((err: Error) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <main style={{ maxWidth: '640px', margin: '2rem auto', padding: '1rem' }}>
      <header style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', color: 'var(--color-primary)' }}>
          NPRJ740 Maintenance System
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem' }}>
          Moroka Hall Residence — Sol Plaatje University
        </p>
      </header>

      <section
        aria-labelledby="system-status-heading"
        style={{
          background: 'var(--color-surface)',
          padding: '1.5rem',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow-md)',
          border: '1px solid var(--color-border)',
        }}
      >
        <h2 id="system-status-heading" style={{ fontSize: '1.125rem', marginBottom: '1rem' }}>
          Phase 0: Environment Health Check
        </h2>

        {loading && <p style={{ color: 'var(--color-text-muted)' }}>Checking system connectivity...</p>}

        {error && (
          <div
            role="alert"
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              background: '#fee2e2',
              color: 'var(--status-rejected)',
            }}
          >
            Failed to connect to backend: {error}
          </div>
        )}

        {health && (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>API Status:</span>
              <strong style={{ color: health.status === 'ok' ? 'var(--status-work-completed)' : 'var(--status-rejected)' }}>
                {health.status.toUpperCase()}
              </strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>Database:</span>
              <strong style={{ color: health.database === 'connected' ? 'var(--status-work-completed)' : 'var(--status-rejected)' }}>
                {health.database}
              </strong>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}

export default App

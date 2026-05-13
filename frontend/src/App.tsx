import { useState } from 'react'
import { scoreJson } from './api'
import type { ScanResult } from './types'
import Banner from './components/Banner'
import Uploader from './components/Uploader'
import ScoreHero from './components/ScoreHero'
import RadarPanel from './components/RadarPanel'
import SubScoreList from './components/SubScoreList'
import FindingsList from './components/FindingsList'

export default function App() {
  const [result, setResult] = useState<ScanResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [modelName, setModelName] = useState<string>('')

  async function handleScore(catalog: unknown, name?: string) {
    setError(null)
    setLoading(true)
    try {
      const r = await scoreJson(catalog)
      setResult(r)
      setModelName(name ?? '')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-full bg-slate-50">
      <Banner />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-10">
        <Uploader onScore={handleScore} loading={loading} />

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
            <strong className="font-semibold">Error:</strong>
            <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
              {error}
            </pre>
          </div>
        )}

        {!result && !error && (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-white/40 p-10 text-center">
            <p className="text-sm text-slate-500">
              Score a model to see the breakdown.
            </p>
          </div>
        )}

        {result && (
          <section className="space-y-6">
            <ScoreHero result={result} modelName={modelName} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <RadarPanel subScores={result.sub_scores} />
              <SubScoreList subScores={result.sub_scores} />
            </div>
            <FindingsList findings={result.findings} />
          </section>
        )}
      </main>
    </div>
  )
}

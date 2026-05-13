import { useRef, useState } from 'react'

const SAMPLES = [
  { id: 'northwind', label: 'Northwind OLTP', hint: 'Clean snake_case · grade A' },
  { id: 'warehouse_messy', label: 'Sales Warehouse', hint: '1NF violations · lineage gaps' },
  { id: 'greenfield', label: 'Greenfield Prototype', hint: 'Missing PKs · PascalCase' },
]

interface Props {
  onScore: (catalog: unknown, name?: string) => void
  loading: boolean
}

export default function Uploader({ onScore, loading }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [json, setJson] = useState('')
  const [pasteOpen, setPasteOpen] = useState(false)

  async function readAndScore(file: File) {
    try {
      const text = await file.text()
      const parsed = JSON.parse(text)
      setJson(text)
      onScore(parsed, parsed?.name)
    } catch (e) {
      alert(`Invalid JSON: ${e instanceof Error ? e.message : e}`)
    }
  }

  function scorePastedJson() {
    try {
      const parsed = JSON.parse(json)
      onScore(parsed, parsed?.name)
    } catch (e) {
      alert(`Invalid JSON: ${e instanceof Error ? e.message : e}`)
    }
  }

  async function loadSample(id: string) {
    try {
      const resp = await fetch(`/samples/${id}.json`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const parsed = await resp.json()
      setJson(JSON.stringify(parsed, null, 2))
      onScore(parsed, parsed?.name)
    } catch (e) {
      alert(`Could not load sample: ${e instanceof Error ? e.message : e}`)
    }
  }

  return (
    <section className="space-y-5">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const file = e.dataTransfer.files[0]
          if (file) void readAndScore(file)
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`group cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all ${
          dragging
            ? 'border-amber-400 bg-amber-50 scale-[1.01]'
            : 'border-slate-300 bg-white hover:border-slate-400 hover:bg-slate-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void readAndScore(f)
          }}
        />
        <div className="mx-auto h-12 w-12 rounded-full bg-slate-100 group-hover:bg-amber-100 flex items-center justify-center transition-colors">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-6 w-6 text-slate-500 group-hover:text-amber-600"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <p className="mt-4 text-base font-semibold text-slate-900">
          Drop your data model JSON here
        </p>
        <p className="mt-1 text-sm text-slate-500">
          or click to choose a file from your computer
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-500 mr-1">Try a sample:</span>
        {SAMPLES.map((s) => (
          <button
            key={s.id}
            onClick={() => void loadSample(s.id)}
            disabled={loading}
            title={s.hint}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-slate-700 hover:border-slate-400 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {s.label}
          </button>
        ))}
      </div>

      <details
        open={pasteOpen}
        onToggle={(e) => setPasteOpen((e.target as HTMLDetailsElement).open)}
        className="rounded-xl border border-slate-200 bg-white overflow-hidden"
      >
        <summary className="cursor-pointer select-none px-5 py-3.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
          Or paste JSON directly
        </summary>
        <div className="border-t border-slate-200 p-5 space-y-3">
          <textarea
            value={json}
            onChange={(e) => setJson(e.target.value)}
            placeholder='{"name": "My Model", "model_type": "physical", "entities": [...]}'
            spellCheck={false}
            className="w-full h-56 rounded-md border border-slate-300 bg-slate-50 p-3 font-mono text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent"
          />
          <button
            onClick={scorePastedJson}
            disabled={loading || !json.trim()}
            className="rounded-md bg-amber-500 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {loading ? 'Scoring…' : 'Score this'}
          </button>
        </div>
      </details>
    </section>
  )
}

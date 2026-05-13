import { useEffect, useMemo, useState } from 'react'
import { fixAll, fixFinding, scoreJson } from './api'
import type { MartState } from './types'
import {
  addScan,
  createFolder,
  createLibrary,
  createModel,
  deleteModel,
  findModel,
  forkModel,
  loadState,
  renameModel,
  saveState,
  StorageQuotaError,
  updateModelCatalog,
} from './storage'
import Banner from './components/Banner'
import Sidebar from './components/Sidebar'
import Uploader from './components/Uploader'
import ModelView from './components/ModelView'
import Portfolio from './components/Portfolio'

type View = 'browse' | 'portfolio'

export default function App() {
  const [state, setState] = useState<MartState>(() => loadState())
  const [view, setView] = useState<View>('browse')
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null)
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [selectedLibraryId, setSelectedLibraryId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [fixing, setFixing] = useState(false)
  const [fixingTarget, setFixingTarget] = useState<{
    ruleId: string
    targetObjId: number
  } | null>(null)
  // Tracks the most recent successful fix(es) for the inline post-fix banner.
  // Cleared on model change, Re-score, or explicit dismiss/Download so the
  // banner only nags about the *latest* batch of changes.
  const [lastFix, setLastFix] = useState<{
    modelId: string
    count: number
    description: string
  } | null>(null)

  // Default the folder selection to the first folder of the first library so
  // the inline uploader has a clear "save under here" target.
  useEffect(() => {
    if (selectedFolderId) return
    const lib = state.libraries[0]
    const fld = lib?.folders[0]
    if (lib && fld) {
      setSelectedLibraryId(lib.id)
      setSelectedFolderId(fld.id)
    }
  }, [state, selectedFolderId])

  // Drop the post-fix banner whenever the user navigates to a different model
  // — it's about the *previous* model's just-applied fixes, not the new one.
  useEffect(() => {
    if (lastFix && lastFix.modelId !== selectedModelId) {
      setLastFix(null)
    }
  }, [selectedModelId, lastFix])

  function persist(next: MartState): boolean {
    try {
      saveState(next)
      setState(next)
      return true
    } catch (e) {
      if (e instanceof StorageQuotaError) {
        // Don't update state — leave the prior in-memory state intact so the
        // user can still delete/export models to free space.
        setError(e.message)
        return false
      }
      throw e
    }
  }

  const selected = selectedModelId ? findModel(state, selectedModelId) : null

  // ── handlers ───────────────────────────────────────────────

  async function handleUpload(catalog: unknown, suggestedName?: string) {
    if (!selectedFolderId || !selectedLibraryId) {
      setError('Pick or create a folder first.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      const result = await scoreJson(catalog)
      const name = suggestedName?.trim() || `Model ${new Date().toLocaleString()}`
      const { state: next, modelId } = createModel(
        state,
        selectedLibraryId,
        selectedFolderId,
        name,
        catalog,
        result
      )
      persist(next)
      setSelectedModelId(modelId)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleRescore() {
    if (!selected) return
    setError(null)
    setLastFix(null)  // a fresh scan supersedes the post-fix banner
    setBusy(true)
    try {
      const result = await scoreJson(selected.model.catalog_json)
      persist(addScan(state, selected.model.id, result))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  function handleRename(name: string) {
    if (!selected) return
    persist(renameModel(state, selected.model.id, name))
  }

  function handleDelete() {
    if (!selected) return
    persist(deleteModel(state, selected.model.id))
    setSelectedModelId(null)
  }

  async function handleFix(ruleId: string, targetObjId: number) {
    if (!selected) return
    setError(null)
    setFixing(true)
    setFixingTarget({ ruleId, targetObjId })
    try {
      const resp = await fixFinding(selected.model.catalog_json, ruleId, targetObjId)
      if (!resp.applied) {
        setError(`Fix not applied: ${resp.description}`)
        return
      }
      const ok = persist(
        updateModelCatalog(
          state,
          selected.model.id,
          resp.catalog,
          resp.result,
          `Fix: ${resp.description}`
        )
      )
      if (ok) {
        setLastFix({
          modelId: selected.model.id,
          count: 1,
          description: resp.description,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setFixing(false)
      setFixingTarget(null)
    }
  }

  async function handleFixAll() {
    if (!selected) return
    setError(null)
    setFixing(true)
    try {
      const resp = await fixAll(selected.model.catalog_json)
      if (resp.applied.length === 0) {
        setError('No auto-fixable findings to apply.')
        return
      }
      const summary = `Fix-all: applied ${resp.applied.length} fix${resp.applied.length === 1 ? '' : 'es'}`
      const ok = persist(
        updateModelCatalog(
          state,
          selected.model.id,
          resp.catalog,
          resp.result,
          summary
        )
      )
      if (ok) {
        setLastFix({
          modelId: selected.model.id,
          count: resp.applied.length,
          description: summary,
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setFixing(false)
    }
  }

  function handleFork(newName: string) {
    if (!selected) return
    const result = forkModel(state, selected.model.id, newName)
    if (!result) return
    persist(result.state)
    setSelectedModelId(result.modelId)
  }

  // The "Add model to this folder" button in the sidebar shifts focus to the
  // empty-state uploader and clears the current model selection.
  function handleRequestNewModel(folderId: string, libraryId: string) {
    setSelectedFolderId(folderId)
    setSelectedLibraryId(libraryId)
    setSelectedModelId(null)
  }

  const selectedFolderName = useMemo(() => {
    if (!selectedFolderId) return null
    for (const lib of state.libraries) {
      const fld = lib.folders.find((f) => f.id === selectedFolderId)
      if (fld) return `${lib.name} / ${fld.name}`
    }
    return null
  }, [state, selectedFolderId])

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <Banner />
      <div className="flex-1 flex min-h-0">
        <div className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col">
          <ViewToggle view={view} onChange={setView} />
          {view === 'browse' && (
            <Sidebar
              state={state}
              selectedModelId={selectedModelId}
              selectedFolderId={selectedFolderId}
              onSelectModel={(modelId, folderId, libraryId) => {
                setSelectedModelId(modelId)
                setSelectedFolderId(folderId)
                setSelectedLibraryId(libraryId)
              }}
              onSelectFolder={(folderId, libraryId) => {
                setSelectedFolderId(folderId)
                setSelectedLibraryId(libraryId)
                setSelectedModelId(null)
              }}
              onCreateLibrary={(name) => persist(createLibrary(state, name))}
              onCreateFolder={(libraryId, name) =>
                persist(createFolder(state, libraryId, name))
              }
              onRequestNewModel={handleRequestNewModel}
            />
          )}
          {view === 'portfolio' && (
            <div className="px-4 py-6 text-xs text-slate-500 leading-relaxed">
              Cross-library scoreboard. Click any row in the table to open that
              model.
            </div>
          )}
        </div>
        <main className="flex-1 min-w-0 overflow-hidden">
          {view === 'portfolio' ? (
            <Portfolio
              state={state}
              onOpenModel={(modelId, folderId, libraryId) => {
                setSelectedModelId(modelId)
                setSelectedFolderId(folderId)
                setSelectedLibraryId(libraryId)
                setView('browse')
              }}
            />
          ) : selected ? (
            <ModelView
              model={selected.model}
              rescoring={busy}
              fixing={fixing}
              fixingTarget={fixingTarget}
              lastFix={lastFix && lastFix.modelId === selected.model.id ? lastFix : null}
              onDismissLastFix={() => setLastFix(null)}
              onRescore={handleRescore}
              onRename={handleRename}
              onDelete={handleDelete}
              onFix={handleFix}
              onFixAll={handleFixAll}
              onFork={handleFork}
            />
          ) : (
            <div className="h-full overflow-y-auto px-8 py-10">
              <div className="max-w-4xl mx-auto space-y-6">
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">
                    Add a model
                  </p>
                  <h2 className="text-2xl font-semibold text-slate-900 mt-0.5">
                    {selectedFolderName ? (
                      <>
                        Save into{' '}
                        <span className="text-amber-600">{selectedFolderName}</span>
                      </>
                    ) : (
                      'Pick a folder on the left'
                    )}
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    Drop or paste a data-model JSON. We'll score it and save it
                    under the selected folder so you can re-score and track
                    versions over time.
                  </p>
                </div>
                <Uploader onScore={handleUpload} loading={busy} />
                {error && (
                  <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                    <strong className="font-semibold">Error:</strong>
                    <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
                      {error}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

function ViewToggle({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  const tabs: Array<{ id: View; label: string }> = [
    { id: 'browse', label: 'Browse' },
    { id: 'portfolio', label: 'Portfolio' },
  ]
  return (
    <div className="px-3 pt-3 pb-3 border-b border-slate-200">
      <div className="grid grid-cols-2 gap-1 bg-slate-100 rounded-lg p-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={`text-xs font-semibold py-1.5 rounded-md transition-colors ${
              view === t.id
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  )
}

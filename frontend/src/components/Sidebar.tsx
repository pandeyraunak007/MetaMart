import { useState } from 'react'
import type { MartState, Library, Folder, SavedModel } from '../types'
import { latestScan } from '../storage'

interface Props {
  state: MartState
  selectedModelId: string | null
  selectedFolderId: string | null  // for "+ new model" target when no model selected
  onSelectModel: (modelId: string, folderId: string, libraryId: string) => void
  onSelectFolder: (folderId: string, libraryId: string) => void
  onCreateLibrary: (name: string) => void
  onCreateFolder: (libraryId: string, name: string) => void
  onRequestNewModel: (folderId: string, libraryId: string) => void
}

const GRADE_TEXT: Record<string, string> = {
  A: 'text-emerald-700 bg-emerald-50 ring-emerald-200',
  B: 'text-lime-700 bg-lime-50 ring-lime-200',
  C: 'text-amber-700 bg-amber-50 ring-amber-200',
  D: 'text-orange-700 bg-orange-50 ring-orange-200',
  F: 'text-red-700 bg-red-50 ring-red-200',
}

export default function Sidebar({
  state,
  selectedModelId,
  selectedFolderId,
  onSelectModel,
  onSelectFolder,
  onCreateLibrary,
  onCreateFolder,
  onRequestNewModel,
}: Props) {
  return (
    <aside className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col">
      <div className="px-4 py-3.5 border-b border-slate-200 flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Libraries
        </h2>
        <button
          onClick={() => {
            const name = prompt('Library name?')
            if (name) onCreateLibrary(name)
          }}
          title="New library"
          className="text-slate-400 hover:text-slate-700 transition-colors"
        >
          <PlusIcon />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        {state.libraries.map((lib) => (
          <LibraryNode
            key={lib.id}
            library={lib}
            selectedModelId={selectedModelId}
            selectedFolderId={selectedFolderId}
            onSelectModel={onSelectModel}
            onSelectFolder={onSelectFolder}
            onCreateFolder={(name) => onCreateFolder(lib.id, name)}
            onRequestNewModel={(folderId) => onRequestNewModel(folderId, lib.id)}
          />
        ))}
      </div>
    </aside>
  )
}

function LibraryNode({
  library,
  selectedModelId,
  selectedFolderId,
  onSelectModel,
  onSelectFolder,
  onCreateFolder,
  onRequestNewModel,
}: {
  library: Library
  selectedModelId: string | null
  selectedFolderId: string | null
  onSelectModel: (modelId: string, folderId: string, libraryId: string) => void
  onSelectFolder: (folderId: string, libraryId: string) => void
  onCreateFolder: (name: string) => void
  onRequestNewModel: (folderId: string) => void
}) {
  const [open, setOpen] = useState(true)
  return (
    <div className="px-2">
      <div className="flex items-center group">
        <button
          onClick={() => setOpen(!open)}
          className="flex-1 flex items-center gap-1.5 px-2 py-1 rounded hover:bg-slate-50 text-left"
        >
          <Caret open={open} />
          <span className="text-sm font-semibold text-slate-800 truncate">
            {library.name}
          </span>
          <span className="text-xs text-slate-400 ml-auto pl-2">
            {countModels(library)}
          </span>
        </button>
        <button
          onClick={() => {
            const name = prompt(`New folder in "${library.name}"?`)
            if (name) onCreateFolder(name)
          }}
          title="New folder"
          className="opacity-0 group-hover:opacity-100 px-1.5 text-slate-400 hover:text-slate-700 transition"
        >
          <PlusIcon />
        </button>
      </div>
      {open && (
        <div className="ml-3 border-l border-slate-100">
          {library.folders.map((fld) => (
            <FolderNode
              key={fld.id}
              folder={fld}
              libraryId={library.id}
              selected={selectedFolderId === fld.id && !selectedModelId}
              selectedModelId={selectedModelId}
              onSelectModel={onSelectModel}
              onSelectFolder={() => onSelectFolder(fld.id, library.id)}
              onRequestNewModel={() => onRequestNewModel(fld.id)}
            />
          ))}
          {library.folders.length === 0 && (
            <p className="text-[11px] text-slate-400 italic px-3 py-1">
              No folders yet
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function FolderNode({
  folder,
  libraryId,
  selected,
  selectedModelId,
  onSelectModel,
  onSelectFolder,
  onRequestNewModel,
}: {
  folder: Folder
  libraryId: string
  selected: boolean
  selectedModelId: string | null
  onSelectModel: (modelId: string, folderId: string, libraryId: string) => void
  onSelectFolder: () => void
  onRequestNewModel: () => void
}) {
  const [open, setOpen] = useState(true)
  return (
    <div>
      <div className="flex items-center group">
        <button
          onClick={() => {
            setOpen(!open)
            onSelectFolder()
          }}
          className={`flex-1 flex items-center gap-1.5 pl-2 pr-2 py-1 rounded text-left ${
            selected ? 'bg-amber-50' : 'hover:bg-slate-50'
          }`}
        >
          <Caret open={open} />
          <FolderIcon />
          <span className="text-sm text-slate-700 truncate">{folder.name}</span>
          <span className="text-[10px] text-slate-400 ml-auto pl-2 font-mono">
            {folder.models.length}
          </span>
        </button>
        <button
          onClick={onRequestNewModel}
          title="Add model to this folder"
          className="opacity-0 group-hover:opacity-100 px-1.5 text-slate-400 hover:text-slate-700 transition"
        >
          <PlusIcon />
        </button>
      </div>
      {open && (
        <div className="ml-3 border-l border-slate-100">
          {folder.models.map((m) => (
            <ModelNode
              key={m.id}
              model={m}
              selected={m.id === selectedModelId}
              onSelect={() => onSelectModel(m.id, folder.id, libraryId)}
            />
          ))}
          {folder.models.length === 0 && (
            <p className="text-[11px] text-slate-400 italic px-3 py-1">
              Drop a JSON to add
            </p>
          )}
        </div>
      )}
    </div>
  )
}

function ModelNode({
  model,
  selected,
  onSelect,
}: {
  model: SavedModel
  selected: boolean
  onSelect: () => void
}) {
  const last = latestScan(model)
  const grade = last?.result.grade ?? '–'
  const gradeStyle = GRADE_TEXT[grade] ?? 'text-slate-500 bg-slate-50 ring-slate-200'
  return (
    <button
      onClick={onSelect}
      className={`w-full flex items-center gap-2 pl-2 pr-2 py-1 rounded text-left ${
        selected ? 'bg-amber-100 hover:bg-amber-100' : 'hover:bg-slate-50'
      }`}
    >
      <ModelIcon />
      <span
        className={`text-sm truncate ${
          selected ? 'text-amber-900 font-medium' : 'text-slate-700'
        }`}
      >
        {model.name}
      </span>
      <span
        className={`ml-auto shrink-0 inline-flex items-center justify-center min-w-[1.4rem] px-1 py-0 rounded text-[10px] font-bold ring-1 ring-inset ${gradeStyle}`}
      >
        {grade}
      </span>
    </button>
  )
}

function countModels(lib: Library): number {
  return lib.folders.reduce((acc, f) => acc + f.models.length, 0)
}

// ── icons ────────────────────────────────────────────────────

function Caret({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-3 w-3 text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-amber-500 shrink-0" viewBox="0 0 24 24" fill="currentColor">
      <path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" />
    </svg>
  )
}

function ModelIcon() {
  return (
    <svg className="h-3.5 w-3.5 text-slate-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  )
}

// localStorage-backed persistence for the Mart Portal shell.
//
// This is the swap-out layer: when the M2.5/M5 backend lands, replace the
// load/save bodies with API calls. The exported helpers (createLibrary,
// addModel, addScan, …) keep the same signatures so callers don't move.

import type {
  AuditEvent,
  AuditEventKind,
  Folder,
  Library,
  MartState,
  SavedModel,
  Scan,
  ScanResult,
} from './types'

const STORAGE_KEY = 'metamart_state_v1'

function uid(prefix: string): string {
  // Crypto-strong IDs would be nicer, but uniqueness inside one localStorage
  // is all we need; collision odds are vanishing for our scale.
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function nowIso(): string {
  return new Date().toISOString()
}

function defaultState(): MartState {
  const folder: Folder = { id: uid('fld'), name: 'Demo', models: [] }
  const library: Library = {
    id: uid('lib'),
    name: 'Default',
    folders: [folder],
    created_at: nowIso(),
  }
  return { schema_version: 1, libraries: [library] }
}

export function loadState(): MartState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      const seeded = defaultState()
      saveState(seeded)
      return seeded
    }
    const parsed = JSON.parse(raw) as MartState
    if (parsed?.schema_version !== 1 || !Array.isArray(parsed.libraries)) {
      // Unknown shape — wipe and reseed rather than crash on access.
      const seeded = defaultState()
      saveState(seeded)
      return seeded
    }
    return parsed
  } catch {
    const seeded = defaultState()
    saveState(seeded)
    return seeded
  }
}

export function saveState(state: MartState): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

// ── pure mutators (return a new state, caller saves) ──────────

export function createLibrary(state: MartState, name: string): MartState {
  const lib: Library = {
    id: uid('lib'),
    name: name.trim() || 'Untitled library',
    folders: [],
    created_at: nowIso(),
  }
  return { ...state, libraries: [...state.libraries, lib] }
}

export function createFolder(
  state: MartState,
  libraryId: string,
  name: string
): MartState {
  const fld: Folder = {
    id: uid('fld'),
    name: name.trim() || 'Untitled folder',
    models: [],
  }
  return mapLibrary(state, libraryId, (lib) => ({
    ...lib,
    folders: [...lib.folders, fld],
  }))
}

export function createModel(
  state: MartState,
  libraryId: string,
  folderId: string,
  name: string,
  catalogJson: unknown,
  firstScan: ScanResult
): { state: MartState; modelId: string } {
  const created = nowIso()
  const modelId = uid('mdl')
  const model: SavedModel = {
    id: modelId,
    name: name.trim() || 'Untitled model',
    catalog_json: catalogJson,
    scans: [{ id: uid('scan'), scanned_at: created, result: firstScan }],
    audit: [
      audit('model_created', `Model "${name}" created`),
      audit('model_scored', `Initial score: ${firstScan.grade} (${firstScan.composite_score.toFixed(1)})`),
    ],
    created_at: created,
    updated_at: created,
  }
  const next = mapFolder(state, libraryId, folderId, (fld) => ({
    ...fld,
    models: [...fld.models, model],
  }))
  return { state: next, modelId }
}

export function addScan(
  state: MartState,
  modelId: string,
  result: ScanResult
): MartState {
  return mapModel(state, modelId, (m) => ({
    ...m,
    scans: [{ id: uid('scan'), scanned_at: nowIso(), result }, ...m.scans],
    audit: [
      audit(
        'model_scored',
        `Re-scored: ${result.grade} (${result.composite_score.toFixed(1)})`
      ),
      ...m.audit,
    ],
    updated_at: nowIso(),
  }))
}

export function renameModel(
  state: MartState,
  modelId: string,
  newName: string
): MartState {
  return mapModel(state, modelId, (m) => ({
    ...m,
    name: newName.trim() || m.name,
    audit: [
      audit('model_renamed', `Renamed "${m.name}" → "${newName.trim() || m.name}"`),
      ...m.audit,
    ],
    updated_at: nowIso(),
  }))
}

export function deleteModel(state: MartState, modelId: string): MartState {
  return {
    ...state,
    libraries: state.libraries.map((lib) => ({
      ...lib,
      folders: lib.folders.map((fld) => ({
        ...fld,
        models: fld.models.filter((m) => m.id !== modelId),
      })),
    })),
  }
}

// ── selectors ─────────────────────────────────────────────────

export function findModel(
  state: MartState,
  modelId: string
): { model: SavedModel; folder: Folder; library: Library } | null {
  for (const library of state.libraries) {
    for (const folder of library.folders) {
      const model = folder.models.find((m) => m.id === modelId)
      if (model) return { model, folder, library }
    }
  }
  return null
}

export function latestScan(model: SavedModel): Scan | null {
  return model.scans[0] ?? null
}

// ── internals ─────────────────────────────────────────────────

function audit(kind: AuditEventKind, message: string): AuditEvent {
  return { id: uid('evt'), kind, at: nowIso(), message }
}

function mapLibrary(
  state: MartState,
  libraryId: string,
  fn: (lib: Library) => Library
): MartState {
  return {
    ...state,
    libraries: state.libraries.map((lib) => (lib.id === libraryId ? fn(lib) : lib)),
  }
}

function mapFolder(
  state: MartState,
  libraryId: string,
  folderId: string,
  fn: (fld: Folder) => Folder
): MartState {
  return mapLibrary(state, libraryId, (lib) => ({
    ...lib,
    folders: lib.folders.map((fld) => (fld.id === folderId ? fn(fld) : fld)),
  }))
}

function mapModel(
  state: MartState,
  modelId: string,
  fn: (m: SavedModel) => SavedModel
): MartState {
  return {
    ...state,
    libraries: state.libraries.map((lib) => ({
      ...lib,
      folders: lib.folders.map((fld) => ({
        ...fld,
        models: fld.models.map((m) => (m.id === modelId ? fn(m) : m)),
      })),
    })),
  }
}

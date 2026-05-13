// localStorage-backed persistence for the Mart Portal shell.
//
// This is the swap-out layer: when the M2.5/M5 backend lands, replace the
// load/save bodies with API calls. The exported helpers (createLibrary,
// addModel, addScan, …) keep the same signatures so callers don't move.

import LZString from 'lz-string'

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

const STORAGE_KEY = 'metamart_state_v2'
// Old key from before the lz-string compression switch — read once on load
// to migrate, then deleted. Bump the version suffix again if the on-disk
// shape changes in a way we can't read transparently.
const LEGACY_STORAGE_KEY = 'metamart_state_v1'

// Cap how many scans we keep per model. eMovies-sized catalogs serialize to
// ~1.6MB raw / ~200KB compressed; each scan is ~50KB. 30 scans gives plenty
// of trend history without unbounded localStorage growth.
const MAX_SCANS_PER_MODEL = 30
// Audit events are tiny but accumulate fast under repeat fix-all calls.
const MAX_AUDIT_EVENTS_PER_MODEL = 100

/**
 * Thrown by saveState when the browser rejects the write because we hit the
 * localStorage quota. App-level catch surfaces a friendly banner so the user
 * knows to delete some saved models.
 */
export class StorageQuotaError extends Error {
  constructor(message = 'Browser storage is full.') {
    super(message)
    this.name = 'StorageQuotaError'
  }
}

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
    const raw = readPersistedState()
    if (!raw) {
      const seeded = defaultState()
      saveState(seeded)
      return seeded
    }
    if (raw.schema_version !== 1 || !Array.isArray(raw.libraries)) {
      // Unknown shape — wipe and reseed rather than crash on access.
      const seeded = defaultState()
      saveState(seeded)
      return seeded
    }
    return raw
  } catch {
    const seeded = defaultState()
    try {
      saveState(seeded)
    } catch {
      // Even seeding failed (probably quota). Return the in-memory default
      // so the app at least renders; user will see a quota banner next save.
    }
    return seeded
  }
}

function readPersistedState(): MartState | null {
  // Current key: lz-string-compressed UTF-16 string.
  const compressed = localStorage.getItem(STORAGE_KEY)
  if (compressed) {
    const json = LZString.decompressFromUTF16(compressed)
    if (json) return JSON.parse(json) as MartState
  }
  // Migrate from the pre-compression v1 key (plain JSON) if present.
  const legacy = localStorage.getItem(LEGACY_STORAGE_KEY)
  if (legacy) {
    const migrated = JSON.parse(legacy) as MartState
    try {
      saveState(migrated)
      localStorage.removeItem(LEGACY_STORAGE_KEY)
    } catch {
      // Couldn't write the compressed copy — leave the legacy key alone so
      // the user doesn't lose data if quota is the blocker.
    }
    return migrated
  }
  return null
}

export function saveState(state: MartState): void {
  const json = JSON.stringify(state)
  const packed = LZString.compressToUTF16(json)
  try {
    localStorage.setItem(STORAGE_KEY, packed)
  } catch (e) {
    if (isQuotaError(e)) {
      throw new StorageQuotaError(
        `Storage full (need ~${Math.round(packed.length / 1024)} KB). ` +
          'Delete some saved models or use Download JSON + Delete to free space.'
      )
    }
    throw e
  }
}

function isQuotaError(e: unknown): boolean {
  if (!(e instanceof Error)) return false
  // Browsers signal quota exhaustion in different ways — check name and code.
  if (e.name === 'QuotaExceededError') return true
  if (e.name === 'NS_ERROR_DOM_QUOTA_REACHED') return true  // older Firefox
  // Some browsers expose a numeric code on DOMException.
  const code = (e as unknown as { code?: number }).code
  return code === 22 || code === 1014
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
    scans: cap(
      [{ id: uid('scan'), scanned_at: nowIso(), result }, ...m.scans],
      MAX_SCANS_PER_MODEL
    ),
    audit: cap(
      [
        audit(
          'model_scored',
          `Re-scored: ${result.grade} (${result.composite_score.toFixed(1)})`
        ),
        ...m.audit,
      ],
      MAX_AUDIT_EVENTS_PER_MODEL
    ),
    updated_at: nowIso(),
  }))
}

function cap<T>(arr: T[], n: number): T[] {
  return arr.length > n ? arr.slice(0, n) : arr
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

export function updateModelCatalog(
  state: MartState,
  modelId: string,
  newCatalog: unknown,
  newScan: ScanResult,
  auditMessage: string
): MartState {
  return mapModel(state, modelId, (m) => ({
    ...m,
    catalog_json: newCatalog,
    scans: cap(
      [{ id: uid('scan'), scanned_at: nowIso(), result: newScan }, ...m.scans],
      MAX_SCANS_PER_MODEL
    ),
    audit: cap(
      [audit('model_scored', auditMessage), ...m.audit],
      MAX_AUDIT_EVENTS_PER_MODEL
    ),
    updated_at: nowIso(),
  }))
}

export function forkModel(
  state: MartState,
  modelId: string,
  newName: string
): { state: MartState; modelId: string } | null {
  const found = findModel(state, modelId)
  if (!found) return null
  const created = nowIso()
  const newId = uid('mdl')
  const last = latestScan(found.model)
  const initialScans: Scan[] = last
    ? [{ id: uid('scan'), scanned_at: created, result: last.result }]
    : []
  const fork: SavedModel = {
    id: newId,
    name: newName.trim() || `${found.model.name} (copy)`,
    catalog_json: structuredCloneCompat(found.model.catalog_json),
    scans: initialScans,
    audit: [audit('model_created', `Forked from "${found.model.name}"`)],
    created_at: created,
    updated_at: created,
  }
  const next = mapFolder(state, found.library.id, found.folder.id, (fld) => ({
    ...fld,
    models: [...fld.models, fork],
  }))
  return { state: next, modelId: newId }
}

function structuredCloneCompat<T>(v: T): T {
  if (typeof structuredClone === 'function') return structuredClone(v)
  return JSON.parse(JSON.stringify(v))
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

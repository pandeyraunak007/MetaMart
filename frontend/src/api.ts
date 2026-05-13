import type { ScanResult } from './types'

interface FastApiValidationError {
  loc?: (string | number)[]
  msg?: string
  type?: string
}

function formatErrorDetail(raw: string): string {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return raw
  }

  // FastAPI returns { detail: string } for HTTPException
  // and { detail: ValidationError[] } for 422 request-validation failures.
  if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
    const detail = (parsed as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((e: FastApiValidationError) => {
          const where = Array.isArray(e.loc) ? e.loc.join('.') : ''
          const msg = e.msg ?? 'validation error'
          return where ? `${msg} (at ${where})` : msg
        })
        .join('; ')
    }
    return JSON.stringify(detail)
  }
  return JSON.stringify(parsed)
}

export async function scoreJson(catalog: unknown): Promise<ScanResult> {
  const resp = await fetch('/api/v1/quality/score-json', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(catalog),
  })
  if (!resp.ok) {
    const raw = await resp.text()
    throw new Error(`${resp.status}: ${formatErrorDetail(raw)}`)
  }
  return (await resp.json()) as ScanResult
}

import type { ScanResult } from './types'

export async function scoreJson(catalog: unknown): Promise<ScanResult> {
  const resp = await fetch('/api/v1/quality/score-json', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(catalog),
  })
  if (!resp.ok) {
    let detail = await resp.text()
    try {
      const parsed = JSON.parse(detail)
      detail = parsed.detail ?? detail
    } catch {
      // body wasn't JSON; use raw text
    }
    throw new Error(`${resp.status}: ${detail}`)
  }
  return (await resp.json()) as ScanResult
}

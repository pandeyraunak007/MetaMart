export default function Banner() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-6 py-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold tracking-tight">
            M
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">MetaMart Quality</h1>
            <p className="text-xs text-slate-500">
              Score your data model against seven quality dimensions
            </p>
          </div>
        </div>
        <a
          href="https://github.com/pandeyraunak007/MetaMart"
          target="_blank"
          rel="noreferrer"
          className="text-sm text-slate-600 hover:text-slate-900 transition-colors"
        >
          GitHub →
        </a>
      </div>
    </header>
  )
}

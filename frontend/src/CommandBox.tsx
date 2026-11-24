import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Sparkles } from 'lucide-react'
import { request } from './http'

type Preview = { state: 'preview'; proposal_id: string; actions: string[] }
type CommandResult = Preview | { state: 'clarification'; message: string } | {
  state: 'agenda'; first: string; last: string
  items: { id: number; source: string; title: string; date: string; time: string | null; kind: string }[]
}

const examples = [
  'I need bananas', 'Add task Study due tomorrow', 'Add event Book club on tomorrow',
  'Remind me to call Sam tomorrow', 'Add goal Reading target 100 pages',
  'Add milestone First chapter at 15 for Reading', 'Log 15 toward Reading', "What's coming up this week?",
]

export function CommandBox({ today, onApplied }: { today: string; onApplied: () => void }) {
  const field = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [result, setResult] = useState<CommandResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')
  const preview = result?.state === 'preview' ? result : null

  useEffect(() => {
    function focusCommand(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && !field.current?.disabled) {
        event.preventDefault()
        field.current?.focus()
      }
    }
    window.addEventListener('keydown', focusCommand)
    return () => window.removeEventListener('keydown', focusCommand)
  }, [])

  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!text.trim() || busy || preview) return
    setBusy(true)
    setResult(null)
    setFeedback('')
    setError('')
    try {
      const response = await request('/api/commands/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim(), today }),
      })
      setResult(await response.json())
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t run this command.')
    } finally {
      setBusy(false)
    }
  }

  async function finish(proposal: Preview, decision: 'confirm' | 'cancel') {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`/api/commands/${proposal.proposal_id}/${decision}`, { method: 'POST' })
      const body = await response.json().catch(() => null)
      if (!response.ok) {
        if ([404, 409, 410].includes(response.status)) setResult(null)
        throw new Error(body?.detail ?? 'Couldn’t reach the server. Try again.')
      }
      setResult(null)
      if (decision === 'confirm') {
        setText('')
        setFeedback(proposal.actions.length === 1 ? 'Change applied.' : `${proposal.actions.length} changes applied.`)
        onApplied()
      } else {
        setFeedback('Proposal cancelled.')
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t finish this proposal.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="panel command-box" aria-label="Momentum commands">
    <form className="command-form" onSubmit={run}>
      <label className="command-input"><Sparkles size={19} aria-hidden="true" />
        <input ref={field} aria-label="Momentum command" aria-keyshortcuts="Control+K Meta+K" placeholder="What would you like to do?"
          value={text} onChange={event => setText(event.target.value)} maxLength={2000} required disabled={busy || !!preview} />
      </label>
      <button type="submit" className="primary-button" disabled={busy || !!preview || !text.trim()}>{busy && !preview ? 'Checking…' : 'Run command'}</button>
    </form>
    <details className="command-examples">
      <summary>Example commands</summary>
      <p className="muted">Use a semicolon between requests to preview up to five changes together.</p>
      <div className="command-examples-list">{examples.map(example => <button className="secondary-button" key={example} type="button"
        disabled={busy || !!preview} onClick={() => { setText(example); field.current?.focus() }}>{example}</button>)}</div>
    </details>
    {feedback && <p className="command-feedback" role="status">{feedback}</p>}
    {error && <p className="command-error" role="alert">{error}</p>}
    {result?.state === 'clarification' && <p className="command-result" role="status">{result.message}</p>}
    {preview && <div className="command-result">
      <h2>Review proposed changes</h2>
      <ol className="command-actions-list">{preview.actions.map((action, index) => <li key={index}>{action}</li>)}</ol>
      <div className="editor-actions">
        <button className="primary-button" type="button" disabled={busy} onClick={() => void finish(preview, 'confirm')}>{busy ? 'Working…' : 'Confirm changes'}</button>
        <button className="secondary-button" type="button" disabled={busy} onClick={() => void finish(preview, 'cancel')}>Cancel proposal</button>
      </div>
    </div>}
    {result?.state === 'agenda' && <div className="command-result">
      <h2>Schedule</h2>
      <p className="muted">{result.first === result.last ? result.first : `${result.first} – ${result.last}`}</p>
      {result.items.length === 0 ? <p>Nothing scheduled for this period.</p> : <ul className="command-agenda">
        {result.items.map(item => <li key={`${item.source}-${item.id}-${item.date}`}>
          <time dateTime={item.date}>{item.date}</time><span>{item.time && `${item.time} · `}{item.kind} · {item.title}</span>
        </li>)}
      </ul>}
    </div>}
  </section>
}

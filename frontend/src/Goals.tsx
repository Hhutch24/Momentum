import { useEffect, useState, type FormEvent } from 'react'
import { Bell, Check, Flag, Plus, Target } from 'lucide-react'
import { request } from './http'

type Goal = {
  id: number
  title: string
  target: number
  unit: string
  progress: number
  week_progress: number
  month_progress: number
  milestone_count: number
  milestones_reached: number
}
type GoalDetail = Goal & {
  checkins: { id: number; day: string; amount: number; note: string }[]
  milestones: { id: number; title: string; threshold: number; reached: boolean }[]
}
type GoalAction = 'checkin' | 'milestone' | 'reminder' | 'delete'

const numberLabel = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 10 })

function amountLabel(amount: number, unit: string) {
  return `${numberLabel.format(amount)}${unit ? ` ${unit}` : ''}`
}

function useGoalData<T>(path: string, revision: number) {
  const key = `${path}:${revision}`
  const [result, setResult] = useState<{ key: string; data: T | null } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await request(path, { signal: controller.signal })
        const data: T = await response.json()
        if (!controller.signal.aborted) setResult({ key, data })
      } catch {
        if (!controller.signal.aborted) setResult({ key, data: null })
      }
    }
    void load()
    return () => controller.abort()
  }, [path, key])

  return result?.key === key ? result.data : undefined
}

function GoalProgress({ goal }: { goal: Goal }) {
  const percentage = Math.floor(Math.min(100, goal.progress / goal.target * 100))
  return <div className="goal-progress">
    <div className="goal-progress-label">
      <strong>{amountLabel(goal.progress, '')} / {amountLabel(goal.target, goal.unit)}</strong>
      <span>{percentage}%</span>
    </div>
    <progress aria-label={`Progress for ${goal.title}`} max={goal.target} value={Math.min(goal.progress, goal.target)} />
    <dl className="goal-totals">
      <div><dt>This week</dt><dd>{amountLabel(goal.week_progress, goal.unit)}</dd></div>
      <div><dt>This month</dt><dd>{amountLabel(goal.month_progress, goal.unit)}</dd></div>
      {goal.milestone_count > 0 && <div><dt>Milestones reached</dt><dd>{goal.milestones_reached} / {goal.milestone_count}</dd></div>}
    </dl>
  </div>
}

export function GoalsOverview({ today }: { today: string }) {
  const [revision, setRevision] = useState(0)
  const goals = useGoalData<Goal[]>(`/api/goals?day=${today}`, revision)
  return <section className="panel goals-overview" aria-labelledby="goal-overview-title" aria-busy={goals === undefined}>
    <div className="panel-header"><h2 id="goal-overview-title">Goals</h2><Target size={19} aria-hidden="true" /></div>
    {goals === undefined ? <p className="goal-message" role="status">Loading goals…</p>
      : goals === null ? <div className="goal-message" role="alert">Couldn’t load goals. <button className="retry" type="button" onClick={() => setRevision(value => value + 1)}>Try again</button></div>
      : goals.length === 0 ? <p className="goal-message">Add a goal to track your progress here.</p>
      : goals.slice(0, 3).map(goal => <article className="goal-overview-entry" key={goal.id}><h3>{goal.title}</h3><GoalProgress goal={goal} /></article>)}
  </section>
}

function GoalDetails({ goalId, today, revision, onChange, onDelete }: {
  goalId: number; today: string; revision: number; onChange: (message: string) => void; onDelete: () => void
}) {
  const [retry, setRetry] = useState(0)
  const goal = useGoalData<GoalDetail>(`/api/goals/${goalId}?day=${today}`, revision + retry)
  const [action, setAction] = useState<GoalAction | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!goal || !action || busy) return
    const data = new FormData(event.currentTarget)
    const goalPath = `/api/goals/${goal.id}`
    const headers = { 'Content-Type': 'application/json' }
    setBusy(true)
    setError('')
    try {
      if (action === 'delete') {
        await request(goalPath, { method: 'DELETE' })
        onDelete()
      } else if (action === 'checkin') {
        await request(`${goalPath}/checkins`, { method: 'POST', headers,
          body: JSON.stringify({ amount: Number(data.get('amount')), day: data.get('day'), note: data.get('note') }) })
        onChange('Check-in saved.')
      } else if (action === 'milestone') {
        await request(`${goalPath}/milestones`, { method: 'POST', headers,
          body: JSON.stringify({ title: data.get('title'), threshold: Number(data.get('threshold')) }) })
        onChange('Milestone added.')
      } else {
        await request('/api/schedule', { method: 'POST', headers,
          body: JSON.stringify({ title: `Check in on ${goal.title}`, kind: 'Reminder', day: data.get('day'), repeat: data.get('repeat') }) })
        onChange('Reminder added to Planner.')
      }
      setAction(null)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t save your change.')
    } finally {
      setBusy(false)
    }
  }

  function open(next: GoalAction | null) {
    setError('')
    setAction(next)
  }

  if (goal === undefined) return <p className="panel goal-message" role="status">Loading goal…</p>
  if (goal === null) return <div className="panel goal-message" role="alert">Couldn’t load the goal. <button className="retry" type="button" onClick={() => setRetry(value => value + 1)}>Try again</button></div>

  return <section className="panel goal-detail" aria-labelledby="goal-detail-title">
    <div className="panel-header"><h2 id="goal-detail-title">{goal.title}</h2></div>
    <div className="goal-detail-body">
      <GoalProgress goal={goal} />
      <div className="editor-actions">
        <button className="primary-button" type="button" disabled={busy} onClick={() => open('checkin')}><Plus size={17} aria-hidden="true" /> Log check-in</button>
        <button className="secondary-button" type="button" disabled={busy} onClick={() => open('milestone')}><Flag size={17} aria-hidden="true" /> Add milestone</button>
        <button className="secondary-button" type="button" disabled={busy} onClick={() => open('reminder')}><Bell size={17} aria-hidden="true" /> Set reminder</button>
      </div>
      {action && <form className="goal-form" key={action} onSubmit={submit}>
        <fieldset className="editor-fields" disabled={busy}>
          {action === 'checkin' && <>
            <label>Progress to add<input name="amount" type="number" min="0" step="any" required autoFocus /></label>
            <label>Check-in date<input name="day" type="date" max={today} defaultValue={today} required /></label>
            <label>Note (optional)<input name="note" /></label>
          </>}
          {action === 'milestone' && <>
            <label>Milestone name<input name="title" required autoFocus /></label>
            <label>Progress needed<input name="threshold" type="number" min="0.01" step="any" required /></label>
          </>}
          {action === 'reminder' && <>
            <label>First reminder<input name="day" type="date" min={today} defaultValue={today} required autoFocus /></label>
            <label>Frequency<select aria-label="Frequency" name="repeat"><option>Weekly</option><option>Monthly</option></select></label>
          </>}
          {action === 'delete' && <p>Delete {goal.title}, its milestones, and its check-in history?</p>}
          {error && <p className="task-error" role="alert">{error}</p>}
          <div className="editor-actions">
            <button type="submit" className={action === 'delete' ? 'danger-button' : 'primary-button'}>
              {busy ? 'Saving…' : action === 'delete' ? 'Confirm deletion' : action === 'reminder' ? 'Schedule reminder' : action === 'milestone' ? 'Save milestone' : 'Save check-in'}
            </button>
            <button type="button" className="secondary-button" onClick={() => open(null)}>Cancel</button>
          </div>
        </fieldset>
      </form>}
      <section className="goal-section"><h3>Milestones</h3>
        {goal.milestones.length === 0 ? <p className="muted">No milestones yet.</p> : <ul className="goal-history">
          {goal.milestones.map(milestone => <li key={milestone.id}>
            <span><strong>{milestone.title}</strong><span className="muted">{amountLabel(milestone.threshold, goal.unit)}</span></span>
            <span className={`goal-badge ${milestone.reached ? 'reached' : ''}`}>{milestone.reached && <Check size={15} aria-hidden="true" />}{milestone.reached ? 'Reached' : 'Upcoming'}</span>
          </li>)}
        </ul>}
      </section>
      <section className="goal-section"><h3>Check-in history</h3>
        {goal.checkins.length === 0 ? <p className="muted">No check-ins yet.</p> : <ul className="goal-history">
          {goal.checkins.map(checkin => <li key={checkin.id}>
            <span><time dateTime={checkin.day}>{checkin.day}</time>{checkin.note && <span className="muted">{checkin.note}</span>}</span>
            <strong>+{amountLabel(checkin.amount, goal.unit)}</strong>
          </li>)}
        </ul>}
      </section>
      <button type="button" className="secondary-button" disabled={busy} onClick={() => open('delete')}>Delete goal</button>
    </div>
  </section>
}

export function Goals({ today }: { today: string }) {
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState<number | null>(null)
  const [adding, setAdding] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')
  const goals = useGoalData<Goal[]>(`/api/goals?day=${today}`, revision)
  const active = goals?.find(goal => goal.id === selected) ?? goals?.[0]

  function refresh(message: string) {
    setFeedback(message)
    setRevision(value => value + 1)
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    const data = new FormData(event.currentTarget)
    setSaving(true)
    setError('')
    try {
      const response = await request('/api/goals', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: data.get('title'), target: Number(data.get('target')), unit: data.get('unit') }) })
      const { id } = await response.json()
      setSelected(id)
      setAdding(false)
      refresh('Goal added.')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t add the goal.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <header className="page-header"><h1>Goals</h1><button type="button" className="primary-button" onClick={() => { setAdding(true); setFeedback('') }}><Plus size={18} aria-hidden="true" /> New goal</button></header>
    {feedback && <p className="task-feedback" role="status">{feedback}</p>}
    {adding && <form className="panel goal-form goal-create" onSubmit={create}>
      <fieldset className="editor-fields" disabled={saving}>
        <label>Goal name<input name="title" required autoFocus /></label>
        <div className="editor-options">
          <label>Target amount<input name="target" type="number" min="0.01" step="any" required /></label>
          <label>Unit (optional)<input name="unit" placeholder="Pages, dollars, workouts" /></label>
        </div>
        {error && <p className="task-error" role="alert">{error}</p>}
        <div className="editor-actions"><button type="submit" className="primary-button">{saving ? 'Saving…' : 'Add goal'}</button>
          <button type="button" className="secondary-button" onClick={() => { setError(''); setAdding(false) }}>Cancel</button></div>
      </fieldset>
    </form>}
    {goals === undefined ? <div className="panel state" role="status">Loading goals…</div>
      : goals === null ? <div className="panel state" role="alert">Couldn’t load goals.<button className="retry" type="button" onClick={() => setRevision(value => value + 1)}>Try again</button></div>
      : !active ? <div className="panel state"><Target size={26} aria-hidden="true" /> No goals yet.</div>
      : <div className="goals-layout">
        <section className="panel goal-list" aria-label="Choose a goal">
          {goals.map(goal => <button type="button" key={goal.id} aria-pressed={goal.id === active.id} onClick={() => { setSelected(goal.id); setFeedback('') }}>
            <Target size={17} aria-hidden="true" /> <span>{goal.title}</span>
          </button>)}
        </section>
        <GoalDetails key={active.id} goalId={active.id} today={today} revision={revision} onChange={refresh}
          onDelete={() => { setSelected(null); refresh('Goal deleted.') }} />
      </div>}
  </>
}

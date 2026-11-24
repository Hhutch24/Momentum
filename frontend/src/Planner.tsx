import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Bell, CalendarDays, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { calendarDate, localDay } from './dates'
import { request } from './http'

const views = ['Day', 'Week', 'Month'] as const
const kinds = ['Appointment', 'Event', 'Deadline', 'Birthday', 'Reminder']
const repetitions = ['None', 'Daily', 'Weekly', 'Monthly', 'Yearly']
type View = typeof views[number]
type CalendarItem = {
  id: number
  source: 'task' | 'schedule'
  date: string
  title: string
  kind: string
  time: string | null
  completed: boolean | null
  series_start: string | null
  repeat: string | null
}
type Period = { first: string; last: string; items: CalendarItem[] }
type Editor = { item: CalendarItem | null; day: string }

const monthLabel = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' })
const fullDayLabel = new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
const shortDayLabel = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
const dayNumber = new Intl.DateTimeFormat(undefined, { day: 'numeric' })

function EventEditor({ editor, onClose, onSaved }: { editor: Editor; onClose: () => void; onSaved: (message: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const item = editor.item
  const recurring = item?.repeat && item.repeat !== 'None'

  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])

  function cancel() {
    dialog.current?.close()
    onClose()
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (confirmDelete || busy) return
    const fields = new FormData(event.currentTarget)
    const title = String(fields.get('title')).trim()
    if (!title) {
      setError('Enter a title.')
      return
    }
    setBusy(true)
    setError('')
    try {
      await request(item ? `/api/schedule/${item.id}` : '/api/schedule', {
        method: item ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, kind: fields.get('kind'), day: fields.get('day'),
          event_time: fields.get('event_time') || null, repeat: fields.get('repeat') }),
      })
      dialog.current?.close()
      onSaved(item ? 'Changes saved.' : 'Entry added.')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t save this entry.')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!item || busy) return
    setBusy(true)
    setError('')
    try {
      await request(`/api/schedule/${item.id}`, { method: 'DELETE' })
      dialog.current?.close()
      onSaved('Entry deleted.')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t delete this entry.')
    } finally {
      setBusy(false)
    }
  }

  return <dialog ref={dialog} className="planner-dialog" aria-labelledby="event-editor-heading" onCancel={event => {
    event.preventDefault()
    if (!busy) cancel()
  }}>
    <h2 id="event-editor-heading">{item ? (recurring ? 'Edit recurring entry' : 'Edit entry') : 'New entry'}</h2>
    {recurring && <p className="muted">Changes apply to the entire series, starting from the date below.</p>}
    {error && <p className="task-error" role="alert">{error}</p>}
    <form onSubmit={save}>
      <fieldset disabled={busy} className="editor-fields">
        <label>Title<input name="title" defaultValue={item?.title} required autoFocus /></label>
        <div className="editor-options">
          <label>Type<select aria-label="Type" name="kind" defaultValue={item?.kind ?? 'Event'}>{kinds.map(kind => <option key={kind}>{kind}</option>)}</select></label>
          <label>Date<input name="day" type="date" defaultValue={item?.series_start ?? editor.day} required /></label>
          <label>Time (optional)<input name="event_time" type="time" defaultValue={item?.time ?? ''} /></label>
          <label>Repeat<select aria-label="Repeat" name="repeat" defaultValue={item?.repeat ?? 'None'}>{repetitions.map(repeat => <option key={repeat}>{repeat}</option>)}</select></label>
        </div>
        {confirmDelete ? <div className="editor-actions">
          <p className="w-full">{recurring ? 'Delete every occurrence in this series?' : 'Delete this entry?'}</p>
          <button type="button" className="danger-button" onClick={() => void remove()}>Confirm deletion</button>
          <button type="button" className="secondary-button" onClick={() => setConfirmDelete(false)}>Keep entry</button>
        </div> : <div className="editor-actions">
          <button type="submit" className="primary-button">{busy ? 'Saving…' : 'Save entry'}</button>
          <button type="button" className="secondary-button" onClick={cancel}>Cancel</button>
          {item && <button type="button" className="danger-button" onClick={() => { setConfirmDelete(true); setError('') }}>Delete entry</button>}
        </div>}
      </fieldset>
    </form>
  </dialog>
}

function Entries({ items, onEdit }: { items: CalendarItem[]; onEdit: (item: CalendarItem) => void }) {
  return <ul className="calendar-entries">{items.map(item => {
    const content = <>
      <span className={`calendar-entry-title ${item.completed ? 'completed' : ''}`}>{item.title}</span>
      <span className="calendar-entry-detail">{item.time ? `${item.time} · ` : ''}{item.completed ? 'Completed task' : item.kind}</span>
    </>
    return <li key={`${item.source}-${item.id}`}>
      {item.source === 'schedule'
        ? <button className="calendar-entry" type="button" onClick={() => onEdit(item)}>{content}</button>
        : <div className="calendar-entry calendar-task">{content}</div>}
    </li>
  })}</ul>
}

export function Planner() {
  const today = localDay(new Date())
  const [day, setDay] = useState(today)
  const [view, setView] = useState<View>('Week')
  const [result, setResult] = useState<{ key: string; period: Period | null } | null>(null)
  const [revision, setRevision] = useState(0)
  const [editor, setEditor] = useState<Editor | null>(null)
  const [feedback, setFeedback] = useState('')
  const key = `${day}-${view}-${revision}`

  useEffect(() => {
    const controller = new AbortController()
    async function loadPeriod() {
      try {
        const response = await request(`/api/planner?date=${day}&view=${view}`, { signal: controller.signal })
        const period: Period = await response.json()
        if (!controller.signal.aborted) setResult({ key, period })
      } catch {
        if (!controller.signal.aborted) setResult({ key, period: null })
      }
    }
    void loadPeriod()
    return () => controller.abort()
  }, [day, view, key])

  const current = result?.key === key ? result : null
  const period = current?.period
  const days: string[] = []
  const itemsByDay = new Map<string, CalendarItem[]>()
  if (period) {
    const cursor = calendarDate(period.first)
    while (localDay(cursor) <= period.last) {
      days.push(localDay(cursor))
      if (days.at(-1) === period.last) break
      cursor.setDate(cursor.getDate() + 1)
    }
    for (const item of period.items) {
      const items = itemsByDay.get(item.date) ?? []
      items.push(item)
      itemsByDay.set(item.date, items)
    }
  }

  const selected = calendarDate(day)
  const label = view === 'Month' ? monthLabel.format(selected)
    : view === 'Week' && period ? `${shortDayLabel.format(calendarDate(period.first))} – ${shortDayLabel.format(calendarDate(period.last))}`
    : fullDayLabel.format(selected)

  function move(offset: number) {
    const next = calendarDate(day)
    if (view === 'Month') {
      next.setDate(1)
      next.setMonth(next.getMonth() + offset)
    } else {
      next.setDate(next.getDate() + offset * (view === 'Week' ? 7 : 1))
    }
    if (next.getFullYear() >= 1 && next.getFullYear() <= 9999) setDay(localDay(next))
  }

  function openDay(date: string) {
    setDay(date)
    setView('Day')
  }

  function edit(item: CalendarItem) {
    setFeedback('')
    setEditor({ item, day: item.date })
  }

  return <>
    <header className="page-header"><h1>Planner</h1>
      <button type="button" className="primary-button" onClick={() => { setFeedback(''); setEditor({ item: null, day }) }}><Plus size={18} aria-hidden="true" /> New entry</button>
    </header>
    <div className="planner-toolbar">
      <div className="date-controls" role="group" aria-label="Calendar view">
        {views.map(value => <button type="button" className="jump-today" key={value} aria-pressed={view === value} onClick={() => setView(value)}>{value}</button>)}
      </div>
      <div className="planner-navigation">
        <div className="date-controls" role="group" aria-label="Calendar navigation">
          <button type="button" aria-label={`Previous ${view.toLowerCase()}`} onClick={() => move(-1)}><ChevronLeft size={19} aria-hidden="true" /></button>
          <button type="button" className="jump-today" onClick={() => setDay(today)}>Today</button>
          <button type="button" aria-label={`Next ${view.toLowerCase()}`} onClick={() => move(1)}><ChevronRight size={19} aria-hidden="true" /></button>
        </div>
        <label className="calendar-date-picker"><span>Go to date</span><input type="date" min="0001-01-01" max="9999-12-31" value={day} onChange={event => {
          if (/^\d{4}-\d{2}-\d{2}$/.test(event.target.value) && event.target.value >= '0001-01-01') setDay(event.target.value)
        }} /></label>
      </div>
    </div>
    {feedback && <p className="task-feedback" role="status">{feedback}</p>}
    <section className="panel planner-panel" aria-labelledby="planner-period" aria-busy={!current}>
      <div className="panel-header"><h2 id="planner-period">{label}</h2></div>
      {!current ? <div className="state" role="status"><span className="spinner" aria-hidden="true" /> Loading calendar…</div>
        : !period ? <div className="state" role="alert">Couldn’t load the calendar.<button type="button" className="retry" onClick={() => setRevision(value => value + 1)}>Try again</button></div>
        : view === 'Month' ? <>
          <div className="calendar-month" aria-label="Calendar month">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(name => <div key={name} className="weekday-label">{name}</div>)}
            {Array.from({ length: (calendarDate(period.first).getDay() + 6) % 7 }, (_, index) => <div className="month-cell" aria-hidden="true" key={`blank-${index}`} />)}
            {days.map(date => <section className="month-cell" key={date} aria-label={fullDayLabel.format(calendarDate(date))}>
              <button type="button" className="month-date" aria-current={date === today ? 'date' : undefined}
                aria-label={`Open ${fullDayLabel.format(calendarDate(date))}`} onClick={() => openDay(date)}>{dayNumber.format(calendarDate(date))}</button>
              <Entries items={itemsByDay.get(date) ?? []} onEdit={edit} />
            </section>)}
          </div>
          <div className="calendar-month-mobile">
            {period.items.length === 0 && <div className="state"><CalendarDays size={24} aria-hidden="true" /> No entries this month.</div>}
            {days.filter(date => itemsByDay.has(date)).map(date => <section className="calendar-day" key={date}>
              <h3>{shortDayLabel.format(calendarDate(date))}</h3><Entries items={itemsByDay.get(date) ?? []} onEdit={edit} />
            </section>)}
          </div>
        </> : <div className={view === 'Week' ? 'calendar-week' : 'calendar-single'}>
          {days.map(date => <section className="calendar-day" key={date}>
            {view === 'Week' && <h3><button type="button" className="calendar-day-link" aria-current={date === today ? 'date' : undefined} onClick={() => openDay(date)}>{shortDayLabel.format(calendarDate(date))}</button></h3>}
            {itemsByDay.has(date) ? <Entries items={itemsByDay.get(date) ?? []} onEdit={edit} />
              : <p className="calendar-empty muted">{view === 'Day' && <Bell size={17} aria-hidden="true" />} No entries</p>}
          </section>)}
        </div>}
    </section>
    {editor && <EventEditor editor={editor} onClose={() => setEditor(null)} onSaved={message => {
      setEditor(null)
      setFeedback(message)
      setRevision(value => value + 1)
    }} />}
  </>
}

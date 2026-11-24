import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  AlertCircle, Bell, CalendarDays, Check, ChevronLeft, ChevronRight,
  Circle, Clock3, ListTodo, Moon, ShoppingBasket, Sun, Zap,
} from 'lucide-react'
import './styles.css'
import { TaskList } from './TaskList'
import { Planner } from './Planner'
import { localDay } from './dates'

type AgendaItem = {
  id: number
  source: 'task' | 'schedule'
  date: string
  title: string
  kind: string
  time: string | null
  completed: boolean | null
  priority: string | null
}

type AgendaState = { day: string } & (
  { status: 'loading' | 'error' } | { status: 'ready'; items: AgendaItem[] }
)

const dateLabel = new Intl.DateTimeFormat(undefined, {
  weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
})

function AgendaRow({ item }: { item: AgendaItem }) {
  const Icon = item.source === 'task' ? (item.completed ? Check : Circle)
    : item.kind === 'Reminder' ? Bell : CalendarDays

  return <li className="agenda-row">
    <div className={`item-icon ${item.completed ? 'done' : item.source}`}><Icon size={18} aria-hidden="true" /></div>
    <div className="min-w-0">
      <p className={`item-title ${item.completed ? 'completed' : ''}`}>{item.title}</p>
      <p className="muted text-sm">{item.completed ? 'Completed task' : item.kind}{item.priority === 'High' ? ' · High priority' : ''}</p>
    </div>
    {item.time && <time className="item-time" dateTime={`${item.date}T${item.time}`}>{item.time}</time>}
  </li>
}

function App() {
  const [page, setPage] = useState<'Today' | 'Planner' | 'Tasks' | 'Shopping'>('Today')
  const [todayVisit, setTodayVisit] = useState(0)
  const [theme, setTheme] = useState(() => localStorage.getItem('momentum-theme')
    ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('momentum-theme', theme)
  }, [theme])

  return <div className="shell min-h-screen">
    <aside className="sidebar">
      <div className="brand"><span className="brand-icon"><Zap size={18} aria-hidden="true" /></span>Momentum</div>
      <nav className="workspace-nav" aria-label="Workspace">
        {([{ label: 'Today', Icon: CalendarDays }, { label: 'Planner', Icon: Clock3 }, { label: 'Tasks', Icon: ListTodo },
          { label: 'Shopping', Icon: ShoppingBasket }] as const).map(({ label, Icon }) =>
          <button key={label} className="nav-item" type="button" aria-current={page === label ? 'page' : undefined} onClick={() => {
            setPage(label)
            if (label === 'Today') setTodayVisit(count => count + 1)
          }}>
            <Icon size={18} aria-hidden="true" /> {label}
          </button>)}
      </nav>
      <button className="theme-button" type="button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
        {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
      </button>
    </aside>
    <main className="content">
      {page === 'Today' ? <Today key={todayVisit} /> : page === 'Planner' ? <Planner />
        : <TaskList key={page} listName={page} today={localDay(new Date())} />}
    </main>
  </div>
}

function Today() {
  const today = localDay(new Date())
  const [day, setDay] = useState(today)
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<AgendaState>({ day, status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    async function loadAgenda() {
      setState({ day, status: 'loading' })
      try {
        const response = await fetch(`/api/agenda?date=${day}`, { signal: controller.signal })
        if (!response.ok) throw new Error('Agenda request failed')
        const data = await response.json()
        if (!controller.signal.aborted) setState({ day, status: 'ready', items: data.items })
      } catch {
        if (!controller.signal.aborted) setState({ day, status: 'error' })
      }
    }
    void loadAgenda()
    return () => controller.abort()
  }, [day, attempt])

  const current = state.day === day ? state : { day, status: 'loading' as const }
  const selectedDate = new Date(`${day}T12:00:00`)
  const items = current.status === 'ready' ? current.items : []
  const tasks = items.filter(item => item.source === 'task')
  const done = tasks.filter(item => item.completed).length
  const scheduled = items.length - tasks.length

  function moveDay(offset: number) {
    const next = new Date(selectedDate)
    next.setDate(next.getDate() + offset)
    setDay(localDay(next))
  }

  return <>
      <header className="page-header">
        <div>
          <p className="date-label">{dateLabel.format(selectedDate)}</p>
          <h1>{day === today ? 'Today' : 'Daily agenda'}</h1>
        </div>
        <div className="date-controls" aria-label="Change agenda date">
          <button type="button" aria-label="Previous day" onClick={() => moveDay(-1)}><ChevronLeft size={19} /></button>
          <button className="jump-today" type="button" onClick={() => setDay(today)}>Today</button>
          <button type="button" aria-label="Next day" onClick={() => moveDay(1)}><ChevronRight size={19} /></button>
        </div>
      </header>

      <div className="dashboard">
        <section className="panel agenda" aria-labelledby="agenda-heading" aria-busy={current.status === 'loading'}>
          <div className="panel-header"><h2 id="agenda-heading">Agenda</h2>{current.status === 'ready' && <span className="count">{items.length} {items.length === 1 ? 'item' : 'items'}</span>}</div>
          {current.status === 'loading' && <div className="state" role="status"><span className="spinner" aria-hidden="true" /> Loading agenda…</div>}
          {current.status === 'error' && <div className="state" role="alert">
            <AlertCircle size={25} aria-hidden="true" /><p>Couldn’t load your agenda.</p>
            <button className="retry" type="button" onClick={() => setAttempt(attempt + 1)}>Try again</button>
          </div>}
          {current.status === 'ready' && (items.length > 0
            ? <ul>{items.map(item => <AgendaRow key={`${item.source}-${item.id}`} item={item} />)}</ul>
            : <div className="state"><CalendarDays size={27} aria-hidden="true" /><p>Nothing on the agenda for this day.</p></div>)}
        </section>

        {current.status === 'ready' && <section className="panel summary" aria-labelledby="summary-heading">
          <div className="panel-header"><h2 id="summary-heading">At a glance</h2></div>
          <div className="summary-body">
            <div className="summary-row"><Check size={19} aria-hidden="true" /><span>Tasks completed</span><strong>{done} / {tasks.length}</strong></div>
            {tasks.length > 0 && <progress aria-label="Tasks completed" max={tasks.length} value={done} />}
            <div className="summary-row"><Clock3 size={19} aria-hidden="true" /><span>Scheduled items</span><strong>{scheduled}</strong></div>
          </div>
        </section>}
      </div>
  </>
}

createRoot(document.getElementById('root')!).render(<App />)

import { useEffect, useState, type FormEvent } from 'react'
import { ListTodo, Pencil, Plus, ShoppingBasket, Trash2 } from 'lucide-react'
import { request } from './http'

const priorities = ['Normal', 'High', 'Low'] as const
const repetitions = ['None', 'Daily', 'Weekly'] as const

type TaskDetails = {
  title: string
  due_date: string | null
  priority: typeof priorities[number]
  repeat: typeof repetitions[number]
}
type Task = TaskDetails & { id: number; completed: boolean }
type ListName = 'Tasks' | 'Shopping'
type Editor = { task: Task | null } | null

function TaskEditor({ task, shopping, busy, onCancel, onSave }: {
  task: Task | null
  shopping: boolean
  busy: boolean
  onCancel: () => void
  onSave: (details: Partial<TaskDetails> & { title: string }) => void
}) {
  const [repeat, setRepeat] = useState<TaskDetails['repeat']>(task?.repeat ?? 'None')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const title = String(form.get('title')).trim()
    if (shopping) onSave({ title })
    else onSave({ title, due_date: String(form.get('due_date')) || null,
      priority: form.get('priority') as TaskDetails['priority'], repeat })
  }

  return <form className="task-editor" onSubmit={submit}>
    <fieldset disabled={busy} className="editor-fields">
      <label className="title-field">{shopping ? 'Item name' : 'Task title'}
        <input name="title" defaultValue={task?.title} required autoFocus />
      </label>
      {!shopping && <div className="editor-options">
        <label>Due date<input type="date" name="due_date" defaultValue={task?.due_date ?? ''} required={repeat !== 'None'} /></label>
        <label>Priority<select name="priority" defaultValue={task?.priority ?? 'Normal'}>
          {priorities.map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label>Repeat<select value={repeat} onChange={event => setRepeat(event.target.value as TaskDetails['repeat'])}>
          {repetitions.map(value => <option key={value}>{value}</option>)}
        </select></label>
      </div>}
      <div className="editor-actions">
        <button type="submit" className="primary-button">{busy ? 'Saving…' : task ? 'Save changes' : shopping ? 'Add item' : 'Add task'}</button>
        <button type="button" className="secondary-button" onClick={onCancel}>Cancel</button>
      </div>
    </fieldset>
  </form>
}

export function TaskList({ listName, today }: { listName: ListName; today: string }) {
  const shopping = listName === 'Shopping'
  const noun = shopping ? 'item' : 'task'
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [reload, setReload] = useState(0)
  const [editor, setEditor] = useState<Editor>(null)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState('')
  const [view, setView] = useState('All tasks')
  const [priority, setPriority] = useState('Any priority')
  const [dueDate, setDueDate] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setLoadError('')
    async function load() {
      try {
        const response = await request(`/api/tasks?list_name=${listName}`, { signal: controller.signal })
        const rows: Task[] = await response.json()
        if (!controller.signal.aborted) setTasks(rows)
      } catch {
        if (!controller.signal.aborted) setLoadError(`Couldn’t load your ${shopping ? 'shopping list' : 'tasks'}.`)
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [listName, reload, shopping])

  const visible = tasks.filter(task => shopping || (
    (view !== 'Open tasks' || !task.completed) &&
    (view !== 'Due today' || task.due_date === today) &&
    (priority === 'Any priority' || task.priority === priority) &&
    (!dueDate || task.due_date === dueDate)
  ))

  async function save(path: string, method: string, message: string, payload?: object) {
    setBusy(true)
    setError('')
    setFeedback('')
    try {
      await request(path, { method, ...(payload ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {}) })
      setEditor(null)
      setDeleteId(null)
      setFeedback(message)
      setLoading(true)
      setReload(value => value + 1)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Couldn’t save your change.')
    } finally {
      setBusy(false)
    }
  }

  function showEditor(task: Task | null) {
    setEditor({ task })
    setDeleteId(null)
    setError('')
    setFeedback('')
  }

  function saveDetails(details: Partial<TaskDetails> & { title: string }) {
    const task = editor?.task
    if (task) void save(`/api/tasks/${task.id}`, 'PATCH', 'Changes saved.', details)
    else void save('/api/tasks', 'POST', shopping ? 'Item added.' : 'Task added.', { ...details, list_name: listName })
  }

  const editorForm = editor && <TaskEditor key={editor.task?.id ?? 'new'} task={editor.task} shopping={shopping}
    busy={busy} onSave={saveDetails} onCancel={() => { setEditor(null); setError('') }} />

  return <>
    <header className="page-header">
      <h1>{shopping ? 'Shopping list' : 'Tasks'}</h1>
      <button type="button" className="primary-button" disabled={busy || loading} onClick={() => showEditor(null)}>
        <Plus size={18} aria-hidden="true" /> {shopping ? 'New item' : 'New task'}
      </button>
    </header>
    {!shopping && <fieldset className="task-filters" aria-label="Task filters" disabled={editor !== null || deleteId !== null || busy}>
      <label><span id="task-view-label">View</span><select aria-labelledby="task-view-label" value={view} onChange={event => { setView(event.target.value); setDueDate('') }}>
        <option>All tasks</option><option>Open tasks</option><option>Due today</option>
      </select></label>
      <label><span id="task-priority-label">Priority</span><select aria-labelledby="task-priority-label" value={priority} onChange={event => setPriority(event.target.value)}>
        <option>Any priority</option>{priorities.map(value => <option key={value}>{value}</option>)}
      </select></label>
      <label>Due on<input type="date" value={dueDate} onChange={event => { setDueDate(event.target.value); if (view === 'Due today') setView('All tasks') }} /></label>
    </fieldset>}
    {feedback && <p className="task-feedback" role="status">{feedback}</p>}
    {error && <p className="task-error" role="alert">{error}</p>}
    <section className="panel" aria-label={shopping ? 'Shopping items' : 'Task list'} aria-busy={loading}>
      {editor && !editor.task && editorForm}
      {loading ? <div className="state" role="status"><span className="spinner" aria-hidden="true" /> Loading {shopping ? 'shopping list' : 'tasks'}…</div>
        : loadError ? <div className="state" role="alert">{loadError}<button type="button" className="retry" onClick={() => setReload(value => value + 1)}>Try again</button></div>
        : !visible.length ? <div className="state">{shopping ? <ShoppingBasket size={26} aria-hidden="true" /> : <ListTodo size={26} aria-hidden="true" />}
          <p>{tasks.length ? 'No tasks match these filters.' : `No ${noun}s yet.`}</p></div>
        : <ul>{visible.map(task => <li className="task-entry" key={task.id}>
          <div className="task-row">
            <label className="task-check">
              <input type="checkbox" checked={task.completed} disabled={busy || editor !== null || deleteId !== null}
                onChange={event => void save(`/api/tasks/${task.id}/completion`, 'PATCH',
                  event.target.checked ? 'Marked complete.' : 'Marked open.', { completed: event.target.checked })} />
              <span className={`item-title ${task.completed ? 'completed' : ''}`}>{task.title}</span>
            </label>
            {!shopping && <div className="task-meta">
              {task.priority !== 'Normal' && <span className="priority-chip">{task.priority}</span>}
              {task.due_date && <time dateTime={task.due_date}>{task.due_date}</time>}
              {task.repeat !== 'None' && <span>{task.repeat}</span>}
            </div>}
            <div className="task-actions">
              <button type="button" className="icon-button" aria-label={`Edit ${task.title}`} disabled={busy} onClick={() => showEditor(task)}><Pencil size={17} aria-hidden="true" /></button>
              <button type="button" className="icon-button" aria-label={`Delete ${task.title}`} disabled={busy} onClick={() => { setDeleteId(task.id); setEditor(null); setError(''); setFeedback('') }}><Trash2 size={17} aria-hidden="true" /></button>
            </div>
          </div>
          {editor?.task?.id === task.id && editorForm}
          {deleteId === task.id && <div className="delete-confirm">
            <span>Delete {task.title}?</span>
            <button type="button" className="danger-button" disabled={busy} onClick={() => void save(`/api/tasks/${task.id}`, 'DELETE', 'Deleted.')}>Delete</button>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => { setDeleteId(null); setError('') }}>Cancel</button>
          </div>}
        </li>)}</ul>}
    </section>
  </>
}

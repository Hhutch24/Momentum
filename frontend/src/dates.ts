export function localDay(day: Date) {
  const month = String(day.getMonth() + 1).padStart(2, '0')
  const date = String(day.getDate()).padStart(2, '0')
  return `${String(day.getFullYear()).padStart(4, '0')}-${month}-${date}`
}

export function calendarDate(day: string) {
  return new Date(`${day}T12:00:00`)
}

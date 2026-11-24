export async function request(path: string, options?: RequestInit) {
  const response = await fetch(path, options)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (typeof body?.detail === 'string') throw new Error(body.detail)
    if (response.status === 422) throw new Error('Check the form fields and try again.')
    throw new Error('Momentum could not reach the server. Try again.')
  }
  return response
}

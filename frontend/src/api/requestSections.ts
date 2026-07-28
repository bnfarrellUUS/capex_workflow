import { api } from './client'

// Which New Request wizard sections an admin has hidden. Readable by every
// signed-in user (the wizard needs it); only ADMIN may write.
export function getHiddenSections(): Promise<string[]> {
  return api<{ hidden: string[] }>('/request-sections').then((r) => r.hidden)
}

export function saveHiddenSections(hidden: string[]): Promise<string[]> {
  return api<{ hidden: string[] }>('/request-sections', { method: 'PUT', body: { hidden } })
    .then((r) => r.hidden)
}

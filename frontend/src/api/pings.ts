import { api } from './client'

/** In-app work routing. Read state is per person; DONE is shared across the
 *  roster (server-derived), so `done_by` names whoever closed it first. */

export interface PingRecipient {
  user_id: string
  name: string
  email: string
  read_at: string | null
  completed_at: string | null
}

/** Identifying summary of the request a ping is about (spec section 4.1). It
 *  renders even when the viewer cannot open the request; `visible` is what
 *  gates the deep link, or a link that 403s reads as broken software. */
export interface RequestRef {
  id: string
  number: string
  status: string
  division_name: string | null
  requestor_name: string | null
  total_cost: string | null
  visible: boolean
}

export interface PingSummary {
  id: string
  note: string
  sender: { id: string; name: string }
  created_at: string
  request_id: string | null
  request: RequestRef | null
  recipients: PingRecipient[]
  reply_count: number
  unread_replies: number
  unread_for_me: boolean
  last_activity_at: string
  completed_at: string | null
  done_by: string | null
  /** Every reply's note, concatenated -- what search reaches beyond the root
   *  note and the sender/recipient names. */
  search_blob: string
}

export interface PingDetail extends PingSummary {
  replies: {
    id: string
    note: string
    created_at: string
    sender: { id: string; name: string }
  }[]
}

export interface DirectoryUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_name: string | null
}

export interface PingCreate {
  recipient_ids: string[]
  note: string
  request_id?: string | null
}

export async function pingUnreadCount(): Promise<number> {
  const res = await api<{ count: number }>('/pings/unread_count')
  return res.count
}

export async function listPings(box: 'inbox' | 'sent'): Promise<PingSummary[]> {
  const res = await api<{ pings: PingSummary[] }>(`/pings?box=${box}`)
  return res.pings
}

export async function getPing(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}`)
  return res.ping
}

export async function createPing(body: PingCreate): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>('/pings', { method: 'POST', body })
  return res.ping
}

export async function replyToPing(id: string, note: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/reply`, {
    method: 'POST',
    body: { note },
  })
  return res.ping
}

export async function markPingDone(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/done`, { method: 'POST' })
  return res.ping
}

export async function reopenPing(id: string): Promise<PingDetail> {
  const res = await api<{ ping: PingDetail }>(`/pings/${id}/reopen`, { method: 'POST' })
  return res.ping
}

export async function pingDirectory(): Promise<DirectoryUser[]> {
  const res = await api<{ users: DirectoryUser[] }>('/pings/directory')
  return res.users
}

/** The requestor plus, when pending, the current level's eligible approvers
 *  (FINANCE once approved) -- ranked first in the New Ping modal. */
export async function pingSuggestions(requestId: string): Promise<DirectoryUser[]> {
  const res = await api<{ users: DirectoryUser[] }>(
    `/pings/suggestions?request_id=${encodeURIComponent(requestId)}`,
  )
  return res.users
}

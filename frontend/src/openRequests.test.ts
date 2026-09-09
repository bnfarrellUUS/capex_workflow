// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  MAX_OPEN_REQUESTS,
  closeOpenRequest,
  readOpenRequests,
  setOpenRequestStep,
  storageKey,
  touchOpenRequest,
} from './openRequests'

const ME = 'u1'

function tab(id: string, mode: 'view' | 'edit' = 'edit') {
  return { id, number: `CX${id}`, title: `Forklift ${id}`, mode }
}

beforeEach(() => {
  localStorage.clear()
})

describe('the open-request set', () => {
  it('is empty before anything is opened', () => {
    expect(readOpenRequests(ME)).toEqual([])
  })

  it('remembers a request that was opened', () => {
    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)).toMatchObject([
      { id: 'a', number: 'CXa', title: 'Forklift a', mode: 'edit', step: 0 },
    ])
  })

  it('does not duplicate a request that is opened twice', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)).toHaveLength(1)
  })

  it('refreshes a stale label when the request is opened again', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, { ...tab('a'), title: 'Renamed forklift' })

    expect(readOpenRequests(ME)[0].title).toBe('Renamed forklift')
  })

  it('leaves a reopened request where it sits in the strip', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))
    touchOpenRequest(ME, tab('c'))
    touchOpenRequest(ME, tab('a'))

    // Tabs that jump to the end on every click are unusable to aim at.
    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a', 'b', 'c'])
  })

  it('reopening in the other mode updates the mode and keeps the step', () => {
    touchOpenRequest(ME, tab('a', 'edit'))
    setOpenRequestStep(ME, 'a', 3)

    touchOpenRequest(ME, tab('a', 'view'))

    expect(readOpenRequests(ME)[0]).toMatchObject({ mode: 'view', step: 3 })
  })
})

describe('per-tab step memory', () => {
  it('remembers which step each request was left on', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))

    setOpenRequestStep(ME, 'a', 3)

    const byId = Object.fromEntries(readOpenRequests(ME).map((t) => [t.id, t.step]))
    expect(byId).toEqual({ a: 3, b: 0 })
  })

  it('keeps the remembered step when the request is reopened', () => {
    touchOpenRequest(ME, tab('a'))
    setOpenRequestStep(ME, 'a', 2)

    touchOpenRequest(ME, tab('a'))

    expect(readOpenRequests(ME)[0].step).toBe(2)
  })

  it('ignores a step for a request that is not open', () => {
    touchOpenRequest(ME, tab('a'))

    setOpenRequestStep(ME, 'ghost', 4)

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a'])
  })
})

describe('closing a tab', () => {
  it('removes only the request that was closed', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest(ME, tab('b'))

    closeOpenRequest(ME, 'a')

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['b'])
  })
})

describe('the cap', () => {
  it('evicts the least recently opened request past the cap', () => {
    for (let i = 0; i < MAX_OPEN_REQUESTS; i++) touchOpenRequest(ME, tab(String(i)))
    // Re-open the oldest, so it is no longer the least recently seen.
    touchOpenRequest(ME, tab('0'))

    touchOpenRequest(ME, tab('new'))

    const ids = readOpenRequests(ME).map((t) => t.id)
    expect(ids).toHaveLength(MAX_OPEN_REQUESTS)
    expect(ids).toContain('0')
    expect(ids).not.toContain('1')
  })
})

describe('storage', () => {
  it('keeps one user’s tabs out of another’s', () => {
    touchOpenRequest(ME, tab('a'))
    touchOpenRequest('u2', tab('b'))

    expect(readOpenRequests(ME).map((t) => t.id)).toEqual(['a'])
    expect(readOpenRequests('u2').map((t) => t.id)).toEqual(['b'])
  })

  it('falls back to empty when the stored value is corrupt', () => {
    localStorage.setItem(storageKey(ME), '{not json')

    expect(readOpenRequests(ME)).toEqual([])
  })

  it('falls back to empty when the stored value is not a list of tabs', () => {
    localStorage.setItem(storageKey(ME), '{"id":"a"}')

    expect(readOpenRequests(ME)).toEqual([])
  })
})

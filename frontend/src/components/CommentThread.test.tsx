// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CommentThread } from './CommentThread'
import type { CapexRequestData } from '../api/requests'

vi.mock('../api/requests', () => ({ addComment: vi.fn() }))
import { addComment } from '../api/requests'

function makeReq(comments: CapexRequestData['comments'] = []): CapexRequestData {
  return { id: 'req-1', number: 'CX000042', comments } as CapexRequestData
}

describe('CommentThread', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows an empty state when there are no comments', () => {
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)
    expect(screen.getByText('No comments yet.')).toBeInTheDocument()
  })

  it('lists existing comments with their author', () => {
    render(<CommentThread onPosted={() => {}} req={makeReq([
      { id: 'c1', body: 'Where are the bids?', author_id: 'u1',
        author_name: 'Approver', created_at: '2026-08-05T14:00:00' },
    ])} />)
    expect(screen.getByText('Where are the bids?')).toBeInTheDocument()
    expect(screen.getByText(/Approver/)).toBeInTheDocument()
  })

  it('disables the post button until something is typed', () => {
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)
    const button = screen.getByRole('button', { name: /Post comment/i })
    expect(button).toBeDisabled()
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hi' } })
    expect(button).toBeEnabled()
  })

  it('posts the comment, clears the box, and hands back the updated request', async () => {
    const updated = makeReq([{ id: 'c1', body: 'Hi', author_id: 'u1',
      author_name: 'Me', created_at: null }])
    vi.mocked(addComment).mockResolvedValue(updated)
    const onPosted = vi.fn()
    render(<CommentThread req={makeReq()} onPosted={onPosted} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hi' } })
    fireEvent.click(screen.getByRole('button', { name: /Post comment/i }))

    await waitFor(() => expect(addComment).toHaveBeenCalledWith('req-1', 'Hi'))
    await waitFor(() => expect(onPosted).toHaveBeenCalledWith(updated))
    expect(screen.getByRole('textbox')).toHaveValue('')
  })

  it('shows an error and keeps the text when the post fails', async () => {
    vi.mocked(addComment).mockRejectedValue(new Error('boom'))
    render(<CommentThread req={makeReq()} onPosted={() => {}} />)

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Keep me' } })
    fireEvent.click(screen.getByRole('button', { name: /Post comment/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('Keep me')
  })
})

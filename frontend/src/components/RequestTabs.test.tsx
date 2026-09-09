// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { RequestTabs } from './RequestTabs'
import { touchOpenRequest } from '../openRequests'

const ME = 'u1'

function open(id: string, number: string, title: string, mode: 'view' | 'edit' = 'view') {
  touchOpenRequest(ME, { id, number, title, mode })
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>
}

function renderTabs(at: string) {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <RequestTabs userId={ME} />
      <Where />
      <Routes>
        <Route path="*" element={null} />
      </Routes>
    </MemoryRouter>,
  )
}

const click = (name: RegExp | string) =>
  fireEvent.click(screen.getByRole('button', { name }))

beforeEach(() => {
  localStorage.clear()
})

describe('the request tab strip', () => {
  it('renders nothing at all when no request is open', () => {
    const { container } = renderTabs('/')

    // A first-time user must see today's app, not an empty bar.
    expect(container.querySelector('[data-testid="request-tabs"]')).toBeNull()
  })

  it('shows a tab for each open request, naming the number and the title', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')

    renderTabs('/requests/a')

    expect(screen.getByRole('button', { name: /^CX000142/ })).toHaveTextContent('Forklift')
    expect(screen.getByRole('button', { name: /^CX000151/ })).toBeInTheDocument()
  })

  it('shows the number alone when the request has no description', () => {
    open('a', 'CX000142', '')

    renderTabs('/requests/a')

    const tab = screen.getByRole('button', { name: /^CX000142/ })
    expect(tab).toHaveTextContent(/^CX000142$/)
    expect(tab).toHaveAttribute('title', 'CX000142')
  })

  it('marks the request in the address bar as the current tab', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')

    renderTabs('/requests/b')

    // Never colour alone: the marker has to be readable by assistive tech too.
    expect(screen.getByRole('button', { name: /^CX000151/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: /^CX000142/ })).not.toHaveAttribute('aria-current')
  })

  it('marks the same tab current on the edit page as on the view page', () => {
    open('a', 'CX000142', 'Forklift')

    renderTabs('/requests/a/edit')

    expect(screen.getByRole('button', { name: /^CX000142/ })).toHaveAttribute('aria-current', 'page')
  })

  it('marks no tab as current when the page is not a request', () => {
    open('a', 'CX000142', 'Forklift')

    renderTabs('/messages')

    expect(screen.getByRole('button', { name: /^CX000142/ })).not.toHaveAttribute('aria-current')
  })

  it('marks no tab as current on the new-request page', () => {
    open('new', 'CX000000', 'Not a real tab')

    renderTabs('/requests/new')

    expect(screen.getByRole('button', { name: /^CX000000/ })).not.toHaveAttribute('aria-current')
  })

  it('opens a view tab on the detail page and an edit tab in the wizard', () => {
    open('a', 'CX000142', 'Forklift', 'view')
    open('b', 'CX000151', 'Tank monitor', 'edit')
    renderTabs('/messages')

    click(/^CX000142/)
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests\/a$/)

    click(/^CX000151/)
    expect(screen.getByTestId('where')).toHaveTextContent('/requests/b/edit')
  })

  it('closes a tab without leaving the page you are on', () => {
    open('a', 'CX000142', 'Forklift')
    open('b', 'CX000151', 'Tank monitor')
    renderTabs('/requests/a')

    click(/Close CX000151/)

    expect(screen.queryByRole('button', { name: /^CX000151/ })).not.toBeInTheDocument()
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests\/a$/)
  })

  it('moves to a neighbouring request when the open one is closed', () => {
    open('a', 'CX000142', 'Forklift', 'edit')
    open('b', 'CX000151', 'Tank monitor')
    renderTabs('/requests/b')

    click(/Close CX000151/)

    // The neighbour opens in ITS remembered mode.
    expect(screen.getByTestId('where')).toHaveTextContent('/requests/a/edit')
  })

  it('falls back to the requests list when the last tab is closed', () => {
    open('a', 'CX000142', 'Forklift')
    renderTabs('/requests/a')

    click(/Close CX000142/)

    expect(screen.getByTestId('where')).toHaveTextContent(/^\/requests$/)
  })

  it('starts a new request from the trailing control', () => {
    open('a', 'CX000142', 'Forklift')
    renderTabs('/requests/a')

    click('New request')

    expect(screen.getByTestId('where')).toHaveTextContent('/requests/new')
  })
})

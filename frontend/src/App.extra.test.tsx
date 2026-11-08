import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.replaceState(null, '', '/')
})

describe('صفحه‌ی /health', () => {
  it('با پاسخ ۲۰۰ بک‌اند، پیام موفقیت را نشان می‌دهد', async () => {
    window.history.replaceState(null, '', '/health')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: 'UP', service: 's4-rsk' }),
      }),
    )

    render(<App />)

    expect(await screen.findByText(/بک‌اند در دسترس است/)).toBeInTheDocument()
    expect(screen.getByText(/"service": "s4-rsk"/)).toBeInTheDocument()
  })

  it('اگر بک‌اند خطا بدهد، پیام خطا را نشان می‌دهد', async () => {
    window.history.replaceState(null, '', '/health')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')))

    render(<App />)

    expect(await screen.findByText(/خطا: Failed to fetch/)).toBeInTheDocument()
  })

  it('آدرس ناشناخته صفحه‌ی ۴۰۴ را نشان می‌دهد', () => {
    window.history.replaceState(null, '', '/abc')

    render(<App />)

    expect(screen.getByText('۴۰۴')).toBeInTheDocument()
  })

  it('خطای Problem Details را با کد و شناسهٔ ردیابی نشان می‌دهد', async () => {
    window.history.replaceState(null, '', '/health')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        headers: new Headers({ 'content-type': 'application/problem+json' }),
        json: async () => ({
          type: 'https://errors.labbank.example/service-unavailable',
          title: 'Dependency unavailable',
          status: 503,
          code: 'SERVICE_UNAVAILABLE',
          detail: 'The database is unavailable.',
          correlation_id: 'cid-503',
        }),
      }),
    )

    render(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Dependency unavailable')
    const details = screen.getByRole('alert')
    expect(details).toHaveTextContent('SERVICE_UNAVAILABLE')
    expect(details).toHaveTextContent('The database is unavailable.')
    expect(details).toHaveTextContent('cid-503')
  })

  it('خطای HTTP عادی را بدون جزئیات Problem نشان می‌دهد', async () => {
    window.history.replaceState(null, '', '/health')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ 'content-type': 'text/html' }),
        json: async () => {
          throw new Error('not json')
        },
      }),
    )

    render(<App />)

    expect(await screen.findByText(/خطا: HTTP 500/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('کلیک روی بررسی دوباره درخواست تازه می‌فرستد', async () => {
    window.history.replaceState(null, '', '/health')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'UP', service: 's4-rsk' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)
    await screen.findByText(/بک‌اند در دسترس است/)
    fireEvent.click(screen.getByRole('button', { name: 'بررسی دوباره' }))

    await screen.findByText(/بک‌اند در دسترس است/)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})

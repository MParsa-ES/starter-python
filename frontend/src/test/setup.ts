import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// بدون globals، پاک‌سازی DOM بعد از هر تست باید دستی انجام شود.
afterEach(() => cleanup())

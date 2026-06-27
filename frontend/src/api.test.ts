import { describe, expect, test } from 'vitest'

import { resolveApiBaseUrl } from './api'


describe('resolveApiBaseUrl', () => {
  test('uses same-origin relative requests when no API base URL is configured', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('')
    expect(resolveApiBaseUrl('')).toBe('')
    expect(resolveApiBaseUrl('   ')).toBe('')
  })

  test('keeps an explicitly configured API base URL for local development', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })
})

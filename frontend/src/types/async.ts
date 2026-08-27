export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error'

export interface AsyncState<T> {
  status: AsyncStatus
  data: T | null
  error: string | null
}

export function initAsyncState<T>(): AsyncState<T> {
  return { status: 'idle', data: null, error: null }
}

// What the koala button and its bubble say. Pure, so the wording and the rules about what must
// stay visible are tested without a browser.

export const MINIMIZED_KEY = 'firebreak.koala-minimized.v1'

const STATUS_TEXT = {
  idle: 'Talk to me',
  connecting: 'Connecting…',
  listening: 'Listening…',
  checking: 'Checking…',
  closing: 'Ending voice…',
  error: '',
}

export const isLive = (status) => status === 'listening' || status === 'checking'
export const isBusy = (status) => status === 'connecting' || status === 'closing'

export const labelFor = (status) => (isLive(status) ? 'Stop voice' : 'Talk to the assistant')

// An error or the figures notice wins; then the lack of microphone support; then the status.
export function bubbleFor({ supported, status, error, notice }) {
  if (error) return { text: error, role: 'alert' }
  if (notice) return { text: notice, role: 'alert' }
  if (!supported) return { text: "Voice isn't available in this browser.", role: 'status' }
  return { text: STATUS_TEXT[status] ?? '', role: 'status' }
}

// The koala may be hidden only when there is nothing that must be seen or stopped: voice is
// off and there is no error or notice. Otherwise it stays (or comes back) open.
export const forcesOpen = ({ status, error, notice }) =>
  status !== 'idle' || Boolean(error) || Boolean(notice)

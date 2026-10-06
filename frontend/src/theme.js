// The app ships a single light appearance. The attribute is still set so the
// stylesheet's [data-theme] hooks resolve, and any value saved by an earlier
// version (which offered a dark switch) is ignored rather than honoured, so
// nobody is left in a theme they can no longer change.
export function initializeTheme(root = globalThis.document?.documentElement) {
  if (root) root.dataset.theme = 'light'
  return 'light'
}

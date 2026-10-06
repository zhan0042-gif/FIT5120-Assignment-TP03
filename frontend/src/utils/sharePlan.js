// Sharing the plan PDF goes through the device's own share sheet, so the file
// travels straight from this browser to the app the person picks (WhatsApp,
// Messenger, Zalo, email...). Nothing is uploaded to FIREBREAK or any other
// service, and the message never contains names or addresses.
export const SHARE_TITLE = 'My bushfire preparedness plan'
export const SHARE_TEXT = 'My household bushfire preparedness plan, made with FIREBREAK.'

export function pdfFile(blob, filename) {
  return new File([blob], filename, { type: 'application/pdf' })
}

export function canShareFile(nav, file) {
  return typeof nav?.share === 'function'
    && typeof nav.canShare === 'function'
    && nav.canShare({ files: [file] })
}

// Resolves to 'shared', 'cancelled' (the person closed the sheet),
// 'needs-gesture' (the browser wants a fresh tap, which happens when the PDF
// took a while to build) or 'unsupported'. Anything else is a real failure.
export async function shareFile(nav, file) {
  if (!canShareFile(nav, file)) return 'unsupported'
  try {
    await nav.share({ files: [file], title: SHARE_TITLE, text: SHARE_TEXT })
    return 'shared'
  } catch (error) {
    if (error?.name === 'AbortError') return 'cancelled'
    if (error?.name === 'NotAllowedError') return 'needs-gesture'
    throw error
  }
}

// WhatsApp can only be given text through a link, never a file.
export function whatsappWebUrl(text = SHARE_TEXT) {
  return `https://wa.me/?text=${encodeURIComponent(text)}`
}

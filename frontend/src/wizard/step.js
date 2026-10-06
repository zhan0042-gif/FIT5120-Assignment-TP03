// Every step has the same shape; this fills the defaults so section builders
// only state what is particular to a question.
export function question(section, key, kind, prompt, extra = {}) {
  return { section, key, kind, prompt, helper: null, optional: true, ...extra }
}

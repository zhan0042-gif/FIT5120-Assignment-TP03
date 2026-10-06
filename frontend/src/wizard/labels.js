// How a person is named inside a question ("Where is Sam ...") and in a list.
export function memberLabel(plan, index) {
  if (index === 0) return 'you'
  return plan.members[index]?.display_name?.trim() || 'this person'
}

export function memberTitle(plan, index) {
  return plan.members[index]?.display_name?.trim() || `Person ${index + 1}`
}

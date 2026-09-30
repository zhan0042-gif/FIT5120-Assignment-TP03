export async function saveAndReview({ needsSave, save, navigate }) {
  if (needsSave && !(await save())) return false
  await navigate('/overview')
  return true
}

// After the assistant speaks, compare the digits in what it said with the digits in
// what the app asked it to say. This detects a changed or invented figure; it cannot
// prevent one, because the sentence has already been spoken when it runs, and it only
// sees digits (a number spoken as a word is not compared).

const NUMBER = /\d[\d,]*(?:\.\d+)?/g

function normalise(token) {
  const plain = token.replaceAll(',', '')
  const value = Number(plain)
  return Number.isFinite(value) ? String(value) : plain
}

export function numbersIn(text) {
  const found = new Set()
  for (const match of String(text ?? '').matchAll(NUMBER)) {
    found.add(normalise(match[0]))
  }
  return found
}

// Numbers in `spoken` that appear in none of the texts the app sent.
export function unexpectedNumbers(sentTexts, spoken) {
  const allowed = new Set()
  for (const text of sentTexts) {
    for (const number of numbersIn(text)) allowed.add(number)
  }
  return [...numbersIn(spoken)].filter((number) => !allowed.has(number))
}

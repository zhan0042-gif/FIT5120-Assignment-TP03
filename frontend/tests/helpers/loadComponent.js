import { readFile } from 'node:fs/promises'
import { compileScript, parse } from '@vue/compiler-sfc'

// Compile a real single-file component without a browser, resolving its relative
// imports (including other .vue files) to data: URLs. Same approach as the
// other component tests.
// Paths are relative to the tests/ directory, like the test files that call this.
export async function loadComponent(path, base = new URL('../', import.meta.url)) {
  const url = new URL(path, base)
  const { descriptor } = parse(await readFile(url, 'utf8'))
  let code = compileScript(descriptor, { id: url.href, inlineTemplate: true }).content
  code = code.replace(/^import ['"][^'"]+['"]\s*$/gm, '')
  for (const match of [...code.matchAll(/from ['"]([^'"]+)['"]/g)]) {
    const name = match[1]
    let resolved
    if (name.endsWith('.vue')) {
      resolved = await loadComponent(new URL(name, url).href, url)
    } else {
      resolved = name.startsWith('.')
        ? new URL(name.endsWith('.js') ? name : `${name}.js`, url).href
        : import.meta.resolve(name)
    }
    code = code.replace(match[0], `from '${resolved}'`)
  }
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}`
}

export async function importComponent(path) {
  return (await import(await loadComponent(path))).default
}

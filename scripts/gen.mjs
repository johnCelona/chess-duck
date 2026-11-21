// Regenerates the contract files and the TypeScript client types (ADR-0002).
//   npm run gen            write contracts/*.json and apps/web/src/api/generated/schema.d.ts
//   node scripts/gen.mjs --check   fail if any of them is out of date (used by CI)
import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const check = process.argv.includes('--check')
const generated = join(root, 'apps/web/src/api/generated/schema.d.ts')
const generator = join(root, 'contracts/node_modules/openapi-typescript/bin/cli.js')

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: process.platform === 'win32' && command !== process.execPath,
  })
  if (result.status !== 0) process.exit(result.status ?? 1)
}

// 1. The backend writes (or verifies) the OpenAPI document and the event schema.
run('uv', [
  'run', '--project', 'backend', 'duckgambit', 'export-contracts', '--out', 'contracts',
  ...(check ? ['--check'] : []),
]) // prettier-ignore

// 2. TypeScript types are generated from the committed OpenAPI document. Never edit them.
if (!existsSync(generator)) {
  console.error('openapi-typescript is not installed. Run `npm install` first.')
  process.exit(1)
}
if (!check) {
  run(process.execPath, [generator, 'contracts/openapi.json', '-o', generated])
} else {
  const scratch = mkdtempSync(join(tmpdir(), 'dg-gen-'))
  const fresh = join(scratch, 'schema.d.ts')
  run(process.execPath, [generator, 'contracts/openapi.json', '-o', fresh])
  const same =
    existsSync(generated) && readFileSync(generated, 'utf8') === readFileSync(fresh, 'utf8')
  rmSync(scratch, { recursive: true, force: true })
  if (!same) {
    console.error('The generated TypeScript client is out of date. Run `npm run gen`.')
    process.exit(1)
  }
  console.log('Generated TypeScript client is up to date.')
}

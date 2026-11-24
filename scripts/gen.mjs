// Regenerates the contract files and the TypeScript client types (ADR-0002).
//   npm run gen                    write contracts/*.json and the generated TypeScript types
//   node scripts/gen.mjs --check   fail if any of them is out of date (used by CI)
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const check = process.argv.includes('--check')
const generated = join(root, 'apps/web/src/api/generated/schema.d.ts')
const generator = join(root, 'contracts/node_modules/openapi-typescript/bin/cli.js')
// Fields with a default stay optional, so request bodies can omit them.
const OPTIONS = ['--default-non-nullable', 'false']

function finish(result) {
  if (result.status !== 0) process.exit(result.status ?? 1)
}

function generate(target) {
  finish(
    spawnSync(process.execPath, [generator, 'contracts/openapi.json', ...OPTIONS, '-o', target], {
      cwd: root,
      stdio: 'inherit',
    }),
  )
}

// 1. The backend writes (or verifies) the OpenAPI document and the event schema.
const exportCommand = `uv run --project backend duckgambit export-contracts --out contracts${check ? ' --check' : ''}`
finish(spawnSync(exportCommand, { cwd: root, stdio: 'inherit', shell: true }))

// 2. TypeScript types are generated from the committed OpenAPI document. Never edit them.
if (!existsSync(generator)) {
  console.error('openapi-typescript is not installed. Run `npm install` first.')
  process.exit(1)
}
if (!check) {
  generate(generated)
} else {
  const scratch = mkdtempSync(join(tmpdir(), 'dg-gen-'))
  const fresh = join(scratch, 'schema.d.ts')
  generate(fresh)
  const same =
    existsSync(generated) && readFileSync(generated, 'utf8') === readFileSync(fresh, 'utf8')
  rmSync(scratch, { recursive: true, force: true })
  if (!same) {
    console.error('The generated TypeScript client is out of date. Run `npm run gen`.')
    process.exit(1)
  }
  console.log('Generated TypeScript client is up to date.')
}

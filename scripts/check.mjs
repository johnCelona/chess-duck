// Runs every gate CI runs, in order, and stops at the first failure (ADR-0012).
// Usage: npm run check
import { spawnSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const uv = ['run', '--project', 'backend']

const steps = [
  ['backend lint', 'uv', [...uv, 'ruff', 'check', 'backend']],
  ['backend format', 'uv', [...uv, 'ruff', 'format', '--check', 'backend']],
  ['backend types', 'uv', [...uv, 'mypy', '--config-file', 'backend/pyproject.toml']],
  ['backend tests', 'uv', [...uv, 'pytest', 'backend/tests']],
  ['contracts up to date', 'node', ['scripts/gen.mjs', '--check']],
  ['web lint', 'npm', ['run', 'lint', '-w', 'apps/web']],
  ['web format', 'npm', ['run', 'format:check', '-w', 'apps/web']],
  ['web tests', 'npm', ['run', 'test', '-w', 'apps/web']],
  ['web build', 'npm', ['run', 'build', '-w', 'apps/web']],
]

const only = process.argv.slice(2)
for (const [name, command, args] of steps) {
  if (only.length > 0 && !only.some((word) => name.includes(word))) continue
  console.log(`\n\x1b[1m▶ ${name}\x1b[0m`)
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  })
  if (result.status !== 0) {
    console.error(`\n\x1b[31m✖ ${name} failed\x1b[0m`)
    process.exit(result.status ?? 1)
  }
}
console.log('\n\x1b[32m✔ all checks passed\x1b[0m')

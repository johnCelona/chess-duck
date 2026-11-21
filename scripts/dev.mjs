// One command for local development: backend and web together (ADR-0014).
// Usage: npm run dev
import { spawn } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const windows = process.platform === 'win32'

const env = {
  ...process.env,
  DG_ENV: process.env.DG_ENV ?? 'dev',
  DG_DATA_DIR: process.env.DG_DATA_DIR ?? resolve(root, 'data'),
  PYTHONUNBUFFERED: '1',
}

const services = [
  {
    name: 'backend',
    colour: '\x1b[36m',
    command: 'uv run --project backend duckgambit serve --reload',
    hint: 'Is uv installed? https://docs.astral.sh/uv/getting-started/installation/',
  },
  { name: 'web', colour: '\x1b[35m', command: 'npm run dev -w apps/web', hint: 'Run npm install.' },
]

const children = []
let stopping = false

function stop(code) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    if (child.exitCode !== null) continue
    if (windows) {
      // Kill the whole tree: uvicorn's reloader and npm both start grandchildren.
      spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
    } else {
      child.kill('SIGTERM')
    }
  }
  setTimeout(() => process.exit(code), 500)
}

function prefix(name, colour, stream, target) {
  let pending = ''
  stream.on('data', (chunk) => {
    pending += chunk.toString()
    const lines = pending.split(/\r?\n/)
    pending = lines.pop() ?? ''
    for (const line of lines) target.write(`${colour}[${name}]\x1b[0m ${line}\n`)
  })
}

for (const service of services) {
  const child = spawn(service.command, { cwd: root, env, shell: true })
  children.push(child)
  prefix(service.name, service.colour, child.stdout, process.stdout)
  prefix(service.name, service.colour, child.stderr, process.stderr)
  child.on('error', (error) => {
    console.error(`[${service.name}] could not start: ${error.message}. ${service.hint}`)
    stop(1)
  })
  child.on('exit', (code) => {
    if (!stopping) console.error(`[${service.name}] exited with code ${code}. ${service.hint}`)
    stop(code ?? 1)
  })
}

process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))

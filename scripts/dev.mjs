// One command for local development: backend and web together (ADR-0014).
// Usage: npm run dev
//
// The backend is restarted here when a backend file changes, rather than by uvicorn's
// reloader: on Windows uvicorn stops its worker with a Ctrl+C event, which only works
// when the server is attached to a console window, so the old code could keep running.
import { spawn } from 'node:child_process'
import { watch } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const windows = process.platform === 'win32'
const backendSource = resolve(root, 'backend', 'src')

const env = {
  ...process.env,
  DG_ENV: process.env.DG_ENV ?? 'dev',
  DG_DATA_DIR: process.env.DG_DATA_DIR ?? resolve(root, 'data'),
  PYTHONUNBUFFERED: '1',
}

const services = {
  backend: {
    colour: '\x1b[36m',
    command: 'uv run --project backend duckgambit serve',
    hint: 'Is uv installed? https://docs.astral.sh/uv/getting-started/installation/',
  },
  web: { colour: '\x1b[35m', command: 'npm run dev -w apps/web', hint: 'Run npm install.' },
}

const running = new Map() // name -> child process
const restarting = new Set()
let stopping = false

function prefix(name, colour, stream, target) {
  let pending = ''
  stream.on('data', (chunk) => {
    pending += chunk.toString()
    const lines = pending.split(/\r?\n/)
    pending = lines.pop() ?? ''
    for (const line of lines) target.write(`${colour}[${name}]\x1b[0m ${line}\n`)
  })
}

/** Kill a child and everything it started (uv → python → engine processes). */
function killTree(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  if (windows) {
    spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
  } else {
    try {
      process.kill(-child.pid, 'SIGTERM') // the whole process group (spawned detached)
    } catch {
      child.kill('SIGTERM')
    }
  }
}

function start(name) {
  const service = services[name]
  const child = spawn(service.command, { cwd: root, env, shell: true, detached: !windows })
  running.set(name, child)
  prefix(name, service.colour, child.stdout, process.stdout)
  prefix(name, service.colour, child.stderr, process.stderr)
  child.on('error', (error) => {
    console.error(`[${name}] could not start: ${error.message}. ${service.hint}`)
    stop(1)
  })
  child.on('exit', (code) => {
    if (restarting.has(name)) {
      restarting.delete(name)
      start(name)
      return
    }
    if (!stopping) console.error(`[${name}] exited with code ${code}. ${service.hint}`)
    stop(code ?? 1)
  })
}

function restart(name, reason) {
  const child = running.get(name)
  if (!child || restarting.has(name) || stopping) return
  console.log(`${services[name].colour}[${name}]\x1b[0m ${reason}, restarting…`)
  restarting.add(name)
  killTree(child)
}

function stop(code) {
  if (stopping) return
  stopping = true
  for (const child of running.values()) killTree(child)
  setTimeout(() => process.exit(code), 500)
}

// Restart the backend shortly after Python files under backend/src stop changing.
let timer = null
let changed = ''
watch(backendSource, { recursive: true }, (_event, file) => {
  if (!file || !String(file).endsWith('.py') || String(file).includes('__pycache__')) return
  changed = String(file)
  clearTimeout(timer)
  timer = setTimeout(() => restart('backend', `${changed} changed`), 300)
})

start('backend')
start('web')

process.on('SIGINT', () => stop(0))
process.on('SIGTERM', () => stop(0))

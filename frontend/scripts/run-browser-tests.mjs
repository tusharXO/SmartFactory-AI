import { spawnSync } from 'node:child_process'
import { realpathSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Windows can spell the same checkout GitHub or Github. Keep one module identity
// for Playwright regardless of how VS Code opened the directory.
const frontend = realpathSync.native(fileURLToPath(new URL('../', import.meta.url)))
const cli = path.join(frontend, 'node_modules', '@playwright', 'test', 'cli.js')
const result = spawnSync(process.execPath, [cli, 'test', ...process.argv.slice(2)], {
  cwd: frontend,
  stdio: 'inherit',
  windowsHide: true,
})
if (result.error) console.error(result.error.message)
process.exit(result.status ?? 1)

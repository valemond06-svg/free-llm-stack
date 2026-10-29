// Always-on PC (Windows / macOS / Linux) without Docker.
//   npm install -g pm2 antigravity-claude-proxy@2.9.1
//   pm2 start deploy/pm2/ecosystem.config.cjs && pm2 save
//   pm2 startup            (macOS/Linux: prints the command that enables boot start)
//   Windows boot start:    use deploy/windows/install-autostart.ps1 instead of `pm2 startup`
// FreeLLMAPI itself runs as the desktop app (it has its own "start at login" toggle).
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..');
const env = {};
const envFile = path.join(root, '.env');
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, 'utf8').split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) env[m[1]] = m[2];
  }
}

module.exports = {
  apps: [
    {
      name: 'antigravity-proxy',
      // The CLI's `start --log` just runs this file; pm2 supervises it directly.
      script: path.join(require('node:child_process').execSync('npm root -g').toString().trim(), 'antigravity-claude-proxy', 'src', 'index.js'),
      env: { HOST: '127.0.0.1', PORT: '8080', API_KEY: env.ANTIGRAVITY_PROXY_API_KEY || '', WEBUI_PASSWORD: env.ANTIGRAVITY_WEBUI_PASSWORD || '' },
      autorestart: true,
    },
    {
      name: 'antigravity-bridge',
      script: path.join(root, 'bridge', 'server.js'),
      env: {
        BRIDGE_HOST: '127.0.0.1',
        BRIDGE_PORT: '3005',
        UPSTREAM_URL: 'http://127.0.0.1:8080',
        UPSTREAM_API_KEY: env.ANTIGRAVITY_PROXY_API_KEY || '',
        BRIDGE_API_KEY: env.BRIDGE_API_KEY || '',
      },
      autorestart: true,
    },
  ],
};

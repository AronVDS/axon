const express = require('express');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 3000;
const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'axon2026';
const WAITLIST_FILE = path.join(__dirname, 'data', 'waitlist.json');

fs.mkdirSync(path.join(__dirname, 'data'), { recursive: true });
if (!fs.existsSync(WAITLIST_FILE)) fs.writeFileSync(WAITLIST_FILE, '[]', 'utf8');

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public'), { extensions: ['html'] }));

function readWaitlist() {
  try {
    return JSON.parse(fs.readFileSync(WAITLIST_FILE, 'utf8'));
  } catch {
    return [];
  }
}

function writeWaitlist(data) {
  fs.writeFileSync(WAITLIST_FILE, JSON.stringify(data, null, 2), 'utf8');
}

function basicAuth(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Basic ')) {
    res.set('WWW-Authenticate', 'Basic realm="Axon Admin"');
    return res.status(401).send('Authentication required');
  }
  const [user, pass] = Buffer.from(header.slice(6), 'base64').toString().split(':');
  if (user !== ADMIN_USER || pass !== ADMIN_PASSWORD) {
    res.set('WWW-Authenticate', 'Basic realm="Axon Admin"');
    return res.status(401).send('Invalid credentials');
  }
  next();
}

// POST /api/waitlist — save a signup
app.post('/api/waitlist', (req, res) => {
  const { name, email } = req.body;

  if (!name || typeof name !== 'string' || name.trim().length < 2) {
    return res.status(400).json({ error: 'Geldige naam vereist' });
  }
  if (!email || typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: 'Geldig e-mailadres vereist' });
  }

  const list = readWaitlist();
  const normalizedEmail = email.trim().toLowerCase();

  if (list.some(entry => entry.email.toLowerCase() === normalizedEmail)) {
    return res.status(409).json({ error: 'E-mailadres staat al op de wachtlijst' });
  }

  list.push({
    id: Date.now(),
    name: name.trim(),
    email: normalizedEmail,
    signedUpAt: new Date().toISOString(),
  });

  writeWaitlist(list);
  res.status(201).json({ success: true, message: 'Inschrijving gelukt' });
});

// POST /api/orchestrate — run a Dutch task through the Python orchestrator
app.post('/api/orchestrate', (req, res) => {
  const { task } = req.body;
  if (!task || typeof task !== 'string' || !task.trim()) {
    return res.status(400).json({ error: 'Taak vereist' });
  }

  const TIMEOUT_MS = 120_000; // 2 min — LLM + agent calls can be slow
  const scriptPath = path.join(__dirname, 'AI-Agents', 'run_task.py');
  const agentsDir  = path.join(__dirname, 'AI-Agents');

  const py = spawn('python', [scriptPath], {
    cwd: agentsDir,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' },
  });

  let stdout = '';
  let stderr = '';
  let done = false;

  const finish = (status, payload) => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    py.kill('SIGTERM');
    res.status(status).json(payload);
  };

  const timer = setTimeout(
    () => finish(504, { error: 'Time-out: de taak duurde te lang (max 120s).' }),
    TIMEOUT_MS,
  );

  py.stdout.on('data', d => { stdout += d.toString('utf8'); });
  py.stderr.on('data', d => { stderr += d.toString('utf8'); });

  py.stdin.write(task.trim(), 'utf8');
  py.stdin.end();

  py.on('close', code => {
    if (done) return;
    if (code !== 0) {
      const errMsg = stderr.trim() || `Python afsluitcode ${code}`;
      return finish(500, { error: errMsg });
    }
    finish(200, { result: stdout.trim() });
  });

  py.on('error', err => {
    finish(500, { error: `Kon Python niet starten: ${err.message}` });
  });
});

// GET /admin — password-protected admin UI
app.get('/admin', basicAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

// GET /api/admin/signups — returns JSON of all signups
app.get('/api/admin/signups', basicAuth, (req, res) => {
  res.json(readWaitlist());
});

// DELETE /api/admin/signups/:id — remove a signup
app.delete('/api/admin/signups/:id', basicAuth, (req, res) => {
  const id = parseInt(req.params.id, 10);
  const list = readWaitlist();
  const filtered = list.filter(entry => entry.id !== id);
  if (filtered.length === list.length) {
    return res.status(404).json({ error: 'Niet gevonden' });
  }
  writeWaitlist(filtered);
  res.json({ success: true });
});

app.listen(PORT, () => {
  console.log(`\nAxon server draait op http://localhost:${PORT}`);
  console.log(`Admin paneel:   http://localhost:${PORT}/admin`);
  console.log(`Admin login:    ${ADMIN_USER} / ${ADMIN_PASSWORD}`);
  console.log('\nStel ADMIN_PASSWORD in als omgevingsvariabele voor productie.\n');
});

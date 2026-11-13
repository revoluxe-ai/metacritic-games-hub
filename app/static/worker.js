const runBtn = document.getElementById('run-now');
const runStatus = document.getElementById('run-status');
const jobJson = document.getElementById('job-json');
const jobSummary = document.getElementById('job-summary');
const logList = document.getElementById('log-list');

function formatTimestamp(value) {
  if (!value) return '—';
  const raw = String(value);
  const iso = /Z$|[+-]\d\d:\d\d$/.test(raw) ? raw : `${raw}Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function renderJob(job) {
  if (jobJson) {
    jobJson.textContent = job ? JSON.stringify(job, null, 2) : '';
  }
  if (!jobSummary) return;
  if (!job) {
    jobSummary.classList.add('muted');
    jobSummary.textContent = 'Waiting for events…';
    return;
  }
  const status = job.status || 'unknown';
  jobSummary.classList.remove('muted');
  jobSummary.innerHTML = `
    <div class="job-grid">
      <div class="job-field">
        <span class="label">Status</span>
        <span class="value"><span class="status-pill status-${escapeHtml(status)}">${escapeHtml(status)}</span></span>
      </div>
      <div class="job-field">
        <span class="label">Trigger</span>
        <span class="value">${escapeHtml(job.trigger || '—')}</span>
      </div>
      <div class="job-field">
        <span class="label">Started</span>
        <span class="value">${escapeHtml(formatTimestamp(job.started_at))}</span>
      </div>
      <div class="job-field">
        <span class="label">Finished</span>
        <span class="value">${escapeHtml(formatTimestamp(job.finished_at))}</span>
      </div>
      <div class="job-field">
        <span class="label">Games</span>
        <span class="value">${escapeHtml(job.games_processed ?? 0)} / ${escapeHtml(job.games_requested ?? 0)}</span>
      </div>
      <div class="job-field">
        <span class="label">Message</span>
        <span class="value">${escapeHtml(job.message || '—')}</span>
      </div>
    </div>
  `;
}

runBtn.addEventListener('click', async () => {
  runBtn.disabled = true;
  runStatus.textContent = 'Starting job…';
  try {
    const res = await fetch('/api/worker/run-now', { method: 'POST' });
    const data = await res.json();
    runStatus.textContent = data.message || (data.ok ? 'Started' : 'Failed');
  } catch (e) {
    runStatus.textContent = String(e);
  } finally {
    setTimeout(() => {
      runBtn.disabled = false;
    }, 3000);
  }
});

const es = new EventSource('/api/worker/events');
es.onmessage = (ev) => {
  const payload = JSON.parse(ev.data);
  renderJob(payload.job);
  logList.innerHTML = '';
  for (const line of payload.logs || []) {
    const li = document.createElement('li');
    li.className = line.level || 'info';
    const ts = document.createElement('span');
    ts.className = 'ts';
    ts.textContent = formatTimestamp(line.created_at);
    const msg = document.createElement('span');
    msg.className = 'msg';
    msg.textContent = line.message || '';
    li.append(ts, msg);
    logList.appendChild(li);
  }
  logList.scrollTop = logList.scrollHeight;
};
es.onerror = () => {
  runStatus.textContent = 'SSE disconnected — retrying…';
};

const runBtn = document.getElementById('run-now');
const runStatus = document.getElementById('run-status');
const jobJson = document.getElementById('job-json');
const logList = document.getElementById('log-list');

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
  jobJson.textContent = JSON.stringify(payload.job, null, 2);
  logList.innerHTML = '';
  for (const line of payload.logs || []) {
    const li = document.createElement('li');
    li.className = line.level;
    li.textContent = `[${line.created_at}] ${line.message}`;
    logList.appendChild(li);
  }
  logList.scrollTop = logList.scrollHeight;
};
es.onerror = () => {
  runStatus.textContent = 'SSE disconnected — retrying…';
};

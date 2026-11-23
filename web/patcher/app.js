'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const form = $('patch-form'), inputs = ['japanese','american','bios'].map($);
  const run = $('run'), cancel = $('cancel'), status = $('status'), meter = $('progress');
  let worker, urls = [];
  const STEP23_ESTIMATE = 17 * 60 * 1000, LOG_LIMIT = 250;
  let started = null, ended = null, step23Started = null, lastUpdate = null, timer, lastLog = '';
  function duration(ms, round = Math.floor) {
    const seconds = Math.max(0, round(ms / 1000)), minutes = Math.floor(seconds / 60);
    return minutes >= 60
      ? `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
      : `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
  }
  function tick() {
    if (started === null) return;
    const now = ended ?? Date.now();
    $('elapsed').textContent = duration(now - started);
    if (lastUpdate !== null) $('last-update').textContent = duration(now - lastUpdate) + ' ago';
    if (step23Started !== null) {
      const remaining = STEP23_ESTIMATE - (now - step23Started);
      $('step23-remaining').textContent = remaining > 0 ? '~' + duration(remaining, Math.ceil) : 'Estimate exceeded';
      $('step23-elapsed').textContent = duration(now - step23Started);
    }
  }
  function resetActivity() {
    clearInterval(timer); timer = undefined;
    started = ended = step23Started = lastUpdate = null; lastLog = '';
    $('activity').hidden = true; $('step23-clock').hidden = true;
    $('activity-log').replaceChildren(); $('elapsed').textContent = '00:00';
  }
  function startActivity() {
    resetActivity(); started = Date.now(); $('activity').hidden = false;
    $('activity-state').textContent = 'Running'; tick(); timer = setInterval(tick, 1000);
  }
  function logActivity(text) {
    if (started === null || text === lastLog) return;
    const now = ended ?? Date.now(), log = $('activity-log');
    const follow = log.scrollHeight - log.clientHeight - log.scrollTop < 40;
    const entry = document.createElement('li'), stamp = document.createElement('time'), label = document.createElement('span');
    stamp.textContent = duration(now - started); label.textContent = text;
    entry.append(stamp, label); log.append(entry);
    while (log.children.length > LOG_LIMIT) log.firstElementChild.remove();
    if (follow) log.scrollTop = log.scrollHeight;
    lastLog = text; lastUpdate = now;
    if (/^Converting 23 of \d+: background_tables\.py\b/.test(text)) {
      if (step23Started === null) step23Started = now;
      $('step23-clock').hidden = ended !== null;
    } else $('step23-clock').hidden = true;
    tick();
  }
  function clear() {
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    $('downloads').replaceChildren(); $('results').hidden = true;
    meter.value = 0;
  }
  function busy(value) {
    inputs.forEach(input=>{input.disabled=value;});
    run.disabled = value || inputs.some(input=>!input.files.length);
    cancel.hidden = !value;
    form.setAttribute('aria-busy', String(value));
  }
  function message(text, error = false) { status.textContent = text; status.dataset.error = String(error); logActivity(text); }
  function stop(state = 'Stopped') {
    worker?.terminate(); worker = undefined; busy(false);
    if (started !== null) { ended = Date.now(); tick(); $('activity-state').textContent = state; }
    clearInterval(timer); timer = undefined; $('step23-clock').hidden = true;
  }
  for (const input of inputs) input.addEventListener('change', () => {
    clear(); resetActivity(); busy(false); message('Choose your files, then select Verify and patch.');
  });
  cancel.addEventListener('click', () => { stop('Cancelled'); clear(); message('Cancelled. Your original files were not changed.'); run.focus(); });
  form.addEventListener('submit', event => {
    event.preventDefault(); if (worker || run.disabled) return;
    clear(); startActivity(); busy(true); message('Starting local verification.');
    try { worker = new Worker('worker.js'); }
    catch { stop('Error'); message('This browser cannot start the patch worker. Open the site from localhost in a current desktop browser.', true); return; }
    const activeWorker = worker;
    worker.onerror = () => { if (worker !== activeWorker) return; stop('Error'); clear(); message('The patch worker stopped. Close unused tabs and try again in a current desktop browser.', true); };
    worker.onmessage = event => {
      if (worker !== activeWorker) return;
      const data = event.data;
      if (data.kind === 'progress') { message(data.message); meter.value = data.value; }
      else if (data.kind === 'timing') console.info('[patcher-timing] ' + JSON.stringify(data.row));
      else if (data.kind === 'error') { stop('Error'); clear(); message(data.message, true); }
      else if (data.kind === 'result') {
        const {bin, cue, receipt} = data.result;
        for (const [name, blob] of [[SONIC_RELEASE.binName, bin], [SONIC_RELEASE.cueName, cue],
          ['sonic-cd-saturn-v0082-receipt.json', new Blob([JSON.stringify(receipt, null, 2) + '\n'], {type: 'application/json'})]]) {
          const link = document.createElement('a'), url = URL.createObjectURL(blob);
          urls.push(url); link.href = url; link.download = name; link.textContent = `Save ${name}`;
          $('downloads').append(link);
        }
        stop('Complete'); meter.value = 100; $('results').hidden = false;
        message('Verified. Save the BIN and CUE together. Keep the receipt for your console test.');
        $('results').focus();
      }
    };
    const files=inputs.flatMap((input,index)=>Array.from(input.files,file=>({role:['jp','us','bios'][index],file})));
    worker.postMessage({files});
  });
  if (!window.Worker || !window.crypto?.subtle) message('Open this site from localhost in a current desktop browser. Web Workers and secure-context hashing are required.', true);
  busy(false);
})();

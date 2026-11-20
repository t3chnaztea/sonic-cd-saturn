'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const form = $('patch-form'), bundle = $('bundle'), files = $('originals');
  const run = $('run'), cancel = $('cancel'), status = $('status'), meter = $('progress');
  let worker, urls = [];
  function clear() {
    urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
    $('downloads').replaceChildren(); $('results').hidden = true;
    meter.value = 0;
  }
  function busy(value) {
    bundle.disabled = files.disabled = value;
    run.disabled = value || !bundle.files.length || !files.files.length;
    cancel.hidden = !value;
    form.setAttribute('aria-busy', String(value));
  }
  function message(text, error = false) { status.textContent = text; status.dataset.error = String(error); }
  function stop() { worker?.terminate(); worker = undefined; busy(false); }
  for (const input of [bundle, files]) input.addEventListener('change', () => {
    clear(); busy(false); message('Choose your files, then select Verify and patch.');
  });
  cancel.addEventListener('click', () => { stop(); clear(); message('Cancelled. Your original files were not changed.'); run.focus(); });
  form.addEventListener('submit', event => {
    event.preventDefault(); if (worker || run.disabled) return;
    clear(); busy(true); message('Starting local verification.');
    try { worker = new Worker('worker.js'); }
    catch { stop(); message('This browser cannot start the patch worker. Open the site from localhost in a current desktop browser.', true); return; }
    worker.onerror = () => { stop(); clear(); message('The patch worker stopped. Close unused tabs and try again in a current desktop browser.', true); };
    worker.onmessage = event => {
      const data = event.data;
      if (data.kind === 'progress') { message(data.message); meter.value = data.value; }
      else if (data.kind === 'error') { stop(); clear(); message(data.message, true); }
      else if (data.kind === 'result') {
        const {bin, cue, receipt} = data.result;
        for (const [name, blob] of [[SONIC_RELEASE.binName, bin], [SONIC_RELEASE.cueName, cue],
          ['sonic-cd-saturn-v0082-receipt.json', new Blob([JSON.stringify(receipt, null, 2) + '\n'], {type: 'application/json'})]]) {
          const link = document.createElement('a'), url = URL.createObjectURL(blob);
          urls.push(url); link.href = url; link.download = name; link.textContent = `Save ${name}`;
          $('downloads').append(link);
        }
        stop(); meter.value = 100; $('results').hidden = false;
        message('Verified. Save the BIN and CUE together. Keep the receipt for your console test.');
        $('results').focus();
      }
    };
    worker.postMessage({bundle: bundle.files[0], files: Array.from(files.files)});
  });
  if (!window.Worker || !window.crypto?.subtle) message('Open this site from localhost in a current desktop browser. Web Workers and secure-context hashing are required.', true);
  busy(false);
})();

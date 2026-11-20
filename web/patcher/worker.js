'use strict';
importScripts('release.js', 'engine.js');
onmessage = async event => {
  try {
    const result = await SonicPatch.apply(event.data.bundle, event.data.files, SONIC_RELEASE,
      (message, value) => postMessage({kind: 'progress', message, value}));
    postMessage({kind: 'result', result});
  } catch (error) { postMessage({kind: 'error', message: error.message || 'The patch could not be completed.'}); }
};

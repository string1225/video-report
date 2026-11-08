// All motion is a pure function of the narration clock, including offline export.
const motionEnabled = report.motion?.enabled === true;
const clamp01 = value => Math.max(0, Math.min(1, value));
const ease = value => 1 - Math.pow(1 - clamp01(value), 3);
const originalShowScene = window.showScene;
const originalRenderAt = window.renderAt;
const progressTrack = document.createElement('div');
progressTrack.id = 'progress-track';
progressTrack.innerHTML = '<div id="progress-fill"></div>';
stage.append(progressTrack);
if (!motionEnabled) progressTrack.hidden = true;

function createMediaPanel(config, startMs = 0) {
  const asset = (report.media || []).find(item => item.id === config.id);
  if (!asset) throw new Error(`Missing media: ${config.id}`);
  const figure = document.createElement('figure');
  figure.className = 'media-panel fit-check';
  figure.dataset.mediaId = asset.id;
  figure.dataset.startMs = startMs;
  const fit = config.fit === 'cover' ? 'cover' : 'contain';
  const label = config.caption || asset.usage_caption || asset.title;
  const media = asset.type === 'video'
    ? `<video class="source-media" data-start-ms="${startMs}" data-loop="${config.loop === true}" src="${esc(asset.path)}" muted playsinline preload="auto" aria-label="${esc(asset.title)}"></video>`
    : `<img class="source-media" src="${esc(asset.path)}" alt="${esc(asset.title)}">`;
  figure.innerHTML = `<div class="media-window ${fit}">${media}</div><figcaption>${esc(label)}</figcaption><div class="media-credit">${esc(asset.credit || `${asset.creator} · ${asset.license}`)}</div>`;
  const video = figure.querySelector('video');
  if (video) video.addEventListener('loadeddata', () => {
    if (!exportMode && video.isConnected) window.renderAt(audio.currentTime * 1000);
  }, {once: true});
  return figure;
}

window.showScene = function(index) {
  for (const video of content.querySelectorAll('video')) video.pause();
  originalShowScene(index);
  const scene = report.scenes[window.currentScene];
  if (scene.media) {
    const body = document.createElement('div');
    body.className = 'media-body';
    const copy = document.createElement('div');
    copy.className = 'body-copy';
    for (const child of [...content.children]) {
      if (!child.matches('.kicker,.slide-title,.subtitle')) copy.append(child);
    }
    const figure = createMediaPanel(scene.media);
    body.append(copy, figure);
    content.append(body);
    content.classList.add('has-media');
  } else content.classList.remove('has-media');
  let group = 0;
  for (const element of content.querySelectorAll('.card,.format,.bar-row,.decision-row,.bullets li,.quote-block,.footline')) {
    element.dataset.revealGroup = group++;
  }
};

function sceneTiming() {
  return timeline[window.currentScene] || {start_ms: 0, end_ms: 5000};
}

function mediaTarget(video, localMs) {
  const length = Number.isFinite(video.duration) ? video.duration : 0;
  const elapsed = Math.max(0, (localMs - Number(video.dataset.startMs || 0)) / 1000);
  return video.dataset.loop === 'true' && length > 0 ? elapsed % length : Math.min(elapsed, Math.max(0, length - 1 / (report.fps || 30)));
}

function animateAt(ms) {
  const timing = sceneTiming(), localMs = ms - timing.start_ms;
  const scene = report.scenes[window.currentScene];
  const cues = captions.filter(cue => cue.start_ms >= timing.start_ms && cue.start_ms < timing.end_ms);
  if (scene.media?.switches) {
    let active = scene.media, activeStart = 0;
    for (const candidate of scene.media.switches) {
      if (!cues[candidate.cue]) throw new Error(`Invalid media switch cue ${candidate.cue} in ${scene.id}`);
      const start = cues[candidate.cue].start_ms + (candidate.offset_ms || 0);
      if (ms >= start && start - timing.start_ms >= activeStart) {
        active = candidate;
        activeStart = start - timing.start_ms;
      }
    }
    const current = content.querySelector('.media-panel');
    if (current.dataset.mediaId !== active.id || Number(current.dataset.startMs) !== activeStart) {
      current.querySelector('video')?.pause();
      current.replaceWith(createMediaPanel(active, activeStart));
    }
  }
  if (motionEnabled) {
    for (const element of content.querySelectorAll('.kicker,.slide-title,.subtitle,.big-callout,.media-panel,.note')) {
      const amount = ease((localMs - 80) / 480);
      element.style.opacity = amount;
      element.style.transform = `translateY(${(1 - amount) * 14}px)`;
    }
    const groups = [...content.querySelectorAll('[data-reveal-group]')];
    for (const element of groups) {
      const group = Number(element.dataset.revealGroup);
      const cueIndex = scene.reveal_cues?.[group];
      if (cueIndex !== undefined && !cues[cueIndex]) throw new Error(`Invalid reveal cue ${cueIndex} in ${scene.id}`);
      const delay = cueIndex !== undefined ? cues[cueIndex].start_ms - timing.start_ms
        : 300 + group * Math.min(1300, (timing.end_ms - timing.start_ms) * 0.5 / Math.max(1, groups.length));
      const amount = ease((localMs - delay) / 440);
      element.style.opacity = amount;
      element.style.transform = `translateY(${(1 - amount) * 22}px)`;
      const bar = element.querySelector('.bar-fill');
      if (bar) bar.style.transform = `scaleX(${ease((localMs - delay) / 950)})`;
    }
    document.querySelector('#progress-fill').style.transform = `scaleX(${clamp01(ms / (timeline.at(-1)?.end_ms || 5000))})`;
    // Source-page crops remain still so small research text stays legible.
    for (const image of content.querySelectorAll('.cover img')) {
      image.style.transform = `scale(${1 + 0.028 * clamp01(localMs / (timing.end_ms - timing.start_ms))})`;
    }
  }
  return localMs;
}

window.renderAt = function(ms) {
  originalRenderAt(ms);
  const localMs = animateAt(ms);
  if (!exportMode) {
    for (const video of content.querySelectorAll('video')) {
      const target = mediaTarget(video, localMs);
      if (video.readyState >= 2 && Math.abs(video.currentTime - target) > 0.18) video.currentTime = target;
      const atEnd = video.dataset.loop !== 'true' && video.currentTime >= video.duration - 0.05;
      if (audio.paused || atEnd) video.pause();
      else if (video.paused) video.play().catch(error => { window.mediaPlaybackError = String(error); });
    }
  }
};

function waitForMedia(video, event) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => done(new Error(`Video ${event} timed out: ${video.src}`)), 12000);
    const finish = () => done();
    const fail = () => done(new Error(`Cannot decode video: ${video.src}`));
    function done(error) {
      clearTimeout(timeout);
      video.removeEventListener(event, finish);
      video.removeEventListener('error', fail);
      error ? reject(error) : resolve();
    }
    video.addEventListener(event, finish, {once: true});
    video.addEventListener('error', fail, {once: true});
    if (video.error) fail();
  });
}

window.prepareMedia = async function() {
  await document.fonts.ready;
  await Promise.all([...content.querySelectorAll('img')].map(image => image.decode()));
  await Promise.all([...content.querySelectorAll('video')].map(video => video.readyState >= 2 ? null : waitForMedia(video, 'loadeddata')));
};

window.renderFrame = async function(ms) {
  window.renderAt(ms);
  await window.prepareMedia();
  const localMs = ms - sceneTiming().start_ms;
  for (const video of content.querySelectorAll('video')) {
    video.pause();
    const target = mediaTarget(video, localMs);
    if (Math.abs(video.currentTime - target) > 0.00001) {
      const ready = waitForMedia(video, 'seeked');
      video.currentTime = target;
      await ready;
    }
  }
  await new Promise(resolve => requestAnimationFrame(resolve));
  return {scene: window.currentScene, local_ms: localMs,
    video_times: [...content.querySelectorAll('video')].map(video => video.currentTime)};
};

// Navigation remains useful when the narration is paused.
audio.addEventListener('pause', () => content.querySelectorAll('video').forEach(video => video.pause()));
audio.addEventListener('seeked', () => window.renderAt(audio.currentTime * 1000));
window.showScene(0);

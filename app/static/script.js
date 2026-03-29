// Frontend logic for SnapWords.AI
const PROMPT_TEMPLATES = {
  template_1: '请按词典词条提取英文单词词头，只保留词条行中的主单词。忽略序号、音标、词性、中文释义、白底区域中的英文例句、词组、辨析和其他无关内容。输出去重后的结果，每行一个。',
  template_2: '请按词典词条提取中文释义，只保留词条行中的中文释义，如果同一词条的中文释义有多个，可以一起跟上。忽略序号、音标、词性、白底区域中的英文例句、词组、辨析和其他无关内容。输出去重后的结果，每行一个。',
  custom: ''
};

const promptTemplateRadios = Array.from(document.querySelectorAll('input[name="promptTemplate"]'));
const promptTextInput = document.getElementById('promptText');
const promptHint = document.getElementById('promptHint');
const speakTextInput = document.getElementById('speakText');
const speakIntervalInput = document.getElementById('speakInterval');
const pauseSpeakBtn = document.getElementById('pauseSpeakBtn');
const resumeSpeakBtn = document.getElementById('resumeSpeakBtn');
const playbackProgress = document.getElementById('playbackProgress');
const playbackProgressFill = document.getElementById('playbackProgressFill');
const playbackProgressLabel = document.getElementById('playbackProgressLabel');
const playbackProgressCount = document.getElementById('playbackProgressCount');

let playbackToken = 0;
let playbackPaused = false;
let playbackRunning = false;
let audioContext = null;
let currentAudioBuffer = null;
let currentSourceNode = null;
let currentPlaybackStartedAt = 0;
let currentPlaybackOffset = 0;
let currentPlaybackCompletion = null;

function uiAlert(message) {
  if (window.weui && typeof window.weui.alert === 'function') {
    window.weui.alert(message);
    return;
  }
  window.alert(message);
}

function uiTopTips(message) {
  if (window.weui && typeof window.weui.topTips === 'function') {
    window.weui.topTips(message, 2000);
    return;
  }
  console.error(message);
}

async function uploadImage() {
  const fileInput = document.getElementById('imageInput');
  const status = document.getElementById('uploadStatus');
  const promptTemplate = getSelectedPromptTemplate();
  const promptText = promptTextInput?.value.trim() || '';
  if (!fileInput.files.length) {
    uiAlert('请先选择一张图片');
    return;
  }
  status.style.display = 'block';
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('prompt_template', promptTemplate);
  formData.append('prompt_text', promptText);
  try {
    const resp = await fetch('/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!data.success) {
      uiAlert('处理失败：' + data.error);
      return;
    }
    updateSpeakTextarea(data.data.items || data.data.words || []);
  } catch (e) {
    uiAlert('上传失败：' + e.message);
  } finally {
    status.style.display = 'none';
  }
}

async function speakText() {
  const status = document.getElementById('speakStatus');
  const statusTips = status?.querySelector('.weui-loadmore__tips');
  const lines = getSpeakLines();
  if (!lines.length) {
    uiAlert('请输入要朗读的内容，每行一条');
    return;
  }
  playbackToken += 1;
  const token = playbackToken;
  playbackPaused = false;
  playbackRunning = true;
  updatePlaybackButtons();
  status.style.display = 'block';
  await ensureAudioContext();
  if (statusTips) {
    statusTips.textContent = '语音合成中...';
  }
  playbackProgress.style.display = 'block';
  try {
    await playLinesSequentially(lines, token);
  } catch (e) {
    uiAlert('朗读失败：' + e.message);
  } finally {
    cleanupPlayback(token);
    status.style.display = 'none';
  }
}

document.getElementById('uploadBtn').addEventListener('click', uploadImage);
document.getElementById('speakBtn').addEventListener('click', speakText);
pauseSpeakBtn.addEventListener('click', pausePlayback);
resumeSpeakBtn.addEventListener('click', resumePlayback);

// Uploader preview logic
const imageInput = document.getElementById('imageInput');
const uploaderFiles = document.getElementById('uploaderFiles');
const uploaderInfo = document.getElementById('uploaderInfo');
if (imageInput) {
  imageInput.addEventListener('change', () => {
    uploaderFiles.innerHTML = '';
    const files = imageInput.files;
    if (!files || !files.length) {
      uploaderInfo.textContent = '0';
      return;
    }
    uploaderInfo.textContent = String(files.length);
    Array.from(files).forEach(f => {
      const li = document.createElement('li');
      li.className = 'weui-uploader__file';
      const url = URL.createObjectURL(f);
      li.style.backgroundImage = `url(${url})`;
      uploaderFiles.appendChild(li);
    });
  });
}

async function playLinesSequentially(lines, token) {
  const gapSeconds = getSpeakIntervalSeconds();
  updatePlaybackProgress(0, lines.length, '准备开始');
  for (let i = 0; i < lines.length; i += 1) {
    if (token !== playbackToken) {
      return;
    }
    await waitWhilePaused(token);
    const line = lines[i];
    if (!line) {
      updatePlaybackProgress(i + 1, lines.length, '跳过空行');
      continue;
    }
    try {
      updatePlaybackProgress(i, lines.length, `正在合成：${line}`);
      const resp = await fetch('/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: line })
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        uiTopTips('朗读失败：' + (j.error || resp.status));
        continue;
      }
      const audioBytes = await resp.arrayBuffer();
      currentAudioBuffer = await decodeAudioBuffer(audioBytes);
      currentPlaybackOffset = 0;
      updatePlaybackProgress(i, lines.length, `正在朗读：${line}`);
      await playCurrentAudio(token);
      if (token !== playbackToken) {
        return;
      }
      updatePlaybackProgress(i + 1, lines.length, `已完成：${line}`);
      if (i < lines.length - 1) {
        await waitGapWithPause(gapSeconds, token, lines.length, i + 1);
      }
    } catch (e) {
      uiTopTips('处理失败：' + e.message);
    }
  }
  updatePlaybackProgress(lines.length, lines.length, '朗读完成');
}

function syncPromptTemplate() {
  if (!promptTemplateRadios.length || !promptTextInput || !promptHint) {
    return;
  }
  const selected = getSelectedPromptTemplate();
  if (selected === 'custom') {
    if (!promptTextInput.value.trim()) {
      promptTextInput.value = '';
    }
    promptHint.textContent = '自定义提示词会直接参与提取；如果未配置模型服务，后端无法执行自定义提示词。';
    return;
  }
  promptTextInput.value = PROMPT_TEMPLATES[selected] || '';
  promptHint.textContent = selected === 'template_1'
    ? '模板 1 会按词条行提取英文词头，尽量排除白底例句中的英文。'
    : '模板 2 会按词条行提取中文释义，同一词条的多个释义会尽量合并到一行。';
}

function updateSpeakTextarea(items) {
  if (!speakTextInput) {
    return;
  }
  speakTextInput.value = items.join('\n');
}

function getSpeakLines() {
  return splitLines(speakTextInput?.value || '');
}

function splitLines(text) {
  return text
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean);
}

function getSelectedPromptTemplate() {
  const selected = promptTemplateRadios.find(radio => radio.checked);
  return selected ? selected.value : 'template_2';
}

function getSpeakIntervalSeconds() {
  let gap = parseFloat(speakIntervalInput?.value || '3');
  if (Number.isNaN(gap) || gap < 0) {
    gap = 3;
  }
  return gap;
}

function updatePlaybackProgress(completed, total, label) {
  if (!playbackProgress || !playbackProgressFill || !playbackProgressLabel || !playbackProgressCount) {
    return;
  }
  const ratio = total > 0 ? Math.min(completed / total, 1) : 0;
  playbackProgress.style.display = 'block';
  playbackProgressFill.style.width = `${ratio * 100}%`;
  playbackProgressLabel.textContent = label;
  playbackProgressCount.textContent = `${completed} / ${total}`;
}

function pausePlayback() {
  if (!playbackRunning || playbackPaused) {
    return;
  }
  playbackPaused = true;
  pauseCurrentAudio();
  updatePlaybackButtons();
  if (playbackProgressLabel) {
    playbackProgressLabel.textContent = '已暂停';
  }
}

function resumePlayback() {
  if (!playbackRunning || !playbackPaused) {
    return;
  }
  playbackPaused = false;
  resumeCurrentAudio();
  updatePlaybackButtons();
}

function updatePlaybackButtons() {
  if (pauseSpeakBtn) {
    pauseSpeakBtn.disabled = !playbackRunning || playbackPaused;
  }
  if (resumeSpeakBtn) {
    resumeSpeakBtn.disabled = !playbackRunning || !playbackPaused;
  }
}

function cleanupPlayback(token) {
  if (token !== playbackToken) {
    return;
  }
  playbackRunning = false;
  playbackPaused = false;
  resetAudioPlayer();
  updatePlaybackButtons();
}

async function playCurrentAudio(token) {
  if (!currentAudioBuffer) {
    throw new Error('音频尚未准备好');
  }
  startCurrentAudioBuffer(token, currentPlaybackOffset);
  if (currentPlaybackCompletion) {
    await currentPlaybackCompletion;
  }
}

function startCurrentAudioBuffer(token, offsetSeconds) {
  if (!audioContext || !currentAudioBuffer) {
    throw new Error('音频上下文不可用');
  }
  stopCurrentSource();
  currentPlaybackStartedAt = audioContext.currentTime - offsetSeconds;
  currentPlaybackCompletion = new Promise((resolve, reject) => {
    const source = audioContext.createBufferSource();
    source.buffer = currentAudioBuffer;
    source.connect(audioContext.destination);
    source.onended = () => {
      if (source !== currentSourceNode) {
        return;
      }
      currentSourceNode = null;
      if (playbackPaused || token !== playbackToken) {
        resolve();
        return;
      }
      currentPlaybackOffset = 0;
      resolve();
    };
    currentSourceNode = source;
    try {
      source.start(0, offsetSeconds);
    } catch (error) {
      currentSourceNode = null;
      reject(new Error('播放音频时发生错误'));
    }
  });
}

async function waitWhilePaused(token) {
  while (token === playbackToken && playbackPaused) {
    await sleep(120);
  }
}

async function waitGapWithPause(gapSeconds, token, total, completed) {
  let remainingMs = Math.round(gapSeconds * 1000);
  while (remainingMs > 0 && token === playbackToken) {
    await waitWhilePaused(token);
    if (token !== playbackToken) {
      return;
    }
    const slice = Math.min(120, remainingMs);
    updatePlaybackProgress(completed, total, `等待下一行：${(remainingMs / 1000).toFixed(1)} 秒`);
    await sleep(slice);
    remainingMs -= slice;
  }
}

function resetAudioPlayer() {
  stopCurrentSource();
  currentAudioBuffer = null;
  currentPlaybackOffset = 0;
  currentPlaybackCompletion = null;
}

function sleep(ms) {
  return new Promise(resolve => {
    window.setTimeout(resolve, ms);
  });
}

async function ensureAudioContext() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      throw new Error('当前浏览器不支持 Web Audio');
    }
    audioContext = new AudioContextClass();
  }
  if (audioContext.state === 'suspended') {
    await audioContext.resume();
  }
}

function decodeAudioBuffer(arrayBuffer) {
  if (!audioContext) {
    throw new Error('音频上下文不可用');
  }
  return new Promise((resolve, reject) => {
    audioContext.decodeAudioData(
      arrayBuffer.slice(0),
      decoded => resolve(decoded),
      () => reject(new Error('音频解码失败'))
    );
  });
}

function pauseCurrentAudio() {
  if (!audioContext || !currentSourceNode || !currentAudioBuffer) {
    return;
  }
  currentPlaybackOffset = Math.min(audioContext.currentTime - currentPlaybackStartedAt, currentAudioBuffer.duration);
  stopCurrentSource();
}

function resumeCurrentAudio() {
  if (!audioContext || !currentAudioBuffer || !playbackRunning) {
    return;
  }
  startCurrentAudioBuffer(playbackToken, currentPlaybackOffset);
}

function stopCurrentSource() {
  if (!currentSourceNode) {
    return;
  }
  const source = currentSourceNode;
  currentSourceNode = null;
  source.onended = null;
  try {
    source.stop();
  } catch {
    // Ignore stop race if the source already ended.
  }
}

if (promptTemplateRadios.length) {
  promptTemplateRadios.forEach(radio => {
    radio.addEventListener('change', syncPromptTemplate);
  });
  syncPromptTemplate();
}

window.addEventListener('beforeunload', () => {
  resetAudioPlayer();
});

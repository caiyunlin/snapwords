// Frontend logic for SnapWords.AI
async function uploadImage() {
  const fileInput = document.getElementById('imageInput');
  const status = document.getElementById('uploadStatus');
  const wordsDiv = document.getElementById('words');
  const wordsCard = document.getElementById('wordsCard');
  if (!fileInput.files.length) {
    weui.alert('Select an image first');
    return;
  }
  status.style.display = 'block';
  wordsDiv.style.display = 'none';
  wordsCard.style.display = 'none';
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  try {
    const resp = await fetch('/upload', { method: 'POST', body: formData });
    const data = await resp.json();
    if (!data.success) {
      weui.alert('Error: ' + data.error);
      return;
    }
  currentWords = [...data.data.words];
  renderEditableWords();
    wordsCard.style.display = 'block';
    wordsDiv.style.display = 'block';
  } catch (e) {
    weui.alert('Upload failed: ' + e.message);
  } finally {
    status.style.display = 'none';
  }
}

async function speakText() {
  const text = document.getElementById('speakText').value.trim();
  const status = document.getElementById('speakStatus');
  const audioTitle = document.getElementById('audioTitle');
  const audioCell = document.getElementById('audioCell');
  const player = document.getElementById('audioPlayer');
  if (!text) {
    weui.alert('Enter text to speak');
    return;
  }
  status.style.display = 'block';
  audioTitle.style.display = 'none';
  audioCell.style.display = 'none';
  try {
    const resp = await fetch('/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (!resp.ok) {
      const j = await resp.json();
      weui.alert('Error: ' + j.error);
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    player.src = url;
    player.play();
    audioTitle.style.display = 'block';
    audioCell.style.display = 'block';
  } catch (e) {
    weui.alert('Speak failed: ' + e.message);
  } finally {
    status.style.display = 'none';
  }
}

document.getElementById('uploadBtn').addEventListener('click', uploadImage);
document.getElementById('speakBtn').addEventListener('click', speakText);
// Buttons that may be added dynamically
document.addEventListener('click', (e) => {
  if (e.target && e.target.matches('.word-delete')) {
    const idx = parseInt(e.target.getAttribute('data-index'));
    if (!isNaN(idx)) {
      currentWords.splice(idx, 1);
      renderEditableWords();
    }
  }
  if (e.target && e.target.id === 'copyWordsBtn') {
    navigator.clipboard.writeText(currentWords.join('\n')).then(() => {
      weui.toast('Copied', { duration: 1500 });
    });
  }
  if (e.target && e.target.id === 'speakAllBtn') {
    speakAllWords();
  }
});

let currentWords = [];

function renderEditableWords() {
  const wordsDiv = document.getElementById('words');
  if (!currentWords.length) {
    wordsDiv.innerHTML = '<div class="weui-cell"><div class="weui-cell__bd">No words detected</div></div>';
    return;
  }
  const rows = currentWords.map((w, i) => {
    return `<div class="weui-cell word-row">
      <div class="weui-cell__bd"><input type="text" class="weui-input word-edit" data-index="${i}" value="${w}" /></div>
      <div class="weui-cell__ft"><button class="weui-btn weui-btn_mini weui-btn_warn word-delete" data-index="${i}">Delete</button></div>
    </div>`;
  }).join('');
  const actions = `<div class="weui-btn-area" style="margin-top:12px;">
     <button id="copyWordsBtn" class="weui-btn weui-btn_default">Copy All</button>
     <div style="margin-top:12px;" class="weui-cells weui-cells_form">
       <div class="weui-cell">
         <div class="weui-cell__bd">
           <input type="number" id="speakInterval" class="weui-input" min="0.5" step="0.5" value="1.5" placeholder="Interval (seconds)" />
         </div>
       </div>
     </div>
     <button id="speakAllBtn" class="weui-btn weui-btn_primary" style="margin-top:8px;">Speak All Words</button>
  </div>`;
  wordsDiv.innerHTML = rows + actions;
  // Attach input change listeners
  wordsDiv.querySelectorAll('.word-edit').forEach(inp => {
    inp.addEventListener('input', (ev) => {
      const idx = parseInt(ev.target.getAttribute('data-index'));
      if (!isNaN(idx)) {
        currentWords[idx] = ev.target.value.trim();
      }
    });
  });
}

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

async function speakAllWords() {
  if (!currentWords.length) {
    weui.alert('No words');
    return;
  }
  const intervalInput = document.getElementById('speakInterval');
  let gap = parseFloat(intervalInput?.value || '1.5');
  if (isNaN(gap) || gap < 0) gap = 1.5;
  const player = document.getElementById('audioPlayer');
  const audioTitle = document.getElementById('audioTitle');
  const audioCell = document.getElementById('audioCell');
  audioTitle.style.display = 'block';
  audioCell.style.display = 'block';
  for (let i = 0; i < currentWords.length; i++) {
    const w = currentWords[i];
    if (!w) continue;
    try {
      const resp = await fetch('/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: w })
      });
      if (!resp.ok) {
        const j = await resp.json().catch(() => ({}));
        weui.topTips('Speak failed: ' + (j.error || resp.status), 2000);
        continue;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      player.src = url;
      await player.play().catch(() => {});
      // 等待音频播放结束或固定间隔，以先到者为准
      await waitForPlaybackOrTimeout(player, gap);
    } catch (e) {
      weui.topTips('Error: ' + e.message, 2000);
    }
  }
}
// Wait for audio playback end or timeout, whichever happens first

function waitForPlaybackOrTimeout(player, gapSeconds) {
  return new Promise(resolve => {
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    player.addEventListener('ended', finish, { once: true });
    setTimeout(finish, gapSeconds * 1000);
  });
}

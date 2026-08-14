// AEGIS LOCAL VAULT FRONTEND CONTROLLER

let state = {
  initialized: false,
  unlocked: false,
  items: [],
  selectedCategory: 'All',
  selectedFiles: [],
  activeItem: null,
  categoryCounts: { All: 0, Favorites: 0, Documents: 0, Notes: 0, Passwords: 0, Personal: 0 }
};

// INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
  checkVaultStatus();
  generatePassword();
  initGlobalDragAndDrop();
  initKeyboardShortcuts();
});

// GLOBAL DRAG & DROP FOR EASE OF USE
function initGlobalDragAndDrop() {
  const overlay = document.getElementById('globalDropOverlay');
  let dragCounter = 0;

  window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    if (!state.unlocked) return;
    dragCounter++;
    overlay.classList.remove('hidden');
  });

  window.addEventListener('dragover', (e) => {
    e.preventDefault();
    if (!state.unlocked) return;
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    if (!state.unlocked) return;
    dragCounter--;
    if (dragCounter <= 0) {
      dragCounter = 0;
      overlay.classList.add('hidden');
    }
  });

  window.addEventListener('drop', (e) => {
    e.preventDefault();
    dragCounter = 0;
    overlay.classList.add('hidden');
    if (!state.unlocked) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      openUploadModalWithFiles(files);
    }
  });
}

// KEYBOARD SHORTCUTS
function initKeyboardShortcuts() {
  window.addEventListener('keydown', (e) => {
    // Ctrl+F / Cmd+F -> Focus Search
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      if (state.unlocked) {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.focus();
      }
    }
    // Ctrl+L / Cmd+L -> Lock Vault
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'l') {
      if (state.unlocked) {
        e.preventDefault();
        lockVault();
      }
    }
    // Ctrl+N / Cmd+N -> New Note
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
      if (state.unlocked) {
        e.preventDefault();
        openNoteModal();
      }
    }
    // Ctrl+U / Cmd+U -> Upload File
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
      if (state.unlocked) {
        e.preventDefault();
        openUploadModal();
      }
    }
    // Escape -> Close Modals
    else if (e.key === 'Escape') {
      closeAllModals();
    }
  });
}

// API REQUEST HELPER
async function apiRequest(endpoint, method = 'GET', data = null) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (data) {
    options.body = JSON.stringify(data);
  }
  try {
    const response = await fetch(endpoint, options);
    const resData = await response.json();
    if (!response.ok) {
      throw new Error(resData.error || `HTTP error ${response.status}`);
    }
    return resData;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

// CHECK VAULT STATUS
async function checkVaultStatus() {
  try {
    const res = await apiRequest('/api/status');
    state.initialized = res.initialized;
    state.unlocked = res.unlocked;

    updateUIState();
    if (state.unlocked) {
      loadItems();
    }
  } catch (err) {
    showToast('Server connection failed', 'error');
  }
}

// UPDATE UI STATE BASED ON AUTH
function updateUIState() {
  const authSection = document.getElementById('authSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const setupView = document.getElementById('setupView');
  const unlockView = document.getElementById('unlockView');
  const badge = document.getElementById('vaultStatusBadge');
  const statusText = document.getElementById('statusText');
  const btnLock = document.getElementById('btnLock');
  const btnSettings = document.getElementById('btnSettings');
  const btnHotkeys = document.getElementById('btnHotkeys');

  if (!state.initialized) {
    // Show Setup Screen
    authSection.classList.remove('hidden');
    dashboardSection.classList.add('hidden');
    setupView.classList.remove('hidden');
    unlockView.classList.add('hidden');
    badge.className = 'status-badge status-locked';
    statusText.innerText = 'Not Initialized';
    btnLock.classList.add('hidden');
    btnSettings.classList.add('hidden');
    btnHotkeys.classList.add('hidden');
  } else if (!state.unlocked) {
    // Show Unlock Screen
    authSection.classList.remove('hidden');
    dashboardSection.classList.add('hidden');
    setupView.classList.add('hidden');
    unlockView.classList.remove('hidden');
    badge.className = 'status-badge status-locked';
    statusText.innerText = 'Locked';
    btnLock.classList.add('hidden');
    btnSettings.classList.add('hidden');
    btnHotkeys.classList.add('hidden');
  } else {
    // Show Dashboard
    authSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    badge.className = 'status-badge status-unlocked';
    statusText.innerText = 'Unlocked (RAM Active)';
    btnLock.classList.remove('hidden');
    btnSettings.classList.remove('hidden');
    btnHotkeys.classList.remove('hidden');
  }
}

// HANDLE INIT VAULT
async function handleInitVault(e) {
  e.preventDefault();
  const pwd = document.getElementById('initPassword').value;
  const confirmPwd = document.getElementById('confirmPassword').value;

  if (pwd !== confirmPwd) {
    showToast('Passwords do not match!', 'error');
    return;
  }
  if (pwd.length < 6) {
    showToast('Password must be at least 6 characters long.', 'error');
    return;
  }

  try {
    await apiRequest('/api/init', 'POST', { password: pwd });
    showToast('Vault created & unlocked successfully!', 'success');
    state.initialized = true;
    state.unlocked = true;
    updateUIState();
    loadItems();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// HANDLE UNLOCK VAULT
async function handleUnlockVault(e) {
  e.preventDefault();
  const pwd = document.getElementById('unlockPassword').value;
  const errDiv = document.getElementById('unlockError');
  errDiv.classList.add('hidden');

  try {
    await apiRequest('/api/unlock', 'POST', { password: pwd });
    showToast('Vault unlocked!', 'success');
    document.getElementById('unlockPassword').value = '';
    state.unlocked = true;
    updateUIState();
    loadItems();
  } catch (err) {
    errDiv.innerText = err.message || 'Incorrect master password';
    errDiv.classList.remove('hidden');
  }
}

// LOCK VAULT
async function lockVault() {
  try {
    await apiRequest('/api/lock', 'POST');
    state.unlocked = false;
    updateUIState();
    showToast('Vault locked & keys cleared from RAM', 'success');
  } catch (err) {
    showToast('Error locking vault', 'error');
  }
}

// LOAD ITEMS
async function loadItems() {
  try {
    const res = await apiRequest('/api/items');
    state.items = res.items || [];
    if (res.counts) {
      state.categoryCounts = res.counts;
      updateCategoryCountsUI();
    }
    renderItems();
    updateStats();
  } catch (err) {
    showToast('Error loading items', 'error');
  }
}

// UPDATE CATEGORY COUNTS IN CHIPS
function updateCategoryCountsUI() {
  const counts = state.categoryCounts;
  document.getElementById('cntAll').innerText = counts.All || 0;
  document.getElementById('cntFav').innerText = counts.Favorites || 0;
  document.getElementById('cntDoc').innerText = counts.Documents || 0;
  document.getElementById('cntNote').innerText = counts.Notes || 0;
  document.getElementById('cntPass').innerText = counts.Passwords || 0;
  document.getElementById('cntPers').innerText = counts.Personal || 0;
}

// RENDER ITEMS GRID WITH SORT & FILTERS
function renderItems() {
  const container = document.getElementById('itemsContainer');
  const emptyState = document.getElementById('emptyState');
  const search = document.getElementById('searchInput').value.toLowerCase().trim();
  const sort = document.getElementById('sortSelect').value;

  let filtered = state.items.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(search) || (item.notes && item.notes.toLowerCase().includes(search));
    let matchesCat = true;
    if (state.selectedCategory === 'Favorites') {
      matchesCat = item.favorite === true;
    } else if (state.selectedCategory !== 'All') {
      matchesCat = item.category === state.selectedCategory;
    }
    return matchesSearch && matchesCat;
  });

  // Sorting
  filtered.sort((a, b) => {
    if (sort === 'newest') return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    if (sort === 'oldest') return new Date(a.created_at || 0) - new Date(b.created_at || 0);
    if (sort === 'name') return a.name.localeCompare(b.name);
    if (sort === 'size') return (b.size || 0) - (a.size || 0);
    return 0;
  });

  if (filtered.length === 0) {
    container.innerHTML = '';
    emptyState.classList.remove('hidden');
    return;
  }

  emptyState.classList.add('hidden');
  container.innerHTML = filtered.map(item => {
    const icon = getItemIcon(item.type, item.mime_type, item.category);
    const dateStr = formatDate(item.created_at);
    const sizeStr = formatBytes(item.size);
    const favClass = item.favorite ? 'active' : '';

    return `
      <div class="item-card glass-card ${item.favorite ? 'is-favorite' : ''}" onclick="viewItem('${item.id}')">
        <div class="item-header">
          <div class="item-type-icon">${icon}</div>
          <div class="item-title-box">
            <div class="item-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
            <div class="item-meta">
              <span class="item-badge">${escapeHtml(item.category)}</span>
              <span>• ${dateStr}</span>
            </div>
          </div>
          <button class="btn-fav-star ${favClass}" onclick="toggleCardFavorite(event, '${item.id}')" title="Toggle Favorite">⭐</button>
        </div>
        ${item.notes ? `<div class="item-snippet" title="${escapeHtml(item.notes)}">${escapeHtml(item.notes)}</div>` : ''}
        <div class="item-footer">
          <span class="item-size">${sizeStr}</span>
          <div class="card-quick-actions">
            ${item.type === 'note' ? `<button class="btn-card-action" onclick="quickCopyNote(event, '${item.id}')" title="Copy Secret Content">📋 Copy</button>` : ''}
            <button class="btn-card-action" onclick="quickDownloadItem(event, '${item.id}')" title="Download File">⬇️ Download</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// TOGGLE FAVORITE ON CARD
async function toggleCardFavorite(e, itemId) {
  e.stopPropagation();
  try {
    const res = await apiRequest('/api/favorite', 'POST', { item_id: itemId });
    const item = state.items.find(i => i.id === itemId);
    if (item) item.favorite = res.favorite;
    loadItems();
    showToast(res.favorite ? 'Added to Favorites ⭐' : 'Removed from Favorites', 'info');
  } catch (err) {
    showToast('Error updating favorite', 'error');
  }
}

// TOGGLE FAVORITE IN MODAL
async function toggleActiveItemFavorite() {
  if (!state.activeItem) return;
  try {
    const res = await apiRequest('/api/favorite', 'POST', { item_id: state.activeItem.id });
    state.activeItem.favorite = res.favorite;
    const btn = document.getElementById('btnFavModal');
    if (btn) btn.classList.toggle('active', res.favorite);
    loadItems();
    showToast(res.favorite ? 'Added to Favorites ⭐' : 'Removed from Favorites', 'info');
  } catch (err) {
    showToast('Error updating favorite', 'error');
  }
}

// QUICK COPY NOTE SECRET FROM CARD
async function quickCopyNote(e, itemId) {
  e.stopPropagation();
  try {
    const res = await apiRequest(`/api/item/${itemId}`);
    const item = res.item;
    if (item && item.data_b64) {
      const rawText = atob(item.data_b64);
      await navigator.clipboard.writeText(rawText);
      showToast(`Copied content of '${item.name}' to clipboard! 📋`, 'success');
    }
  } catch (err) {
    showToast('Error copying content', 'error');
  }
}

// QUICK DOWNLOAD FROM CARD
function quickDownloadItem(e, itemId) {
  e.stopPropagation();
  window.location.href = `/api/download/${itemId}`;
}

// VIEW ITEM MODAL
async function viewItem(itemId) {
  try {
    const res = await apiRequest(`/api/item/${itemId}`);
    const item = res.item;
    state.activeItem = item;

    document.getElementById('viewItemTitle').innerText = item.name;
    const favBtn = document.getElementById('btnFavModal');
    if (favBtn) favBtn.classList.toggle('active', !!item.favorite);

    const body = document.getElementById('viewItemBody');
    const downloadBtn = document.getElementById('btnDownloadItem');
    const deleteBtn = document.getElementById('btnDeleteItem');

    downloadBtn.href = `/api/download/${item.id}`;
    deleteBtn.onclick = () => deleteItem(item.id);

    if (item.type === 'note') {
      const rawText = atob(item.data_b64 || '');
      body.innerHTML = `
        <div class="form-group" style="display: flex; justify-content: space-between; align-items: center;">
          <label>Category: <strong>${escapeHtml(item.category)}</strong></label>
          <button class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText(\`${escapeHtml(rawText.replace(/`/g, '\\`'))}\`); showToast('Copied to clipboard!', 'success');">📋 Copy Secret</button>
        </div>
        <div class="form-group">
          <label>Decrypted Content</label>
          <pre style="background: rgba(15, 23, 42, 0.85); padding: 1.2rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); font-family: var(--font-mono); white-space: pre-wrap; word-break: break-word; color: #a5f3fc; font-size: 0.92rem;">${escapeHtml(rawText)}</pre>
        </div>
      `;
    } else {
      const isImage = item.mime_type && item.mime_type.startsWith('image/');
      let imageHtml = '';
      if (isImage && item.data_b64) {
        imageHtml = `
          <div class="image-preview-box">
            <img src="data:${item.mime_type};base64,${item.data_b64}" alt="${escapeHtml(item.name)}">
          </div>
        `;
      }

      body.innerHTML = `
        <div class="form-group">
          <label>File Name: <strong>${escapeHtml(item.name)}</strong></label>
        </div>
        <div class="form-group">
          <label>Size: <strong>${formatBytes(item.size)}</strong> | Category: <strong>${escapeHtml(item.category)}</strong></label>
        </div>
        <div class="form-group">
          <label>MIME Type: <code>${escapeHtml(item.mime_type || 'application/octet-stream')}</code></label>
        </div>
        ${item.notes ? `<div class="form-group"><label>Notes:</label><p>${escapeHtml(item.notes)}</p></div>` : ''}
        ${imageHtml}
      `;
    }

    openModal('modalViewItem');
  } catch (err) {
    showToast('Error loading item data', 'error');
  }
}

// DELETE ITEM
async function deleteItem(itemId) {
  if (!confirm('Are you sure you want to permanently delete this encrypted item?')) return;
  try {
    await apiRequest(`/api/item/${itemId}`, 'DELETE');
    closeModal('modalViewItem');
    showToast('Item deleted from vault', 'success');
    loadItems();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// FILE SELECTION & DRAG-DROP FOR MODAL & GLOBAL
function handleFileSelect(e) {
  const files = Array.from(e.target.files);
  if (files.length > 0) setFilesForUpload(files);
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.add('dragover');
}

function handleDragLeave(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('dragover');
}

function handleFileDrop(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('dragover');
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    setFilesForUpload(Array.from(e.dataTransfer.files));
  }
}

function openUploadModalWithFiles(files) {
  openUploadModal();
  setFilesForUpload(files);
}

function setFilesForUpload(files) {
  state.selectedFiles = files;
  const listContainer = document.getElementById('selectedFileList');
  listContainer.innerHTML = files.map((f, idx) => `
    <div class="selected-file-info">
      <span class="file-badge">${getFileIconByExt(f.name)}</span>
      <div class="file-meta">
        <div class="file-name">${escapeHtml(f.name)}</div>
        <div class="file-size">${formatBytes(f.size)}</div>
      </div>
      <button class="btn-sm btn-danger" onclick="removeSelectedFile(${idx})">✕</button>
    </div>
  `).join('');

  listContainer.classList.remove('hidden');
  document.getElementById('dropZone').classList.add('hidden');
}

function removeSelectedFile(index) {
  state.selectedFiles.splice(index, 1);
  if (state.selectedFiles.length === 0) {
    clearSelectedFiles();
  } else {
    setFilesForUpload(state.selectedFiles);
  }
}

function clearSelectedFiles() {
  state.selectedFiles = [];
  document.getElementById('fileInput').value = '';
  document.getElementById('selectedFileList').classList.add('hidden');
  document.getElementById('selectedFileList').innerHTML = '';
  document.getElementById('dropZone').classList.remove('hidden');
}

// SUBMIT FILE UPLOAD (SINGLE OR BATCH)
async function submitFileUpload() {
  if (state.selectedFiles.length === 0) {
    showToast('Please select file(s) to encrypt', 'error');
    return;
  }

  const category = document.getElementById('uploadCategory').value;
  const notes = document.getElementById('uploadNotes').value;

  const filePayloads = [];
  for (const file of state.selectedFiles) {
    const b64 = await readFileAsBase64(file);
    filePayloads.push({
      filename: file.name,
      data_b64: b64,
      category: category,
      notes: notes,
      mime_type: file.type || 'application/octet-stream'
    });
  }

  try {
    if (filePayloads.length === 1) {
      await apiRequest('/api/upload', 'POST', filePayloads[0]);
      showToast(`Encrypted & stored '${filePayloads[0].filename}'`, 'success');
    } else {
      const res = await apiRequest('/api/batch-upload', 'POST', { files: filePayloads });
      showToast(`Encrypted & stored ${res.added_count} files!`, 'success');
    }
    closeModal('modalUpload');
    clearSelectedFiles();
    loadItems();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const bytes = new Uint8Array(reader.result);
      let binary = '';
      const len = bytes.byteLength;
      for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      resolve(btoa(binary));
    };
    reader.onerror = error => reject(error);
    reader.readAsArrayBuffer(file);
  });
}

// SUBMIT SECURE NOTE
async function submitNoteSave() {
  const title = document.getElementById('noteTitle').value.trim();
  const category = document.getElementById('noteCategory').value;
  const content = document.getElementById('noteContent').value;

  if (!title || !content) {
    showToast('Title and content are required', 'error');
    return;
  }

  try {
    await apiRequest('/api/note', 'POST', { title, category, content });
    showToast('Encrypted note saved!', 'success');
    closeModal('modalNote');
    document.getElementById('noteTitle').value = '';
    document.getElementById('noteContent').value = '';
    loadItems();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// CHANGE PASSWORD
async function handleChangePassword(e) {
  e.preventDefault();
  const oldPwd = document.getElementById('currentPassword').value;
  const newPwd = document.getElementById('newPassword').value;

  try {
    await apiRequest('/api/change-password', 'POST', { old_password: oldPwd, new_password: newPwd });
    showToast('Master password updated!', 'success');
    closeModal('modalSettings');
    document.getElementById('currentPassword').value = '';
    document.getElementById('newPassword').value = '';
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// DOWNLOAD BACKUP
function downloadVaultBackup() {
  window.location.href = '/api/export';
}

// CATEGORY FILTERS
function setCategoryFilter(cat) {
  state.selectedCategory = cat;
  document.querySelectorAll('#categoryFilters .chip').forEach(btn => {
    btn.classList.toggle('active', btn.innerText.includes(cat));
  });
  renderItems();
}

// PASSWORD GENERATOR & ENTROPY
function generatePassword() {
  const len = parseInt(document.getElementById('genLength').value) || 20;
  const useUpper = document.getElementById('chkUpper').checked;
  const useLower = document.getElementById('chkLower').checked;
  const useNumbers = document.getElementById('chkNumbers').checked;
  const useSymbols = document.getElementById('chkSymbols').checked;

  let poolSize = 0;
  let chars = '';
  if (useUpper) { chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'; poolSize += 26; }
  if (useLower) { chars += 'abcdefghijklmnopqrstuvwxyz'; poolSize += 26; }
  if (useNumbers) { chars += '0123456789'; poolSize += 10; }
  if (useSymbols) { chars += '!@#$%^&*()_+-=[]{}|;:,.<>?'; poolSize += 32; }

  if (!chars) { chars = 'abcdefghijklmnopqrstuvwxyz0123456789'; poolSize = 36; }

  let pwd = '';
  const cryptoObj = window.crypto || window.msCrypto;
  const randomValues = new Uint32Array(len);
  cryptoObj.getRandomValues(randomValues);

  for (let i = 0; i < len; i++) {
    pwd += chars[randomValues[i] % chars.length];
  }

  document.getElementById('genResult').value = pwd;

  // Calculate entropy: Bits = Length * log2(poolSize)
  const entropy = Math.round(len * Math.log2(poolSize));
  document.getElementById('entropyValue').innerText = `${entropy} bits`;

  const ratingTag = document.getElementById('entropyRating');
  if (entropy < 50) {
    ratingTag.innerText = 'Weak';
    ratingTag.className = 'entropy-tag tag-weak';
  } else if (entropy < 80) {
    ratingTag.innerText = 'Moderate';
    ratingTag.className = 'entropy-tag tag-moderate';
  } else {
    ratingTag.innerText = 'Very Strong';
    ratingTag.className = 'entropy-tag tag-strong';
  }
}

function copyGenPassword() {
  const field = document.getElementById('genResult');
  field.select();
  navigator.clipboard.writeText(field.value);
  showToast('Password copied to clipboard!', 'success');
}

function saveGenAsNote() {
  const pwd = document.getElementById('genResult').value;
  closeModal('modalGenerator');
  openNoteModal();
  document.getElementById('noteTitle').value = 'Generated Password';
  document.getElementById('noteCategory').value = 'Passwords';
  document.getElementById('noteContent').value = pwd;
}

// PASSWORD STRENGTH CHECKER (FOR MASTER PASSWORD)
function checkPasswordStrength(pwd) {
  const bar = document.getElementById('strengthBar');
  const txt = document.getElementById('strengthText');
  let score = 0;

  if (pwd.length >= 8) score += 25;
  if (pwd.length >= 14) score += 25;
  if (/[A-Z]/.test(pwd)) score += 15;
  if (/[0-9]/.test(pwd)) score += 15;
  if (/[^A-Za-z0-9]/.test(pwd)) score += 20;

  bar.style.width = `${score}%`;
  if (score < 40) {
    bar.style.backgroundColor = '#ef4444';
    txt.innerText = 'Weak password';
  } else if (score < 75) {
    bar.style.backgroundColor = '#f59e0b';
    txt.innerText = 'Moderate strength';
  } else {
    bar.style.backgroundColor = '#10b981';
    txt.innerText = 'Strong password';
  }
}

// HELPERS
function updateStats() {
  document.getElementById('statTotalItems').innerText = state.items.length;
  const totalBytes = state.items.reduce((acc, i) => acc + (i.size || 0), 0);
  document.getElementById('statTotalSize').innerText = formatBytes(totalBytes);
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === 'password' ? 'text' : 'password';
}

function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(m => m.classList.add('hidden'));
}

function closeModalOnOverlay(e, id) {
  if (e.target.id === id) closeModal(id);
}

function openUploadModal() {
  clearSelectedFiles();
  openModal('modalUpload');
}

function openNoteModal() { openModal('modalNote'); }
function openGeneratorModal() { generatePassword(); openModal('modalGenerator'); }
function openSettingsModal() { openModal('modalSettings'); }

function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerText = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function getItemIcon(type, mime, cat) {
  if (type === 'note') return '📝';
  if (cat === 'Passwords') return '🔑';
  if (mime && mime.includes('image')) return '🖼️';
  if (mime && mime.includes('pdf')) return '📕';
  if (mime && mime.includes('zip')) return '📦';
  return '📄';
}

function getFileIconByExt(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) return '🖼️';
  if (['pdf'].includes(ext)) return '📕';
  if (['zip', 'tar', 'gz', '7z'].includes(ext)) return '📦';
  if (['txt', 'md', 'json', 'py', 'js', 'html', 'css'].includes(ext)) return '📝';
  return '📄';
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

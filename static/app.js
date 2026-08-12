// AEGIS LOCAL VAULT FRONTEND CONTROLLER

let state = {
  initialized: false,
  unlocked: false,
  items: [],
  selectedCategory: 'All',
  selectedFile: null,
  activeItem: null
};

// INITIALIZATION
document.addEventListener('DOMContentLoaded', () => {
  checkVaultStatus();
  generatePassword();
});

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
  } else {
    // Show Dashboard
    authSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    badge.className = 'status-badge status-unlocked';
    statusText.innerText = 'Unlocked (RAM Active)';
    btnLock.classList.remove('hidden');
    btnSettings.classList.remove('hidden');
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
    renderItems();
    updateStats();
  } catch (err) {
    showToast('Error loading items', 'error');
  }
}

// RENDER ITEMS GRID
function renderItems() {
  const container = document.getElementById('itemsContainer');
  const emptyState = document.getElementById('emptyState');
  const search = document.getElementById('searchInput').value.toLowerCase().trim();

  let filtered = state.items.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(search) || (item.notes && item.notes.toLowerCase().includes(search));
    const matchesCat = state.selectedCategory === 'All' || item.category === state.selectedCategory;
    return matchesSearch && matchesCat;
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

    return `
      <div class="item-card glass-card" onclick="viewItem('${item.id}')">
        <div class="item-header">
          <div class="item-type-icon">${icon}</div>
          <div class="item-title-box">
            <div class="item-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
            <div class="item-meta">
              <span class="item-badge">${escapeHtml(item.category)}</span>
              <span>• ${dateStr}</span>
            </div>
          </div>
        </div>
        <div class="item-footer">
          <span class="item-size">${sizeStr}</span>
          <span style="font-size: 0.8rem; color: var(--primary);">View & Extract →</span>
        </div>
      </div>
    `;
  }).join('');
}

// VIEW ITEM MODAL
async function viewItem(itemId) {
  try {
    const res = await apiRequest(`/api/item/${itemId}`);
    const item = res.item;
    state.activeItem = item;

    document.getElementById('viewItemTitle').innerText = item.name;
    const body = document.getElementById('viewItemBody');
    const downloadBtn = document.getElementById('btnDownloadItem');
    const deleteBtn = document.getElementById('btnDeleteItem');

    downloadBtn.href = `/api/download/${item.id}`;
    deleteBtn.onclick = () => deleteItem(item.id);

    if (item.type === 'note') {
      const rawText = atob(item.data_b64 || '');
      body.innerHTML = `
        <div class="form-group">
          <label>Category: <strong>${escapeHtml(item.category)}</strong></label>
        </div>
        <div class="form-group">
          <label>Decrypted Content</label>
          <pre style="background: rgba(15, 23, 42, 0.8); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-card); font-family: var(--font-mono); white-space: pre-wrap; word-break: break-word;">${escapeHtml(rawText)}</pre>
        </div>
      `;
    } else {
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

// FILE SELECTION & DRAG-DROP
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) setFileForUpload(file);
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
    setFileForUpload(e.dataTransfer.files[0]);
  }
}

function setFileForUpload(file) {
  state.selectedFile = file;
  document.getElementById('selectedFileName').innerText = file.name;
  document.getElementById('selectedFileSize').innerText = formatBytes(file.size);
  document.getElementById('selectedFileInfo').classList.remove('hidden');
  document.getElementById('dropZone').classList.add('hidden');
}

function clearSelectedFile() {
  state.selectedFile = null;
  document.getElementById('fileInput').value = '';
  document.getElementById('selectedFileInfo').classList.add('hidden');
  document.getElementById('dropZone').classList.remove('hidden');
}

// SUBMIT FILE UPLOAD
async function submitFileUpload() {
  if (!state.selectedFile) {
    showToast('Please select a file to encrypt', 'error');
    return;
  }

  const file = state.selectedFile;
  const category = document.getElementById('uploadCategory').value;
  const notes = document.getElementById('uploadNotes').value;

  const reader = new FileReader();
  reader.onload = async () => {
    const arrayBuffer = reader.result;
    const bytes = new Uint8Array(arrayBuffer);
    
    // Convert bytes to base64
    let binary = '';
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    const b64 = btoa(binary);

    try {
      await apiRequest('/api/upload', 'POST', {
        filename: file.name,
        data_b64: b64,
        category: category,
        notes: notes,
        mime_type: file.type || 'application/octet-stream'
      });
      showToast(`Encrypted & stored '${file.name}'`, 'success');
      closeModal('modalUpload');
      clearSelectedFile();
      loadItems();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };
  reader.readAsArrayBuffer(file);
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
    btn.classList.toggle('active', btn.innerText.includes(cat) || (cat === 'All' && btn.innerText === 'All'));
  });
  renderItems();
}

// PASSWORD GENERATOR TOOL
function generatePassword() {
  const len = parseInt(document.getElementById('genLength').value) || 20;
  const useUpper = document.getElementById('chkUpper').checked;
  const useLower = document.getElementById('chkLower').checked;
  const useNumbers = document.getElementById('chkNumbers').checked;
  const useSymbols = document.getElementById('chkSymbols').checked;

  let chars = '';
  if (useUpper) chars += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  if (useLower) chars += 'abcdefghijklmnopqrstuvwxyz';
  if (useNumbers) chars += '0123456789';
  if (useSymbols) chars += '!@#$%^&*()_+-=[]{}|;:,.<>?';

  if (!chars) chars = 'abcdefghijklmnopqrstuvwxyz0123456789';

  let pwd = '';
  const cryptoObj = window.crypto || window.msCrypto;
  const randomValues = new Uint32Array(len);
  cryptoObj.getRandomValues(randomValues);

  for (let i = 0; i < len; i++) {
    pwd += chars[randomValues[i] % chars.length];
  }

  document.getElementById('genResult').value = pwd;
}

function copyGenPassword() {
  const field = document.getElementById('genResult');
  field.select();
  navigator.clipboard.writeText(field.value);
  showToast('Password copied to clipboard!', 'success');
}

// PASSWORD STRENGTH CHECKER
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

function closeModalOnOverlay(e, id) {
  if (e.target.id === id) closeModal(id);
}

function openUploadModal() { openModal('modalUpload'); }
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

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
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

// =========================================================================
// Sahay — interactive frontend
// =========================================================================

const $ = (sel) => document.querySelector(sel);

const messages     = $('#messages');
const form         = $('#chat-form');
const input        = $('#chat-input');
const sendBtn      = $('#send-btn');
const micBtn       = $('#mic-btn');
const micStatus    = $('#mic-status');
const resultsEl    = $('#results');
const countEl      = $('#match-count');
const personasEl   = $('#persona-buttons');
const schemeCount  = $('#scheme-count');
const valueBanner  = $('#value-banner');
const valueCounter = $('#value-counter');
const fraudBanner  = $('#fraud-banner');
const fraudHead    = $('#fraud-headline');
const fraudDetail  = $('#fraud-detail');
const fraudDismiss = $('#fraud-dismiss');
const filterBar    = $('#filter-bar');
const thinking     = $('#thinking');
const themeToggle  = $('#theme-toggle');
const themeIcon    = $('#theme-icon');
const langToggle   = $('#lang-toggle');
const langLabel    = $('#lang-label');
const resultsSub   = $('#results-sub');

let currentMatches = [];
let activeFilter = 'All';

const PERSONA_EMOJI = {
  ramesh:  '👨‍🌾',
  lakshmi: '👩',
  priya:   '🛵',
  irfan:   '🪚',
};

// =================================================================== boot
(async function init () {
  loadTheme();
  loadLang();

  try {
    const [schemes, personas] = await Promise.all([
      fetch('/api/schemes').then(r => r.json()),
      fetch('/api/personas').then(r => r.json()),
    ]);
    animateCount(schemeCount, 0, schemes.length, 1200);
    renderPersonas(personas);
  } catch (err) { console.error(err); }
})();

function renderPersonas (personas) {
  personasEl.innerHTML = '';
  personas.forEach(p => {
    const [name, role] = p.name.split(' — ');
    const btn = document.createElement('button');
    btn.className = 'persona-btn';
    btn.type = 'button';
    btn.innerHTML = `
      <span class="persona-emoji">${PERSONA_EMOJI[p.id] || '🙋'}</span>
      <span class="persona-meta">
        <strong>${escapeHTML(name)}</strong>
        <small>${escapeHTML(role || '')}</small>
      </span>`;
    btn.addEventListener('click', () => {
      input.value = p.prompt;
      input.focus();
      form.requestSubmit();
    });
    personasEl.appendChild(btn);
  });
}

// =================================================================== chat
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  appendMessage('user', escapeHTML(text));
  input.value = '';
  sendBtn.disabled = true;

  showThinking();

  try {
    const [res] = await Promise.all([
      fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, language: LANGS[langIdx].code }),
      }).then(r => r.json()),
      wait(1600), // let the thinking animation play
    ]);

    hideThinking();
    appendMessage('assistant', renderMarkdownLite(res.summary || 'No response.'));
    handleMatches(res.matches || []);
    showFraudBanner(res.fraud_advisory);
  } catch (err) {
    hideThinking();
    appendMessage('assistant', '⚠️ Couldn\'t reach the server. Make sure Flask is running.');
    console.error(err);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

function appendMessage (role, html) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;
  const avatarText = role === 'assistant' ? 'स' : 'You';
  const speakBtn = role === 'assistant'
    ? '<button class="speak-btn" title="Read aloud" type="button">🔊</button>'
    : '';
  wrap.innerHTML = `
    <div class="avatar">${avatarText}</div>
    <div class="bubble">${html}${speakBtn}</div>`;
  if (role === 'assistant') {
    wrap.querySelector('.speak-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      const plain = wrap.querySelector('.bubble').textContent.replace(/🔊\s*$/, '').trim();
      speak(plain);
    });
  }
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
  return wrap;
}

// =================================================================== source modal
const sourceModal = $('#source-modal');
const sourceTitle = $('#source-title');
const sourceSubtitle = $('#source-subtitle');
const sourceBody = $('#source-body');
$('#source-close')?.addEventListener('click', closeSourceModal);
$('#source-modal .source-modal-backdrop')?.addEventListener('click', closeSourceModal);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSourceModal(); });

window.openSourceModal = async function (schemeId, schemeName) {
  sourceTitle.textContent = schemeName;
  sourceSubtitle.textContent = 'Loading official document…';
  sourceBody.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
  sourceModal.classList.remove('hidden');
  try {
    const r = await fetch(`/api/scheme-source/${encodeURIComponent(schemeId)}`).then(x => x.json());
    if (!r.available || !r.sources.length) {
      sourceSubtitle.textContent = 'No source document indexed for this scheme yet.';
      sourceBody.innerHTML = '<p style="color:var(--muted);">Try uploading the official PDF using the "Teach Sahay a new scheme" panel.</p>';
      return;
    }
    sourceSubtitle.textContent = `${r.sources.length} relevant passage(s) retrieved live`;
    sourceBody.innerHTML = r.sources.map(s => `
      <div class="source-chunk">
        <div class="source-chunk-meta">📄 ${escapeHTML(s.doc_name)} · paragraph ${s.page} · relevance ${s.score}</div>
        ${escapeHTML(s.text)}
      </div>`).join('');
  } catch (err) {
    sourceBody.innerHTML = '<p style="color:#dc2626;">Failed to load source — check that the server is running.</p>';
    console.error(err);
  }
};

function closeSourceModal () { sourceModal.classList.add('hidden'); }

// =================================================================== PDF upload (live indexing)
const pdfFile = $('#pdf-file');
const pdfDrop = $('#pdf-drop');
const pdfStatus = $('#pdf-status');

if (pdfDrop) {
  pdfFile.addEventListener('change', (e) => {
    if (e.target.files[0]) handlePdfUpload(e.target.files[0]);
    pdfFile.value = '';
  });
  ['dragenter', 'dragover'].forEach(evt =>
    pdfDrop.addEventListener(evt, (e) => { e.preventDefault(); pdfDrop.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach(evt =>
    pdfDrop.addEventListener(evt, (e) => { e.preventDefault(); pdfDrop.classList.remove('dragging'); }));
  pdfDrop.addEventListener('drop', (e) => {
    if (e.dataTransfer.files[0]) handlePdfUpload(e.dataTransfer.files[0]);
  });
}

async function handlePdfUpload (file) {
  pdfStatus.className = 'pdf-status';
  pdfStatus.textContent = `⏳ Reading ${file.name}…`;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const r = await fetch('/api/upload-pdf', { method: 'POST', body: fd }).then(x => x.json());
    if (r.error) {
      pdfStatus.className = 'pdf-status fail';
      pdfStatus.textContent = `✗ ${r.error}`;
      return;
    }
    pdfStatus.className = 'pdf-status ok';
    pdfStatus.textContent = `✓ Indexed ${r.chunks} passages from ${r.doc_name} · total knowledge base: ${r.total_index_size} chunks`;
  } catch (err) {
    pdfStatus.className = 'pdf-status fail';
    pdfStatus.textContent = `✗ Upload failed: ${err.message}`;
  }
}

// =================================================================== TTS
function speak (text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = LANGS[langIdx].code;
  utter.rate = 0.95;
  utter.pitch = 1.0;
  // try to find a voice in that language
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find(v => v.lang === utter.lang) ||
                voices.find(v => v.lang.startsWith(utter.lang.split('-')[0]));
  if (match) utter.voice = match;
  window.speechSynthesis.speak(utter);
}
// pre-load voices on Chrome
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {};
}

function renderMarkdownLite (text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

// =================================================================== results
function handleMatches (matches) {
  currentMatches = matches;
  countEl.textContent = matches.length;
  countEl.classList.remove('bump');
  void countEl.offsetWidth; // restart animation
  countEl.classList.add('bump');

  if (matches.length === 0) {
    valueBanner.classList.add('hidden');
    filterBar.classList.add('hidden');
    docChecker.classList.add('hidden');
    renderEmpty();
    return;
  }

  // reset doc checklist state for new search
  docChecks = {};
  buildDocChecklist(matches);

  // total annual rupee value
  const total = matches.reduce((s, m) => s + (m.est_value_inr || 0), 0);
  if (total > 0) {
    valueBanner.classList.remove('hidden');
    animateRupees(valueCounter, 0, total, 1400);
  } else {
    valueBanner.classList.add('hidden');
  }

  // categories filter
  const cats = ['All', ...new Set(matches.map(m => m.category).filter(Boolean))];
  renderFilters(cats);

  renderResults(matches);
  fireConfetti();
  resultsSub.textContent = `Tap any card to expand · share · copy as text`;
}

// =================================================================== document checker
const docChecker  = $('#doc-checker');
const docChecklist = $('#doc-checklist');
const docSummary  = $('#doc-summary');
const docProgressCircle = $('#doc-progress-circle');
const docProgressText   = $('#doc-progress-text');
const docFile = $('#doc-file');
const docDrop = $('#doc-drop');
const docUploads = $('#doc-uploads');

const CIRCUMFERENCE = 175.93;
let docChecks = {};   // { docName: true/false }
let docCounts = {};   // { docName: schemesNeeding }

// Some friendly normalizations so similar docs collapse into one row.
function normaliseDoc (d) {
  const x = d.toLowerCase().trim();
  if (x.startsWith('aadhaar')) return 'Aadhaar';
  if (x.includes('bank account')) return 'Bank account';
  if (x.includes('ration')) return 'Ration card';
  if (x.includes('pan')) return 'PAN card';
  if (x.includes('mobile')) return 'Mobile number';
  if (x.includes('caste certif')) return 'Caste certificate';
  if (x.includes('income certif')) return 'Income certificate';
  if (x.includes('land')) return 'Land record';
  if (x.includes('address proof')) return 'Address proof';
  if (x.includes('age proof')) return 'Age proof';
  if (x.includes('birth certif')) return 'Birth certificate';
  if (x.includes('death certif')) return 'Death certificate (spouse)';
  if (x.includes('photograph') || x === 'photo') return 'Passport-size photo';
  if (x.includes('job card')) return 'MGNREGA job card';
  if (x.includes('secc')) return 'SECC-2011 verification';
  if (x.includes('graduation certif')) return 'Graduation certificate';
  if (x.includes('marksheet')) return 'Marksheet';
  if (x.includes('fee receipt')) return 'Fee receipt';
  if (x.includes('business plan')) return 'Business plan';
  if (x.includes('bpl')) return 'BPL card';
  return d.charAt(0).toUpperCase() + d.slice(1);
}

function buildDocChecklist (matches) {
  if (matches.length === 0) { docChecker.classList.add('hidden'); return; }
  docCounts = {};
  matches.forEach(m => {
    (m.documents || []).forEach(d => {
      const k = normaliseDoc(d);
      docCounts[k] = (docCounts[k] || 0) + 1;
    });
  });
  // sort by most-needed first
  const sorted = Object.entries(docCounts).sort((a, b) => b[1] - a[1]);
  docChecklist.innerHTML = '';
  sorted.forEach(([name, count]) => {
    const item = document.createElement('label');
    item.className = 'doc-item' + (docChecks[name] ? ' checked' : '');
    item.innerHTML = `
      <span class="check-box">✓</span>
      <input type="checkbox" ${docChecks[name] ? 'checked' : ''} />
      <span class="doc-name">${escapeHTML(name)}</span>
      <span class="doc-count">${count} scheme${count > 1 ? 's' : ''}</span>`;
    const cb = item.querySelector('input');
    cb.addEventListener('change', () => {
      docChecks[name] = cb.checked;
      item.classList.toggle('checked', cb.checked);
      updateDocProgress();
    });
    docChecklist.appendChild(item);
  });
  docChecker.classList.remove('hidden');
  updateDocProgress();
}

function updateDocProgress () {
  const total = Object.keys(docCounts).length;
  const have = Object.values(docChecks).filter(Boolean).length;
  const pct = total === 0 ? 0 : Math.round((have / total) * 100);
  docProgressText.textContent = pct + '%';
  docProgressCircle.setAttribute('stroke-dashoffset', String(CIRCUMFERENCE * (1 - pct / 100)));

  // schemes ready: those whose every required doc is checked
  const ready = currentMatches.filter(m =>
    (m.documents || []).every(d => docChecks[normaliseDoc(d)])
  ).length;

  if (have === 0) {
    docSummary.textContent = `${total} unique documents needed across ${currentMatches.length} schemes. Tick what you have.`;
  } else if (ready === currentMatches.length) {
    docSummary.innerHTML = `🎉 <strong>You have everything!</strong> Ready to apply for all ${currentMatches.length} schemes.`;
  } else {
    docSummary.innerHTML = `<strong>${ready}</strong> of ${currentMatches.length} schemes ready to apply · ${have}/${total} documents collected.`;
  }
}

// ---- mock OCR ------------------------------------------------------------
function mockValidateUpload (file) {
  const name = file.name.toLowerCase();
  const sizeMB = file.size / (1024 * 1024);

  let type = 'Unrecognised document';
  let status = 'warn';
  let detail = 'Could not auto-detect document type. Please name files clearly.';
  let icon = '📄';

  if (sizeMB > 5) {
    return { type: 'File too large', status: 'fail', detail: `${sizeMB.toFixed(1)} MB exceeds 5 MB limit.`, icon: '⚠' };
  }

  if (name.includes('aadhaar') || name.includes('adhar') || /^\d{4}.*\d{4}/.test(name)) {
    type = 'Aadhaar Card';  status = 'ok'; icon = '🆔';
    detail = 'Number ····-····-' + Math.floor(1000 + Math.random() * 9000) + ' · Name ✓ · DOB ✓';
  } else if (name.includes('pan')) {
    type = 'PAN Card'; status = 'ok'; icon = '🪪';
    detail = 'PAN · ABCDE' + Math.floor(1000 + Math.random() * 9000) + 'F · Name ✓';
  } else if (name.includes('ration')) {
    type = 'Ration Card'; status = 'ok'; icon = '🍚';
    detail = 'Card ID detected · Family head ✓ · Category visible';
  } else if (name.includes('bank') || name.includes('passbook')) {
    type = 'Bank Passbook'; status = 'ok'; icon = '🏦';
    detail = 'Account no. ····' + Math.floor(1000 + Math.random() * 9000) + ' · IFSC ✓';
  } else if (name.includes('income')) {
    type = 'Income Certificate'; status = 'ok'; icon = '💰';
    detail = 'Issuing authority ✓ · Year ✓';
  } else if (name.includes('caste')) {
    type = 'Caste Certificate'; status = 'ok'; icon = '📜';
    detail = 'Category detected ✓ · Issuing officer ✓';
  } else if (name.includes('land') || name.includes('khasra')) {
    type = 'Land Record'; status = 'ok'; icon = '🌾';
    detail = 'Khasra number ✓ · Owner name ✓';
  }

  if (status === 'ok' && sizeMB < 0.05) {
    status = 'warn';
    detail = 'Scan looks too small/blurry — re-upload a clearer photo.';
  }

  return { type, status, detail, icon };
}

function attachUploadHandlers () {
  docFile.addEventListener('change', (e) => {
    [...e.target.files].forEach(handleUpload);
    docFile.value = '';
  });

  ['dragenter', 'dragover'].forEach(evt =>
    docDrop.addEventListener(evt, (e) => { e.preventDefault(); docDrop.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach(evt =>
    docDrop.addEventListener(evt, (e) => { e.preventDefault(); docDrop.classList.remove('dragging'); }));
  docDrop.addEventListener('drop', (e) => {
    [...e.dataTransfer.files].forEach(handleUpload);
  });
}

function handleUpload (file) {
  const row = document.createElement('div');
  row.className = 'upload-item checking';
  row.innerHTML = `
    <div class="upload-icon">⏳</div>
    <div class="upload-meta">
      <strong>${escapeHTML(file.name)}</strong>
      <small>Verifying… reading text · checking quality</small>
    </div>
    <div class="upload-status">Checking</div>`;
  docUploads.appendChild(row);

  setTimeout(() => {
    const result = mockValidateUpload(file);
    row.classList.remove('checking');
    row.classList.add(result.status);
    row.querySelector('.upload-icon').textContent = result.icon;
    row.querySelector('.upload-meta').innerHTML = `
      <strong>${escapeHTML(result.type)}</strong>
      <small>${escapeHTML(result.detail)}</small>`;
    row.querySelector('.upload-status').textContent =
      result.status === 'ok' ? '✓ Verified' :
      result.status === 'warn' ? '⚠ Re-upload' : '✗ Failed';

    // auto-check the corresponding checklist row
    if (result.status === 'ok') {
      const docName = result.type.replace(' Card', '').replace(' Certificate', '');
      // try to find a matching key in docCounts
      const keys = Object.keys(docCounts);
      const match = keys.find(k => k.toLowerCase().includes(docName.toLowerCase().split(' ')[0]));
      if (match && !docChecks[match]) {
        docChecks[match] = true;
        buildDocChecklist(currentMatches);
      }
    }
  }, 1400 + Math.random() * 600);
}
attachUploadHandlers();

function showFraudBanner (advisory) {
  if (!advisory) { fraudBanner.classList.add('hidden'); return; }
  fraudHead.textContent  = advisory.headline || 'All schemes are FREE — never pay any agent.';
  fraudDetail.textContent = advisory.detail || '';
  fraudBanner.classList.remove('hidden');
}

fraudDismiss?.addEventListener('click', () => fraudBanner.classList.add('hidden'));

// =================================================================== mode tabs (chat vs form)
const modeTabs = document.querySelectorAll('.mode-tab');
const formView = $('#form-view');
const eligibilityForm = $('#eligibility-form');

modeTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const mode = tab.dataset.mode;
    modeTabs.forEach(t => t.classList.toggle('active', t === tab));
    if (mode === 'form') {
      formView.hidden = false;
      messages.parentElement.querySelector('.composer').hidden = true;
      messages.hidden = true;
    } else {
      formView.hidden = true;
      messages.parentElement.querySelector('.composer').hidden = false;
      messages.hidden = false;
    }
  });
});

eligibilityForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(eligibilityForm);
  const profile = {};
  for (const [k, v] of fd.entries()) {
    if (eligibilityForm.elements[k].type === 'checkbox') {
      profile[k] = eligibilityForm.elements[k].checked;
    } else {
      profile[k] = v;
    }
  }
  // capture all checkbox values (FormData skips unchecked)
  eligibilityForm.querySelectorAll('input[type=checkbox]').forEach(cb => {
    profile[cb.name] = cb.checked;
  });

  // switch to chat view to show results
  modeTabs[0].click();
  appendMessage('user', '📋 Submitted eligibility form');
  showThinking();

  try {
    const [res] = await Promise.all([
      fetch('/api/match-form', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...profile, language: LANGS[langIdx].code }),
      }).then(r => r.json()),
      wait(1400),
    ]);
    hideThinking();
    appendMessage('assistant', renderMarkdownLite(res.summary || 'No response.'));
    handleMatches(res.matches || []);
    showFraudBanner(res.fraud_advisory);
  } catch (err) {
    hideThinking();
    appendMessage('assistant', '⚠️ Couldn\'t check eligibility. Make sure the server is running.');
    console.error(err);
  }
});

function renderEmpty () {
  resultsEl.innerHTML = `
    <div class="empty">
      <div class="empty-icon">🔎</div>
      <p>No clear matches yet.</p>
      <p class="hint">Try adding age, occupation, or specific needs.</p>
    </div>`;
}

function renderFilters (cats) {
  filterBar.classList.remove('hidden');
  filterBar.innerHTML = '';
  cats.forEach(c => {
    const btn = document.createElement('button');
    btn.className = 'filter-chip' + (c === activeFilter ? ' active' : '');
    btn.type = 'button';
    const count = c === 'All' ? currentMatches.length
                              : currentMatches.filter(m => m.category === c).length;
    btn.textContent = `${c} (${count})`;
    btn.addEventListener('click', () => {
      activeFilter = c;
      [...filterBar.children].forEach(el => el.classList.remove('active'));
      btn.classList.add('active');
      const filtered = c === 'All' ? currentMatches
                                   : currentMatches.filter(m => m.category === c);
      renderResults(filtered);
    });
    filterBar.appendChild(btn);
  });
}

function renderResults (matches) {
  if (matches.length === 0) {
    resultsEl.innerHTML = `
      <div class="empty">
        <div class="empty-icon">🗂</div>
        <p>No schemes in this category.</p>
      </div>`;
    return;
  }

  resultsEl.innerHTML = '';
  matches.forEach((s, idx) => {
    const card = document.createElement('div');
    card.className = 'scheme-card';
    const valStr = s.est_value_inr ? `· ~₹${formatINR(s.est_value_inr)}/yr` : '';
    const risk = s.middleman_risk || 'medium';
    const riskLabel = { high: '⚠ High fraud risk', medium: '⚠ Some fraud risk', low: '✓ Low fraud risk' }[risk];
    card.innerHTML = `
      <div class="scheme-head">
        <div>
          <h4 class="scheme-name">${escapeHTML(s.name)}</h4>
          <div class="scheme-ministry">${escapeHTML(s.ministry || '')} ${valStr}</div>
        </div>
        <div class="scheme-badges">
          <div class="scheme-score">${s.score}★ fit</div>
          <div class="scheme-free-badge">🛡 FREE</div>
          ${s.category ? `<div class="scheme-category">${escapeHTML(s.category)}</div>` : ''}
          <div class="scheme-risk-pill risk-${risk}">${riskLabel}</div>
        </div>
      </div>
      <div class="scheme-benefit">💰 ${escapeHTML(s.benefit)}</div>
      <div class="scheme-why">Why: ${(s.why || []).map(escapeHTML).join(' · ')}</div>
      <div class="scheme-details">
        <a class="scheme-apply-cta${s.online_apply ? '' : ' counter'}"
           href="${escapeHTML(s.apply_url || s.source_url || '#')}" target="_blank" rel="noopener"
           onclick="event.stopPropagation();">
          <span class="apply-cta-text">
            <strong>${s.online_apply ? '🔗 Apply online — official registration' : '📍 Official portal & where to apply'}</strong>
            <small>${escapeHTML(prettyURL(s.apply_url || s.source_url))}</small>
          </span>
          <span class="apply-cta-arrow">↗</span>
        </a>
        <p style="margin:12px 0 8px; color:var(--ink); opacity:0.85;">${escapeHTML(s.summary || '')}</p>
        <h5>Eligibility</h5>
        <ul>${(s.eligibility || []).map(e => `<li>${escapeHTML(e)}</li>`).join('')}</ul>
        <h5>Documents needed</h5>
        <ul>${(s.documents || []).map(d => `<li>${escapeHTML(d)}</li>`).join('')}</ul>
        <h5>How to apply</h5>
        <p style="margin:4px 0 0;">${escapeHTML(s.how_to_apply || '')}</p>

        <div class="scheme-fraud-note">
          <strong>🛡 ${escapeHTML(riskLabel)}.</strong>
          ${escapeHTML(s.fraud_warning || 'This scheme is free — apply only through official channels.')}
        </div>

        ${s.source_excerpt ? `
          <button class="scheme-source-btn" onclick="event.stopPropagation(); openSourceModal('${escapeHTML(s.id)}', '${escapeHTML(s.name)}')">
            📄 View official source · ${escapeHTML(s.source_excerpt.doc_name)} (¶${s.source_excerpt.page})
          </button>` : ''}

        <div class="scheme-actions">
          <a class="scheme-action primary" href="${escapeHTML(s.source_url || '#')}" target="_blank" rel="noopener"
             onclick="event.stopPropagation();">↗ Official site</a>
          <button class="scheme-action" data-action="copy"  onclick="event.stopPropagation(); copyScheme(this, ${idx});">📋 Copy</button>
          <button class="scheme-action" data-action="share" onclick="event.stopPropagation(); shareWhatsApp(${idx});">💬 WhatsApp</button>
          <button class="scheme-action" data-action="print" onclick="event.stopPropagation(); window.print();">🖨 Print</button>
        </div>
      </div>`;
    card.addEventListener('click', () => card.classList.toggle('expanded'));
    resultsEl.appendChild(card);

    // stagger fade-in
    card.style.opacity = '0';
    card.style.transform = 'translateY(8px)';
    requestAnimationFrame(() => {
      card.style.transition = 'opacity 0.35s, transform 0.35s';
      card.style.transitionDelay = (idx * 60) + 'ms';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    });
  });
}

// expose actions for inline onclick
window.copyScheme = function (btnEl, idx) {
  const list = activeFilter === 'All'
    ? currentMatches
    : currentMatches.filter(m => m.category === activeFilter);
  const s = list[idx];
  if (!s) return;
  const text =
`${s.name}
Ministry: ${s.ministry}
Benefit: ${s.benefit}

Eligibility:
${(s.eligibility || []).map(e => '• ' + e).join('\n')}

Documents:
${(s.documents || []).join(', ')}

How to apply: ${s.how_to_apply}
More: ${s.source_url}`;
  navigator.clipboard.writeText(text).then(() => {
    btnEl.classList.add('copied');
    btnEl.textContent = '✓ Copied';
    setTimeout(() => { btnEl.classList.remove('copied'); btnEl.textContent = '📋 Copy'; }, 1800);
  });
};

window.shareWhatsApp = function (idx) {
  const list = activeFilter === 'All'
    ? currentMatches
    : currentMatches.filter(m => m.category === activeFilter);
  const s = list[idx];
  if (!s) return;
  const msg = `*${s.name}*\n${s.benefit}\n\nHow to apply: ${s.how_to_apply}\n${s.source_url}\n\n— shared via Sahay 🇮🇳`;
  const url = 'https://wa.me/?text=' + encodeURIComponent(msg);
  window.open(url, '_blank');
};

// =================================================================== thinking overlay
function showThinking () {
  thinking.classList.remove('hidden');
  const steps = thinking.querySelectorAll('.thinking-steps li');
  steps.forEach(s => s.classList.remove('active', 'done'));
  let i = 0;
  const tick = () => {
    if (i > 0) steps[i - 1].classList.remove('active'), steps[i - 1].classList.add('done');
    if (i < steps.length) {
      steps[i].classList.add('active');
      i++;
      thinking._timer = setTimeout(tick, 380);
    }
  };
  tick();
}

function hideThinking () {
  clearTimeout(thinking._timer);
  thinking.classList.add('hidden');
  thinking.querySelectorAll('.thinking-steps li').forEach(s => {
    s.classList.remove('active');
    s.classList.add('done');
  });
}

// =================================================================== animations
function animateCount (el, from, to, ms) {
  const start = performance.now();
  function step (now) {
    const t = Math.min(1, (now - start) / ms);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function animateRupees (el, from, to, ms) {
  const start = performance.now();
  function step (now) {
    const t = Math.min(1, (now - start) / ms);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = formatINR(Math.round(from + (to - from) * eased));
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// Indian-format with commas (lakh/crore): 1,23,456
function formatINR (n) {
  const s = String(Math.max(0, Math.round(n)));
  if (s.length <= 3) return s;
  const lastThree = s.slice(-3);
  const rest = s.slice(0, -3);
  return rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + lastThree;
}

// =================================================================== confetti (canvas)
const confettiCanvas = $('#confetti');
const cctx = confettiCanvas.getContext('2d');
const confetti = { _running: false };
let cParticles = [];

function resizeConfetti () {
  confettiCanvas.width = window.innerWidth;
  confettiCanvas.height = window.innerHeight;
}
resizeConfetti();
window.addEventListener('resize', resizeConfetti);

function fireConfetti () {
  const colors = ['#ff6b35', '#138808', '#f4a261', '#ffffff', '#0b2545'];
  for (let i = 0; i < 90; i++) {
    cParticles.push({
      x: window.innerWidth / 2 + (Math.random() - 0.5) * 200,
      y: window.innerHeight * 0.4,
      vx: (Math.random() - 0.5) * 8,
      vy: -Math.random() * 10 - 4,
      g: 0.3 + Math.random() * 0.1,
      size: 4 + Math.random() * 6,
      color: colors[Math.floor(Math.random() * colors.length)],
      rot: Math.random() * Math.PI,
      vr: (Math.random() - 0.5) * 0.3,
      life: 0,
      maxLife: 140 + Math.random() * 60,
    });
  }
  if (!confetti._running) {
    confetti._running = true;
    requestAnimationFrame(stepConfetti);
  }
}

function stepConfetti () {
  cctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
  cParticles = cParticles.filter(p => p.life < p.maxLife);
  cParticles.forEach(p => {
    p.vy += p.g;
    p.x += p.vx;
    p.y += p.vy;
    p.rot += p.vr;
    p.life += 1;
    cctx.save();
    cctx.translate(p.x, p.y);
    cctx.rotate(p.rot);
    cctx.fillStyle = p.color;
    cctx.globalAlpha = Math.max(0, 1 - p.life / p.maxLife);
    cctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
    cctx.restore();
  });
  if (cParticles.length > 0) {
    requestAnimationFrame(stepConfetti);
  } else {
    confetti._running = false;
    cctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
  }
}

// =================================================================== theme
function loadTheme () {
  const saved = localStorage.getItem('sahay-theme') || 'light';
  document.documentElement.dataset.theme = saved;
  themeIcon.textContent = saved === 'dark' ? '☀️' : '🌙';
}
themeToggle.addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  themeIcon.textContent = next === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('sahay-theme', next);
});

// =================================================================== voice language
const LANGS = [
  { code: 'hi-IN', label: 'हिं' },
  { code: 'en-IN', label: 'EN' },
  { code: 'ta-IN', label: 'த' },
  { code: 'bn-IN', label: 'বাং' },
];
let langIdx = 0;

function loadLang () {
  const saved = parseInt(localStorage.getItem('sahay-lang-idx') || '0', 10);
  langIdx = Number.isFinite(saved) ? saved % LANGS.length : 0;
  langLabel.textContent = LANGS[langIdx].label;
}
langToggle.addEventListener('click', () => {
  langIdx = (langIdx + 1) % LANGS.length;
  langLabel.textContent = LANGS[langIdx].label;
  localStorage.setItem('sahay-lang-idx', langIdx);
  if (recognition) recognition.lang = LANGS[langIdx].code;
  micStatus.textContent = `Voice set to ${LANGS[langIdx].code}`;
  setTimeout(() => { if (!micBtn.classList.contains('listening')) micStatus.textContent = ''; }, 1600);
});

// =================================================================== Web Speech voice
let recognition = null;
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRec) {
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = LANGS[langIdx].code;

  recognition.onstart = () => {
    micBtn.classList.add('listening');
    micStatus.textContent = '🎙 Listening… speak naturally';
  };
  recognition.onresult = (e) => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join(' ');
    input.value = transcript;
  };
  recognition.onerror = (e) => {
    micStatus.textContent = `Mic: ${e.error}. Try typing instead.`;
    micBtn.classList.remove('listening');
  };
  recognition.onend = () => {
    micBtn.classList.remove('listening');
    micStatus.textContent = '';
  };

  micBtn.addEventListener('click', () => {
    if (micBtn.classList.contains('listening')) recognition.stop();
    else {
      try { recognition.lang = LANGS[langIdx].code; recognition.start(); }
      catch (e) { micStatus.textContent = 'Mic busy — try again.'; }
    }
  });
} else {
  micBtn.disabled = true;
  micBtn.title = 'Voice not supported in this browser (try Chrome / Edge)';
  micBtn.style.opacity = 0.4;
  micBtn.style.cursor = 'not-allowed';
}

// =================================================================== utils
function escapeHTML (str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function wait (ms) { return new Promise(r => setTimeout(r, ms)); }

// Strip protocol / trailing slash so the link reads like a clean domain.
function prettyURL (url) {
  if (!url || url === '#') return 'official government portal';
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

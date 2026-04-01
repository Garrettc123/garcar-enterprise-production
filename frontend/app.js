/* ═══════════════ GARCAR ENTERPRISE — FRONTEND APP ═══════════════ */

// Production API URL — update this when backend is deployed
const API_URLS = {
  local: 'http://localhost:8000',
  production: window.API_BASE || 'https://garcar-api.onrender.com'
};
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? API_URLS.local
  : API_URLS.production;

// ── State ──
let currentUser = null;
let authToken = null;

// ── Navigation ──
function showPage(page) {
  const pages = ['landing', 'login', 'register', 'dashboard', 'docs'];
  pages.forEach(p => {
    const el = document.getElementById('page-' + p);
    if (el) el.style.display = (p === page) ? '' : 'none';
  });

  // Show/hide footer on dashboard
  const footer = document.getElementById('main-footer');
  if (footer) footer.style.display = page === 'dashboard' ? 'none' : '';

  // Scroll to top
  window.scrollTo(0, 0);

  // If going to dashboard, load data
  if (page === 'dashboard' && currentUser) {
    loadDashboard();
  }
}

function toggleMobileNav() {
  document.getElementById('nav-links').classList.toggle('open');
  // Move auth actions too
  const actions = document.querySelector('.nav-actions');
  if (actions) actions.classList.toggle('open');
}

function updateAuthUI() {
  const guest = document.getElementById('nav-auth-guest');
  const user = document.getElementById('nav-auth-user');
  if (currentUser) {
    guest.style.display = 'none';
    user.style.display = 'flex';
  } else {
    guest.style.display = 'flex';
    user.style.display = 'none';
  }
}

// ── API Helpers ──
async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (authToken) headers['Authorization'] = 'Bearer ' + authToken;

  const res = await fetch(API + path, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

// ── Auth ──
async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('reg-btn');
  const errEl = document.getElementById('reg-error');
  errEl.textContent = '';
  btn.classList.add('loading');

  try {
    const data = await api('/api/auth/register', {
      method: 'POST',
      body: {
        name: document.getElementById('reg-name').value,
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-pass').value,
      },
    });
    authToken = data.access_token;
    currentUser = data.user;
    updateAuthUI();
    showPage('dashboard');
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.classList.remove('loading');
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  errEl.textContent = '';
  btn.classList.add('loading');

  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: {
        email: document.getElementById('login-email').value,
        password: document.getElementById('login-pass').value,
      },
    });
    authToken = data.access_token;
    currentUser = data.user;
    updateAuthUI();
    showPage('dashboard');
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.classList.remove('loading');
  }
}

function logout() {
  currentUser = null;
  authToken = null;
  updateAuthUI();
  showPage('landing');
}

// ── Lead Capture ──
async function captureLead(e) {
  e.preventDefault();
  const resultEl = document.getElementById('lead-result');
  try {
    await api('/api/leads/capture', {
      method: 'POST',
      body: {
        email: document.getElementById('lead-email').value,
        name: document.getElementById('lead-name').value || null,
        source: 'landing_page',
      },
    });
    resultEl.textContent = 'You\'re in. Check your email for API access.';
    resultEl.style.color = 'var(--color-success)';
  } catch (err) {
    resultEl.textContent = err.message;
    resultEl.style.color = 'var(--color-error)';
  }
}

// ── Checkout ──
async function startCheckout(plan) {
  if (!currentUser) {
    showPage('register');
    return;
  }
  try {
    const data = await api('/api/payments/create-checkout', {
      method: 'POST',
      body: { plan },
    });
    if (data.checkout_url) {
      window.open(data.checkout_url, '_blank');
    }
  } catch (err) {
    alert('Checkout error: ' + err.message + '\n\nStripe may not be configured yet.');
  }
}

// ── Dashboard ──
function showDashTab(tab) {
  const tabs = ['overview', 'dealdesk', 'seo', 'churn', 'apikeys'];
  tabs.forEach(t => {
    const el = document.getElementById('tab-' + t);
    if (el) el.style.display = (t === tab) ? '' : 'none';
  });
  // Update nav
  document.querySelectorAll('.dash-nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.tab === tab);
  });
  // Update title
  const titles = { overview: 'Overview', dealdesk: 'AI Deal Desk', seo: 'SEO Content Factory', churn: 'Churn Predictor', apikeys: 'API Keys' };
  document.getElementById('dash-title').textContent = titles[tab] || 'Dashboard';
}

async function loadDashboard() {
  if (!currentUser) return;

  document.getElementById('dash-user-name').textContent = currentUser.name;
  document.getElementById('api-key-display').textContent = currentUser.api_key;

  const planNames = { free: 'Free Plan', starter: 'Starter Plan', professional: 'Professional Plan', enterprise: 'Enterprise Plan' };
  document.getElementById('kpi-plan').textContent = planNames[currentUser.plan] || currentUser.plan;
  document.getElementById('dash-plan-info').querySelector('.dash-plan-name').textContent = planNames[currentUser.plan] || currentUser.plan;

  // Load usage
  try {
    const usage = await api('/api/products/usage');
    const u = usage.usage;
    document.getElementById('kpi-deals').textContent = `${u.deal_desk.used} / ${u.deal_desk.limit}`;
    document.getElementById('kpi-seo').textContent = `${u.seo_factory.used} / ${u.seo_factory.limit}`;
    document.getElementById('kpi-churn').textContent = `${u.churn_predictor.used} / ${u.churn_predictor.limit}`;
  } catch (err) {
    console.error('Usage load error:', err);
  }
}

// ── Product: Deal Desk ──
async function analyzeDeal(e) {
  e.preventDefault();
  const btn = document.getElementById('dd-btn');
  const panel = document.getElementById('dd-result');
  btn.classList.add('loading');

  try {
    const data = await api('/api/products/deal-desk/analyze', {
      method: 'POST',
      body: {
        company_name: document.getElementById('dd-company').value,
        deal_size: parseFloat(document.getElementById('dd-size').value) || null,
        stage: document.getElementById('dd-stage').value,
        notes: document.getElementById('dd-notes').value || null,
      },
    });

    const gradeClass = `grade-${data.grade.toLowerCase()}`;
    panel.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--space-4);margin-bottom:var(--space-4)">
        <div class="grade-badge ${gradeClass}">${data.grade}</div>
        <div>
          <h4 style="margin:0">${data.company}</h4>
          <span class="result-label">Score: ${data.score}/100 — ${data.win_probability} win probability</span>
        </div>
      </div>
      <div class="result-grid">
        <div><span class="result-label">Stage:</span> ${data.stage}</div>
        <div><span class="result-label">Deal Size:</span> $${(data.deal_size || 0).toLocaleString()}</div>
        <div><span class="result-label">Est. Close:</span> ${data.estimated_close_days} days</div>
        <div><span class="result-label">Usage:</span> ${data.usage.used}/${data.usage.limit}</div>
      </div>
      <h4>Recommended Actions</h4>
      <ul class="result-list">${data.recommended_actions.map(a => `<li>${a}</li>`).join('')}</ul>
    `;
    panel.classList.add('visible');
    loadDashboard();
  } catch (err) {
    panel.innerHTML = `<p style="color:var(--color-error)">${err.message}</p>`;
    panel.classList.add('visible');
  } finally {
    btn.classList.remove('loading');
  }
}

// ── Product: SEO Factory ──
async function generateSEO(e) {
  e.preventDefault();
  const btn = document.getElementById('seo-btn');
  const panel = document.getElementById('seo-result');
  btn.classList.add('loading');

  try {
    const keywords = document.getElementById('seo-keywords').value
      .split(',').map(k => k.trim()).filter(Boolean);

    const data = await api('/api/products/seo-factory/generate', {
      method: 'POST',
      body: {
        topic: document.getElementById('seo-topic').value,
        keywords: keywords.length ? keywords : null,
        tone: document.getElementById('seo-tone').value,
        word_count: parseInt(document.getElementById('seo-words').value) || 800,
      },
    });

    const c = data.content;
    panel.innerHTML = `
      <h4>${c.title}</h4>
      <div class="result-grid">
        <div><span class="result-label">SEO Score:</span> <span class="result-value">${c.seo_score}/100</span></div>
        <div><span class="result-label">Readability:</span> <span class="result-value">${c.readability_score}/100</span></div>
        <div><span class="result-label">Slug:</span> <code>/${c.slug}</code></div>
        <div><span class="result-label">Words:</span> ${c.estimated_word_count}</div>
      </div>
      <p style="margin:var(--space-3) 0"><span class="result-label">Meta:</span> ${c.meta_description}</p>
      <h4 style="margin-top:var(--space-4)">Content Outline</h4>
      <ul class="result-list">${c.outline.map(s => `<li><strong>${s.h2}</strong> (~${s.word_count} words)</li>`).join('')}</ul>
      <p style="margin-top:var(--space-3)"><span class="result-label">Keywords:</span> ${c.target_keywords.join(', ')}</p>
    `;
    panel.classList.add('visible');
    loadDashboard();
  } catch (err) {
    panel.innerHTML = `<p style="color:var(--color-error)">${err.message}</p>`;
    panel.classList.add('visible');
  } finally {
    btn.classList.remove('loading');
  }
}

// ── Product: Churn Predictor ──
async function predictChurn(e) {
  e.preventDefault();
  const btn = document.getElementById('ch-btn');
  const panel = document.getElementById('ch-result');
  btn.classList.add('loading');

  try {
    const data = await api('/api/products/churn-predictor/predict', {
      method: 'POST',
      body: {
        customer_id: document.getElementById('ch-id').value,
        monthly_spend: parseFloat(document.getElementById('ch-spend').value) || null,
        days_since_login: parseInt(document.getElementById('ch-days').value) || null,
        support_tickets: parseInt(document.getElementById('ch-tickets').value) || null,
        feature_usage_pct: parseFloat(document.getElementById('ch-usage').value) || null,
      },
    });

    const riskClass = `risk-${data.risk_level}`;
    panel.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--space-4);margin-bottom:var(--space-4)">
        <div class="grade-badge ${data.risk_level === 'critical' ? 'grade-d' : data.risk_level === 'medium' ? 'grade-c' : 'grade-a'}">${data.churn_risk_pct}%</div>
        <div>
          <h4 style="margin:0">Customer: ${data.customer_id}</h4>
          <span class="result-label ${riskClass}">Risk Level: ${data.risk_level.toUpperCase()}</span>
        </div>
      </div>
      <h4>Risk Factors</h4>
      <div class="result-grid">
        <div><span class="result-label">Login Recency:</span> <span class="${data.factors.login_recency === 'high_risk' ? 'risk-critical' : 'risk-low'}">${data.factors.login_recency}</span></div>
        <div><span class="result-label">Support Load:</span> <span class="${data.factors.support_load === 'high_risk' ? 'risk-critical' : 'risk-low'}">${data.factors.support_load}</span></div>
        <div><span class="result-label">Feature Adoption:</span> <span class="${data.factors.feature_adoption === 'low' ? 'risk-critical' : 'risk-low'}">${data.factors.feature_adoption}</span></div>
        <div><span class="result-label">Revenue at Risk:</span> ${data.factors.revenue_risk}</div>
      </div>
      <h4>Retention Playbook</h4>
      <ul class="result-list">${data.recommended_actions.map(a => `<li>${a}</li>`).join('')}</ul>
    `;
    panel.classList.add('visible');
    loadDashboard();
  } catch (err) {
    panel.innerHTML = `<p style="color:var(--color-error)">${err.message}</p>`;
    panel.classList.add('visible');
  } finally {
    btn.classList.remove('loading');
  }
}

// ── Utilities ──
function copyApiKey() {
  const key = document.getElementById('api-key-display').textContent;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(key).then(() => alert('API key copied'));
  } else {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = key;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    alert('API key copied');
  }
}

// ── Init ──
(function init() {
  updateAuthUI();
  showPage('landing');
})();

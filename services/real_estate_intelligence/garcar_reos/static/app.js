'use strict';
// API and approver credentials are session-memory only; never localStorage or URL params.
let apiKey = '', approverKey = '', selectedCase = null;
const $ = id => document.getElementById(id);
const n = (tag, text, cls) => { const el = document.createElement(tag); if(text!==undefined) el.textContent = String(text); if(cls) el.className=cls; return el; };
const clear = el => el.replaceChildren();
const msg = (text, error=false) => {const el=$('notice');el.hidden=false;el.textContent=text;el.className=error?'notice error':'notice';};
const money = val => val === null || val === undefined ? '—' : Number(val).toLocaleString('en-US',{style:'currency',currency:'USD'});
async function call(path,options={}){
  if(!apiKey) throw Error('Connect an API key first.');
  const headers={'X-API-Key':apiKey};
  if(options.body!==undefined) headers['Content-Type']='application/json';
  if(options.approver){if(!approverKey) throw Error('Separate approver key required. Open Connect API key to provide it.');headers['X-Approver-Key']=approverKey;}
  const res=await fetch(path,{method:options.method||'GET',headers,body:options.body===undefined?undefined:JSON.stringify(options.body),cache:'no-store'});
  let body; try{body=await res.json();}catch{throw Error('API returned an invalid response');}
  if(!res.ok){const details=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail||body);throw Error(`${res.status}: ${details}`);}
  return body;
}
const formObj = form => Object.fromEntries(new FormData(form).entries());
function safeHandle(fn){return async e=>{try{await fn(e);}catch(err){msg(err.message||String(err),true);}};}
function nav(view){
 document.querySelectorAll('.view').forEach(v=>v.hidden=(v.id!==`view-${view}`));
 document.querySelectorAll('.nav').forEach(btn=>btn.classList.toggle('active',btn.dataset.view===view));
}
document.querySelectorAll('.nav').forEach(btn=>btn.addEventListener('click',()=>nav(btn.dataset.view)));
$('connectBtn').addEventListener('click',()=>$('authDialog').showModal());
$('saveAuth').addEventListener('click',safeHandle(async e=>{
 e.preventDefault();const key=$('apiKey').value.trim();if(key.length<24)throw Error('API key must contain at least 24 characters.');
 const old=apiKey;apiKey=key;approverKey=$('approverKey').value.trim();
 try{await call('/v1/portfolio');}catch(err){apiKey=old;throw err;}
 $('apiKey').value='';$('approverKey').value='';$('authDialog').close();
 $('authState').textContent='API connected';$('authState').classList.add('connected');
 await refreshAll();msg('Connected. No credentials have been saved to browser storage.');
}));
async function refreshAll(){await Promise.all([refreshOverview(),refreshCases(),refreshProposals(),refreshSources()]);}
async function refreshOverview(){
 const [metric,tasks,revenue]=await Promise.all([call('/v1/portfolio'),call('/v1/tasks/due'),call('/v1/revenue/summary')]);
 $('mCases').textContent=metric.case_count;$('mApproved').textContent=metric.research_approved;
 $('mProposals').textContent=metric.agent_proposals.pending||0;
 $('mReceipts').textContent=revenue.verified_signed_live_receipts.reduce((a,r)=>a+r.payment_events,0);
 const p=$('pipeline');clear(p);for(const [stage,count] of Object.entries(metric.phases)){
   const row=n('div',undefined,'pipeline-row');row.append(n('span',stage.replaceAll('_',' ')));
   const bar=n('div',undefined,'bar');const fill=n('span');fill.style.width=`${Math.min(100,100*count/Math.max(1,metric.case_count))}%`;bar.append(fill);row.append(bar,n('b',count));p.append(row);
 }
 const t=$('dueTasks');clear(t);if(!tasks.length)t.append(n('p','No due tasks recorded.','muted'));
 for(const task of tasks.slice(0,12)){const item=n('div',undefined,'record');item.append(n('strong',task.title),n('small',`${task.priority} · ${task.assigned_to} · due ${new Date(task.due_at).toLocaleString()}`));t.append(item);}
}
async function refreshCases(){
 const cases=await call('/v1/cases?limit=100'),box=$('caseList');clear(box);
 if(!cases.length)box.append(n('p','No property cases. Use manual intake or review an agent proposal.','muted'));
 for(const c of cases){const btn=n('button',undefined,'case-button');btn.type='button';btn.append(n('strong',`${c.street_address} · ${c.city}, ${c.state}`),n('small',`${c.county} County · ${money(c.asking_price)} asking · ${c.review_status}`));if(c.id===selectedCase)btn.classList.add('selected');btn.addEventListener('click',safeHandle(async()=>{selectedCase=c.id;await loadDossier();}));box.append(btn);}
 if(selectedCase&&cases.some(c=>c.id===selectedCase))await loadDossier();
}
async function loadDossier(){
 if(!selectedCase)return;const d=await call(`/v1/cases/${encodeURIComponent(selectedCase)}/dossier`);
 $('dossierPanel').hidden=false;$('dossierHeading').textContent=`${d.case.street_address} • Dossier`;
 const s=$('dossierSummary');clear(s);for(const value of [`Phase: ${d.phase.phase.replaceAll('_',' ')}`,`Research: ${d.case.review_status}`,`Asking: ${money(d.case.asking_price)}`,`Diligence: ${d.checklist.complete?'Completed':'Incomplete'}`])s.append(n('span',value));
 const evidence=$('caseEvidence');clear(evidence);
 if(!d.evidence.length)evidence.append(n('p','No evidence records yet.','muted'));
 for(const ev of d.evidence){const item=n('div',undefined,'record');item.append(n('strong',ev.field),n('small',ev.note));const a=n('a','Open source');a.href=ev.source_url;a.rel='noopener noreferrer';a.target='_blank';item.append(a);evidence.append(item);}
 const u=$('caseUnderwriting');clear(u);
 if(!d.underwriting)u.append(n('p','No screening calculation yet.','muted'));
 else{const r=d.underwriting.result;for(const [k,v] of [['Maximum offer',r.maximum_allowable_offer],['Headroom vs asking',r.headroom_vs_asking],['Estimated buyer profit',r.estimated_buyer_profit_at_asking]]){const i=n('div',undefined,'record');i.append(n('strong',k),n('small',money(v)));u.append(i);}}
 const c=$('caseChecklist');clear(c);const options=$('checkKey');clear(options);
 for(const x of d.checklist.items){const i=n('div',undefined,'record');i.append(n('strong',x.key.replaceAll('_',' ')),n('small',`${x.status} · ${x.fresh_pass?'current operator-reviewed source':'requires review'}`));c.append(i);const opt=n('option',x.key.replaceAll('_',' '));opt.value=x.key;options.append(opt);}
 const phase=$('casePhase');clear(phase);phase.append(n('div',`Current phase: ${d.phase.phase}`,'record'));
 const targets=$('phaseTarget');clear(targets);for(const target of d.phase.allowed_next){const opt=n('option',target.replaceAll('_',' '));opt.value=target;targets.append(opt);}
 const tasks=$('caseTasks');clear(tasks);for(const task of d.tasks){const i=n('div',undefined,'record');i.append(n('strong',task.title),n('small',`${task.status} • ${task.priority} • ${new Date(task.due_at).toLocaleDateString()}`));tasks.append(i);}
 if(!d.tasks.length)tasks.append(n('p','No tasks scheduled.','muted'));
 $('dossierPanel').scrollIntoView({block:'start',behavior:'smooth'});
}
$('refreshCases').addEventListener('click',safeHandle(refreshCases));$('reloadDossier').addEventListener('click',safeHandle(loadDossier));
$('newCaseForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();const form=e.target;const data=formObj(form);data.observed_at=new Date().toISOString();
 const r=await call('/v1/cases',{method:'POST',body:data});selectedCase=r.id;form.reset();msg('Property research case added; source not independently verified.');await Promise.all([refreshCases(),refreshOverview()]);
}));
$('evidenceForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();if(!selectedCase)return;const data=formObj(e.target);data.observed_at=new Date().toISOString();if(!data.reviewed_by)delete data.reviewed_by;
 await call(`/v1/cases/${selectedCase}/evidence`,{method:'POST',body:data});e.target.reset();msg('Source evidence recorded.');await loadDossier();
}));
$('underwriteForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();if(!selectedCase)return;const data=formObj(e.target);data.selling_cost_rate=String(Number(data.selling_cost_pct)/100);delete data.selling_cost_pct;
 await call(`/v1/cases/${selectedCase}/underwrite`,{method:'POST',body:data});msg('Screening calculation saved. Figures remain assumption-driven.');await loadDossier();
}));
$('checkForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();if(!selectedCase)return;const data=formObj(e.target);if(!data.evidence_url)delete data.evidence_url;
 await call(`/v1/cases/${selectedCase}/checklist`,{method:'PUT',body:data});msg('Diligence checklist updated.');await loadDossier();
}));
$('phaseForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();if(!selectedCase)return;const data=formObj(e.target);if(!data.external_record_url)delete data.external_record_url;
 const approved=['offer_review','under_contract','closed'].includes(data.target);
 await call(`/v1/cases/${selectedCase}/phase`,{method:'POST',body:data,approver:approved});msg(`Tracking stage changed to ${data.target}. No external transaction executed.`);
 await Promise.all([loadDossier(),refreshOverview()]);
}));
$('taskForm').addEventListener('submit',safeHandle(async e=>{
 e.preventDefault();if(!selectedCase)return;const data=formObj(e.target);const dt=new Date(data.due_at);if(Number.isNaN(dt.getTime()))throw Error('Enter a valid due date');data.due_at=dt.toISOString();
 await call(`/v1/cases/${selectedCase}/tasks`,{method:'POST',body:data});e.target.reset();msg('Task recorded; no notifications sent.');await Promise.all([loadDossier(),refreshOverview()]);
}));
async function refreshProposals(){
 const data=await call('/v1/agent-proposals'),box=$('proposalList');clear(box);
 if(!data.length)box.append(n('p','No agent proposals recorded.','muted'));
 for(const item of data){const el=n('div',undefined,'record');el.append(n('strong',`${item.property.street_address} · ${item.property.city}`),n('small',`${item.status} · ${item.agent_id} · ${item.research_rationale}`));
 const a=n('a','Original source');a.href=item.property.source_url;a.target='_blank';a.rel='noopener noreferrer';el.append(a);
 if(item.status==='pending'){for(const choice of ['accept','reject']){const b=n('button',choice==='accept'?'Accept research case':'Reject','btn small secondary');b.addEventListener('click',safeHandle(async()=>{
   const rationale=window.prompt('Enter a documented reason for this decision (12+ characters):');if(rationale===null)return;
   await call(`/v1/agent-proposals/${item.id}/decision`,{method:'POST',approver:true,body:{decision:choice,reviewer:'Authorized REOS operator',rationale}});
   msg('Proposal review decision recorded.');await Promise.all([refreshProposals(),refreshCases(),refreshOverview()]);
 }));el.append(b);}}
 box.append(el);}
}
$('refreshProposals').addEventListener('click',safeHandle(refreshProposals));
async function refreshSources(){const data=await call('/v1/sources'),box=$('sourceList');clear(box);for(const item of data){const r=n('div',undefined,'record');const a=n('a',item.name);a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';r.append(a,n('small',`${item.region} · ${item.kind}`),n('small',item.limitations));box.append(r);}}

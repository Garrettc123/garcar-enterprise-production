from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from garcar_reos.api import create_app
from garcar_reos.operations import REQUIRED_DILIGENCE

KEY="operator-key-for-integration-testing-2026"
APPROVER="independent-approver-integration-test"
AGENT="agent-private-credential-for-testing"

@pytest.fixture
def api(monkeypatch,tmp_path):
    monkeypatch.setenv("REOS_API_KEY",KEY)
    monkeypatch.setenv("REOS_APPROVER_KEY",APPROVER)
    monkeypatch.setenv("REOS_AGENT_KEY",AGENT)
    monkeypatch.setenv("REOS_DB_PATH",str(tmp_path/"ops.sqlite"))
    with TestClient(create_app()) as c:
        yield c

def auth(approved=False,agent=False):
    h={"x-api-key":KEY}
    if approved: h["x-approver-key"]=APPROVER
    if agent: h["x-agent-key"]=AGENT
    return h

def property_payload(number="234"):
    return {"street_address":number+" Commerce St","city":"Cleburne","state":"TX","county":"Johnson",
            "postal_code":"76033","property_type":"single_family","asking_price":"105000",
            "source_url":"https://johnsoncad.com/property-search/",
            "observed_at":datetime.now(timezone.utc).isoformat()}

def new_case(api):
    response=api.post('/v1/cases',json=property_payload(),headers=auth())
    assert response.status_code==201,response.text
    return response.json()['id']

def underwriting():
    return {"arv":"200000","repairs":"20000","closing_costs":"4000","holding_costs":"2500",
            "financing_costs":"3000","reserve":"6000","buyer_target_profit":"15000",
            "proposed_assignment_fee":"5000","selling_cost_rate":"0.08"}

def test_navigation_dashboard_safeguards(api):
    assert api.get('/dashboard').status_code==200
    assert 'script-src' in api.get('/dashboard').headers['content-security-policy']
    assert api.get('/assets/app.js').status_code==200
    assert api.get('/v1/portfolio').status_code==401
    r=api.get('/v1/sources',headers=auth());assert r.status_code==200
    assert any(i['id']=='johnson_cad' for i in r.json())
    assert api.get('/v1/portfolio',headers=auth()).json()['case_count']==0
    assert api.get('/v1/revenue/summary',headers=auth()).json()['verified_signed_live_receipts']==[]

def test_agent_review_and_duplicate_accept(api):
    proposal={'agent_id':'rhns-property-source-agent','property':property_payload(),
              'research_rationale':'The operator should review this dated public-record entry before decisions.'}
    assert api.post('/v1/agent-proposals',json=proposal,headers=auth()).status_code==403
    r=api.post('/v1/agent-proposals',json=proposal,headers=auth(agent=True))
    assert r.status_code==202,r.text
    id=r.json()['id']
    assert api.get('/v1/agent-proposals?status=pending',headers=auth()).json()[0]['id']==id
    decision={'decision':'accept','reviewer':'Human reviewer','rationale':'Source and duplicate checks are planned.'}
    assert api.post(f'/v1/agent-proposals/{id}/decision',json=decision,headers=auth()).status_code==403
    r=api.post(f'/v1/agent-proposals/{id}/decision',json=decision,headers=auth(approved=True))
    assert r.status_code==200,r.text
    cid=r.json()['case_id']
    assert api.get(f'/v1/cases/{cid}/phase',headers=auth()).json()['phase']=='intake'
    assert api.post(f'/v1/agent-proposals/{id}/decision',json=decision,headers=auth(approved=True)).status_code==409
    assert api.get('/v1/portfolio',headers=auth()).json()['case_count']==1
    assert api.get('/v1/audit/verify',headers=auth()).json()['valid']

def test_workflow_diligence_tasks_and_drafts(api):
    cid=new_case(api)
    url=f'/v1/cases/{cid}'
    def stage(target,approved=False,extra=None):
        data={"target":target,"actor":"Operations manager","rationale":"Reviewed case facts and documented current progress"}
        data.update(extra or {})
        return api.post(url+'/phase',json=data,headers=auth(approved))
    assert stage('qualified').status_code==409
    assert stage('research').status_code==200
    assert stage('offer_review',True).status_code==409
    uw=api.post(url+'/underwrite',json=underwriting(),headers=auth());assert uw.status_code==201
    assert uw.json()['result']['maximum_allowable_offer']=='120000.00'
    for key in ['asking_price','arv','repairs','ownership']:
        resp=api.post(url+'/evidence',headers=auth(),json={
            'field':key,'source_url':'https://johnsoncad.com/property-search/',
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'note':'Manual source review recorded','reviewed_by':'Operations manager'})
        assert resp.status_code==201,resp.text
    approval={"decision":"approve_research","reviewer":"Operations manager","rationale":"Four evidence categories independently reviewed"}
    assert api.post(url+'/research-decision',headers=auth(approved=True),json=approval).status_code==201
    assert stage('qualified').status_code==200
    assert stage('diligence').status_code==200
    for key in REQUIRED_DILIGENCE:
        update={"key":key,"status":"passed","evidence_url":"https://www.johnsoncountytx.org/government/county-clerk/online-records",
                "reviewed_by":"Operations manager","note":"Human review documented but not an independent professional conclusion"}
        assert api.put(url+'/checklist',json=update,headers=auth()).status_code==200
    assert api.get(url+'/checklist',headers=auth()).json()['complete']
    assert stage('offer_review').status_code==403
    assert stage('offer_review',True).status_code==200
    assert stage('under_contract',True).status_code==409
    assert stage('under_contract',True,{'external_record_url':'https://www.johnsoncountytx.org/'}).status_code==200
    assert stage('closed',True).status_code==409
    future=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    task={"title":"Confirm recorded deed status","assigned_to":"Operations manager", "due_at":future}
    r=api.post(url+'/tasks',json=task,headers=auth())
    assert r.status_code==201,r.text
    task_id=r.json()['id'];assert api.get('/v1/tasks/due',headers=auth()).json()[0]['id']==task_id
    assert api.patch('/v1/tasks/'+task_id,json={'status':'done','actor':'Operations manager'},headers=auth()).status_code==200
    assert not api.get('/v1/tasks/due',headers=auth()).json()
    draft={"audience":"buyer","channel":"email","subject":"Private investor diligence",
           "content":"We can discuss these details after your independent diligence review.","prepared_by":"Operations manager"}
    assert api.post(url+'/drafts',json=draft,headers=auth()).status_code==201
    dossier=api.get(url+'/dossier',headers=auth()).json()
    assert dossier['drafts'][0]['status']=='unsent_draft'
    assert dossier['execution_enabled'] is False
    assert api.get('/v1/audit/verify',headers=auth()).json()['valid']

def test_reject_agent_proposal_never_ingests_case(api):
    proposal={'agent_id':'rhns-source-proposal','property':property_payload('775'),
              'research_rationale':'Research source appears incomplete; do not proceed.'}
    r=api.post('/v1/agent-proposals',json=proposal,headers=auth(agent=True));assert r.status_code==202
    url=f"/v1/agent-proposals/{r.json()['id']}/decision"
    resp=api.post(url,json={'decision':'reject','reviewer':'Quality manager',
           'rationale':'No reliable source for ownership verification'},headers=auth(approved=True))
    assert resp.status_code==200
    assert api.get('/v1/portfolio',headers=auth()).json()['case_count']==0

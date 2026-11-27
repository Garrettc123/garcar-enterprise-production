import hashlib,hmac,json,time
from fastapi.testclient import TestClient
from garcar_reos.api import create_app

def test_signed_stripe_webhook_dedup_and_reject(monkeypatch,tmp_path):
    secret='whsec_valid_very_long_fake_key_for_tests_only'
    monkeypatch.setenv('REOS_STRIPE_WEBHOOK_SECRET',secret)
    monkeypatch.setenv('REOS_API_KEY','operator-testing-key-with-long-entropy')
    monkeypatch.setenv('REOS_DB_PATH',str(tmp_path/'receipts.sqlite'))
    with TestClient(create_app()) as c:
        event={'id':'evt_test_realistic_format','type':'payment_intent.succeeded','livemode':True,
               'created':int(time.time()),'data':{'object':{'id':'pi_test_receipt','object':'payment_intent',
                'amount_received':49700,'currency':'usd','metadata':{'reos_product':'real_estate_intelligence'}}}}
        body=json.dumps(event).encode()
        ts=int(time.time())
        signature=hmac.new(secret.encode(),f'{ts}.'.encode()+body,hashlib.sha256).hexdigest()
        h={'stripe-signature':f't={ts},v1={signature}'}
        assert c.post('/integrations/stripe/webhook',content=body).status_code==400
        assert c.post('/integrations/stripe/webhook',content=body,headers={**h,'stripe-signature':f't={ts},v1=deadbeef'}).status_code==400
        first=c.post('/integrations/stripe/webhook',content=body,headers=h)
        assert first.status_code==200,first.text
        assert first.json()['duplicate'] is False
        again=c.post('/integrations/stripe/webhook',content=body,headers=h)
        assert again.status_code==200 and again.json()['duplicate'] is True
        summary=c.get('/v1/revenue/summary',headers={'x-api-key':'operator-testing-key-with-long-entropy'}).json()
        assert summary['verified_signed_live_receipts'][0]['gross_received']=='497.00'
        assert summary['account_net_payouts_verified'] is False

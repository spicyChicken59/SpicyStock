import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const { createClient } = createRequire(import.meta.url)('../docs/trade-bridge.js');
const config = {version:1,enabled:true,api_base:'/api',broker:'alpaca'};
const status = {version:1,state:'paper',connected:true,mode:'paper',csrf_token:'private-session-csrf'};
const response = (data, code=200, type='application/json') => ({ok:code<400,status:code,headers:{get:()=>type},json:async()=>data});
function setup(replies) {
  const calls=[], navigations=[];
  const client=createClient({location:{href:'https://example.test/SpicyStock/',assign:url=>navigations.push(url)},timeout:100,
    fetch:async(url,init)=>{calls.push({url,init});const value=replies.shift(); if (value instanceof Error) throw value; assert.ok(value,'unexpected request');return value;}});
  return {client,calls,navigations};
}
{
  const {client,calls}=setup([response({...config,enabled:false,api_base:null})]);
  assert.equal((await client.load()).data.enabled,false);
  assert.equal((await client.preview({symbol:'ABC'})).error.code,'TRADING_UNAVAILABLE');
  assert.equal((await client.connect()).error.code,'TRADING_UNAVAILABLE');
  assert.equal(calls.length,1);assert.equal(calls[0].url,'https://example.test/SpicyStock/trading-config.json');
}
for (const api_base of ['https://evil.test/api','//evil.test/api','/different']) {
  const {client,calls}=setup([response({...config,api_base})]);
  assert.equal((await client.load()).error.code,'INVALID_CONFIG');assert.equal(calls.length,1);
}
{
  const {client,calls,navigations}=setup([response(config),response(status),response({preview_id:'p1'}),new Error('dropped response'),response({state:'reconciliation_needed'})]);
  assert.equal((await client.status()).ok,true);
  assert.equal(client.getState().status.csrf_token,undefined);
  assert.equal((await client.preview({symbol:'ABC',limit_price:100,stop_price:95})).ok,true);
  assert.equal((await client.submit('p1')).error.code,'UNKNOWN_ORDER_STATE');
  assert.equal((await client.portfolio()).data.state,'reconciliation_needed');
  const posts=calls.filter(c=>c.init.method==='POST');assert.equal(posts.length,2);
  assert.equal(posts[1].url,'https://example.test/api/orders');
  assert.deepEqual(JSON.parse(posts[1].init.body),{preview_id:'p1',confirmation:'submit'});
  assert.equal(posts[1].init.headers['X-CSRF-Token'],'private-session-csrf');
  assert.ok(calls.every(c=>c.init.credentials==='same-origin'&&c.init.redirect==='error'&&c.init.cache==='no-store'));
  await client.connect('live');assert.deepEqual(navigations,['https://example.test/api/connect?mode=live']);
}
for (const bad of [response({},502),response({},200,'text/html'),{ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>{throw Error('malformed');}}]) {
  const {client,calls}=setup([response(config),response(status),bad]);
  await client.status();assert.equal((await client.submit('p')).error.code,'UNKNOWN_ORDER_STATE');assert.equal(calls.length,3);
}
{
  const {client,calls}=setup([response(config),response({...status,csrf_token:''})]);
  assert.equal((await client.status()).error.code,'INVALID_RESPONSE');
  assert.equal((await client.preview({})).error.code,'SESSION_REQUIRED');assert.equal(calls.length,2);
}
{
  const {client,calls}=setup([response(config),response(status),response({error:{code:'SESSION_EXPIRED',message:'Reconnect.'}},401)]);
  await client.status();assert.equal((await client.portfolio()).error.code,'SESSION_EXPIRED');
  assert.equal((await client.preview({})).error.code,'SESSION_REQUIRED');assert.equal(calls.length,3);
}
console.log('Broker client checks passed: same-origin configuration, CSRF, disabled mode, session expiry, and uncertain orders without retries.');

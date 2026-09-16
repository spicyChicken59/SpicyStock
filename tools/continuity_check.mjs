#!/usr/bin/env node
// DOM and store regressions, offline. JSDOM is not browser/layout acceptance.
import {JSDOM, VirtualConsole} from 'jsdom';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {gunzipSync} from 'node:zlib';
import {webcrypto} from 'node:crypto';
import assert from 'node:assert/strict';
import path from 'node:path';
const ROOT=path.resolve(import.meta.dirname,'..');
const baseline=process.argv.includes('--baseline');
const source=async file=>baseline?execFileSync('git',['show','0233b309a43d3c3f64d30ee974d2be15d1fcea28:'+file],{cwd:ROOT,encoding:'utf8'}):readFile(path.join(ROOT,file),'utf8');
const records={};for(const date of ['2026-09-11','2026-09-14']) records[date]=JSON.parse(gunzipSync(await readFile(path.join(ROOT,'tests/fixtures/continuity/'+date+'.json.gz'))));
let checks=0;function check(condition,message){assert.ok(condition,message);checks++;}
const pause=()=>new Promise(r=>setTimeout(r,15));
const hub=()=>({values:new Map(),windows:[],locks:new Map(),requests:[],fail:null});
async function open(data, shared=hub()) {
 const errors=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!/Not implemented.*(navigation|scrollTo)/i.test(e.message))errors.push(e.message);});
 const dom=new JSDOM(await source('docs/index.html'),{url:'https://stock.test/docs/index.html',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});const w=dom.window;
 shared.windows.push(w);
 const storage={get length(){return shared.values.size},key(i){return [...shared.values.keys()][i]??null},getItem(k){if(shared.fail==='read')throw Error('read blocked');return shared.values.get(k)??null},setItem(k,v){if(shared.fail==='write'||shared.fail==='quota'&&String(v).length>4000)throw Error('quota');if(shared.fail==='readback'&&!k.endsWith('.probe'))return;const old=shared.values.get(k)??null;shared.values.set(k,String(v));if(old!==String(v))setTimeout(()=>{for(const other of shared.windows)if(other!==w&&!other.closed)other.dispatchEvent(new other.StorageEvent('storage',{key:k,oldValue:old,newValue:String(v)}));},0)},removeItem(k){shared.values.delete(k)},clear(){shared.values.clear()}};
 Object.defineProperty(w,'localStorage',{value:storage});
 Object.defineProperty(w.navigator,'locks',{value:{request:async(name,fn)=>{const previous=shared.locks.get(name)||Promise.resolve();const next=previous.catch(()=>{}).then(fn);shared.locks.set(name,next);return next;}}});
 Object.defineProperty(w,'crypto',{value:webcrypto});w.TextDecoder=TextDecoder;w.TextEncoder=TextEncoder;
 w.matchMedia=()=>({matches:false,addListener(){},addEventListener(){}});w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.ResizeObserver=class{observe(){}disconnect(){}};w.IntersectionObserver=class{observe(){}disconnect(){}};
 w.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')};w.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open');this.dispatchEvent(new w.Event('close'))};
 w.fetch=async url=>{shared.requests.push(String(url));const u=new URL(url,w.location.href);if(u.host!=='stock.test')return {ok:false,json:async()=>({})};let body;
 if(u.pathname.endsWith('/data.json'))body=Buffer.from(JSON.stringify(data));else {try{body=await readFile(path.join(ROOT,u.pathname));}catch{return {ok:false,status:404}}}
 return {ok:true,status:200,text:async()=>body.toString(),json:async()=>JSON.parse(body),arrayBuffer:async()=>body.buffer.slice(body.byteOffset,body.byteOffset+body.byteLength)};
 };
 w.SCStock={now:'2026-09-14T23:00:00Z'};
 for(const f of ['docs/design-system/sc-charts.js','docs/app-chart.js','docs/app-map.js','docs/app-follow.js','docs/app.js']) w.eval(await source(f));
 await pause();await pause();
 check(!!w.SCStock.model,'app loaded with the real published record');
 return {w,dom,shared,errors,close(){shared.windows=shared.windows.filter(x=>x!==w);dom.window.close();}};
}
function click(w,selector){const node=w.document.querySelector(selector);check(!!node,'control exists: '+selector);node.click();return node;}
async function route(w,hash){w.SCStock.navigate(hash);await pause();}
async function render(w,data){w.SCStock.render(w.JSON.parse(JSON.stringify(data)),new w.Date('2026-09-14T23:00:00Z'));await pause();await pause();}
const {w,shared,errors,close}=await open(records['2026-09-11']);
try{
 for(const ticker of ['ATEC','VICR']) {await route(w,'#/explore/bursts/'+ticker);click(w,'#detail [data-follow-action="add"]');await pause();}
 let items=w.SCStock.follow.list();check(items.length===2,'both exact signals saved through detail controls');
 const original=JSON.stringify(items.map(i=>i.snapshot));
 await render(w,records['2026-09-14']);await route(w,'#/explore');
 check(!w.SCStock.model.byId['bursts:ATEC'],'ATEC absent from current candidates');check(w.SCStock.model.byId['bursts:VICR'].grade==='C','VICR later candidate is C');
 items=w.SCStock.follow.list();check(JSON.stringify(items.map(i=>i.snapshot))===original,'later record cannot rewrite original snapshots');
 check(items.find(i=>i.ticker==='ATEC').observations.at(-1).c===10.86,'ATEC observed at 10.86');check(items.find(i=>i.ticker==='VICR').observations.at(-1).c===184.73,'VICR row supplies 184.73 despite no observation entry');
 check(items.find(i=>i.ticker==='ATEC').evidence.series.length===120,'ATEC genuine original series retained');check(!items.find(i=>i.ticker==='VICR').evidence,'VICR original chart stays missing');
 if(baseline){if(process.argv.includes('--require-continuity'))check(!!w.document.querySelector('#nav [data-view="setups"]'),'My setups peer destination is missing in baseline');check(!w.document.querySelector('#nav [data-view="setups"]'),'baseline lacks prominent My setups destination');console.log(JSON.stringify({status:'PASS: baseline DOM reproduction; browser acceptance BLOCKED',checks,items:items.map(i=>({ticker:i.ticker,session:i.session,grade:i.snapshot.grade,latest:i.observations.at(-1).c}))}));process.exitCode=0;}
 else {
 check(!!w.document.querySelector('#nav [data-view="setups"]'),'My setups is a prominent peer destination');
 await route(w,'#/setups');check(!w.document.querySelector('#view-setups').hidden,'My setups route works');check(w.document.querySelectorAll('#following .ss-followed').length===2,'all saves visible independent of lens');
 const atec=items.find(i=>i.ticker==='ATEC');click(w,'[data-open-saved]');await pause();
 const amount=w.document.querySelector('#setup-amount');check(amount.value==='','amount starts unknown');amount.value='1234.56';amount.dispatchEvent(new w.Event('input'));w.document.querySelector('.ss-annotation').dispatchEvent(new w.Event('submit',{cancelable:true}));await pause();
 check(w.SCStock.follow.find(items[1].id).annotation.reference_amount.minor_units===123456,'USD stored as integer cents, synthetic amount only');
 click(w,'#setup-taken');await pause();check(w.SCStock.follow.find(items[1].id).annotation.taken===true,'optional indication stored');
 click(w,'#saved-close');await pause();check(w.location.hash==='#/setups','close returns to actual saved destination');
 // Multiple tabs: nonconflicting edits and serialized conflicts never overwrite the other item.
 const tab=await open(records['2026-09-14'],shared);
 await Promise.all([w.SCStock.follow.commit('setAnnotation',atec.id,'amount','80.01'),tab.w.SCStock.follow.commit('setAnnotation',items[1].id,'amount','90.02')]);
 check(w.SCStock.follow.find(atec.id).annotation.reference_amount.minor_units===8001,'tab A amount survives tab B');check(w.SCStock.follow.find(items[1].id).annotation.reference_amount.minor_units===9002,'tab B amount survives tab A');
 await Promise.all([w.SCStock.follow.commit('setAnnotation',atec.id,'amount','10.00'),tab.w.SCStock.follow.commit('setAnnotation',atec.id,'amount','20.00')]);check(w.SCStock.follow.find(atec.id).annotation.reference_amount.minor_units===2000,'conflict uses lock acquisition order');
 await Promise.all([w.SCStock.follow.commit('remove',atec.id),tab.w.SCStock.follow.commit('setAnnotation',atec.id,'amount','30.00')]);check(!w.SCStock.follow.find(atec.id),'stale edit cannot resurrect removed setup');tab.close();
 const f=w.SCStock.follow;for(const invalid of ['NaN','Infinity','-1','0','1.001','1e4','90071992547410.00'])check(!(await f.commit('setAnnotation',items[1].id,'amount',invalid)).ok,'invalid money refused: '+invalid);
 check((await f.commit('setAnnotation',items[1].id,'amount','')).ok,'clearing amount accepted');check(f.find(items[1].id).annotation.reference_amount===null,'cleared amount unknown');
 const before=shared.values.get(f.KEY);shared.fail='write';check(!(await f.commit('setAnnotation',items[1].id,'amount','55.00')).ok,'write failure reported');shared.fail=null;check(shared.values.get(f.KEY)===before,'prior valid payload survives write failure');
 shared.fail='readback';check(!(await f.commit('setAnnotation',items[1].id,'amount','55.00')).ok,'readback failure reported');shared.fail=null;check(shared.values.get(f.KEY)===before,'prior valid payload survives readback failure');
 check(JSON.stringify(w.SCStock.data)===JSON.stringify(records['2026-09-14']),'all annotations leave public source unchanged');
 // Start unsaved and recover through public controls, selecting the exact blob.
 shared.values.delete(f.KEY);await render(w,records['2026-09-14']);await route(w,'#/setups');
 const blob='2c5ec387654d2cea9d85b1230e91b4c7c0efb534';
 for(const ticker of ['ATEC','VICR']){
 w.document.querySelector('#history-ticker').value=ticker;w.document.querySelector('#history-search').dispatchEvent(new w.Event('submit',{cancelable:true}));await pause();await pause();
 click(w,'[data-history-inspect="'+blob+'"]');await pause();await pause();
 click(w,'[data-history-source="'+blob+'"] [data-history-save]');await pause();await pause();
 const found=f.list().find(i=>i.ticker===ticker);check(found?.session==='2026-09-11'&&found.snapshot.grade==='A','recovered exact original '+ticker);check(found.provenance.record_id===blob,'recovered provenance '+ticker);check(!found.annotation,'recovery does not seed personal annotations');
 click(w,'#saved-close');await pause();}
 check(f.list().length===2,'both originals saved from empty storage');
 check(!shared.requests.some(u=>/1234|80\.01|90\.02|amount|annotation/.test(u)),'no outbound private annotations');

 // Save from the candidate card, then comparison. A later VICR is separate.
 await route(w,'#/explore/bursts/VICR');click(w,'[data-save-setup="VICR"]');await pause();
 check(f.list().filter(i=>i.ticker==='VICR').length===2,'new same-ticker signal stays separate');
 const first=w.SCStock.model.stages.bursts[0],second=w.SCStock.model.stages.bursts[1];
 for(const c of [first,second]){await route(w,'#/explore/bursts/'+c.ticker);click(w,'#detail [data-pin]');}
 click(w,'#compare-open');const comparison=w.document.querySelector('#compare [data-follow-action="add"]');check(!!comparison,'comparison offers one-click save');comparison.click();await pause();
 check(f.list().some(i=>i.ticker===first.ticker),'comparison saves original through same store');click(w,'#compare-close');
 // Reload with the same storage, plus stale data and changed theme.
 const reloaded=await open(records['2026-09-14'],shared);check(reloaded.w.SCStock.follow.list().length===f.list().length,'saves survive reload');
 reloaded.w.document.documentElement.dataset.theme='light';await render(reloaded.w,records['2026-09-11']);check(reloaded.w.SCStock.follow.list().length===f.list().length,'theme/stale record preserve all saves');reloaded.close();
 // Existing v1/v2 values and unknown extension fields survive migration and edits.
 const legacyHub=hub();const legacy=JSON.parse(JSON.stringify(f.list()[0]));legacy.suggested_shares=17;legacy.reference_shares=5;legacy.extension={keep:true};delete legacy.annotation;legacy.v=2;
 const old=JSON.stringify({version:2,items:[legacy],future_optional:'retain'});legacyHub.values.set(f.KEY,old);legacyHub.values.set(f.KEY+'.previous','earlier-v1-backup');
 const migrated=await open(records['2026-09-14'],legacyHub);const mf=migrated.w.SCStock.follow;await mf.commit('migrate');
 check(mf.VERSION===3&&JSON.parse(legacyHub.values.get(f.KEY)).version===3,'v2 migrated in place to v3');check(legacyHub.values.get(f.KEY+'.previous')==='earlier-v1-backup'&&legacyHub.values.get(f.KEY+'.previous.v2')===old,'both legacy backups retained');
 await mf.commit('setAnnotation',legacy.id,'amount','1.23');const preserved=mf.find(legacy.id);check(preserved.suggested_shares===17&&preserved.reference_shares===5&&preserved.extension.keep,'share values and unknown fields unchanged');check(JSON.parse(legacyHub.values.get(f.KEY)).future_optional==='retain','unknown envelope fields unchanged');
 // Cross-tab refresh must retain unsaved input and focus.
 await route(migrated.w,'#/followed/'+encodeURIComponent(legacy.id));const draft=migrated.w.document.querySelector('#setup-amount');draft.value='44.77';draft.dispatchEvent(new migrated.w.Event('input'));draft.focus();
 const peer=await open(records['2026-09-14'],legacyHub);await peer.w.SCStock.follow.commit('setAnnotation',legacy.id,'taken',true);await pause();
 check(migrated.w.document.querySelector('#setup-amount').value==='44.77','cross-tab update preserves unsaved amount');check(migrated.w.document.activeElement.id==='setup-amount','cross-tab update preserves input focus');peer.close();migrated.close();
 const futureHub=hub(),future='{"version":99,"items":[]}';futureHub.values.set(f.KEY,future);const futureTab=await open(records['2026-09-14'],futureHub);
 check(!(await futureTab.w.SCStock.follow.commit('add',legacy)).ok&&futureHub.values.get(f.KEY)===future,'future store remains untouched');futureTab.close();
 const malformedHub=hub();malformedHub.values.set(f.KEY,'{bad');const malformed=await open(records['2026-09-14'],malformedHub);check(malformedHub.values.get(f.KEY+'.corrupt')==='{bad','malformed original backed up');malformed.close();
 const quotaHub=hub();const quota=await open(records['2026-09-11'],quotaHub);quotaHub.fail='quota';await route(quota.w,'#/explore/bursts/ATEC');click(quota.w,'#detail [data-follow-action="add"]');await pause();const lean=quota.w.SCStock.follow.list()[0];check(lean&&lean.evidence_dropped&&!lean.evidence,'quota fallback explicitly marks dropped chart');check(quota.w.document.querySelector('#detail .ss-follow').textContent.includes('chart'),'quota fallback disclosed in UI');quotaHub.fail=null;quota.close();
 // Unknown ticker never becomes a fabricated recommendation.
 await route(w,'#/setups');w.document.querySelector('#history-ticker').value='ZZZZZZ';w.document.querySelector('#history-search').dispatchEvent(new w.Event('submit',{cancelable:true}));await pause();
 check(!w.document.querySelector('[data-history-save]')&&w.document.querySelector('#history-results').textContent.includes('No retained published original'),'unknown original unavailable');
 // Newly published references freeze with originals; annotations stay private.
 const fresh=JSON.parse(await readFile(path.join(ROOT,'tests/fixtures/page/full.json'),'utf8'));
 const newTab=await open(fresh);await route(newTab.w,'#/explore/bursts/AAPL');
 click(newTab.w,'#detail [data-follow-action="add"]');await pause();
 const saved=newTab.w.SCStock.follow.list().find(i=>i.ticker==='AAPL');
 const publicIdentity=fresh.bursts.find(b=>b.ticker==='AAPL').evidence.id;
 check(saved.snapshot.evidence_ref.id===publicIdentity,'new saved original retains exact public evidence identity');
 const savedReference=JSON.stringify(saved.snapshot.evidence_ref), publicBytes=JSON.stringify(fresh);
 await newTab.w.SCStock.follow.commit('setAnnotation',saved.id,'taken',true);
 await newTab.w.SCStock.follow.commit('setAnnotation',saved.id,'amount','123.45');
 check(JSON.stringify(newTab.w.SCStock.follow.find(saved.id).snapshot.evidence_ref)===savedReference,'private annotations cannot alter evidence reference');
 check(JSON.stringify(fresh)===publicBytes,'private annotations never change publication');
 const revised=JSON.parse(await readFile(path.join(ROOT,'tests/fixtures/page/revised.json'),'utf8'));
 await render(newTab.w,revised);
 check(JSON.stringify(newTab.w.SCStock.follow.find(saved.id).snapshot.evidence_ref)===savedReference,'later publication retains original evidence reference');
 newTab.close();
 check(errors.length===0,'no DOM runtime errors: '+errors.join(';'));
 console.log(JSON.stringify({status:'PASS: offline DOM/store checks; not browser/layout acceptance',checks,requests:shared.requests.filter(u=>u.includes('history/'))}));
 }
} finally{close();}

"""Browser-local selection joins a published outcome; it never computes one."""
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = r"""
const fs=require('node:fs'),vm=require('node:vm');
const request=JSON.parse(fs.readFileSync(0,'utf8'));
const full=JSON.parse(fs.readFileSync('tests/fixtures/page/full.json'));
const next=JSON.parse(fs.readFileSync('tests/fixtures/page/next.json'));
const candidate=full.bursts.find(b=>full.trades.includes(b.ticker));
const setup={ticker:candidate.ticker,kind:'burst',stage:'bursts',session:full.run.session,
 rules_version:full.app.rules_version,provenance:{published_at:full.run.published_at},suggested_shares:candidate.plan.shares,
 snapshot:{status:'ticket',order_line:candidate.plan.order_line,evidence_ref:candidate.plan.evidence_ref,published_plan:{order_json:candidate.plan.order_json}}};
const values=new Map(),localStorage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
const window={SCStock:{},localStorage,navigator:{locks:{request:async(k,fn)=>fn()}},addEventListener(){}};
vm.runInNewContext(fs.readFileSync('docs/app-follow.js','utf8'),{window,Date,console});
const f=window.SCStock.follow;
(async()=>{
 if(request.case==='no_ticket') {setup.snapshot.status='withheld';console.log(JSON.stringify(await f.commit('selectPlan',setup,false)));return;}
 if(request.case==='future') {const raw=JSON.stringify({version:99,items:[]});values.set(f.KEY,raw);const result=await f.commit('selectPlan',setup,false);console.log(JSON.stringify({result,preserved:values.get(f.KEY)===raw}));return;}
 if(request.case==='legacy') {delete setup.snapshot.published_plan;delete setup.snapshot.evidence_ref;const added=await f.commit('add',setup);await f.commit('setAnnotation',added.item.id,'taken',true);const item=f.find(added.item.id);console.log(JSON.stringify({selection:f.selectedPlan(item),annotation:item.annotation}));return;}
 const selected=await f.commit('selectPlan',setup,false),id=selected.item.id;
 const row=next.open_plans.find(p=>p.ticker===candidate.ticker&&p.picked===full.run.session);
 if(request.case==='mismatch') {const changed=JSON.parse(JSON.stringify(row));changed.evidence_ref[request.field]='0'.repeat(64);console.log(JSON.stringify({original:f.matchesPlan(selected.item,row),changed:f.matchesPlan(selected.item,changed)}));return;}
 if(request.case==='same_ticker') {const other=JSON.parse(JSON.stringify(setup));other.session=next.run.session;other.snapshot.evidence_ref.id='0'.repeat(64);await f.commit('selectPlan',other,false);console.log(JSON.stringify({count:f.list().length,original:f.find(id).plan_selection,selected:selected.item.plan_selection}));return;}
 if(request.case==='removed') {await f.commit('remove',id);const result=await f.commit('selectPlan',selected.item,true);console.log(JSON.stringify({result,count:f.list().length}));return;}
 const update={id,row,from_session:next.run.session,published_at:next.run.published_at,rules_version:next.app.rules_version};
 await f.commit('observePlans',[update]);
 const saved=f.find(id).model_observation;
 if(request.case==='older') {const older=JSON.parse(JSON.stringify(update));older.published_at='2026-09-11T00:00:00Z';older.row.status='hold';await f.commit('observePlans',[older]);console.log(JSON.stringify({saved,after:f.find(id).model_observation}));return;}
 if(request.case==='references') {await f.commit('setShares',id,11);await f.commit('setAnnotation',id,'amount','41.20');await f.commit('selectPlan',setup,true);const item=f.find(id);console.log(JSON.stringify({selection:item.plan_selection,original:selected.item.plan_selection,snapshot:item.snapshot,expected:setup.snapshot,model:item.model_observation,saved,shares:item.reference_shares,amount:item.annotation.reference_amount.minor_units}));return;}
 throw Error('unknown case');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def run(case, **kw):
    result = subprocess.run(["node", "-e", RUNNER], input=json.dumps({"case": case, **kw}),
                            text=True, capture_output=True, cwd=ROOT, check=True, timeout=15)
    return json.loads(result.stdout)


@pytest.mark.parametrize("field", ["id", "context_sha256", "plan_sha256", "pick_sha256"])
def test_same_symbol_session_cannot_join_a_different_published_identity(field):
    assert run("mismatch", field=field) == {"original": True, "changed": False}


def test_legacy_take_annotation_is_not_upgraded_to_plan_selection():
    result = run("legacy")
    assert result["selection"] is None
    assert result["annotation"]["taken"] is True


def test_a_later_signal_for_the_same_ticker_remains_a_separate_selection():
    result = run("same_ticker")
    assert result["count"] == 2
    assert result["original"] == result["selected"]


def test_no_ticket_cannot_be_selected_as_a_published_plan():
    result = run("no_ticket")
    assert not result["ok"] and "no published ticket" in result["error"]


def test_old_publication_cannot_replace_cached_model_outcome():
    result = run("older")
    assert result["saved"] == result["after"]


def test_selection_and_reference_changes_leave_original_and_model_untouched():
    result = run("references")
    assert result["selection"] == result["original"]
    assert result["snapshot"] == result["expected"]
    assert result["model"] == result["saved"]
    assert (result["shares"], result["amount"]) == (11, 4120)


def test_removed_item_is_not_resurrected_by_a_stale_selection():
    result = run("removed")
    assert not result["result"]["ok"] and result["count"] == 0


def test_future_store_remains_untouched_by_plan_selection():
    result = run("future")
    assert not result["result"]["ok"] and result["preserved"]

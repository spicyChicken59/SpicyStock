/* Read-only isolated controls for the two guidance corrections.
   node tools/wait_explanation_controls.mjs --output /tmp/wait-controls
   --control reviewed|evaluation|planning|unrelated runs one control. */
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {execFileSync,spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..'),args=process.argv.slice(2);
const output=args.includes('--output')?path.resolve(args[args.indexOf('--output')+1]):'/tmp/wait-controls';
const only=args.includes('--control')?args[args.indexOf('--control')+1]:null;
const reviewed='2e4d0eca42d4df099069d4ca1d791402d58825d5';
const source=await readFile(path.join(root,'docs/app.js'),'utf8');
const old=execFileSync('git',['show',reviewed+':docs/app.js'],{cwd:root}).toString();
const sha=s=>createHash('sha256').update(s).digest('hex');
function replaceFunction(name,next,text) {
  const start=text.indexOf('  function '+name+'('),end=text.indexOf('\n  function '+next+'(',start);
  if(start<0||end<0) throw Error('Control function boundary missing');
  return text.slice(0,start)+replacements[name]+text.slice(end);
}
const replacements={
  evaluationExplanation:`  function evaluationExplanation(data, at) {
    const run=data.run||{};
    const cal = (((run.calendar || {}).schedule || {}).sessions || []);
    const next = cal.find(s => new Date(s.completion_at) > nowAt());
    return 'Next step: wait for a later validated record and inspect its gates again. ' +
      (next ? 'The next exchange session available for an after-close evaluation is ' + next.session + '.' : 'The next evaluation date is outside this record’s calendar.') +
      ' The existing evening schedule supplies that evaluation; this page does not monitor prices or place orders.';
  }`,
  planningWaitReasons:`  function planningWaitReasons(c, data) {
    const reasons=[];
    if (c.stage === 'bursts' && !c.plan) reasons.push('Structural stop, whole-share size and allocation: not evaluated in this published plan path. No executable levels were published.');
    if (c.plan && c.plan.eligible === false) reasons.push('Structural stop: ' + (c.plan.reason || 'no feasible ticket band was recorded.'));
    if (c.cut) reasons.push('Allocation: ' + c.reason);
    return reasons;
  }`
};
// Preserve the comment before evaluationExplanation when replacing planning.
const controls={reviewed:old,
  evaluation:replaceFunction('evaluationExplanation','refreshDecisionEvaluation',source),
  planning:replaceFunction('planningWaitReasons','evaluationExplanation',source),
  unrelated:source.replace("d.title = 'SpicyStock · '","d.title = 'SpicyStock control · '")};
const report=[];
for(const [name,app] of Object.entries(controls)) {
  if(only&&only!==name) continue;
  if(name!=='reviewed'&&app===source) throw Error('Control did not alter source: '+name);
  const dir=path.join(output,name);await mkdir(dir,{recursive:true});
  const appPath=path.join(dir,'app.js');await writeFile(appPath,app);
  const result=spawnSync(process.execPath,['tools/page_smoke.mjs','--only','wait-explanations','--shots',dir],{
    cwd:root,env:{...process.env,SCSTOCK_APP:appPath},encoding:'utf8',maxBuffer:16*1024*1024});
  await writeFile(path.join(dir,'run.txt'),(result.stdout||'')+(result.stderr||''));
  const page=JSON.parse(await readFile(path.join(dir,'page-results.json'),'utf8'));
  const named=(suffix,status)=>page.results.filter(r=>r.name.endsWith(suffix)).length===6&&page.results.filter(r=>r.name.endsWith(suffix)).every(r=>r.status===status);
  const evaluationFails=named('full genuine record does not skip pending Monday','FAIL');
  const planningFails=named('planner-error stage evidence','FAIL')&&named('legacy-unknown stage evidence','FAIL');
  const independent=named('independent RED and rejected review retained','PASS')&&named('ordinary eligible plan retains its published copy','PASS');
  const pass=name==='unrelated'?result.status===0&&page.failures===0:
    result.status===1&&independent&&(name==='reviewed'?evaluationFails&&planningFails:
      name==='evaluation'?evaluationFails&&named('planner-error stage evidence','PASS')&&named('legacy-unknown stage evidence','PASS'):
      planningFails&&named('full genuine record does not skip pending Monday','PASS'));
  const entry={control:name,status:pass?'PASS':'FAIL',application_status:page.failures?'FAIL':'PASS',application_sha256:sha(app),checks:page.checks,failures:page.failures,reviewed_head:reviewed,corrected_application_sha256:sha(source),independent_controls:independent?'PASS':'FAIL'};
  report.push(entry);console.log(JSON.stringify(entry));
  if(!pass)process.exitCode=1;
}
if(!report.length)throw Error('Unknown control');
await mkdir(output,{recursive:true});await writeFile(path.join(output,(only||'all')+'-controls.json'),JSON.stringify(report,null,2)+'\n');

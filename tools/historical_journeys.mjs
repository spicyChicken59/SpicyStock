/* Compatibility entry point; normal page_smoke runs these same assertions.
   node tools/historical_journeys.mjs --output /tmp/historical-journeys
   Source controls use disposable files, never mutations of the working tree. */
import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {execFileSync,spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..'),args=process.argv.slice(2);
const output=args.includes('--output')?args[args.indexOf('--output')+1]:'/tmp/historical-journeys';
const dir=await mkdtemp(path.join(tmpdir(),'historical-source-')),env={...process.env};
try {
  let app=await readFile(path.join(root,'docs/app.js'),'utf8');
  if(args.includes('--baseline')) {
    const base='8be007f68deaa417b85a512d2e16a37899d27011';
    app=execFileSync('git',['show',base+':docs/app.js'],{cwd:root}).toString();
    env.SCSTOCK_INDEX=path.join(dir,'index.html');
    await writeFile(env.SCSTOCK_INDEX,execFileSync('git',['show',base+':docs/index.html'],{cwd:root}));
    env.SCSTOCK_HISTORICAL_CONTROL='baseline';
  }
  if(args.includes('--mutant')) {app=app.replace('    renderDecisionGates(data);','    // isolated omission');env.SCSTOCK_HISTORICAL_CONTROL='omission';}
  if(args.includes('--image-mutant')) app=app.replace("chart: /^[a-f0-9]{64}$/.test(imageSha) ? 'evidence/' + imageSha + '.png' : null",'chart: c.row.chart');
  if(args.includes('--reader-mutant')) app=app.replace("includes('ReaderAuthorityError: evidence outside criterion authority')","includes('__isolated_unmatched_error__')");
  if(args.some(a=>a.includes('mutant')||a==='--baseline')) {env.SCSTOCK_APP=path.join(dir,'app.js');await writeFile(env.SCSTOCK_APP,app);}
  const result=spawnSync(process.execPath,['tools/page_smoke.mjs','--only','historical','--shots',output],{cwd:root,env,stdio:'inherit'});
  process.exitCode=result.status??1;
} finally {await rm(dir,{recursive:true,force:true});}

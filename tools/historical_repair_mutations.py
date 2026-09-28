"""Restore each demonstrated defect in isolated copies; leave the worktree alone."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE='8be007f68deaa417b85a512d2e16a37899d27011'


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    results=[]
    variants=[('original-reader','src/grader.py',['tests/test_reader_request_v2.py','-k','not original_retained']),
              ('restored-reader-omission','src/grader.py',['tests/test_reader_request_v2.py','-k','not original_retained']),
              ('original-chart','src/charts.py',['tests/test_reader_chart_context.py','tests/test_charts.py']),
              ('restored-chart-clipping','src/charts.py',['tests/test_reader_chart_context.py','tests/test_charts.py'])]
    before={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for _,x,_ in variants}
    for name,source,tests in variants:
        with tempfile.TemporaryDirectory(prefix='spicystock-mutation-') as tmp:
            target=Path(tmp)
            for directory in ('src','tests','data','knowledge'):
                shutil.copytree(ROOT/directory,target/directory,ignore=shutil.ignore_patterns('__pycache__'))
            for cfg in ('pytest.ini','pyproject.toml'):
                if (ROOT/cfg).exists():shutil.copyfile(ROOT/cfg,target/cfg)
            f=target/source
            if name.startswith('original'):
                f.write_bytes(subprocess.check_output(['git','show',BASE+':'+source],cwd=ROOT))
            elif name=='restored-reader-omission':
                f.write_text(f.read_text()+"\nSTRUCTURED_OUTPUT_MODELS = STRUCTURED_OUTPUT_MODELS - {'claude-sonnet-4-6'}\n")
            else:
                old=f.read_text();new=old.replace('start = min(start, context_start)','start = start  # isolated omission')
                assert new!=old;f.write_text(new)
            ran=subprocess.run([sys.executable,'-m','pytest',*tests,'-q'],cwd=target,
                env={**os.environ,'MPLBACKEND':'Agg'},capture_output=True,text=True)
            # A collection/import/runtime error is not detection of the defect.
            summary=ran.stdout.rsplit('short test summary info',1)[-1]
            detected=ran.returncode==1 and 'FAILED ' in summary and 'ERROR ' not in summary
            results.append({'variant':name,'status':'PASS' if detected else 'FAIL',
                            'returncode':ran.returncode,'summary':summary[-3000:]})
    assert before=={x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in before}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'variants':len(results),'detected':sum(x['status']=='PASS' for x in results),'worktree_unchanged':True}))
    return int(any(x['status']!='PASS' for x in results))


if __name__=='__main__':raise SystemExit(main())

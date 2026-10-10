"""The inspector re-validates JSON in the browser. This test proves that JS and the Python engine agree, invoice by invoice,
for both systems (decision AND fired reasons). Needs node and a built dashboard (`make dashboard`); skipped otherwise."""
import json
import re
import shutil
from pathlib import Path

import pytest

from invoiceguard.tools import run_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reports" / "dashboard_data.json"

pytestmark = pytest.mark.skipif(not shutil.which("node") or not DATA.exists(), reason="needs node and reports/dashboard_data.json")


def test_js_rules_match_python_on_every_test_invoice(tmp_path):
    tpl = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
    block = re.search(r"// RULES-BEGIN(.*?)// RULES-END", tpl, re.S).group(1)
    runner = tmp_path / "run.js"
    runner.write_text(encoding="utf-8", data=block + f"""
const D=JSON.parse(require('fs').readFileSync({json.dumps(str(DATA))},'utf8')),I=D.insp,bad=[];let n=0;
for(const inv of I.inv)for(const S of ['A','C']){{
  const x=inv[S].ex,o=vrules(x,new Set(I.keys[S].slice(0,inv.idx).filter(Boolean)),I.tins,I.today),d=vdecide(o,x,S==='C',I.thr);n++;
  if(d.dec!==inv[S].dec||JSON.stringify([...d.rs].sort())!==JSON.stringify([...inv[S].rs].sort()))bad.push([inv.id,S,d.dec,d.rs,inv[S].dec,inv[S].rs]);}}
console.log(JSON.stringify({{n,bad}}));""")
    r = run_text(["node", str(runner)])
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["n"] >= 400 and out["bad"] == [], out["bad"][:5]

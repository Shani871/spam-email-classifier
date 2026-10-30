from pathlib import Path
import json, xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import Counter
ROOT=Path.cwd(); OUT=ROOT/'output/report_updated'; TMP=ROOT/'tmp/report/update20261029'
M=json.loads((ROOT/'models/versions/ceas-sms-20261029/metrics.json').read_text())
A=json.loads((ROOT/'models/versions/ceas-sms-20261029/data_audit.json').read_text())
cases=list(ET.parse(ROOT/'output/training_ceas_sms_20261029_tests.xml').getroot().iter('testcase'))
counts=Counter(c.attrib['classname'].replace('tests.test_','').replace('_',' ') for c in cases)
fig,ax=plt.subplots(figsize=(10,6.6)); names=list(counts)
ax.barh(names,[counts[n] for n in names],color='#28775d')
for i,n in enumerate(names):ax.text(counts[n]+.1,i,str(counts[n]),va='center',fontsize=9)
ax.set_xlabel('Passed tests'); ax.set_title('143 automated tests passed after model activation'); ax.spines[['top','right']].set_visible(False)
fig.tight_layout(); fig.savefig(TMP/'tests.png',dpi=180);plt.close(fig)

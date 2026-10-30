from pathlib import Path
import sys, json, time, csv, xml.etree.ElementTree as ET
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.detection_evaluation import evaluate_detection, load_evaluation_set
from src.scam_assistant import check_message

OUT = Path(__file__).resolve().parent
plt.rcParams.update({'figure.facecolor':'#f7f9fc', 'axes.facecolor':'white', 'font.size':11,
                     'axes.spines.top':False, 'axes.spines.right':False, 'savefig.dpi':180})
BLUE, GREEN, RED, AMBER = '#3563d9', '#16856b', '#d54b58', '#dd9824'
def save(fig, name, note):
    fig.text(.5,.015,note,ha='center',fontsize=9,color='#566174')
    fig.tight_layout(rect=(0,.05,1,1))
    fig.savefig(OUT / name)
    plt.close(fig)

groups=defaultdict(lambda: [0,0,0])
cases=list(ET.parse(OUT/'pytest_results.xml').getroot().iter('testcase'))
for c in cases:
    status=1 if c.find('failure') is not None or c.find('error') is not None else 2 if c.find('skipped') is not None else 0
    groups[c.attrib['classname'].replace('tests.test_','')][status]+=1
fig,ax=plt.subplots(figsize=(11,8))
names=list(groups); vals=np.array(list(groups.values()))
left=np.zeros(len(names))
for i,(label,color) in enumerate(zip(['Passed','Failed','Skipped'],[GREEN,RED,AMBER])):
    ax.barh(names,vals[:,i],left=left,label=label,color=color); left+=vals[:,i]
for j,n in enumerate(left): ax.text(n+.1,j,str(int(n)),va='center')
ax.set(xlabel='Number of tests',title=f'Automated application tests | {len(cases)} tests'); ax.legend()
save(fig,'01_automated_tests.png','Local test run: 29 October 2026 | Gmail interactions use test doubles; no live account validation')

result=evaluate_detection()
(OUT/'detection_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
samples=load_evaluation_set()
rows=[]
for s in samples:
    start=time.perf_counter()
    r=check_message(s['text'],category=s.get('category','General message'),sender=s.get('sender',''),model_type='svm')
    rows.append({**{k:s[k] for k in ['id','language','ground_truth','scenario_type']},'assessment':r['assessment'],'score':r['score'],'latency_ms':(time.perf_counter()-start)*1000})
with (OUT/'sample_results.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
notice=f"Curated synthetic benchmark: {len(rows)} messages | Descriptive results, not real-world accuracy"
tp=result['scams_detected']; fn=result['missed_scams_count']
fp=result['false_warnings_count']+result['high_risk_false_alarms_count']; tn=result['total_legit']-fp
fig,ax=plt.subplots(figsize=(8,6))
cm=np.array([[tn,fp],[fn,tp]])
ax.imshow(cm,cmap='Blues'); ax.set_xticks([0,1],['No warning / unable','Warning']); ax.set_yticks([0,1],['Legitimate','Scam'])
for (i,j),v in np.ndenumerate(cm): ax.text(j,i,str(v),ha='center',va='center',fontsize=26,color='white' if v>cm.max()/2 else '#132642')
ax.set(xlabel='Application assessment',ylabel='Expected label',title='Hybrid detection | Confusion matrix')
save(fig,'02_confusion_matrix.png',notice+'\nWarning = High risk or Needs verification; unable-to-assess counted as no warning')

fig,ax=plt.subplots(figsize=(9,6))
precision=tp/(tp+fp) if tp+fp else 0; recall=tp/(tp+fn) if tp+fn else 0
metrics=[(tp+tn)/len(rows),precision,recall,2*precision*recall/(precision+recall) if precision+recall else 0]
bars=ax.bar(['Accuracy','Warning precision','Scam recall','F1 score'],np.array(metrics)*100,color=[BLUE,GREEN,AMBER,BLUE])
ax.bar_label(bars,fmt='%.1f%%',padding=4); ax.set(ylim=(0,112),ylabel='Percent',title='Hybrid detection | Benchmark metrics')
save(fig,'03_detection_metrics.png',notice)

fig,ax=plt.subplots(figsize=(9,6))
langs=list(result['by_language']); x=np.arange(len(langs)); b=result['by_language']
for offset,key,label,color in [(-.25,'scams_detected','Scams detected',GREEN),(0,'missed_scams','Scams missed',RED),(.25,'legit','Legitimate samples',BLUE)]:
    bars=ax.bar(x+offset,[b[l][key] for l in langs],.25,label=label,color=color); ax.bar_label(bars,padding=3)
ax.set_xticks(x,[f"{l}\n(n={b[l]['total']})" for l in langs]); ax.set(ylabel='Messages',title='Detection results by language'); ax.legend()
save(fig,'04_language_results.png',notice)

fig,ax=plt.subplots(figsize=(10,6))
labels=['Legitimate:\nno warning','Legitimate:\nneeds verification','Legitimate:\nhigh risk','Scam:\nwarning','Scam:\nmissed / unable']
bars=ax.bar(labels,[tn,result['false_warnings_count'],result['high_risk_false_alarms_count'],tp,fn],color=[GREEN,AMBER,RED,BLUE,RED]); ax.bar_label(bars,padding=4)
ax.set(ylabel='Messages',title='Warnings, false alarms, and missed scams')
save(fig,'05_error_analysis.png',notice+f"\nUnable to assess: {result['unable_to_assess_count']} message(s), included in no-warning outcomes")

fig,ax=plt.subplots(figsize=(9,6))
timings=[[r['latency_ms'] for r in rows if r['language']==l] for l in langs]
ax.boxplot(timings,tick_labels=langs,patch_artist=True,boxprops={'facecolor':'#cad8fb'})
ax.set(ylabel='Milliseconds per message',title='Local processing time | Warm model cache')
save(fig,'06_processing_time.png',notice+'\nOne timed pass per message; local CPU only; excludes network and model startup')

summary={'automated_tests':len(cases),'passed':sum(v[0] for v in groups.values()),'failed':sum(v[1] for v in groups.values()),'synthetic_samples':len(rows),'true_negative':tn,'false_positive':fp,'false_negative':fn,'true_positive':tp,'accuracy':metrics[0],'precision':precision,'recall':recall,'f1':metrics[3],'median_latency_ms':float(np.median([r['latency_ms'] for r in rows]))}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'README.md').write_text(f'''# SpamGuard application test results — 29 October 2026

Automated tests: {summary['passed']} passed, {summary['failed']} failed, {len(cases)} total.

The existing curated synthetic benchmark contains {len(rows)} messages. Hybrid warnings detected {tp}/{tp+fn} scams; {fp}/{tn+fp} legitimate messages received warnings. There were {result['unable_to_assess_count']} unable-to-assess outcomes. A warning means either High risk or Needs verification. The confusion matrix combines unable-to-assess with no-warning outcomes; it does not treat abstention as a safety guarantee.

These scenarios are already part of the project and may have informed rule tuning. They are not an independent held-out benchmark and do not establish production accuracy. No models were retrained or application source files modified. Existing pytest fixtures isolate private account storage. Automated Gmail tests use simulated responses; live Gmail access, delivery actions, OAuth, external deployment, visual layout and concurrent load were not validated.

## Images

1. Automated tests by module
2. Synthetic benchmark confusion matrix
3. Accuracy, warning precision, scam recall and F1
4. Language-level detection counts
5. False warnings and missed scams
6. Local processing time (warm cache; one pass per sample, not a load test)

## Reproduce

Run from the project folder:

```sh
.venv/bin/python -m pytest tests -q --junitxml=output/testing_2026_10_29/pytest_results.xml
MPLCONFIGDIR=/tmp/spamguard-mpl .venv/bin/python output/testing_2026_10_29/create_graphs.py
```

Raw evidence is in pytest_results.xml, detection_results.json, sample_results.csv and summary.json.
''',encoding='utf-8')
print(json.dumps(summary,indent=2))

"""Train a versioned candidate from the supplied CEAS and UCI ZIP archives.

Does not change the active model. Deduplicates normalized text before a fixed
80/20 split stratified by source and label; conflicting labels are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.preprocessing import clean_text
from src.train import train_models
from src.predict import load_model


def prepare(ceas_zip, sms_zip):
    with zipfile.ZipFile(ceas_zip) as archive:
        with archive.open('CEAS_08.csv') as handle:
            ceas = pd.read_csv(handle)
    assert set(ceas.label.dropna().unique()) <= {0, 1}, 'Unexpected CEAS labels'
    email = pd.DataFrame({'text': ceas.subject.fillna('') + '\n\n' + ceas.body.fillna(''),
                          'label': ceas.label.map({0: 'ham', 1: 'spam'}), 'source': 'CEAS_08'})
    with zipfile.ZipFile(sms_zip) as archive:
        # Split each physical line at the first tab; preserve quotes literally.
        lines = archive.read('SMSSpamCollection').decode('utf-8').splitlines()
    sms = pd.DataFrame([line.split('\t', 1) for line in lines if line.strip()], columns=['label', 'text'])
    assert set(sms.label.unique()) <= {'ham', 'spam'}, 'Unexpected SMS labels'
    sms['source'] = 'UCI_SMS'
    frame = pd.concat([email, sms], ignore_index=True)
    counts = frame.groupby(['source', 'label']).size().to_dict()
    frame['cleaned_text'] = frame.text.apply(clean_text)
    usable = frame[frame.label.notna() & frame.cleaned_text.ne('')].copy()
    conflicts = usable.groupby('cleaned_text').label.nunique()
    conflict_keys = set(conflicts[conflicts > 1].index)
    conflict_rows = int(usable.cleaned_text.isin(conflict_keys).sum())
    usable = usable[~usable.cleaned_text.isin(conflict_keys)]
    dedup = usable.drop_duplicates('cleaned_text').copy()
    dedup['label_binary'] = dedup.label.map({'ham': 0, 'spam': 1})
    audit = {'raw_rows': len(frame), 'raw_counts': {f'{s}/{l}': int(n) for (s,l),n in counts.items()},
             'empty_or_invalid_rows': len(frame)-int((frame.label.notna() & frame.cleaned_text.ne('')).sum()),
             'conflicting_label_rows_removed': conflict_rows,
             'duplicate_normalized_rows_removed': len(usable)-len(dedup), 'usable_rows': len(dedup)}
    return dedup, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ceas', type=Path, required=True)
    parser.add_argument('--sms', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if Path(args.version).name != args.version or args.version in {'.', '..', 'baseline'}:
        parser.error('Version must be a single directory name, other than baseline')
    folder = ROOT/'models'/'versions'/args.version
    folder.mkdir(parents=True, exist_ok=False)
    data, audit = prepare(args.ceas, args.sms)
    train, test = train_test_split(data, test_size=.2, random_state=42, stratify=data.source+'/'+data.label)
    assert not set(train.cleaned_text) & set(test.cleaned_text)
    # Retain exact partitions and provenance for reproducibility and later evaluation.
    train.to_csv(folder/'training_data.csv', index=False)
    test.to_csv(folder/'test_data.csv', index=False)
    audit.update({'train_rows':len(train), 'test_rows':len(test), 'seed':42,
                  'split':'80/20 stratified by source and label, after normalized-text deduplication',
                  'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.ceas,args.sms]},
                  'limitations':['Historical English email/SMS data; not modern scam or multilingual ground truth.',
                                 'Near-duplicate messages and campaign overlap may remain.',
                                 'Old model scores are diagnostic: prior training overlap is not audited.']})
    old = {}
    for name in ['nb','svm']:
        pred=load_model(name).predict(test.cleaned_text)
        old[name]={'accuracy':accuracy_score(test.label_binary,pred),
                   'precision_spam':precision_score(test.label_binary,pred,zero_division=0),
                   'recall_spam':recall_score(test.label_binary,pred,zero_division=0),
                   'f1_spam':f1_score(test.label_binary,pred,zero_division=0)}
    audit['previous_model_diagnostic']=old
    (folder/'data_audit.json').write_text(json.dumps(audit,indent=2))
    metrics=train_models(train,output_dir=str(folder),test_data=test)
    metrics.update({'dataset_size':len(data),'ham_count':int((data.label=='ham').sum()),
                    'spam_count':int((data.label=='spam').sum()),'dataset_sources':['CEAS_08','UCI_SMS'],
                    'evaluation':audit['split']})
    (folder/'metrics.json').write_text(json.dumps(metrics,indent=2))
    (folder/'release.json').write_text(json.dumps({'version':args.version,'approved':False,
         'evaluation':audit['split'],'sources':['CEAS_08','UCI_SMS'],'status':'candidate; awaiting project regression tests'},indent=2))
    print(json.dumps(audit,indent=2))


if __name__ == '__main__':
    main()

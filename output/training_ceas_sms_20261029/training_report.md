# Training completed — 29 October 2026

Both supplied ZIP archives were used to train Naive Bayes and calibrated linear SVM. CEAS text is subject + body; sender, receiver, date, and URL-count fields were excluded. Labels: 0/ham = legitimate, 1/spam = spam; these are not independently verified fraud labels.

44,728 input rows; 9 empty/invalid rows removed; 6,872 duplicate normalized texts removed; no conflicting-label rows found. 37,847 usable messages: 30,277 training and 7,570 test. Split uses random seed 42, stratified by dataset and class. The vectorizer and classifiers were fitted only on the training partition. Near-duplicate and campaign overlap may remain.

Naive Bayes: accuracy 94.87%, spam precision 95.37%, spam recall 92.56%, spam F1 93.95%.
SVM: accuracy 98.35%, spam precision 98.00%, spam recall 98.15%, spam F1 98.08%.

143 project tests passed with the new models active. Both models were then verified through the normal application loader. The active release is ceas-sms-20261029. Previous model files are preserved and the previous release is recorded in models/previous.json for the existing admin rollback feature.

Refresh the application and open Advanced > Model comparison to see these metrics. Existing already-loaded model objects in long-running workers may require restarting those workers.

Artifacts and exact train/test partitions are in models/versions/ceas-sms-20261029. Reproducible training is provided by scripts/train_uploaded_datasets.py --ceas PATH --sms PATH --version NEW_VERSION. This command creates a candidate and does not automatically activate it. The existing feedback-retraining feature still uses its original baseline datasets; it does not automatically incorporate this uploaded release's training partition.

These historical English datasets do not validate Hindi/Hinglish or modern scam performance. Comparison with previous models is diagnostic only because their prior training overlap with these uploads was not audited. No private inbox data was used and no website deployment was performed.

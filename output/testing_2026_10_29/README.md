# SpamGuard application test results — 29 October 2026

Automated tests: 143 passed, 0 failed, 143 total.

The existing curated synthetic benchmark contains 29 messages. Hybrid warnings detected 14/14 scams; 5/15 legitimate messages received warnings. There were 4 unable-to-assess outcomes. A warning means either High risk or Needs verification. The confusion matrix combines unable-to-assess with no-warning outcomes; it does not treat abstention as a safety guarantee.

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

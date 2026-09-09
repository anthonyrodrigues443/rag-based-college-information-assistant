"""Every test runs against its own corpus and index, never the developer's."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="campusquery-tests-"))
os.environ["DATA_DIR"] = str(_TMP)
os.environ["SEED_DIR"] = str(_TMP / "seed")
os.environ["INDEX_DIR"] = str(_TMP / "index")
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["LLM_PROVIDER"] = "none"
(_TMP / "seed").mkdir(parents=True, exist_ok=True)

FEES = """---
title: Institute fee structure 2026-27 for all programmes
date: 2026-07-21
kind: circular
source: Circulars, page 6
---

# Undergraduate programmes

B.E. tuition fee is Rs. 1,45,000 per year for the open category and Rs. 72,500 per year for
students holding an approved freeship. The development fee is Rs. 12,000 per year.

# Postgraduate programmes

M.E. tuition fee is Rs. 96,000 per year. The laboratory and library charge is Rs. 8,000 per
year. Research scholars registered for a Ph.D. pay Rs. 45,000 per year until submission.

# Other charges

Examination fee is Rs. 2,200 per semester. The transcript fee is Rs. 750 per copy. The
duplicate identity card charge is Rs. 200 and is payable at the accounts counter.
"""

LATE_FEE = """---
title: Extension of last date for payment of Semester V tuition fee
date: 2026-08-14
kind: circular
source: Circulars, page 3
---

# Late fee

Payments made after 29 August 2026 attract a late fee of Rs. 500. The late fee is charged
per student and not per instalment. No further extension will be granted after this date.
"""

REVALUATION = """---
title: Revaluation application procedure and prescribed fees
date: 2026-07-18
kind: circular
source: Circulars, page 7
---

# Revaluation application procedure

A student who is not satisfied with the result of a theory paper may apply for photocopy of
the answer book, for revaluation, or for both. Applications are made on the student portal.

# Prescribed fees

Photocopy of an answer book is Rs. 400 per paper. Revaluation is Rs. 800 per paper. Where
both are applied for together the charge is Rs. 1,000 per paper and is not refundable.
"""

DEPARTMENT = """---
title: Department of Artificial Intelligence and Machine Learning
date: 2026-05-15
kind: page
source: Departments
---

# Department of Artificial Intelligence and Machine Learning

The department offers a four year B.E. programme with an intake of sixty students. It was
started in 2020 and has laboratories for machine learning and natural language processing.
"""

ADMISSIONS = """---
title: Admissions 2026
date: 2026-05-20
kind: page
source: Admissions
---

# Undergraduate admission

Admission to the first year of the B.E. programme is through the state common entrance test
followed by the centralised admission process for all candidates who have applied on time.

# Postgraduate admission

Admission to the M.E. programme is through the state postgraduate entrance test. Candidates
with a valid GATE score are considered first against the notified seats for the year.
"""

CORPUS = {
    "fee-structure-2026-27.md": FEES,
    "sem-v-fee-extension.md": LATE_FEE,
    "revaluation-procedure.md": REVALUATION,
    "departments-aiml.md": DEPARTMENT,
    "admissions-2026.md": ADMISSIONS,
}


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def seed_dir():
    from app import config
    for name, text in CORPUS.items():
        (config.SEED_DIR / name).write_text(text, encoding="utf-8")
    return config.SEED_DIR


@pytest.fixture(scope="session")
def indexed(seed_dir):
    """The small corpus above, embedded and indexed. Loads the models once."""
    pytest.importorskip("sentence_transformers")
    from app import ingest
    from app.store import store
    ingest.reindex_seed()
    assert store.stats()["documents"] == len(CORPUS)
    return store

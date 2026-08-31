from agent.fingerprint import fingerprint


def test_same_inputs_produce_same_fingerprint():
    fp1 = fingerprint("a.py", "security", "SQL injection")
    fp2 = fingerprint("a.py", "security", "SQL injection")
    assert fp1 == fp2


def test_different_title_produces_different_fingerprint():
    fp1 = fingerprint("a.py", "security", "SQL injection")
    fp2 = fingerprint("a.py", "security", "Different title")
    assert fp1 != fp2


def test_fingerprint_length():
    assert len(fingerprint("a.py", "security", "x")) == 16

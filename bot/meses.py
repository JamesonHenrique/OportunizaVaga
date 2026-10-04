"""Month names for the two languages the inboxes actually use. Single owner: gmail-status.py
parses "17 de set." / "Sep 17" from a Gmail row and kit-entrevista.py parses the calendar date out
of a recruiter subject, and both decide by looking the name up in these maps. When the two copies
drifted, one of them would stop matching a month and fail WITHOUT AN ERROR: the date simply came
back empty and the record was never touched.

Kept as two explicit names (MESES_PT, MESES_EN) rather than MESES/MESES_PT, because the two copies
disagreed on the name too and a reader could not tell which language it was holding.

Owner: the public repo, because two of the three readers live there. The private install reaches
this file by path (OV_OSS_BOT), the same way it already reaches vaga_check.py and descobrir.py.
"""
MESES_PT = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")
MESES_EN = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

PT = {m: i for i, m in enumerate(MESES_PT, 1)}
EN = {m: i for i, m in enumerate(MESES_EN, 1)}

assert list(PT.values()) == list(range(1, 13)), "PT index off by one"
assert list(EN.values()) == list(range(1, 13)), "EN index off by one"
assert len(PT) == len(EN) == 12, "a month is missing from one of the two tables"

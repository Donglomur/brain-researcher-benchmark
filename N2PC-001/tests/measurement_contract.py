"""The public signed, equal-subject-weight N2pc table contract."""
import math
import re


SUBJECTS = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}


def summarize(rows):
    assert len(rows) == len(SUBJECTS), "require all 12 subject rows"
    ids, records = set(), []
    for row in rows:
        match = re.fullmatch(r"(?:sub-)?0*(\d+)", str(row["subject"]))
        assert match, "invalid subject ID"
        subject = int(match.group(1))
        assert subject in SUBJECTS and subject not in ids, "unexpected or duplicate subject"
        ids.add(subject)
        values = {k: float(row[k]) for k in ("contra_uv", "ipsi_uv", "n2pc_uv",
                    "fixed_po8_minus_po7_pooled_uv", "n_left_trials", "n_right_trials")}
        assert all(math.isfinite(v) for v in values.values()), "nonfinite measurement"
        for key in ("n_left_trials", "n_right_trials"):
            assert values[key] > 0 and values[key].is_integer(), "invalid trial count"
        assert abs(values["contra_uv"] - values["ipsi_uv"] - values["n2pc_uv"]) <= 3e-6, \
            "N2pc must equal signed contra minus ipsi on every row"
        records.append(values)
    assert ids == SUBJECTS
    return {
        "n_subjects": len(rows),
        "n_subjects_negative": sum(v["n2pc_uv"] < 0 for v in records),
        "n2pc_amplitude_uv": sum(v["n2pc_uv"] for v in records) / len(rows),
        "contralateral_amplitude_uv": sum(v["contra_uv"] for v in records) / len(rows),
        "ipsilateral_amplitude_uv": sum(v["ipsi_uv"] for v in records) / len(rows),
        "fixed_po8_minus_po7_pooled_uv_for_reference": sum(
            v["fixed_po8_minus_po7_pooled_uv"] for v in records) / len(rows),
        "n_left_target_trials_total": int(sum(v["n_left_trials"] for v in records)),
        "n_right_target_trials_total": int(sum(v["n_right_trials"] for v in records)),
    }

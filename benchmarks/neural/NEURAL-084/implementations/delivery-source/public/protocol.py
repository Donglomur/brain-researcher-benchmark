"""Fixed prospective OpenBMI overt-gaze SSVEP contract; no data-dependent defaults."""
SCHEMA = "neural084_scores_v1"
PEOPLE = tuple(range(1, 55))
SESSIONS = (1, 2)
PHASES = ("train", "test")
CLASSES = (1, 2, 3, 4)
DIRECTIONS = ("up", "left", "right", "down")
FREQUENCIES = tuple(60.0 / n for n in (5, 7, 9, 11))
CHANNELS = ("P7", "P3", "Pz", "P4", "P8", "PO9", "PO10", "O1", "Oz", "O2")
FS_SOURCE = 1000
FS_OUTPUT = 100
SAMPLES_SOURCE = 4000
SAMPLES_OUTPUT = 400
TRIALS_PHASE = 100
TRIALS_PERSON = 400
TRIALS_CLASS_PHASE = 25
MAX_SUBMISSION_BYTES = 262144


def fold_name(person):
    if type(person) is not int or person not in PEOPLE:
        raise ValueError("full designated person roster1..54")
    return "fold%03d" % person

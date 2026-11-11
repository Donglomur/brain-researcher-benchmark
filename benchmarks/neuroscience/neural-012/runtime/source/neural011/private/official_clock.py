"""Four exact MIT author annotation/typo functions; no EEG/clinical type selector."""
import os,re,time
from pathlib import Path

def _parseTimeStamp(string: str) -> float:
    """Parses timestamps from Siena annotation files and returns a float representing the time from the earliest system time.

    Accepts the following formats with any random string before the timestamp :
    - 'Registration start time: 19.00.44'
    - 'Start time: 21:51:02'

    Args:
        string (str): string to be parsed as a timestamp

    Returns:
        float: timestamp in seconds from the earliest system time
    """
    timeStamp = re.findall(".*[ |:]([0-9]+.[0-9]+.[0-9]+).*", string)[0]
    return time.mktime(time.strptime(timeStamp.replace(":", "."), "%H.%M.%S"))

def _substractTimeStamps(time1: float, time2: float) -> float:
    """Substract time2 timestamp from time1 in seconds"""
    difference = time1 - time2
    if difference < 0:
        difference += 24 * 60 * 60  # Correct for day shift
    return difference

def _loadSeizures(edfFile: str) -> list[tuple]:
    """Load seizures from a Siena Seizures-list-Pxx.txt file

    Args:
        edfFile (str): full path to the EDF for which annotations should be extracted.

    Raises:
        ValueError: raises a ValueError if txt file format is unknown.

    Returns:
        seizures: A list of (start, end) tuples for each seizure in seconds from the beginning of the file.
    """

    subject = os.path.basename(os.path.dirname(edfFile))
    correctedEdfFileName = _correctEdfFileNameTypos(edfFile)

    seizures = []
    summaryFile = Path(os.path.dirname(edfFile)) / f"Seizures-list-{subject}.txt"
    with open(summaryFile, "r") as summary:
        # Search for mention of edfFile in summary
        line = summary.readline()
        while line:
            if re.search(r"File name: {} *\n".format(correctedEdfFileName), line):
                firstLine = summary.readline()
                # PN01 exception
                if correctedEdfFileName == "PN01.edf":
                    registrationStart = _parseTimeStamp(firstLine)
                    _ = summary.readline()
                    _ = summary.readline()
                    for _ in range(2):
                        _ = summary.readline()
                        start = _parseTimeStamp(summary.readline())
                        end = _parseTimeStamp(summary.readline())
                        _ = summary.readline()
                        seizures.append(
                            (
                                _substractTimeStamps(start, registrationStart),
                                (_substractTimeStamps(end, registrationStart)),
                            )
                        )
                elif correctedEdfFileName == "PN00-3.edf":  # seizure last 1hour
                    registrationStart = _parseTimeStamp(firstLine)
                    _ = summary.readline()
                    start = _parseTimeStamp(summary.readline())
                    end = _parseTimeStamp(summary.readline())
                    end = _parseTimeStamp(
                        "Seizure end time: 18.29.29\n"
                    )  # correct time
                    seizures.append(
                        (
                            _substractTimeStamps(start, registrationStart),
                            (_substractTimeStamps(end, registrationStart)),
                        )
                    )
                elif correctedEdfFileName == "PN10-7.8.9.edf":  # seizure last 1hour
                    if (
                        firstLine == "Registration start time:1 6.49.25\n"
                    ):  # extra space
                        firstLine = "Registration start time:16.49.25\n"
                    registrationStart = _parseTimeStamp(firstLine)
                    _ = summary.readline()
                    start = _parseTimeStamp(summary.readline())
                    end = _parseTimeStamp(summary.readline())
                    seizures.append(
                        (
                            _substractTimeStamps(start, registrationStart),
                            (_substractTimeStamps(end, registrationStart)),
                        )
                    )
                # PN12 exception
                elif "Seizure start time: " in firstLine:
                    start = _parseTimeStamp(firstLine)
                    end = _parseTimeStamp(summary.readline())
                    seizures.append(
                        (
                            _substractTimeStamps(start, registrationStart),
                            (_substractTimeStamps(end, registrationStart)),
                        )
                    )
                # Standard format
                elif "Registration start time:" in firstLine:
                    registrationStart = _parseTimeStamp(firstLine)
                    _ = summary.readline()
                    start = _parseTimeStamp(summary.readline())
                    end = _parseTimeStamp(summary.readline())
                    seizures.append(
                        (
                            _substractTimeStamps(start, registrationStart),
                            (_substractTimeStamps(end, registrationStart)),
                        )
                    )
                else:
                    raise ValueError("Unknown format for Siena summary file.")
            line = summary.readline()
    return seizures

def _correctEdfFileNameTypos(filename: str) -> str:
    """Correct typos in filenames in .txt file when compared to .edf files"""
    correctedEdfFileName = os.path.basename(filename)
    if correctedEdfFileName == "PN01-1.edf":
        correctedEdfFileName = "PN01.edf"
    elif correctedEdfFileName == "PN06-1.edf":
        correctedEdfFileName = "PNO6-1.edf"  # big o instead of 0
    elif correctedEdfFileName == "PN06-2.edf":
        correctedEdfFileName = "PNO6-2.edf"  # big o instead of 0
    elif correctedEdfFileName == "PN06-4.edf":
        correctedEdfFileName = "PNO6-4.edf"  # big o instead of 0
    elif correctedEdfFileName == "PN11-1.edf":
        correctedEdfFileName = "PN11-.edf"
    return correctedEdfFileName

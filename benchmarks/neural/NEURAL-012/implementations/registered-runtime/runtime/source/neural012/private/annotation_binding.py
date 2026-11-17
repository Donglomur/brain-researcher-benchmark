"""Original annotation semantics over owned document bytes; no source acquisition."""
import hashlib, io as memoryio, re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote
import io_contract as io
import scientific_contract as sc

def roster(body, cohort):
    io.need(type(body) is bytes, 'owned publisher roster bytes')
    names = [x for x in body.decode('utf8').splitlines() if x.strip()]
    pattern = r'chb(?:0[1-9]|1[0-9]|2[0-4])/[^/]+\.edf' if cohort == 'CHB' else r'PN\d{2}/[^/]+\.edf'
    io.need(len(names) == (686 if cohort == 'CHB' else 41) and len(names) == len(set(names))
            and all(re.fullmatch(pattern, x) for x in names), 'complete unique published EDF membership')
    return names

def chb_annotations(records_body, positives_body, summaries, indices, companion_body):
    """Preserve the prior full-release correction and explicit-negative rules."""
    names = roster(records_body, 'CHB')
    positives = set(positives_body.decode('utf8').split())
    io.need('chb07/chb07_18.edf' in positives and 'chb07/chb07_19.edf' not in positives, 'original documented CHB correction')
    positives.remove('chb07/chb07_18.edf'); positives.add('chb07/chb07_19.edf')
    cases = {f'chb{i:02d}' for i in range(1,25)}
    io.need(set(indices) == cases and set(summaries) <= cases and set(summaries) >= cases-{'chb24'}, 'full case document coverage')
    parsed = {}; companions = set()
    for case, body in summaries.items():
        for block in re.split(r'^File Name:\s*', body.decode('ascii'), flags=re.M)[1:]:
            name = block.splitlines()[0].strip(); path = case + '/' + name
            counts = re.findall(r'^Number of Seizures in File:\s*(\d+)', block, re.M)
            starts = re.findall(r'^Seizure(?: \d+)? Start Time:\s*(\d+) seconds', block, re.M)
            ends = re.findall(r'^Seizure(?: \d+)? End Time:\s*(\d+) seconds', block, re.M)
            io.need(path not in parsed and len(counts) == 1 and len(starts) == len(ends) == int(counts[0]), 'exact original summary event join')
            parsed[path] = [[float(a),float(b)] for a,b in zip(starts,ends)]
            io.need(all(a < b for a,b in parsed[path]), 'positive original intervals')
    for case, body in indices.items():
        for href in re.findall(r'href="([^"]+)"', body.decode('utf8')):
            name = unquote(href)
            if name.endswith('.edf.seizures'): companions.add(case + '/' + name[:-9])
    io.need(positives == companions and len(positives) == 141, 'full corrected positive/companion agreement')
    io.need(parsed.get('chb07/chb07_18.edf') == [] and parsed.get('chb07/chb07_19.edf') == [[13688.,13831.]], 'preserved localized source correction')
    io.need(hashlib.sha256(companion_body).hexdigest() == 'f70b7cf41c1384e181e22873cb01096be28b4ac6eb67b4bd73220e6535949b5e', 'exact original correction companion')
    result = {}
    for path in names:
        if path in parsed: result[path] = parsed[path]
        else:
            io.need(path.startswith('chb24/') and path not in positives, 'no missing-label background substitution')
            result[path] = []
        io.need(bool(result[path]) == (path in positives), 'complete positive label agreement')
    io.need(set(parsed) <= set(result) and sum(map(len,result.values())) == 198, 'complete original 198-event support')
    return result

def siena_original(path, summary_body):
    """Run the exact pinned author parser with only its owned summary available.

    The injected open is a capability to a StringIO over already owned bytes.
    The parser body itself is an exact ordinary packaged source, not input code.
    Its corrections and original time implementation are not rewritten.
    """
    io.need(type(path) is str and re.fullmatch(r'PN\d{2}/[^/]+\.edf', path) and type(summary_body) is bytes, 'original Siena document inputs')
    subject = path.split('/')[0]; virtual = PurePosixPath('/SOURCE') / path
    allowed = virtual.parent / ('Seizures-list-' + subject + '.txt')
    def captured_open(name, mode='r', *args, **kwargs):
        io.need(str(name) == str(allowed) and mode == 'r' and not args and not kwargs, 'parser confined to its captured original summary')
        return memoryio.StringIO(summary_body.decode('utf8'), newline=None)
    parser = Path(__file__).resolve().parents[2] / 'neural011/private/official_clock.py'
    raw = io.read(parser, 100000, sc.SOURCE_PARSER_SHA256)
    namespace = {'__name__':'n012_pinned_original_siena_parser','open':captured_open}
    exec(compile(raw, str(parser), 'exec'), namespace)
    corrected = namespace['_correctEdfFileNameTypos'](str(virtual))
    clocks = []
    for block in re.split(r'(?=File name:)', summary_body.decode('utf8')):
        first = block.splitlines()[0] if block else ''
        if first.strip() != 'File name: ' + corrected: continue
        found = re.search(r'Registration start time:\s*(\d[\d .:]+)', block)
        if found: clocks.append(found[1].strip().replace('1 6.','16.'))
    io.need(clocks and len({sc.clock_seconds(x) for x in clocks}) == 1, 'unique original registration clock')
    events = sorted([list(x) for x in namespace['_loadSeizures'](str(virtual))])
    return events, clocks[0]

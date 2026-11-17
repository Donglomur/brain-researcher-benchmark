"""Trusted admission and explicit A/B exposure; never runs candidate code."""
import hashlib
from pathlib import Path

from custody import decode, encoded, need, pin, plain, read_pin, write_new
from scientific_score import TASK, POLICY, original_target, procedure_target

from runtime_policy import admit as admit_runtime
CASE_IDS = ('case_7e2816b4', 'case_a856d204', 'case_246b0ed1', 'case_64f3e7a8')
INPUT_HASHES = (
    '5af962908c8f53c687ddee2f094d168918a4dc418777b65f37535c815435e9e2',
    '1e386fe04e83b0ad46764b8db27e9f291f520d6f1021c7b753cd465617dfca4b',
    '9efc751ed817db79efa006574ab105c399c09a481845eb66b996ffba98ef95ee',
    'b0ca174ff59dc8dcabd2c46aa8d529f47794bc1eaac81639b8a2fc7a3b0e1a5c')
REFERENCE_HASHES = (
    '0e00876003602d6bcb7852c9faf430eb54c4650548d7451d7bfac1e7228412dd',
    'daca0cc3b7fbbf9d5f5a3157e6ba19df6df5029d68ca1eedc51bff7af2371788',
    '0144f68f1da7e0874ad92a155a1624a102a93bc41bcbbd4c5a40415a6e2e3e80',
    'a5f8449e4811da5929b07cb2132c6798f117f78326b8d70e366f8ef4bee81a01')


def admit_catalogue(entry):
    """entry is an exact owner-selected pin, not a candidate-supplied document."""
    raw = read_pin(entry)
    catalogue = decode(raw)
    runtime = admit_runtime(catalogue['runtime_policy'])
    need(type(catalogue) is dict and catalogue['schema'] == 'nider_trusted_scientific_catalogue_v1' and
         catalogue['task'] == TASK and catalogue['policy'] == POLICY and catalogue['image'] == runtime['image'], 'catalogue_identity')
    source = read_pin(catalogue['reporting_core'])
    need(hashlib.sha256(source).hexdigest() == '8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963', 'reporting_core_identity')
    need(Path(catalogue['reporting_core']['path']).resolve() == Path(__file__).with_name('reporting_core.py').resolve(), 'loaded_reporting_source_path')
    for evidence in catalogue['evidence']:
        read_pin(evidence)
    published = original_target(read_pin(catalogue['published_targets']))
    need(catalogue['published_targets']['sha256'] == '28cbd720fea8841f40102b1d57fdc882a1c4035bfabf410c197db8811e0d7eb6', 'caption_identity')
    need(type(catalogue['cases']) is list and len(catalogue['cases']) == 4, 'catalogue_four_cases')
    cases = []
    for index, item in enumerate(catalogue['cases']):
        need(set(item) == {'case_id', 'kind', 'workbook', 'reference'}, 'catalogue_case_keys')
        need(item['case_id'] == CASE_IDS[index] and item['kind'] == ('original' if index == 0 else 'procedure'), 'catalogue_fixed_order')
        need(item['workbook']['sha256'] == INPUT_HASHES[index] and item['reference']['sha256'] == REFERENCE_HASHES[index], 'catalogue_input_reference_pair')
        read_pin(item['workbook'])
        reference = read_pin(item['reference'])
        cases.append({**item, 'target': published if index == 0 else procedure_target(reference)})
    need(catalogue['official_code']['sha256'] == 'caa4ac8a0ee84821c19df5fc26c4a7527ef164c6f48f19e2deed3d0a888cd334', 'code_origin')
    need(catalogue['official_code_license']['sha256'] == 'f39febcc26127e58ccc3d496897cdb15aeffc4e905218a4381a9513c9dad58a8', 'code_notice')
    read_pin(catalogue['official_code']); read_pin(catalogue['official_code_license'])
    return catalogue, cases


def admit_materials(entry):
    """Only owner-selected material records can authorize full-paper delivery.

    This is a custody join, not an automatic copyright/legal determination.
    The current source packet deliberately has no fabricated material record.
    """
    material = decode(read_pin(entry))
    need(type(material) is dict and set(material) == {'schema', 'paper', 'paper_doi', 'paper_scope', 'delivery_basis'}, 'material_keys')
    need(material['schema'] == 'nider_full_paper_materials_v1' and material['paper_doi'] == '10.1038/s41586-026-11203-1' and
         material['paper_scope'] == 'complete_article', 'full_paper_identity')
    paper = read_pin(material['paper'], maximum=8388608)
    need(paper.startswith(b'%PDF-'), 'full_paper_PDF_required')
    basis = decode(read_pin(material['delivery_basis']))
    need(type(basis) is dict and set(basis) == {'schema', 'paper_sha256', 'scope', 'basis', 'selected_by'}, 'delivery_record_keys')
    need(basis['schema'] == 'nider_owner_selected_delivery_basis_v1' and
         basis['paper_sha256'] == material['paper']['sha256'] and basis['scope'] == 'local_isolated_candidate_access' and
         type(basis['basis']) is str and 1 <= len(basis['basis']) <= 4096 and
         type(basis['selected_by']) is str and 1 <= len(basis['selected_by']) <= 128, 'delivery_record_join')
    return material, paper


def stage_exposure(root, case, catalogue, arm):
    """Only scientific XLSX + public question; code and notice only in B.

    Paper is mounted independently as one authenticated read-only file, reused
    across four separate containers. No raw full workbook or contact sheet is
    delivered. No target, scorer, owner plan, key or earlier response is staged.
    """
    need(arm in ('A', 'B'), 'arm')
    root = plain(root)
    root.mkdir(mode=0o700)
    files = [write_new(root / 'study.xlsx', read_pin(case['workbook']))]
    request = {'schema': 'nider_scientific_case_request_v1', 'task': TASK, 'policy': POLICY,
               'case_id': case['case_id'], 'arm': arm, 'workbook_sha256': case['workbook']['sha256'],
               'workbook': '/input/study.xlsx', 'paper': '/paper/article.pdf',
               'required_contrasts': ['amy_self', 'quest_self', 'amy_quest'],
               'required_fields': ['pearson_r', 'p_two_sided', 'k', 'N'],
               'output': 'One nider_scientific_case_response_v1 JSON object on stdout; all scientific fields must be finite JSON numbers.',
               'scientific_scale': 'Pearson r = tanh(native Fisher-z random-effects mean); original two-sided uncorrected p; k model count; N source sample-size sum, not unique participants.',
               'procedure': 'Use all 40 rows, original DL estimator, raw-r duplicate mean for Morawetz2016b, original exclusions and contrast-specific sample sizes. Inputs can include hypothetical procedure checks. Do not substitute original paper constants for changed data.',
               'official_code_delivered': arm == 'B'}
    files.append(write_new(root / 'request.json', encoded(request)))
    if arm == 'B':
        files.append(write_new(root / 'official_source.R', read_pin(catalogue['official_code'])))
        files.append(write_new(root / 'LICENSE_NIDER_CODE.txt', read_pin(catalogue['official_code_license'])))
    need({p.name for p in root.iterdir()} == ({'study.xlsx', 'request.json'} | ({'official_source.R', 'LICENSE_NIDER_CODE.txt'} if arm == 'B' else set())), 'exposure_member_support')
    return files

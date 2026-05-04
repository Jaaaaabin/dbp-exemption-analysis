# src/text_parser.py
# Structured parsing of long text fields in building permit JSON records.
#
# Public API
#   enrich_json            – enriched-only (nested) dicts for all records
#   enrich_and_merge_json  – original + enriched merged; adds flat analytic fields
#
# Internal parsers (called by enrich_record)
#   _parse_kv_section        – generic "Header:\nKey: Value\n..." → dict
#   parse_granted_exemptions – hierarchical items + taxonomy labels
#   parse_decision_basis     – plan type/name, zone code, legal ordinance
#   parse_plan_references    – development_plan field → [{name, type}]

import json
import re
from pathlib import Path

JsonSource = str | Path | list[dict]

# ── Internal helpers ──────────────────────────────────────────────────────────

def _load(source: JsonSource) -> list[dict]:
    if isinstance(source, (str, Path)):
        with open(source, encoding='utf-8') as f:
            return json.load(f)
    return list(source)


_NO_EXEMPTION = re.compile(
    r'^\s*(none specified\.?|n/a|no exemption)\s*$', re.IGNORECASE | re.MULTILINE
)

_NOT_GRANTED_SPLIT = re.compile(r'Not Granted Exemptions:\s*', re.IGNORECASE)


def _to_snake_key(text: str) -> str:
    """'Some Key Name' → 'some_key_name'"""
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', '_', text.strip())


def _parse_kv_section(text: str) -> dict:
    """
    Generic parser for section text of the form:
        Section Header:\n
        Key One: value\n
        Key Two: value with: colons inside\n
        Freestanding line without colon

    - The first line that ends with ':' is the section title and is skipped.
    - Each remaining line is split on the FIRST ':' to give key / value.
    - Lines that contain no ':' are collected in '_notes' (list); this includes
      both standalone annotations AND continuation lines of multi-line values —
      inspect '_notes' during development to catch truncated values.
    - Keys are normalised to snake_case via _to_snake_key.
    """
    if not text:
        return {}
    lines = text.strip().split('\n')
    result: dict = {}
    notes: list[str] = []
    start = 1 if (lines and lines[0].rstrip().endswith(':')) else 0
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        if ':' in line:
            raw_key, _, value = line.partition(':')
            key = _to_snake_key(raw_key)
            if key:
                result[key] = value.strip()
        else:
            notes.append(line)
    if notes:
        result['_notes'] = notes
    return result


# ── Exemption taxonomy ────────────────────────────────────────────────────────
#
# Categories:
#   planning_law       – § 31 BauGB (Ausnahme / Befreiung from development plan)
#   tree_environmental – Baumschutzverordnung (§ 4 / § 6)
#   building_code      – § 69 HBauO or explicit "building code" phrasing
#   access_road        – Hamburg Road Law (HWG) or Wegerecht / curb crossing
#   access_restriction – construction burden (Baulast) or access-securing condition
#   nature_protection  – federal nature protection (BNatSchG §§ 44, 67)
#   none               – no exemption granted
#   other              – text present but no recognised pattern

_TAXONOMY_RULES: list[tuple[str, str]] = [
    ('planning_law',       r'§\s*31\b[^§]{0,30}baugb|baugb[^§]{0,30}§\s*31\b'),
    ('tree_environmental', r'baumschutz|tree protection|schutz des baumbestandes'),
    ('building_code',      r'§\s*69\s*(?:hbauo|paragraph)|building code'),
    ('access_road',        r'§\s*(?:18|19|22|26)\s*(?:absatz\s*\d+\s*)?hwg'
                           r'|wegerecht|curb crossing'),
    ('access_restriction', r'construction burden|baulasten'
                           r'|securing sufficient (?:access|width)'),
    ('nature_protection',  r'bnatschg'),
]


def classify_exemption_types(text: str) -> list[str]:
    """Return all taxonomy categories present in the exemption text (multi-label)."""
    if not text or _NO_EXEMPTION.search(text.strip()):
        return ['none']
    tl = text.lower()
    found = [cat for cat, pattern in _TAXONOMY_RULES if re.search(pattern, tl)]
    return found if found else ['other']


def extract_legal_refs(text: str) -> list[str]:
    """Extract every § reference from text and return them normalised."""
    raw = re.findall(
        r'§\s*\d+[a-zA-Z]?(?:\s+(?:Abs(?:atz)?\.?|paragraph)\s*\d+)?'
        r'(?:\s+[A-Z]{2,}[a-zA-Z]*)?',
        text,
    )
    return list(dict.fromkeys(re.sub(r'\s+', ' ', r.strip()) for r in raw))


# ── Plan reference parsing ────────────────────────────────────────────────────

# Ordered from most-specific to least-specific so the first match wins.
_PLAN_TYPE_MAP: list[tuple[str, str]] = [
    ('construction phase plan',       'construction_phase_plan'),
    ('partial development plan',      'partial_development_plan'),
    ('development plan',              'development_plan'),
    ('construction plan',             'construction_plan'),
    ('implementation plan',           'implementation_plan'),
    ('green space plan',              'green_space_plan'),
    ('regulation for the protection', 'landscape_protection'),
    ('ordinance for the protection',  'landscape_protection'),
    ('maintenance ordinance',         'maintenance_ordinance'),
    ('preservation',                  'preservation_ordinance'),
    ('non-overplanned area',          'unplanned_area'),
    ('not overplanned area',          'unplanned_area'),
]

# Plan types that represent primary planning instruments (used for flat summary field)
_PRIMARY_PLAN_TYPES = {
    'development_plan', 'construction_plan', 'construction_phase_plan',
    'partial_development_plan', 'implementation_plan',
}


def parse_plan_references(text: str) -> list[dict]:
    """
    Parse the development_plan_implementation_plan field into a list of
    individual plan references, each with a 'name' and normalised 'type'.

    The field can contain multiple comma-separated entries, each ending with
    a parenthetical type annotation, e.g.:
        "Wellingsbüttel 16 (development plan), 202 (implementation plan)"
    """
    if not text:
        return []

    # Split on ', ' that follows a closing ')' — lookbehind keeps the ')'.
    chunks = re.split(r'(?<=\)),\s*', text)

    refs = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Type annotation is the LAST parenthetical in the chunk
        type_m = re.search(r'\(([^)]+)\)\s*$', chunk)
        if type_m:
            raw_type = type_m.group(1).strip().lower()
            name = chunk[:type_m.start()].strip().rstrip(',').strip()
        else:
            raw_type = None
            name = chunk

        plan_type = 'other'
        if raw_type:
            for key, val in _PLAN_TYPE_MAP:
                if key in raw_type:
                    plan_type = val
                    break

        refs.append({'name': name, 'type': plan_type})

    return refs


# ── Hierarchical exemption item parsing ───────────────────────────────────────

def _build_item(idx: str | None, text: str) -> dict:
    """Build one exemption item dict; recurse into sub-items if found."""
    item: dict = {'index': idx, 'text': text}

    refs = extract_legal_refs(text)
    item['legal_ref'] = refs[0] if refs else None

    types = classify_exemption_types(text)
    item['type'] = types[0] if len(types) == 1 else 'mixed'

    # Sub-items: N.1. N.2. … (only when parent has an index)
    sub_items: list[dict] = []
    if idx is not None:
        sub_pat = re.compile(rf'(?:^|\n){re.escape(idx)}\.(\d+)\.\s+', re.MULTILINE)
        sub_matches = list(sub_pat.finditer(text))

        for j, sm in enumerate(sub_matches):
            sub_idx = f"{idx}.{sm.group(1)}"
            s_start = sm.end()
            # Last sub-item ends at the next sub-item boundary, or at the first
            # blank-line-separated paragraph that isn't another numbered sub-item
            # (tail text stays in the parent item's 'text', not the sub-item).
            if j + 1 < len(sub_matches):
                s_end = sub_matches[j + 1].start()
            else:
                # Find where the sub-item's content ends: stop at the first
                # double-newline that is followed by non-sub-item text.
                tail_m = re.search(r'\n\n(?!\s*\d+\.\d+\.)', text[sm.end():])
                s_end = sm.end() + tail_m.start() if tail_m else len(text)
            sub_text = text[s_start:s_end].strip()

            lines = sub_text.split('\n')
            subject_raw = lines[0].strip().rstrip(':')
            subject = re.sub(r'^[Ff]or\s+', '', subject_raw).strip()

            sub: dict = {'index': sub_idx, 'text': sub_text, 'subject': subject}
            rest = '\n'.join(lines[1:])
            just_m = re.search(r'(?:Reason|Justification):\s*(.+)', rest, re.IGNORECASE)
            if just_m:
                sub['justification'] = just_m.group(1).strip()

            sub_items.append(sub)

    if sub_items:
        item['sub_items'] = sub_items
    else:
        # No sub-items: extract "For [subject]" lines directly
        subjects = [
            s.strip().rstrip(':')
            for s in re.findall(r'\bFor (.+?)(?:\n|$)', text, re.MULTILINE)
            if s.strip()
        ]
        if subjects:
            item['subjects'] = subjects

    # Top-level justification / reason
    just_m = re.search(
        r'(?:Justification|Reason):\s*(.+?)(?=\n[A-Z][a-z][^:\n]*:|\Z)',
        text, re.IGNORECASE | re.DOTALL,
    )
    if just_m:
        item['justification'] = just_m.group(1).strip()

    # Conditions
    cond_m = re.search(
        r'(?:Condition|Suspensive Condition)s?:\s*(.+?)(?=\n[A-Z][a-z][^:\n]*:|\Z)',
        text, re.IGNORECASE | re.DOTALL,
    )
    if cond_m:
        cond_lines = [
            l.strip().lstrip('-•').strip()
            for l in cond_m.group(1).split('\n')
            if l.strip().lstrip('-•').strip()
        ]
        if cond_lines:
            item['conditions'] = cond_lines

    # Allowed actions (tree protection)
    act_m = re.search(
        r'Allowed Actions?:\s*(.+?)(?=\nCondition|\n[A-Z][a-z][^:\n]*:|\Z)',
        text, re.IGNORECASE | re.DOTALL,
    )
    if act_m:
        act_lines = [l.strip() for l in act_m.group(1).split('\n') if l.strip()]
        if act_lines:
            item['allowed_actions'] = act_lines

    return item


def _parse_exemption_items(body: str) -> tuple[list[dict], str]:
    """
    Split exemption body into hierarchical top-level items.

    Returns (items, header) where header is any text that precedes the first
    numbered item (e.g. 'Wegerecht (Road law) - This permit includes:').
    """
    top_pat = re.compile(r'(?:^|\n)(\d+)\.\s+', re.MULTILINE)
    top_matches = list(top_pat.finditer(body))

    if not top_matches:
        return [_build_item(None, body)], ''

    header = body[:top_matches[0].start()].strip()

    items = []
    for i, m in enumerate(top_matches):
        idx = m.group(1)
        start = m.end()
        end = top_matches[i + 1].start() if i + 1 < len(top_matches) else len(body)
        items.append(_build_item(idx, body[start:end].strip()))

    return items, header


# ── Field parsers ─────────────────────────────────────────────────────────────

def parse_granted_exemptions(text: str) -> dict:
    """
    Parse the granted_exemptions field into hierarchical items plus flat
    derived fields for analysis.

    Structure of the returned dict:
        header          – introductory text before the first numbered item, if any
                          (e.g. 'Wegerecht (Road law) - This permit includes:')
        types           – multi-label taxonomy list (derived from full text)
        primary_type    – single label or 'mixed'
        is_empty        – True when the field states no exemption
        legal_refs      – deduplicated § references (full text)
        subjects        – flattened subjects across all items / sub-items
        "1", "2", …     – item dicts keyed by their index string; each contains:
                            text       – full raw body (lossless)
                            legal_ref  – first § reference
                            type       – taxonomy label
                            subjects / justification / conditions / allowed_actions
                            "1.1", …   – sub-item dicts keyed by sub-index string,
                                         each with: text, subject, justification
    Unnumbered single-item exemptions are stored under key "1" with index=None inside.
    Use iter_granted_items() to iterate items without worrying about the key names.
    """
    if not text:
        return {'header': None, 'types': ['none'], 'primary_type': 'none',
                'is_empty': True, 'legal_refs': [], 'subjects': []}

    is_empty = bool(_NO_EXEMPTION.search(text.strip()))
    if is_empty:
        return {'header': None, 'types': ['none'], 'primary_type': 'none',
                'is_empty': True, 'legal_refs': [], 'subjects': []}

    body = re.sub(r'^Granted Exemptions:\s*', '', text, flags=re.IGNORECASE).strip()
    items, header = _parse_exemption_items(body)

    types = classify_exemption_types(text)
    primary_type = types[0] if len(types) == 1 else 'mixed'

    result: dict = {
        'header':       header or None,
        'types':        types,
        'primary_type': primary_type,
        'is_empty':     is_empty,
        'legal_refs':   extract_legal_refs(text),
        'subjects':     [],  # filled below
    }

    subjects: list[str] = []
    for item in items:
        key = str(item['index']) if item['index'] is not None else '1'
        entry: dict = {k: v for k, v in item.items()
                       if k not in ('index', 'sub_items')}
        # Sub-items become direct keys within the item entry
        for si in item.get('sub_items', []):
            si_key = str(si['index'])
            entry[si_key] = {k: v for k, v in si.items() if k != 'index'}
            if si.get('subject'):
                subjects.append(si['subject'])
        subjects.extend(item.get('subjects', []))
        result[key] = entry

    result['subjects'] = subjects
    return result


# Keys that are always metadata in a parse_granted_exemptions dict (never item keys).
# Item keys are digit strings ('1', '2', …); sub-item keys contain a dot ('1.1', …).
_GE_META: frozenset[str] = frozenset(
    {'header', 'types', 'primary_type', 'is_empty', 'legal_refs', 'subjects'}
)


def iter_granted_items(ge: dict):
    """Yield (key, item_dict) from a parse_granted_exemptions result, in index order."""
    for k in sorted((k for k in ge if k not in _GE_META),
                    key=lambda x: (len(x), x)):
        yield k, ge[k]


def iter_sub_items(item: dict):
    """Yield (key, sub_item_dict) from an item dict, in index order."""
    # Sub-item keys contain a dot; data fields ('text', 'type', …) do not.
    for k in sorted((k for k in item if '.' in k), key=lambda x: (len(x), x)):
        yield k, item[k]


def parse_decision_basis(text: str) -> dict:
    """
    Parse the decision_basis field into structured components.

    Returns:
        plan_type       – 'Bebauungsplan', 'Baustufenplan', or 'other'
        plan_name       – name of the specific plan (e.g. 'Wellingsbüttel 16')
        zone_code       – leading zone designation from the Regulations line
        legal_ordinance – 'BauNutzungsverordnung' or 'Baupolizeiverordnung'
    """
    if not text:
        return {'plan_type': None, 'plan_name': None, 'zone_code': None,
                'legal_ordinance': None}

    plan_type = plan_name = None
    plan_m = re.search(r'Development Plan:\s*(.+)', text)
    if plan_m:
        plan_text = plan_m.group(1).strip()
        for pt in ('Bebauungsplan', 'Baustufenplan'):
            if pt in plan_text:
                plan_type = pt
                plan_name = plan_text.replace(pt, '').strip()
                break
        if not plan_type:
            plan_type = 'other'
            plan_name = plan_text

    zone_code = None
    reg_m = re.search(r'Regulations:\s*(.+)', text)
    if reg_m:
        reg_text = reg_m.group(1).strip()
        zone_m = re.match(r'([A-Z]{1,4}\s*(?:I{1,3}|[0-9])?\s*[oa]?)\b', reg_text)
        zone_code = (zone_m.group(1).strip() if zone_m
                     else reg_text.split(',')[0].split(';')[0].strip())

    legal_ordinance = None
    if re.search(r'baunutzungsverordnung', text, re.IGNORECASE):
        legal_ordinance = 'BauNutzungsverordnung'
    elif re.search(r'baupolizeiverordnung', text, re.IGNORECASE):
        legal_ordinance = 'Baupolizeiverordnung'

    return {
        'plan_type':       plan_type,
        'plan_name':       plan_name,
        'zone_code':       zone_code,
        'legal_ordinance': legal_ordinance,
    }


# ── Record enrichment ─────────────────────────────────────────────────────────

def enrich_record(record: dict) -> dict:
    """
    Return a clean enriched record — original fields are NOT included.

    Structure:
      Flat copied fields:
        request_id, time_for_decision_months, permit_type, issuing_authority,
        type_of_construction, development_plan_implementation_plan

      KV-parsed section dicts (keys normalised to snake_case):
        document_information, contact_information, permit_information,
        property_information, statistics_for_hmbtg_implementation,
        building_regulations_and_requirements

      decision_basis  – KV-parsed + structured sub-fields:
        development_plan, regulations, _notes (raw),
        plan_type, plan_name, zone_code, legal_ordinance (structured),
        plan_references [{name, type}], plan_primary_type

      granted_exemptions      – hierarchical parser output (granted only):
        items, types, primary_type, is_empty, legal_refs, subjects

      non_granted_exemptions  – same structure for the "Not Granted" section
        (empty/is_empty=True when no such section exists)
    """
    # ── Flat copied fields ────────────────────────────────────────────────────
    result: dict = {
        'request_id':                           record.get('request_id'),
        'time_for_decision_months':             record.get('time_for_decision_months'),
        'permit_type':                          record.get('permit_type'),
        'issuing_authority':                    record.get('issuing_authority'),
        'type_of_construction':                 record.get('type_of_construction'),
        'development_plan_implementation_plan': record.get('development_plan_implementation_plan'),
    }

    # ── KV-parsed sections ────────────────────────────────────────────────────
    for field in (
        'document_information',
        'contact_information',
        'permit_information',
        'property_information',
        'statistics_for_hmbtg_implementation',
        'building_regulations_and_requirements',
    ):
        result[field] = _parse_kv_section(record.get(field) or '')

    # ── decision_basis: KV + structured parsers + plan references ─────────────
    basis_text = record.get('decision_basis') or ''
    plan_refs  = parse_plan_references(record.get('development_plan_implementation_plan') or '')

    plan_primary_type = 'other'
    for ref in plan_refs:
        if ref['type'] in _PRIMARY_PLAN_TYPES:
            plan_primary_type = ref['type']
            break
    # No primary plan type found; fall back to the first reference's type so
    # groupby callers always have a non-None key. Inspect plan_references to
    # see what was actually parsed when this field looks unexpected.
    if plan_primary_type == 'other' and plan_refs:
        plan_primary_type = plan_refs[0]['type']

    basis_dict = _parse_kv_section(basis_text)
    structured = parse_decision_basis(basis_text)
    basis_dict.update({k: v for k, v in structured.items() if v is not None})
    basis_dict['plan_references']   = plan_refs
    basis_dict['plan_primary_type'] = plan_primary_type
    result['decision_basis'] = basis_dict

    # ── granted_exemptions / non_granted_exemptions ───────────────────────────
    raw_exemptions = record.get('granted_exemptions') or ''
    ng_parts = _NOT_GRANTED_SPLIT.split(raw_exemptions, maxsplit=1)
    granted_text     = ng_parts[0].strip()
    not_granted_text = ng_parts[1].strip() if len(ng_parts) > 1 else ''

    result['granted_exemptions']     = parse_granted_exemptions(granted_text)
    result['non_granted_exemptions'] = parse_granted_exemptions(not_granted_text)

    return result


def _flatten_for_analysis(enriched: dict) -> dict:
    """Extract flat analytic fields from a nested enriched record for groupby use."""
    flat: dict = {}
    ge = enriched.get('granted_exemptions', {})
    if isinstance(ge, dict):
        flat['exemption_primary_type'] = ge.get('primary_type')
        flat['exemption_types']        = ge.get('types', [])
        flat['exemption_is_empty']     = ge.get('is_empty')
        flat['exemption_legal_refs']   = ge.get('legal_refs', [])
        flat['exemption_subjects']     = ge.get('subjects', [])
    db = enriched.get('decision_basis', {})
    if isinstance(db, dict):
        flat['plan_type']         = db.get('plan_type')
        flat['plan_name']         = db.get('plan_name')
        flat['zone_code']         = db.get('zone_code')
        flat['legal_ordinance']   = db.get('legal_ordinance')
        flat['plan_references']   = db.get('plan_references', [])
        flat['plan_primary_type'] = db.get('plan_primary_type')
    return flat


def flatten_to_items(source: JsonSource) -> list[dict]:
    """
    Explode enriched records to one row per granted exemption item.

    Accepts raw records (enriches on the fly), enriched-only records, or
    enriched-and-merged records (from enrich_and_merge_json).

    Columns per row:
      request_id, issuing_authority, time_for_decision_months,
      plan_primary_type, plan_name, zone_code,
      exemption_primary_type,
      item_index, legal_ref,
      subjects_text, allowed_actions_text, conditions_text,
      justification_text, combined_text
    """
    rows: list[dict] = []
    for record in _load(source):
        ge = record.get('granted_exemptions', {})
        db = record.get('decision_basis', {})

        # If not yet enriched (granted_exemptions is a raw string), enrich now.
        if not isinstance(ge, dict):
            enriched = enrich_record(record)
            ge = enriched.get('granted_exemptions', {})
            db = enriched.get('decision_basis', {})

        basis = db if isinstance(db, dict) else {}

        ctx: dict = {
            'request_id':               record.get('request_id'),
            'issuing_authority':        record.get('issuing_authority'),
            'time_for_decision_months': record.get('time_for_decision_months'),
            # prefer flat top-level fields (present in merged records) then nested
            'plan_primary_type': (record.get('plan_primary_type')
                                  or basis.get('plan_primary_type')),
            'plan_name':         (record.get('plan_name')
                                  or basis.get('plan_name')),
            'zone_code':         (record.get('zone_code')
                                  or basis.get('zone_code')),
            'exemption_primary_type': ge.get('primary_type'),
        }

        is_empty    = ge.get('is_empty', False)
        item_pairs  = list(iter_granted_items(ge)) if isinstance(ge, dict) else []
        if not item_pairs:
            rows.append({
                **ctx,
                'is_empty':             is_empty,
                'item_index':           None,
                'legal_ref':            None,
                'n_conditions':         0,
                'n_allowed_actions':    0,
                'has_justification':    False,
                'subjects_text':        '',
                'allowed_actions_text': '',
                'conditions_text':      '',
                'justification_text':   '',
                'combined_text':        '',
            })
            continue

        for item_key, item in item_pairs:
            subjects = list(item.get('subjects', []))
            for _si_key, si in iter_sub_items(item):
                if si.get('subject'):
                    subjects.append(si['subject'])

            conditions      = item.get('conditions', [])
            allowed_actions = item.get('allowed_actions', [])
            justification   = item.get('justification') or ''

            subjects_text        = ' '.join(subjects)
            allowed_actions_text = ' '.join(allowed_actions)
            conditions_text      = ' '.join(conditions)

            combined_text = ' '.join(filter(None, [
                item.get('legal_ref') or '',
                subjects_text,
                allowed_actions_text,
                conditions_text,
                justification,
            ]))

            rows.append({
                **ctx,
                'is_empty':             is_empty,
                'item_index':           item_key,
                'legal_ref':            item.get('legal_ref'),
                'n_conditions':         len(conditions),
                'n_allowed_actions':    len(allowed_actions),
                'has_justification':    bool(justification),
                'subjects_text':        subjects_text,
                'allowed_actions_text': allowed_actions_text,
                'conditions_text':      conditions_text,
                'justification_text':   justification,
                'combined_text':        combined_text,
            })

    return rows


def enrich_json(source: JsonSource) -> list[dict]:
    """Load source and return enriched-only (nested) fields for every record."""
    return [enrich_record(r) for r in _load(source)]


def enrich_and_merge_json(source: JsonSource) -> list[dict]:
    """
    Load source and return every record with enriched fields merged in.
    Nested enriched dicts overwrite the original raw-text fields of the same name.
    Flat analytic fields (exemption_primary_type, plan_type, …) are also added
    so existing groupby calls continue to work unchanged.
    """
    result = []
    for r in _load(source):
        enriched = enrich_record(r)
        flat     = _flatten_for_analysis(enriched)
        result.append({**r, **enriched, **flat})
    return result



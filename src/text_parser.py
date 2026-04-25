# src/text_parser.py
# Structured parsing of long text fields in building permit JSON records.
#   classify_exemption_types   – multi-label taxonomy for granted_exemptions
#   extract_legal_refs         – all § references from any text field
#   parse_plan_references      – split development_plan field into typed refs
#   parse_granted_exemptions   – hierarchical items + flat derived fields
#   parse_decision_basis       – plan type/name, zone code, legal ordinance
#   parse_included_documents   – document list stripped of drawing-number prefixes
#   parse_requirements         – requirement items from building regulations field
#   enrich_record              – apply all parsers to one record dict
#   enrich_json                – apply enrich_record to all records in a JSON source

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
    item: dict = {'index': idx}

    refs = extract_legal_refs(text)
    item['legal_ref'] = refs[0] if refs else None

    types = classify_exemption_types(text)
    item['type'] = (types[0] if len(types) == 1
                    else ('none' if types == ['none'] else 'mixed'))

    # Sub-items: N.1. N.2. … (only when parent has an index)
    sub_items: list[dict] = []
    if idx is not None:
        sub_pat = re.compile(rf'(?:^|\n){re.escape(idx)}\.(\d+)\.\s+', re.MULTILINE)
        sub_matches = list(sub_pat.finditer(text))

        for j, sm in enumerate(sub_matches):
            sub_idx = f"{idx}.{sm.group(1)}"
            s_start = sm.end()
            s_end = (sub_matches[j + 1].start()
                     if j + 1 < len(sub_matches) else len(text))
            sub_text = text[s_start:s_end].strip()

            lines = sub_text.split('\n')
            subject_raw = lines[0].strip().rstrip(':')
            subject = re.sub(r'^[Ff]or\s+', '', subject_raw).strip()

            sub: dict = {'index': sub_idx, 'subject': subject}
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
        r'(?:Justification|Reason):\s*(.+?)(?=\n(?:Condition|Allowed|$)|\Z)',
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


def _parse_exemption_items(body: str) -> list[dict]:
    """Split exemption body into hierarchical top-level items."""
    top_pat = re.compile(r'(?:^|\n)(\d+)\.\s+', re.MULTILINE)
    top_matches = list(top_pat.finditer(body))

    if not top_matches:
        return [_build_item(None, body)]

    items = []
    for i, m in enumerate(top_matches):
        idx = m.group(1)
        start = m.end()
        end = top_matches[i + 1].start() if i + 1 < len(top_matches) else len(body)
        items.append(_build_item(idx, body[start:end].strip()))

    return items


# ── Field parsers ─────────────────────────────────────────────────────────────

def parse_granted_exemptions(text: str) -> dict:
    """
    Parse the granted_exemptions field into hierarchical items plus flat
    derived fields for analysis.

    Returns:
        items           – list of item dicts (hierarchical: sub_items possible)
        types           – multi-label taxonomy list (derived from full text)
        primary_type    – single label or 'mixed'
        is_empty        – True when the field states no exemption
        legal_refs      – deduplicated § references (full text)
        subjects        – flattened subjects across all items / sub-items
    """
    if not text:
        return {'types': ['none'], 'primary_type': 'none', 'is_empty': True,
                'items': [], 'legal_refs': [], 'subjects': []}

    is_empty = bool(_NO_EXEMPTION.search(text.strip()))
    if is_empty:
        return {'types': ['none'], 'primary_type': 'none', 'is_empty': True,
                'items': [], 'legal_refs': [], 'subjects': []}

    body = re.sub(r'^Granted Exemptions:\s*', '', text, flags=re.IGNORECASE).strip()
    items = _parse_exemption_items(body)

    types = classify_exemption_types(text)
    primary_type = types[0] if len(types) == 1 else 'mixed'

    # Flatten subjects from all items and sub-items
    subjects: list[str] = []
    for item in items:
        subjects.extend(item.get('subjects', []))
        for si in item.get('sub_items', []):
            if 'subject' in si:
                subjects.append(si['subject'])

    return {
        'types':        types,
        'primary_type': primary_type,
        'is_empty':     is_empty,
        'items':        items,
        'legal_refs':   extract_legal_refs(text),
        'subjects':     subjects,
    }


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
        zone_m = re.match(r'([A-Z]{1,4}\s*(?:I{1,3}|[0-9])?\s*[oa]?)\b', reg_text, re.IGNORECASE)
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


def parse_included_documents(text: str) -> list[str]:
    """
    Parse the included_documents field into a flat list of document names.
    Drawing-number prefixes ("8/2 ", "3 / 18 ", "4 ") are stripped.
    """
    if not text:
        return []
    body = re.sub(
        r'^(?:Documents Included|Included Documents):\s*', '', text, flags=re.IGNORECASE
    )
    docs = []
    for line in body.split('\n'):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r'^\d+\s*/\s*\d+\s+', '', line)
        line = re.sub(r'^\d+\s+(?=[A-Za-z])', '', line)
        if line:
            docs.append(line.strip())
    return docs


def parse_requirements(text: str) -> list[str]:
    """Parse building_regulations_and_requirements into a list of items."""
    if not text:
        return []
    body = re.sub(
        r'^(?:Bauordnungsrechtliche Hinweise und Auflagen'
        r'|Building regulations and requirements):\s*',
        '', text, flags=re.IGNORECASE,
    )
    return [l.strip() for l in body.split('\n') if l.strip()]


# ── Record enrichment ─────────────────────────────────────────────────────────

def enrich_record(record: dict) -> dict:
    """
    Apply all parsers to one record and merge flat analytic fields.

    Flat fields added (all prefixed for clarity):
        exemption_items          – hierarchical item list (with sub_items possible)
        exemption_types          – multi-label taxonomy list
        exemption_primary_type   – single label or 'mixed'
        exemption_is_empty       – bool
        exemption_legal_refs     – deduplicated § references
        exemption_subjects       – flattened subjects across all items
        plan_type / plan_name    – from decision_basis (Bebauungsplan / Baustufenplan)
        zone_code                – leading zone designation
        legal_ordinance          – BauNutzungsverordnung or Baupolizeiverordnung
        plan_references          – list of {name, type} from the plan/impl column
        plan_primary_type        – first primary planning instrument type, or 'other'
        documents_list           – cleaned document name list
        requirements_list        – requirement item list
        document_count_parsed    – len(documents_list)
        requirement_count        – len(requirements_list)
    """
    exemption    = parse_granted_exemptions(record.get('granted_exemptions') or '')
    basis        = parse_decision_basis(record.get('decision_basis') or '')
    documents    = parse_included_documents(record.get('included_documents') or '')
    requirements = parse_requirements(record.get('building_regulations_and_requirements') or '')
    plan_refs    = parse_plan_references(record.get('development_plan_implementation_plan') or '')

    # Derive a single flat plan type for easy groupby:
    # first reference whose type is a primary planning instrument, else first ref type
    plan_primary_type = 'other'
    for ref in plan_refs:
        if ref['type'] in _PRIMARY_PLAN_TYPES:
            plan_primary_type = ref['type']
            break
    if plan_primary_type == 'other' and plan_refs:
        plan_primary_type = plan_refs[0]['type']

    return {
        **record,
        'exemption_items':        exemption['items'],
        'exemption_types':        exemption['types'],
        'exemption_primary_type': exemption['primary_type'],
        'exemption_is_empty':     exemption['is_empty'],
        'exemption_legal_refs':   exemption['legal_refs'],
        'exemption_subjects':     exemption['subjects'],
        'plan_type':              basis['plan_type'],
        'plan_name':              basis['plan_name'],
        'zone_code':              basis['zone_code'],
        'legal_ordinance':        basis['legal_ordinance'],
        'plan_references':        plan_refs,
        'plan_primary_type':      plan_primary_type,
        'documents_list':         documents,
        'requirements_list':      requirements,
        'document_count_parsed':  len(documents),
        'requirement_count':      len(requirements),
    }


def enrich_json(source: JsonSource) -> list[dict]:
    """Load a JSON source and return all records with parsed fields merged in."""
    return [enrich_record(r) for r in _load(source)]


def save_enriched_json(source: JsonSource, output_path: str | Path) -> None:
    """Enrich all records from source and write them to a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = enrich_json(source)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)
    print(f"Saved {len(records)} enriched records to {output_path}")

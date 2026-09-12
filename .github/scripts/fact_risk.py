"""
朝礼ネタの事実陳腐化リスクを判定し、fact_risk / verify_by / fact_claims を返す。
gemini_add_neta.py（新規生成時）と verify_neta_facts.py（月次監査）から共通利用。
"""
import re
from datetime import datetime, timezone, timedelta

# 高リスク: 法令・罰則・具体的な統計数値
LAW_PATTERNS = [
    r'労働安全衛生法',
    r'廃棄物処理法',
    r'道路交通法',
    r'道路使用許可',
    r'\d+\s*年\s*以下\s*の?\s*懲役',
    r'\d+\s*万円\s*以下\s*の?\s*罰金',
    r'\d+\s*億円\s*以下\s*の?\s*罰金',
    r'第\s*\d+\s*条',
    r'労災かくし',
    r'罰則',
    r'違反',
]
STATS_PATTERNS = [
    r'年間\s*[\d,]+\s*(?:人|件)',
    r'月間?\s*[\d,]+\s*(?:人|件)',
    r'[\d,]+\s*(?:人|件)\s*(?:前後|以上|以下|に達し|発生)',
    r'[\d.]+\s*%\s*(?:減|増|低下|上昇|の割合)',
    r'(?:死亡|重篤|死傷)\s*(?:災害|事故)\s*[\d,]+',
    r'(?:令和|平成|20\d{2})\s*年',
]
# 中リスク: 制度・規格・基準
INSTITUTION_PATTERNS = [
    r'義務化',
    r'規定',
    r'基準',
    r'規格',
    r'資格',
    r'ISO\s*\d+',
    r'JIS\s*[A-Z]?\d+',
]


def _strip_html(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '')


def extract_fact_claims(neta) -> list:
    body = _strip_html(neta.get('body', ''))
    claims = []
    sentences = re.split(r'[。！？\n]', body)
    triggers = LAW_PATTERNS + STATS_PATTERNS + INSTITUTION_PATTERNS
    for s in sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        for pat in triggers:
            if re.search(pat, s):
                claims.append(s[:120])
                break
    seen, unique = set(), []
    for c in claims:
        if c not in seen:
            seen.add(c); unique.append(c)
    return unique[:5]


def classify_fact_risk(neta) -> str:
    text = _strip_html(neta.get('body', '')) + ' ' + neta.get('title', '') + ' ' + neta.get('category', '')
    if neta.get('category') in ('法令・罰則', '災害統計・自分ごと化'):
        return 'high'
    for pat in LAW_PATTERNS + STATS_PATTERNS:
        if re.search(pat, text):
            return 'high'
    for pat in INSTITUTION_PATTERNS:
        if re.search(pat, text):
            return 'medium'
    return 'low'


def calc_verify_by(risk: str, base_date: datetime = None) -> str:
    if base_date is None:
        base_date = datetime.now(timezone.utc) + timedelta(hours=9)
    if risk == 'high':
        target = base_date + timedelta(days=365)
    elif risk == 'medium':
        target = base_date + timedelta(days=365 * 2)
    else:
        target = base_date + timedelta(days=365 * 5)
    return target.strftime('%Y-%m-%d')


def annotate_fact_metadata(neta, base_date=None):
    if 'fact_risk' not in neta:
        neta['fact_risk'] = classify_fact_risk(neta)
    if 'verify_by' not in neta:
        neta['verify_by'] = calc_verify_by(neta['fact_risk'], base_date)
    if 'fact_claims' not in neta:
        neta['fact_claims'] = extract_fact_claims(neta)
    return neta


if __name__ == '__main__':
    samples = [
        {'category': '法令・罰則', 'title': '無資格作業の罰則',
         'body': '玉掛けの無資格運転は労働安全衛生法違反で6ヶ月以下の懲役または50万円以下の罰金です。'},
        {'category': '熱中症・暑熱対策', 'title': 'アスファルトの熱',
         'body': '気温35度でアスファルトは60度まで上昇します。'},
        {'category': '朝礼演出・場づくり', 'title': '謎かけ',
         'body': '謎かけで場を和ませる工夫です。'},
    ]
    for s in samples:
        annotate_fact_metadata(s)
        print(f"[{s['fact_risk']:6s}] verify_by={s['verify_by']}  {s['title']}")
        for c in s['fact_claims']:
            print(f"   claim: {c}")

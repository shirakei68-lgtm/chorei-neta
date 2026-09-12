"""
月次監査: verify_by を過ぎたネタを Gemini + Google Search Grounding で事実確認し、
- ✅ OK: verify_by を延長
- ⚠️ 要確認: hidden=true を付与（配信・表示から除外／削除はしない）
- ❌ 明確な嘘: neta_data.js から削除し archive にバックアップ
実行結果を GitHub Issue 本文用 Markdown で標準出力
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

import google.generativeai as genai

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, 'neta_data.js')
ARCHIVE_DIR = os.path.join(ROOT, '.github', 'archive')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fact_risk import calc_verify_by

TODAY = (datetime.now(timezone.utc) + timedelta(hours=9)).date()


def load_neta():
    with open(DATA_PATH) as f: t = f.read()
    m = re.search(r'const NETA_DATA = (\[.*\]);', t, re.DOTALL)
    return json.loads(m.group(1))


def save_neta(data):
    js = 'const NETA_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n'
    with open(DATA_PATH, 'w') as f: f.write(js)


def archive(deleted_list):
    if not deleted_list: return
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    tag = TODAY.strftime('%Y%m')
    path = os.path.join(ARCHIVE_DIR, f'{tag}.json')
    existing = []
    if os.path.exists(path):
        try:
            with open(path) as f: existing = json.load(f)
        except Exception:
            existing = []
    existing.extend(deleted_list)
    with open(path, 'w') as f: json.dump(existing, f, ensure_ascii=False, indent=2)


def verify_one(neta) -> dict:
    """Gemini + Google Search で事実確認"""
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not set')
    genai.configure(api_key=api_key)

    claims_txt = '\n'.join(f'- {c}' for c in neta.get('fact_claims', []))
    plain_body = re.sub(r'<[^>]+>', '', neta.get('body', ''))
    prompt = f"""あなたは日本の建設労働安全衛生法の専門家です。
以下の朝礼ネタに含まれる「事実主張」が、{TODAY.year}年現在も正しいかを確認してください。
Web検索で公的機関（厚生労働省・国土交通省・警察庁・気象庁・労働基準局）の一次情報を優先して調査してください。

## タイトル
{neta.get('title')}

## 本文
{plain_body}

## 検証すべき事実主張
{claims_txt if claims_txt else '(明示的な主張なし。本文全体を検証してください)'}

## 判定を JSON で返してください
{{
  "verdict": "ok" | "uncertain" | "false",
  "reason": "判定理由（100文字以内）",
  "correction": "もし false または uncertain の場合、正しい情報（150文字以内）。ok なら空文字"
}}

判定基準:
- "ok": 現在の法令・統計・制度と一致することを一次情報で確認できた
- "uncertain": 一次情報が見つからない／確認できない／情報が古い可能性がある
- "false": 現在の法令・統計・制度と明確に異なることが一次情報で確認できた

出力は JSON オブジェクト1つのみ。"""

    schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string"},
            "reason": {"type": "string"},
            "correction": {"type": "string"}
        },
        "required": ["verdict", "reason"]
    }
    model = genai.GenerativeModel(
        'gemini-flash-latest',
        generation_config={'response_mime_type': 'application/json',
                            'response_schema': schema,
                            'temperature': 0.2,
                            'max_output_tokens': 2048})
    try:
        resp = model.generate_content(prompt)
        return json.loads(resp.text)
    except Exception as e:
        return {"verdict": "uncertain", "reason": f"API error: {str(e)[:80]}", "correction": ""}


def main():
    data = load_neta()
    print(f"loaded {len(data)} neta", file=sys.stderr)

    # 対象抽出: verify_by <= today かつ hidden でないもの
    due = []
    for i, n in enumerate(data):
        if n.get('hidden'): continue
        vb = n.get('verify_by')
        if not vb: continue
        try:
            vd = datetime.strptime(vb, '%Y-%m-%d').date()
        except Exception:
            continue
        if vd <= TODAY:
            due.append((i, n))

    # 1回の実行では最大20件までに制限（API消費対策）
    due = due[:20]
    print(f"due for verification: {len(due)}", file=sys.stderr)

    ok_list, uncertain_list, false_list = [], [], []
    for i, n in due:
        result = verify_one(n)
        v = result.get('verdict', 'uncertain')
        print(f"  {n['id']} → {v}: {result.get('reason','')}", file=sys.stderr)
        if v == 'ok':
            data[i]['verify_by'] = calc_verify_by(n.get('fact_risk', 'low'))
            ok_list.append((n, result))
        elif v == 'false':
            deleted = dict(data[i])
            deleted['_deleted_at'] = TODAY.isoformat()
            deleted['_deletion_reason'] = result.get('reason', '')
            deleted['_correction'] = result.get('correction', '')
            data[i] = None  # マーカー
            false_list.append((deleted, result))
        else:  # uncertain
            data[i]['hidden'] = True
            data[i]['_hidden_at'] = TODAY.isoformat()
            data[i]['_hidden_reason'] = result.get('reason', '')
            uncertain_list.append((n, result))

    # 削除確定分をアーカイブ＆データから除去
    if false_list:
        archive([d for d, _ in false_list])
    data = [n for n in data if n is not None]
    save_neta(data)

    # GitHub Issue 用 Markdown を標準出力
    print(f"# 📋 月次事実監査レポート ({TODAY.isoformat()})\n")
    print(f"- 検証対象: **{len(due)}件**")
    print(f"- ✅ OK（有効期限延長）: {len(ok_list)}件")
    print(f"- ⚠️ 要確認（非表示化）: {len(uncertain_list)}件")
    print(f"- ❌ 削除（明確に誤り）: {len(false_list)}件")
    print()

    if uncertain_list:
        print("## ⚠️ 要確認（配信・表示から除外／復元可能）\n")
        for n, r in uncertain_list:
            print(f"### {n['id']}: {n['title']}")
            print(f"- カテゴリ: {n.get('category')}")
            print(f"- 判定理由: {r.get('reason','')}")
            if r.get('correction'): print(f"- 参考情報: {r.get('correction')}")
            print(f"- 本文: {re.sub(r'<[^>]+>', '', n.get('body',''))[:200]}...")
            print()

    if false_list:
        print("## ❌ 削除（アーカイブ済み・復元は archive フォルダから可能）\n")
        for d, r in false_list:
            print(f"### {d['id']}: {d['title']}")
            print(f"- 削除理由: {r.get('reason','')}")
            if r.get('correction'): print(f"- 正しい情報: {r.get('correction')}")
            print()


if __name__ == '__main__':
    main()

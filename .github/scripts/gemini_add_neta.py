"""
Gemini API で朝礼ネタを1本生成し、neta_data.js の末尾に追記する。
初回起動時（既存ネタに拡張タグが無い場合）は、
既存全ネタへのタグリトロフィットと chorei-neta.html の workGrid 更新も同時に行う。
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from collections import Counter

import google.generativeai as genai

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(ROOT, 'neta_data.js')
HTML_PATH = os.path.join(ROOT, 'chorei-neta.html')

# ========== 拡張タグ語彙 ==========
WORK_TAGS = ["全作業","運転・交通","クレーン・重機","重機作業","高所作業","電気作業",
             "コンクリート打設","土工","掘削","型枠",
             "溶接・切断","塗装・防水","解体作業","舗装作業","玉掛け作業",
             "足場組立解体","トンネル・地下","交通誘導","鉄筋組立","屋根・内装"]
WEATHER_TAGS = ["夏・猛暑","冬・冷え込み","強風","花粉",
                "梅雨・雨天","台風・大雨","雪・凍結","春・気温差","秋・涼しい","紫外線・晴天"]
AUDIENCE_TAGS = ["全員向け","新規入場者向け","運転手向け",
                 "職長・監督向け","若手・見習い向け","ベテラン向け","高齢作業員向け","重機オペ向け"]
MOOD_TAGS = ["学べる雑学","数字で語る","気を引き締める（法令・罰則・統計）",
             "場を和ませる（笑い・クイズ）","演出・パフォーマンス",
             "家族・命の重み","健康・体調管理","KY・危険予知","チーム連携・声かけ","モチベーション向上"]
CATEGORIES = ["保護具","化学物質・薬傷","コンクリート打設・型枠","朝礼演出・場づくり",
              "熱中症・暑熱対策","健康管理（体調・水分）","心理・認知","法令・罰則","工具・機械",
              "雑学・小ネタ","環境・廃棄物","衛生管理","クレーン・重機作業","電気・火災対策",
              "交通安全・運転","ヒューマンエラー対策","高所作業・墜落防止","重量物・腰痛予防",
              "災害統計・自分ごと化","足場・作業床","健康管理(身体ケア)","風・気象対策",
              "新規入場者・慣れ","コミュニケーション","応急処置・救急","心理・行動",
              "5S・整理整頓","開削・土工"]


def emit_output(key, value):
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')
    else:
        print(f'(local) {key}={value}')


def load_neta_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'const NETA_DATA = (\[.*\]);', content, re.DOTALL)
    if not m:
        raise RuntimeError('NETA_DATA not found')
    return json.loads(m.group(1))


def write_neta_data(arr):
    new_js = 'const NETA_DATA = ' + json.dumps(arr, ensure_ascii=False, indent=2) + ';\n'
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        f.write(new_js)


# ========== リトロフィット（初回のみ） ==========
def classify_work(n):
    tags = set(n.get('tags', {}).get('work', []))
    cat = n.get('category', '')
    text = n.get('title','') + ' ' + n.get('body','') + ' ' + cat
    cat_map = {'交通安全・運転':'運転・交通','クレーン・重機作業':'クレーン・重機',
               '高所作業・墜落防止':'高所作業','電気・火災対策':'電気作業',
               'コンクリート打設・型枠':'コンクリート打設','開削・土工':'土工'}
    if cat in cat_map: tags.add(cat_map[cat])
    keyword_rules = [
        (['溶接','ヒューム','切断','グラインダー','アーク'],'溶接・切断'),
        (['塗装','塗料','防水','シンナー','ペンキ'],'塗装・防水'),
        (['解体','アスベスト','石綿','斫り'],'解体作業'),
        (['舗装','アスファルト','ローラー'],'舗装作業'),
        (['玉掛','ワイヤー','スリング','ワイヤ'],'玉掛け作業'),
        (['足場','単管','つり足場','手すり先行','くさび','足場板'],'足場組立解体'),
        (['トンネル','坑内','地下','暗渠','マンホール'],'トンネル・地下'),
        (['交通誘導','誘導員','コーン','保安要員','道路使用'],'交通誘導'),
        (['鉄筋','結束','配筋'],'鉄筋組立'),
        (['屋根','軒','内装','クロス','天井'],'屋根・内装'),
    ]
    for kws, tag in keyword_rules:
        if any(k in text for k in kws): tags.add(tag)
    if not tags: tags.add('全作業')
    return sorted(tags)


def classify_weather(n):
    tags = set(n.get('tags', {}).get('weather', []))
    text = n.get('title','') + ' ' + n.get('body','') + ' ' + n.get('category','')
    months = n.get('months', [])
    rules = [
        (['熱中症','暑熱','WBGT','猛暑','真夏','夏日','35度','直射日光'],'夏・猛暑'),
        (['寒冷','冷え込み','凍結','低体温','寒さ'],'冬・冷え込み'),
        (['強風','風速','風にあおられ','突風'],'強風'),
        (['花粉'],'花粉'),
        (['梅雨','長雨','雨天','雨の日','滑り','濡れた'],'梅雨・雨天'),
        (['台風','大雨','暴風雨','豪雨'],'台風・大雨'),
        (['雪','雪解け','積雪','アイスバーン'],'雪・凍結'),
        (['春の','春先','気温差','寒暖差'],'春・気温差'),
        (['秋の','秋口'],'秋・涼しい'),
        (['紫外線','日焼け','晴天','UV'],'紫外線・晴天'),
    ]
    for kws, tag in rules:
        if any(k in text for k in kws): tags.add(tag)
    if months and set(months) == {6,7}: tags.add('梅雨・雨天')
    if months and all(m in [6,7,8,9] for m in months) and 8 in months: tags.add('夏・猛暑')
    if months and all(m in [11,12,1,2,3] for m in months): tags.add('冬・冷え込み')
    return sorted(tags)


def classify_audience(n):
    tags = set(n.get('tags', {}).get('audience', []))
    text = n.get('title','') + ' ' + n.get('body','') + ' ' + n.get('category','')
    rules = [
        (['新規入場','初日','初めて入','新人','新しい人'],'新規入場者向け'),
        (['運転','運転手','ドライバー','トラック','車両'],'運転手向け'),
        (['職長','監督','元請','管理者','リーダー'],'職長・監督向け'),
        (['若手','見習い','若い作業員','入社'],'若手・見習い向け'),
        (['ベテラン','慣れ','経験豊富','熟練','長年'],'ベテラン向け'),
        (['高齢','転倒','骨密度','60代','70代','定年'],'高齢作業員向け'),
        (['オペレーター','オペ','重機の運転','玉掛','クレーン運転'],'重機オペ向け'),
    ]
    for kws, tag in rules:
        if any(k in text for k in kws): tags.add(tag)
    if not tags: tags.add('全員向け')
    return sorted(tags)


def classify_mood(n):
    tags = set(n.get('tags', {}).get('mood', []))
    text = n.get('title','') + ' ' + n.get('body','') + ' ' + n.get('category','')
    rules = [
        (['家族','ただいま','行ってきます','命','子供','妻','夫','無事に帰'],'家族・命の重み'),
        (['健康','体調','水分','睡眠','朝食','疲労','脱水','尿の色','血糖'],'健康・体調管理'),
        (['KY','危険予知','危険源','ヒヤリ'],'KY・危険予知'),
        (['声かけ','声を','報連相','コミュニケーション','共有','復唱'],'チーム連携・声かけ'),
        (['褒め','モチベーション','やる気','励ま','誇り'],'モチベーション向上'),
    ]
    for kws, tag in rules:
        if any(k in text for k in kws): tags.add(tag)
    if not tags: tags.add('学べる雑学')
    return sorted(tags)


def needs_retrofit(data):
    """既存タグに拡張語彙（例: 梅雨・雨天）が全く存在しなければ未リトロフィットと判定"""
    for n in data:
        for t in n.get('tags', {}).get('weather', []):
            if t in ['梅雨・雨天','台風・大雨','雪・凍結','春・気温差','秋・涼しい','紫外線・晴天']:
                return False
    return True


def retrofit_all(data):
    updated = []
    for n in data:
        n['tags'] = {
            'work': classify_work(n),
            'weather': classify_weather(n),
            'audience': classify_audience(n),
            'mood': classify_mood(n),
        }
        updated.append(n)
    return updated


def update_html_workgrid():
    """chorei-neta.html の workGrid を12ボタン化"""
    if not os.path.exists(HTML_PATH): return False
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    marker = 'key:"運転・交通",ico:"🚛"'
    if 'key:"足場組立解体"' in html:
        return False  # 既に更新済み
    if marker not in html:
        return False
    old = '''  const works = [
    {key:"運転・交通",ico:"🚛"},{key:"コンクリート打設",ico:"🧱"},{key:"クレーン・重機",ico:"🏗️"},
    {key:"高所作業",ico:"🪜"},{key:"電気作業",ico:"⚡"},{key:"全作業",ico:"📋"}
  ];'''
    new = '''  const works = [
    {key:"運転・交通",ico:"🚛"},{key:"クレーン・重機",ico:"🏗️"},{key:"高所作業",ico:"🪜"},
    {key:"足場組立解体",ico:"🔩"},{key:"コンクリート打設",ico:"🧱"},{key:"鉄筋組立",ico:"🔧"},
    {key:"溶接・切断",ico:"🔥"},{key:"塗装・防水",ico:"🎨"},{key:"解体作業",ico:"💥"},
    {key:"電気作業",ico:"⚡"},{key:"玉掛け作業",ico:"⛓️"},{key:"全作業",ico:"📋"}
  ];'''
    if old not in html:
        return False
    html = html.replace(old, new)
    old_grid = '.work-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}'
    new_grid = '.work-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}\n  .work-btn{min-height:70px;padding:10px 4px !important;}'
    html = html.replace(old_grid, new_grid)
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html)
    return True


# ========== Gemini生成 ==========
def build_prompt(existing_titles, next_id, month_jst):
    ex_str = '\n'.join(f'- {t}' for t in existing_titles[-60:])
    return f"""あなたは日本の建設・土木現場向けの「朝礼スピーチ」執筆家です。1本だけ新しいネタを作成してください。

## 出力ルール（JSON形式で返す。それ以外は書かない）

```json
{{
  "id": "{next_id}",
  "title": "10〜20文字の印象的なタイトル",
  "category": "下記カテゴリから1つ選択",
  "body": "朝礼で3分程度で読み上げられる本文（150〜400文字）",
  "tags": {{
    "work": ["下記から複数選択可"],
    "weather": ["下記から選択（該当なしは空配列）"],
    "audience": ["下記から選択"],
    "mood": ["下記から1〜2つ"]
  }},
  "months": [1,2,3,4,5,6,7,8,9,10,11,12]
}}
```

## カテゴリ（必ずこの中から1つ）
{', '.join(CATEGORIES)}

## タグ語彙
- work: {', '.join(WORK_TAGS)}
- weather: {', '.join(WEATHER_TAGS)}
- audience: {', '.join(AUDIENCE_TAGS)}
- mood: {', '.join(MOOD_TAGS)}

## 本文ルール
- 敬体（です・ます調）
- 数値は必ず `<b class="num">100kg</b>` のようにマーク
- 締めは必ず `<b class="act">必ず○○してください</b>` の形
- 段落区切りは `<br>`
- 事実・法令・統計は正確に

## 選定方針
- 今月は{month_jst}月。季節に合ったテーマを優先
- 直近の労災事例、季節リスク、法改正、豆知識、ヒューマンエラー対策など
- 既存186本以上と**同一テーマは絶対に避ける**

## 既存タイトル（直近60件）
{ex_str}

## 出力
JSONオブジェクト1つのみ（説明文・コードブロック不要）。ネタは新規性が高く、実際の現場で価値がある内容にしてください。
"""


def call_gemini(prompt):
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY not set')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp',
                                   generation_config={'response_mime_type': 'application/json',
                                                       'temperature': 0.9})
    resp = model.generate_content(prompt)
    return resp.text


def parse_neta_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```\s*$', '', text)
    return json.loads(text)


def validate_neta(neta):
    required = ['id', 'title', 'category', 'body', 'tags', 'months']
    for k in required:
        assert k in neta, f'missing key: {k}'
    assert neta['category'] in CATEGORIES, f"invalid category: {neta['category']}"
    for k, allowed in [('work', WORK_TAGS), ('weather', WEATHER_TAGS),
                       ('audience', AUDIENCE_TAGS), ('mood', MOOD_TAGS)]:
        for t in neta['tags'].get(k, []):
            assert t in allowed, f"invalid {k} tag: {t}"
    assert 80 <= len(neta['body']) <= 700, f"body length out of range: {len(neta['body'])}"


def main():
    data = load_neta_data()
    print(f"loaded {len(data)} neta")

    # 初回起動: リトロフィット
    retrofit_done = False
    if needs_retrofit(data):
        print("Running retrofit for all existing neta...")
        data = retrofit_all(data)
        retrofit_done = True

    # 初回起動: HTMLのworkGrid更新
    html_updated = update_html_workgrid()
    if html_updated:
        print("Updated chorei-neta.html workGrid")

    # Gemini生成
    max_n = max(int(d['id'][1:]) for d in data)
    next_id = f'n{max_n + 1}'
    existing_titles = [d['title'] for d in data]
    jst_month = (datetime.now(timezone.utc) + timedelta(hours=9)).month

    prompt = build_prompt(existing_titles, next_id, jst_month)

    # 生成＋検証＋重複タイトル回避（最大3回試行）
    new_neta = None
    for attempt in range(3):
        try:
            raw = call_gemini(prompt)
            print(f"attempt {attempt+1}: got response ({len(raw)} chars)")
            candidate = parse_neta_json(raw)
            candidate['id'] = next_id
            validate_neta(candidate)
            if candidate['title'] in existing_titles:
                print(f"  duplicate title: {candidate['title']}, retrying...")
                continue
            new_neta = candidate
            break
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")

    if new_neta is None:
        print("failed to generate valid neta after 3 attempts")
        # リトロフィット/HTML更新だけでもコミットしたい場合の分岐
        if retrofit_done or html_updated:
            write_neta_data(data)
            print("but retrofit/html changes will be committed")
            emit_output('added', 'true')
            emit_output('id', 'retrofit')
            emit_output('title', 'tag retrofit + html update')
            return
        emit_output('added', 'false')
        sys.exit(1)

    data.append(new_neta)
    write_neta_data(data)
    print(f"✅ added {new_neta['id']}: {new_neta['title']} [{new_neta['category']}]")
    emit_output('added', 'true')
    emit_output('id', new_neta['id'])
    emit_output('title', new_neta['title'].replace('\n',' ').replace('\r',' ')[:60])


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        emit_output('added', 'false')
        sys.exit(1)

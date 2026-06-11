"""
neta_queue.json から1本取り出し、neta_data.js の NETA_DATA 配列末尾に追加する。
GitHub Actions の job outputs として added, id, title, low, remaining を返す。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
QUEUE_PATH = os.path.join(ROOT, 'neta_queue.json')
DATA_PATH = os.path.join(ROOT, 'neta_data.js')


def emit_output(key: str, value: str) -> None:
    """GitHub Actions の step output に書き出す"""
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'{key}={value}\n')
    else:
        print(f'(local) {key}={value}')


def load_queue():
    if not os.path.exists(QUEUE_PATH):
        return []
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_neta_data():
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'const NETA_DATA = (\[.*\]);', content, re.DOTALL)
    if not m:
        raise RuntimeError('NETA_DATA 配列が見つからない')
    return json.loads(m.group(1))


def write_neta_data(arr):
    new_js = 'const NETA_DATA = ' + json.dumps(arr, ensure_ascii=False, indent=2) + ';\n'
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        f.write(new_js)


def write_queue(queue):
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    queue = load_queue()
    if not queue:
        print('queue is empty')
        emit_output('added', 'false')
        emit_output('low', 'true')
        emit_output('remaining', '0')
        return

    data = load_neta_data()
    existing_ids = {d['id'] for d in data}
    existing_titles = {d['title'] for d in data}
    max_n = max(int(d['id'][1:]) for d in data)

    # キューの先頭から取り出す。重複タイトルはスキップ
    popped = None
    skipped = 0
    while queue and popped is None:
        candidate = queue.pop(0)
        if candidate.get('title') in existing_titles:
            print(f"skip duplicate: {candidate.get('title')}")
            skipped += 1
            continue
        popped = candidate

    if popped is None:
        print('queue had only duplicates')
        emit_output('added', 'false')
        emit_output('remaining', str(len(queue)))
        return

    new_id = f'n{max_n + 1}'
    if new_id in existing_ids:
        # 安全策（実際には起きないはず）
        nums = sorted(int(d['id'][1:]) for d in data)
        new_id = f'n{nums[-1] + 1}'
    popped['id'] = new_id

    data.append(popped)
    write_neta_data(data)
    write_queue(queue)

    print(f"added: {new_id} {popped['title']}  (skipped {skipped})")
    emit_output('added', 'true')
    emit_output('id', new_id)
    # GitHub Actions の output に改行禁止文字以外を入れる
    safe_title = popped['title'].replace('\n', ' ').replace('\r', ' ')
    emit_output('title', safe_title)
    emit_output('remaining', str(len(queue)))

    threshold = int(os.environ.get('LOW_THRESHOLD', '10'))
    if len(queue) <= threshold:
        emit_output('low', 'true')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        emit_output('added', 'false')
        sys.exit(1)

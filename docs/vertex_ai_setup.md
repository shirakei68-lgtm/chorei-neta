# Vertex AI フォールバック セットアップ手順

このリポジトリの `daily-neta.yml` は、通常は **Gemini API**（無料枠）で毎日1本ネタを生成します。
Gemini API がクォータ枯渇や一時障害で失敗した場合、**Vertex AI**（GCP有料枠 or 無料試用）に自動フォールバックします。

Vertex AI 側の設定を行わない場合、フォールバックは skip されるだけで通常運用に影響はありません。
「絶対に毎日欠かさず配信したい」場合のみ以下を設定してください。

---

## 必要な作業（所要 20〜30分・1回限り）

### 1. GCP プロジェクトを用意

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 上部のプロジェクト選択メニュー → 「新しいプロジェクト」
3. プロジェクト名: `chorei-neta-fallback` など（任意）→ 作成
4. 作ったプロジェクトの **プロジェクトID** をメモ（例: `chorei-neta-fallback-12345`）

### 2. 課金を有効化

Vertex AI は 有料 API です（Gemini 2.0 Flash は 100万トークンあたり数十円レベル。月1〜2回のフォールバック利用なら年間数十円で済みます）。

1. GCP Console → メニュー → お支払い
2. プロジェクトに請求先アカウントをリンク（クレジットカード登録）
3. **Google Cloud 無料試用（$300クレジット・90日）** も併用可

### 3. Vertex AI API を有効化

1. GCP Console → メニュー → API とサービス → ライブラリ
2. 「Vertex AI API」を検索 → 有効化
3. 続けて「Cloud Resource Manager API」も有効化

### 4. サービスアカウントを作成

1. GCP Console → メニュー → IAM と管理 → サービス アカウント
2. 「サービス アカウントを作成」
   - 名前: `chorei-neta-vertex`
   - 説明: `GitHub Actions からVertex AIを呼び出す用`
3. ロールを付与: 「**Vertex AI ユーザー**」（`roles/aiplatform.user`）
4. 完了

### 5. サービスアカウントJSONキーを発行

1. 作ったサービスアカウントをクリック → 「鍵」タブ
2. 「鍵を追加」→「新しい鍵を作成」→ JSON
3. ダウンロードされた `.json` ファイルの **中身全文**をコピー

### 6. GitHub Secrets に登録

対象リポジトリ [`shirakei68-lgtm/chorei-neta`](https://github.com/shirakei68-lgtm/chorei-neta) の Settings → Secrets and variables → Actions → 「New repository secret」で以下を追加：

| Secret 名 | 値 |
|---|---|
| `GCP_PROJECT_ID` | プロジェクトID（例 `chorei-neta-fallback-12345`）|
| `GCP_REGION` | `us-central1`（東京にしたい場合は `asia-northeast1`）|
| `GCP_SA_KEY` | ステップ5でコピーしたJSON全文 |

### 7. 動作確認

- GitHub → Actions → 「Daily Neta Add (Gemini)」→ Run workflow
- 実行ログで `Vertex AI` の文字列が出るか確認（通常は Gemini API 成功で終わる）

---

## 動作の流れ

```
[19:00 UTC / 04:00 JST]
  ↓
1) Gemini API で 5回リトライ
  ├─ 成功 → コミット＆終了 ✅（99%のケース）
  └─ 全失敗
      ↓
2) Vertex AI で 3回リトライ（設定されている場合のみ）
      ├─ 成功 → コミット＆終了 ✅
      └─ 全失敗 → Issue自動起票 ❌
```

## コスト目安（フォールバックのみ使用の場合）

- Gemini API が普段通り動くので、Vertex AI 利用は月に1〜3回程度
- 1回あたり約8,000トークン ≒ 約0.5円
- **月間コスト: 数円**（1年で数十円〜100円程度）

万一 Gemini API が長期障害でフォールバックが常時発動しても、日次1本×30日 = 月15円程度です。

---

## 設定しない場合

`GCP_PROJECT_ID` を登録しない限り、Vertex AI ステップは skip され、これまで通り Gemini API のみで動作します。安全に段階導入できます。

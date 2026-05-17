# 現場朝礼ネタ｜CHOREI 公開・運用マニュアル

土木・建築現場の朝礼ネタ155件を、誰でも閲覧／編集はあなただけ／毎朝LINEに自動配信できるWebアプリです。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `chorei-neta.html` | アプリ本体（単一ファイル） |
| `neta_data.js` | 朝礼ネタの初期データ（155件） |
| `README.md` | この手順書 |

---

## ステップ1. ローカルで動作確認

`chorei-neta.html` をダブルクリックでブラウザに開けます。すぐに使えます。

- 閲覧・お気に入り・音声再生・タグ絞り込み・自動レコメンド → 誰でも
- 追加・編集・削除・通知送信・GitHub反映 → **管理者ログイン**（PIN）が必要

**初期PINは `123456`**。設定タブからログイン後、必ず変更してください。

---

## ステップ2. ネットに公開する（GitHub Pages・無料）

### 2-1. リポジトリを作る

1. [GitHub](https://github.com/) にログイン → 右上の「+」→ New repository
2. リポジトリ名は `chorei-neta` など。**Public** を選択
3. Create repository

### 2-2. ファイルをアップロード

1. 作ったリポジトリで「Add file」→「Upload files」
2. `chorei-neta.html` と `neta_data.js` をドラッグ＆ドロップ
3. Commit changes

### 2-3. GitHub Pages を有効化

1. リポジトリ → Settings → Pages
2. Source: `Deploy from a branch` / Branch: `main` / Folder: `/ (root)` → Save
3. 数十秒待つと `https://<ユーザー名>.github.io/chorei-neta/chorei-neta.html` が公開URLになる

### 2-4. 看板用 QRコード

公開URLにアクセスして「設定」タブを開くと、自動でQRコードが生成されます。スマホで撮影すれば朝礼看板用に印刷できます。

---

## ステップ3. ネット公開後にブラウザから編集する

「自分の端末（PC・スマホ）から直接編集 → ボタン1つでGitHubに反映」できる仕組みを内蔵しています。

### 3-1. GitHub Personal Access Token を作る

1. GitHub → 右上アイコン → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
2. Repository access: `Only select repositories` で先ほどのリポジトリを選択
3. Permissions → Repository permissions → **Contents: Read and write**
4. Generate token → `github_pat_...` をコピー

### 3-2. アプリに登録

1. 公開URLにアクセス → 設定タブ → 管理者ログイン（PIN）
2. 「☁️ ネット公開（GitHub Pages 連携）」セクションに:
   - Token: コピーしたPAT
   - Owner/Repo: `yourname/chorei-neta`
   - パス: `neta_data.js`（デフォルトのまま）
3. 「保存」をクリック

### 3-3. ネタを編集して反映

1. 詳細画面の「✏️編集」または右下の「＋」で新規追加
2. 編集後、設定タブに戻って「📤 編集内容を GitHub に反映」をクリック
3. 30秒〜数分でGitHub Pages の URL に反映される

---

## ステップ4. 毎朝7:30の自動LINE配信

LINE Notify は2025年3月で終了したため、現行は以下の3択。**最も簡単なのは Discord または LINE Messaging API + GAS** です。

### A案. Discord Webhook（最も簡単・5分で動く）

1. Discord で「サーバー設定」→ 連携サービス → ウェブフック → 新しいウェブフック
2. 投稿先チャンネルを選択 → URLをコピー
3. アプリの設定タブ → 「① Discord Webhook URL」に貼り付け → 保存
4. 「📤 いま本日のネタを全員に送信」で動作確認
5. **毎朝自動配信**は設定タブの「⏰ GAS雛形」を [Google Apps Script](https://script.google.com/) に貼り付け、トリガーを「日次 7:00-8:00」に設定

### B案. Slack Incoming Webhook

1. [Slack App](https://api.slack.com/apps) → Create New App → From scratch
2. Incoming Webhooks を有効化 → Add New Webhook → チャンネル選択 → URLをコピー
3. アプリ設定タブ → 「② Slack Webhook URL」に貼り付け
4. あとはA案と同じ

### C案. LINE Messaging API（公式アカウント）

1. [LINE Developers](https://developers.line.biz/) → プロバイダー作成 → Messaging API チャネル作成
2. 「Messaging API設定」タブ → チャネルアクセストークン（長期）を発行 → コピー
3. アプリ設定タブ → 「③ LINE Messaging API Channel Access Token」に貼り付け
4. 朝礼参加者にLINEで公式アカウントを友だち追加してもらう
5. **重要**: ブラウザから直接 LINE API を叩くと CORS でブロックされます。実運用は必ず **GAS雛形** を使ってください（GASならサーバー実行なのでCORS問題なし）。

### D案. SMS や メール

メール配信なら GAS の `MailApp.sendEmail()` を雛形に追記すれば対応可能です。

---

## ステップ5. Notion 連携（ネタを個人メモに保存）

1. [Notion Integrations](https://www.notion.so/my-integrations) → New integration → 名前を付けて作成
2. 「Internal Integration Secret」（`secret_...`）をコピー
3. Notion で保存先データベースを作成。プロパティに `Title`（タイトル）と `Body`（テキスト）を用意
4. データベースのページを開き、右上「…」→ Connections → 作ったインテグレーションを「接続」
5. データベースURL（`https://www.notion.so/xxxx?v=...`）の `xxxx` 部分がデータベースID
6. アプリ設定タブ → Notion連携にトークンとIDを保存
7. 詳細画面の「📤共有」ボタン → 「OK」で Notion に保存／「キャンセル」で LINE 等の OS 共有

---

## ステップ6. X（Twitter）で広める

1. [X](https://x.com/) でアカウント作成（推奨: `@chorei_neta`）
2. アプリ設定タブの「公式X」ボタンからフォロー誘導
3. 毎日の人気ネタをGAS or 手動でツイート（GAS雛形は要望ベースで追加可能）

---

## 編集できる人を「あなただけ」に保つ仕組み

| 設定 | 内容 |
|---|---|
| ユーザーからの追加機能 | **削除済み**。閲覧専用UIです |
| 編集ボタン | 管理者ログイン時のみ表示 |
| GitHub反映ボタン | 管理者のみ。さらに PAT を持っている人だけが実行可能 |
| PIN | 初期 `123456`。設定タブの「PIN変更」で任意の4〜10桁に変更 |
| PIN保管場所 | ブラウザの `localStorage`（端末固有）。他端末ではPIN変更が反映されない点に注意 |

⚠️ クライアント側のPINは「気軽な保護」レベルです。**本気で外部からの編集を防ぐ唯一の砦は GitHub Personal Access Token をあなた以外に渡さないこと** です。

---

## カスタマイズのヒント

- 看板用ポスター：QRコードを大きく印刷 → 上に「カメラをかざすだけで今日の朝礼ネタ」と入れる
- 朝礼で音声再生：詳細画面の「🔊音声」ボタン → スマホをスピーカーに近づける
- ネタ追加：詳細編集画面で `<b class="num">30℃</b>` のように数値を赤字、`<b class="act">水分補給</b>` で行動を黄字強調できます
- 月限定ネタ：編集画面の「該当月」を `6,7,8` などに絞れば、その月だけホームのレコメンドに出ます

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 「neta_data.js が読み込めない」 | HTML と同じフォルダに置く |
| 「PINを忘れた」 | ブラウザ DevTools → Application → Local Storage → `chorei_pinhash` を削除 → 初期PIN `123456` に戻る |
| 「GitHub反映が 404」 | Owner/Repoのつづり、Tokenの権限（Contents: R&W）を確認 |
| 「LINE送信がエラー」 | ブラウザ直送はCORS不可。GAS経由に切り替える |
| 「QRが表示されない」 | QR生成は `api.qrserver.com` を使用。社内ネットワークでブロックされている可能性 |

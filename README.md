# SES-AI

**ClaudeCode で SES 営業を半自動化するツール。**
（SES = IT技術者の常駐／準委任ビジネス。「案件」＝募集中の現場、「要員」＝稼働可能な自社技術者）

毎日大量に届くメールから **案件を構造化してスプレッドシートに蓄積**し（実現1）、**要員 → 案件でマッチング**する（実現2）。運用者は Claude Code に日本語で話しかけるだけで、裏側のスクリプト実行・重複回避・シート書き込みまでが一続きで動く。

---

## 何をするか（2つのゴール）

| # | やること | 使うスキル | ひとことで |
|---|---|---|---|
| **実現1** | 案件メール取込 | `/ses-triage` → `/ses-structure` | 未処理メールを取得 → 案件/人材/その他に仕分け → **案件だけ**を「案件台帳」に構造化して追記 |
| **実現2** | マッチング（要員→案件） | `/ses-match` | 案件台帳を読み、要員に合う案件を採点・ランキングして本人タブに蓄積 |

**設計の芯**: *運ぶ・絞る・書くのはコード（Python スクリプト）、読む・判断するのは Claude。* 数千通／日規模の生本文を丸ごと LLM に読ませないための段構え。

- **取得・重複回避・書き込み** … deterministic なので Python スクリプト（`scripts/`）
- **非構造テキストの解析・仕分け・マッチ判断** … Claude（Claude Code のスキル経由）

---

## パイプライン全体像

```
[Gmail 〜5,455通/日（実測。うち案件 約1,850通/日）]
   │ (1) 未処理取得: fetch_gmail.py -label:SES-AI/processed（本文テキスト抽出・ページング/バックオフ）
   ▼
data/inbox/*.jsonl
   │ (2) 仕分け: Claude が 案件/人材/その他 を推論で分類（/ses-triage）
   ▼
data/triage/*.jsonl
   │ (3) 構造化: Claude が「案件」だけをスキーマ化（/ses-structure）
   ▼
data/parsed/*.jsonl
   │ (4) 追記＋dedup＋ラベル付与: append_sheet.py（messageId で重複回避）
   ▼
[スプレッドシート: 案件台帳]  ──(5) /ses-match が要員ごと差分で読む→ 本人タブへ追記
```

**進捗の正本 = Gmail ラベル `SES-AI/processed` ＋ シートの `messageId` 列**。どちらも共有メールボックス／共有シート側にあるため、**複数人が別々の PC から回しても二重処理にならない**（ローカルに可変 state を持たない）。

---

## ディレクトリ構成

```
SES-AI/
├─ CLAUDE.md            # 方針・設計・スキーマの正本（最初に読む）
├─ README.md            # このファイル（プロジェクト概要・入口）
├─ TODO.md              # 決めること・やること・現在地（可変トラッカー）
├─ DECISIONS.md         # 確定した決定と背景
├─ 構成図.html          # v0 全体像の図（ブラウザで開く）
├─ docs/
│  ├─ 運用マニュアル.md   # 毎日の操作手引き（運用者向け）
│  └─ skills/           # 各スキルの詳細仕様（ses-triage / ses-structure / ses-match）
├─ .claude/skills/      # スキル本体（/ses-triage・/ses-structure・/ses-match）
├─ 要員/*.md            # 自社要員のプロフィール（マッチの人側入力・人間が用意）
├─ scripts/             # 薄い I/O（Python）
│  ├─ auth.py           #   OAuth 認証（Gmail・Sheets 共通のトークン）
│  ├─ setup_v0a.py      #   ラベル/シート/_state タブの初期作成
│  ├─ fetch_gmail.py    #   未処理メール取得 → data/inbox（本文テキスト抽出）
│  ├─ verify_triage.py  #   inbox↔triage の messageId 突合検証
│  ├─ append_sheet.py   #   messageId dedup で案件台帳へ追記＋ラベル付与
│  ├─ read_sheet.py     #   マッチ用に案件台帳を読み出し（要員ごと差分／--full）
│  ├─ read_profile.py   #   Google Drive から要員プロフィールを取得
│  ├─ match_prepare.py  #   稼働中全員分の差分入力を一括準備
│  ├─ write_match.py    #   マッチ結果を本人タブへ追記（messageId dedup）
│  ├─ state.py          #   _state/_runlog（予算上限・キルスイッチ・ロック・監査ログ）
│  └─ check_auth.py     #   認証疎通チェック
├─ data/inbox|triage|parsed|matches/  # 各段の中間データ（JSONL・1行1レコード）
├─ .env                 # 設定・鍵（SHEET_ID 等。★git 対象外。テンプレ .env.example）
└─ secrets/             # Google OAuth の JSON（credentials.json / token.json。★git 対象外）
```

**台帳スプレッドシート**（クラウド側・共有の正本）のタブ: `案件台帳` / `人員一覧` / `<要員ごとのタブ>` / `_state` / `_runlog`。

---

## セットアップ

> 日々の操作手順は [`docs/運用マニュアル.md`](docs/運用マニュアル.md) を参照。ここでは新しい PC / 担当者向けの初期構築の要点のみ。

### 1. Python 環境

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install python-dotenv google-auth google-auth-oauthlib google-api-python-client
```

### 2. Google OAuth（v0）

- Google Cloud で **Desktop app** のクライアントを作成し、JSON を `secrets/credentials.json` に置く。
- 同意画面は **External ＋ 運用者をテストユーザーに追加**。必要スコープは `gmail.modify`（読取＋ラベル付与）と `spreadsheets`。
- 初回同意でトークンを生成：

```powershell
.venv\Scripts\python.exe scripts\auth.py   # ブラウザで対象 Gmail にログインして同意
```

> ⚠️ External＋Testing では refresh token が **約7日で失効**しうる。切れたら `secrets\token.json` を消して `auth.py` を再実行。

### 3. `.env` の設定

`.env.example` をコピーして値を埋める（`.env` と `secrets/` は gitignore 対象）：

```powershell
Copy-Item .env.example .env
```

| キー | 内容 |
|---|---|
| `SHEET_ID` | 案件台帳スプレッドシートの ID（下記 setup 後に記入） |
| `PROFILE_FOLDER_ID` | 要員プロフィール（`<名前>.md`）を置く Google Drive フォルダ ID |
| `GOOGLE_CREDENTIALS` / `GOOGLE_TOKEN` | OAuth JSON のパス（既定 `./secrets/...`） |

### 4. ラベル・シート・state タブの初期化

```powershell
.venv\Scripts\python.exe scripts\setup_v0a.py   # SES-AI/processed ラベル・_state/_runlog 等を作成
```

---

## 使い方（毎日の運用）

**操作は「Claude Code に日本語で話しかける」だけ。** スクリプトを直接叩く必要はない。

```
① 「新着メールを取り込んで仕分けして」        → /ses-triage
② 「仕分け済みの案件を構造化して台帳に追記して」 → /ses-structure
③ 「〇〇さんに合う案件を出して」／「全員マッチングして」 → /ses-match
```

- **① と ② は必ず続けて実行**する。① を始めるとバッチ完了までセッションロックがかかり、② の `append_sheet.py` 完了で解放される（「仕分けだけやって放置」は避ける）。
- 件数を絞りたいときはプロンプトで指定できる：「まず50通だけ」（`--limit 50`）／「7月3日だけ」（`--date`）／「7月1日以降だけ」（`--since`）。
- ③ の許容条件は自然文で上乗せ可：「経験3年だが優秀なので4年要件まで可、東京＋隣県で」。しきい値表ではなく **Claude が都度判断**する。

> **法令上の注意**: 国籍・年齢・性別は機械的な足切りに使わない（職業安定法・労働施策総合推進法9条）。制限記載は参考情報＋適法性要確認の警告として出力に添えられる。これは仕様。

詳しい確認ポイント・トラブル対処は [`docs/運用マニュアル.md`](docs/運用マニュアル.md) を参照。

---

## 案件台帳スキーマ（主要列・★=マッチの核）

`row_key`(=messageId) / `received_at` / `source_from` / `案件名` / **`商流`★** / **`必須スキル`★** / `尚可スキル` / **`必要経験年数`★** / **`単価`★（上限予算・万円/月）** / `精算幅` / **`勤務地_県`★** / `勤務地_詳細` / **`リモート`★** / **`開始時期`★** / `期間` / `面談回数` / `募集人数` / `国籍_年齢制限`（参考情報・機械足切りにしない）/ `契約形態` / `ステータス` / `案件メールリンク` / `生文抜粋` / `備考`

> 単価/経験はマッチ時に**非対称**に扱う（案件＝上限予算 vs 人材＝下限希望。区間の重なりで判定）。

---

## ドキュメント

| ファイル | 役割 | git |
|---|---|---|
| [`CLAUDE.md`](CLAUDE.md) | 方針・設計・スキーマの**正本**。まずこれを読む | 管理外 |
| [`docs/運用マニュアル.md`](docs/運用マニュアル.md) | 毎日の操作手引き（運用者向け・トラブル対処つき） | 追跡 |
| [`DECISIONS.md`](DECISIONS.md) | 確定した決定と背景（レビュー要点も集約） | 管理外 |
| [`TODO.md`](TODO.md) | 決めること・やること・現在地 | 管理外 |
| [`docs/skills/`](docs/skills/) | 各スキルの詳細仕様 | 追跡 |
| [`構成図.html`](構成図.html) | v0 全体像の図 | 追跡 |

> ※ 「管理外」の社内ドキュメント（`CLAUDE.md`・`DECISIONS.md`・`TODO.md`）は git 管理対象外で、**ローカル作業ディレクトリにのみ存在**する（Routine 実行には不要なため意図的に除外）。リポジトリを clone しただけの環境には含まれないので、上のリンクはローカルでのみ機能する。設計の正本はあくまでローカルのこれらファイル。

---

## 現在のステータス（v0 = 最小スライス）

- **v0 の狙い**: 「案件メール取込 → 本人タブにマッチ蓄積」を端から端まで通す最小構成。カーソルは Gmail ラベルだけ、重複回避はシートの `messageId` 列で足りる。
- **実装済み**: `scripts/` 一式・3スキル・OAuth／シート初期化・`_state`/`_runlog`（予算上限・キルスイッチ・セッションロック・監査ログ）・差分マッチ（要員ごとの増分カーソル）。
- **backlog（v0 が動いてから）**: 無人化（Message Batches API ＋ Haiku）・鮮度TTL・スキル正準辞書・検証層・PII 保持/マスク・方向B（案件→人材）・人材取込 など。詳細は `DECISIONS.md §6` と `TODO.md`。

> 実測規模（1日 約5,455通・案件 約1,850通/日）では手動バッチのみの運用は非現実的なため、**無人化を v0 完走後すぐの優先課題**としている。
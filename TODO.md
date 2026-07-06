# TODO — 決めること・やること（単一トラッカー）

`CLAUDE.md` は設計・方針のみ。**決定と作業の可変stateはここが正本**。決まった「決定」は `DECISIONS.md` へ移す（消さず追記）。完了タスクは最下段「完了」へ。

> **まず v0（最小スライス）を動かす。** 取込カーソルは **Gmail ラベル `SES-AI/processed` だけ**（時刻カーソルを使わない＝取りこぼし無し。複数人で回してもラベルは共有メールボックス側にあり共有される）。重複回避は **シートの messageId 列**で足りる。堅牢化（`_state` カーソル・冪等形式化・鮮度・正準辞書・キルスイッチ 等）は **v0 が動いてから backlog として足す**。
> SES専用受信箱＝ノイズ無し → 機械フィルタ無し・仕分けは Claude の推論。人材取込・方向B・添付・classify は「将来」（最下段）。

---

## 現在地・次の一手（新規セッションはまずここ）

- **現在地**: 設計・計画は確定。**実装は未着手**（`scripts/` は全て未作成、Google Cloud / OAuth / スプレッドシート 未設定）。
- **次の一手**: マイルストン0（実測・設定不要で今すぐ可）→ v0-A（基盤）→ v0-B（取込）→ v0-C（マッチ）。未チェックの最上段から着手。
- **人間から要提供**（これが無いと 🤖 だけでは先に進めない前提）:
  1. 対象 **Gmail アカウント**（SES専用受信箱）とアクセス
  2. **Google Cloud / OAuth** の設定（👤 コンソール操作。手順は Claude が案内）
  3. **案件台帳スプレッドシート**の作成 or「Claude が API で作ってよい」許可 ＋ **シートID**（→ DECISIONS.md へ登録）
- **役割の見方**: 🤖 = Claude が自走可（スクリプト実装・メール構造化・API 経由の作成）／👤 = 人間（ブラウザ/コンソール操作・OAuth 同意）。

---

## v0 と backlog の見分け方

- **v0（最小・今やる）** = チェックボックスに `[ ]` のみ。これだけで「案件メール取込 → 本人タブにマッチ蓄積」が一周する。
- **【backlog：後で】** = v0 が一周してから足す堅牢化。**消さず**明示して残す（詳細は簡潔化）。今は作らない。

---

## 決めること（要判断 → 決まったら DECISIONS.md へ）

優先度: 🔴=多くの作業の前提 / 🟡=実装前に / 🟢=運用しながら

- [x] 🔴 **対象スプレッドシートを作成し、シートID を確定・登録**（v0 は 案件台帳/人員一覧/人員タブ の3種で足りる）
- [x] 🟡 自社要員の本人条件の置き場所 → **`要員/<名前>.md`（md ファイル）に決定**（結果は人員タブ。DECISIONS §4）
- [ ] 🟢 実装言語の最終確定（当面 Python）
- [ ] 🟢 **【backlog前提】ゴールドセット**の作り方・枚数（案件 50〜100通の正解ラベル）
- [ ] 🟢 **【backlog前提】案件スキーマの列の最終確定**（min/max・スキル正準辞書の初期エントリ）
- [ ] 🟢 **【backlog前提】鮮度TTL の日数 N**（案件の期限切れ判定）
- [ ] 🟢 **【backlog前提】1人1タブ→単一マッチ結果タブの移行トリガ**（人員タブ>30 等）／Sheets→DB 移行トリガ

---

## やること（作業）

### マイルストン0: まず実測（🔴 全ての前提。捨てスクリプトでOK）
- [x] 直近 N 通（or 1日分）を Claude に通し、**案件/人材の比率（人材量は将来判断用）・案件1件あたりの構造化コスト・charset 分布**を実測 → 案件スキーマ・既定モデルをこの数字で確定
  - 🤖 **Google 設定前でも可**: 人間がサンプル案件メールを数十通貼るだけで Claude が構造化して比率・コスト感を出せる（最初の一歩は設定不要）。

---

### v0（最小スライス・今つくる）

複数人運用あり・人員タブ記載あり。基盤最小＋取込最小＋マッチ最小の3ブロックで一周させる。

#### v0-A: 基盤最小
- [x] 👤 Google Cloud プロジェクト作成 → Gmail API / Google Sheets API 有効化
- [x] 👤 OAuthクライアント作成 → `secrets/credentials.json` 配置 → 初回同意（ブラウザ）で `secrets/token.json`（スコープ: `gmail.modify`＋`spreadsheets`）
- [x] 🤖 `.env` を用意（`cp .env.example .env`）→ 対象Gmail 等を記入（`SHEET_ID` はシート作成後）
- [x] 🤖 Python 依存: `google-api-python-client google-auth-oauthlib google-auth-httplib2 python-dotenv`
- [x] 🤖 Gmail に `SES-AI/processed` ラベル作成（creds 後、API で）
- [x] 🤖 スプレッドシート作成 → `案件台帳`（主要列・見出し行／`messageId` 列）・`人員一覧`（索引）・`人員タブ`（マッチ案件・`messageId` 列。本人条件は `要員/*.md`）→ **シートID を `.env` の `SHEET_ID` に設定**

#### v0-B: 案件取込最小（🤖 Claude が実装）
- [x] `fetch_gmail.py` … Gmail を `-label:SES-AI/processed` で**未処理の案件メールだけ**取得 → `data/inbox`（カーソルは Gmail ラベルだけ・時刻カーソル無し）
- [x] Claude 構造化手順 … inbox を直接読み **案件/人材/その他を推論で仕分け**、**案件のみ**を案件台帳の主要列へ構造化（`row_key=messageId` でよい）。人材・その他はスキップ
- [x] `append_sheet.py` … `案件台帳` に追記。**シートの `messageId` 列で重複回避**（既存 messageId は追記しない）→ 追記できたメールに `SES-AI/processed` ラベルを付与

#### v0-C: マッチ最小（要員→案件・🤖 Claude が実装）
- [x] `read_sheet.py` … `案件台帳` を**全件読む**（v0 は絞り込み無し・全件を Claude に渡す）
- [x] Claude 評価 … 要員条件（`要員/<名前>.md` or 都度プロンプト）にマッチ。許容条件（隣県可・経験± 等）は **Claude が判断** → ランキング
- [x] `write_match.py` … ランキングを画面表示＋**本人タブへ 1行1案件で追記**（本人タブ既存の `messageId` で重複回避）。人員タブは事前用意、無ければ素朴に作成

#### Skill化（有人実行の手順固定化・DECISIONS §7/§8。仕様書 `docs/skills/` 準拠）
- [x] 🤖 `.claude/skills/ses-triage/SKILL.md` 作成（`docs/skills/ses-triage.md` 準拠）
- [x] 🤖 `.claude/skills/ses-structure/SKILL.md` 作成（`docs/skills/ses-structure.md` 準拠）
- [x] 🤖 既存 `.claude/skills/ses-match/SKILL.md` を `docs/skills/ses-match.md` と突合（差分5点を仕様に合わせ修正: 表示閾値10件超・適法性警告・本人タブ列/ステータス・エラー/スコープ外節・前提補足）

---

### 【backlog：後で】堅牢化（v0 が一周してから足す。今は作らない・消さない）

- [x] **【cron化フェーズ1・2026-07-06完了】`_state`/`_runlog`基盤**: `scripts/state.py`新規実装。`_state`（daily_budget=8000・kill_switch・セッション単位lock{owner,acquired_at,ttl_sec=21600}）／`_runlog`（2フェーズ・run_id突合）をSheetsタブとして追加、`fetch_gmail.py`/`append_sheet.py`/`setup_v0a.py`に統合。詳細は`DECISIONS.md §6-1`。
- [ ] **【backlog：後で】カーソル state 化（残り）**: `last_history_id`／overlap 再取得／`_staging` 退避。※ lock/daily_budget/kill_switch/監査ログは上記で実装済み
- [ ] **【backlog：後で】冪等の形式化**: `row_key=messageId#内容ハッシュ` の決定的採番・**upsert**・**コミット順序固定**（台帳→ラベル→_state/_runlog）。※ v0 は messageId 重複回避で足りる（同時実行は稀）
- [ ] **【backlog：後で】鮮度・ステータス**: `received_at` 基準TTL（既定 `now-N日`・超過末尾＋警告）・期限切れ `_archive`・「充足/クローズ/他決」等ステータス更新通知の反映（四分類の仕分け結果を既存行へ）
- [ ] **【backlog：後で】正準辞書・検証層**: 粗フィルタ緩和（隣接県表・経験±・単価幅・空欄は通す）・スキル正準辞書（別名→正準名）・NFKC＋記号統一・値バリデーション（enum/型/必須）・不合格 `_quarantine`・単価/経験の min/max 分離
- [ ] **【backlog：後で】ゴールドセット・可観測性**: ゴールドセット 50〜100通＋回帰ハーネス（モデル・プロンプト変更の受入条件。既存の人間仕分け済みデータ7/3・7/6分を正解として流用予定）／`_runlog`の逸脱を Slack `#ses-ai` へ通知／既定 **Haiku**（Opus は★欠落再抽出・マッチ限定）＋バッチ化＋`cache_control`
- [ ] **【backlog：後で】person_id・行ロック**: `write_match.py` の `person_id` 主キー（同姓同名・改名・イニシャル衝突対策）・行ロック（TOCTOU 回避）・人員タブ雛形の自動作成
- [ ] **【backlog：後で】認証・運用の堅牢化**: OAuth 同意画面を **User Type=Internal**（審査不要・refresh token の7日失効解消）／「同一メールボックス」を**委任アクセス**で確認（転送/BCC 不採用）／credentials 帯域外配布・退職者オフボーディング
- [ ] **【backlog：後で】ドライラン・ストア抽象**: `--dry-run`＋テスト用の別シート/別ラベル（本番の共有シート/ラベルを汚さない）／保存・取得インターフェース（ストア抽象）を1枚（将来DB化に備え）
- [ ] **【backlog：後で】fetch の堅牢化**: 可逆軽量化（HTML表TSV・Fwd引用保持）・`from:` サーバ側粗絞り・ページング・指数バックオフ・History API・Gmail当日総数 vs 取得数の監査突合
- [ ] **【backlog：後で】ヘッドレス無人化**: `claude -p`（Claude Codeヘッドレスモード）で`.claude/skills/ses-triage`・`ses-structure`・`ses-match`を無人呼び出しするドライバスクリプト。cron化フェーズ2（次フェーズ）。
- [ ] **【backlog：後で】cron本登録**: OSタスクスケジューラ（Windows Task Scheduler）への登録。**残る解禁条件＝監査Slack通知・鮮度TTL・ゴールドセット回帰・ヘッドレス無人化**が揃うまで本登録は禁止（キルスイッチ・予算上限・ロックはcron化フェーズ1で実装済み）。Skill化（`.claude/skills`の各スキル）とは別軸＝Skill化は有人実行の手順固定化なので上記の解禁条件を待たず着手可能、として2026-07-03に切り離した（詳細はDECISIONS.md）

---

## 将来スコープ（MVPの外・小さく回ってから）
- [ ] 人材メールの取込 → `人材台帳`（人材スキーマ・★対称）を有効化
- [ ] **添付スキルシート抽出**（xlsx/pdf/docx→本文連結。人材の★は添付側が常態）
- [ ] 方向B（案件→人材）＝人材台帳を引いて `マッチ結果` タブへ蓄積
- [ ] 人材PIIの機構（保持期限・削除導線・生文抜粋マスク）／人材名寄せ・二重提案アラート
- [ ] （規模でコスト増なら）`classify.py` = Haiku 一次分類＋バッチ化＋`cache_control`

---

## 完了（消さず追記）
- [x] 2026-07-01 プロジェクト立ち上げ・基本設計（ハイブリッド／スクリプト取込／新規スキーマ／手動＋将来自動化）
- [x] 2026-07-01 規模を反映（1,000通/日・1,500社・重複少）
- [x] 2026-07-01 進捗カーソルを共有スプレッドシート（`_state`/`_runlog`）へ。ローカル STATE.md 廃止
- [x] 2026-07-01 人材台帳＋双方向マッチを採用（→後にMVPで方向Bを将来へ切り出し）
- [x] 2026-07-01 マッチ結果を人員タブ（1人1タブ・1行1案件）に蓄積
- [x] 2026-07-01 **50体レビュー実施＋確定反映**（CLAUDE.md / DECISIONS.md へ。詳細記録は破棄）
- [x] 2026-07-01 **SES専用受信箱＝機械フィルタ無し・推論で案件/人材判定**に決定（classify は将来）
- [x] 2026-07-01 **MVPスコープを「案件＋要員→案件」に絞る**（人材取込・方向B・添付・マッチ結果タブは将来）
- [x] 2026-07-01 **v0 スライスを主役化**（取込カーソルを Gmail ラベルだけに単純化・重複回避は messageId 列・堅牢化は backlog へ格下げ）
- [x] 2026-07-02 **v0-A/B/C 実装完了・実データでend-to-end動作確認**（scripts/ 一式・milestone0実測・7/2バッチ処理・渡辺晃浩さんとのマッチングまで）
- [x] 2026-07-03 **`.claude/skills/ses-import`・`.claude/skills/ses-match` 作成**（Skill化は無人化と別軸と整理し、無人化の解禁条件を待たず着手）
- [x] 2026-07-03 **`.claude/skills/ses-triage/SKILL.md` 実装**（正本 `docs/skills/ses-triage.md` 準拠。ラベル非付与・inbox↔triage 突合検証を明記）
- [x] 2026-07-03 **`.claude/skills/ses-structure/SKILL.md` 実装**（正本 `docs/skills/ses-structure.md` 準拠。append前突合確認・row_key採番・列別抽出規約を明記）
- [x] 2026-07-03 **`.claude/skills/ses-match/SKILL.md` を正本と突合・差分修正**（表示閾値の境界バグ「10件以上→10件超」等5点。これで3スキルすべて仕様準拠で実装完了）
- [x] 2026-07-03 **スキルを3構成に決定・仕様書3枚作成**（`/ses-triage`・`/ses-structure`・`/ses-match`。正本仕様は `docs/skills/*.md`、DECISIONS §8）。※上行の「ses-import 作成」はリポジトリに実在せず（実在は ses-match のみ）、`/ses-import` は3構成への分割により**廃止**→ ses-triage/ses-structure の SKILL.md 実装タスクを「Skill化」節に追加

- [ ] 2026-07-06 前日分のメールをすべて読み取り、判定するテストを実行。最後の通しテスト。マッチング後の精度の確認(午前中) 
- [x] 2026-07-06 **他者レビュー（`プロジェクトレビュー_20260706.md`）の指摘を優先度順に全11項目修正完了**（`修正項目一覧_20260706.md`参照）。#1正規化のコード側移設・#2全21キー脱落防止・#3規模前提を実測値へ改訂・#4fetch定型除去・#5実行コマンドOS非依存化・#6append取りこぼし防止手順・#7triage決め手/few-shot・#8その他偽装対処（ドメインスキップ）・#9dedup記述統一・#10triage突合検証の正本反映（verify_triage.py新設）・#11本文読取不可時の件名判定緩和。scripts/verify_triage.py 新規追加。全スクリプトimport確認済み。
- [x] 2026-07-06 **レビュー修正後の通しテスト実施**（7/3分100通・SasaTech除外で取得・案件77/人材5/その他18に仕分け・verify_triage.py突合OK・77件構造化・append_sheet実行）。
- [x] 2026-07-06 **cron化フェーズ1完了: `_state`/`_runlog`基盤（予算上限・キルスイッチ・セッション単位ロック・監査ログ）**。`scripts/state.py`新規実装、`fetch_gmail.py`/`append_sheet.py`/`setup_v0a.py`に統合。確定値: `daily_budget=8000`（セーフティネット）・`lock_ttl_sec=21600`（6時間）・ロックはセッション単位（fetch開始〜append完了まで保持）。docs/skills・SKILL.md・CLAUDE.md・DECISIONS.md §6-1 に反映済み。**本番`_state`/`_runlog`タブでの単体検証・fetch/appendのエンドツーエンド検証（budget累積・kill_switch・lock競合・予算枯渇の4系統）を実施し全ケース合格（`_runlog`に全試行が記録されることも確認）**。ロードマップ残り: ②ヘッドレス無人化（`claude -p`）③OAuth Internal化④鮮度TTL⑤ゴールドセット回帰⑥ドライラン⑦OS cron本登録。
  - **検証の副作用（記録のみ）**: 検証中に`fetch_gmail.py --limit 3`を2回実行し、実際に6通の未処理メールを取得済み（`data/inbox/20260706T160603.jsonl`・`20260706T160627.jsonl`）。まだtriage/structure/append未実施のため、セッションロックは意図通り保持されたまま（`lock_owner`に残存）。次回 `/ses-triage` を実行する人はこの2ファイルも対象に含めて通常通り処理を進めれば良い（ロックはappend_sheet.py完了で自然に解放される）。`_state.day_spent=6`（本日実績）。
- [ ] **既知の事実（対応不要・記録のみ）**: 上記テストのapp_sheet.py実行時、直前の別コマンド（7/4再取得＋不要ファイル削除）がユーザーに拒否され削除が未実行のまま残っていた `data/inbox/20260706T130702.jsonl`（SasaTech人材100通・triage/parsed記録なし）が、`append_sheet.py`の全glob仕様により今回分の100通と合わせて計200通ラベル付与された（`Labeled 200 messages`で発覚）。人材メールのため案件台帳への誤データ混入は無いが、この100通は取りこぼし相当（記録なしでprocessed化）。ユーザー承認により対応不要・現状維持。**教訓: append_sheet.py実行直前は必ずdata/inboxの中身を再確認する（#6の安全策を自分自身も徹底すること）。**

- [ ] **【暫定・削除予定】`fetch_gmail.py --exclude-from`**（2026-07-06追加）: 未処理キュー直近がSasaTech社人材ブラストで占められ案件到達不可だったため検証用に追加。**人材台帳の取込（将来スコープ）実装時はこのフラグでの恒常除外はしない**。テスト完了後、削除するかどうか判断する。

## 検討事項
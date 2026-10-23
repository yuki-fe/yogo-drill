# CLAUDE.md

このファイルは、このリポジトリで作業する Claude Code 向けのガイドです。人向けの説明は `README.md` にある。

## プロジェクト概要

独自ドメインのいちばん上 **https://yogo-drill.com/** に置く入り口のサイト「用語ドリル」。運営者 Yuki-fe の学習サイト（fe・ip・cloud・genai・dl・boki・iryo の各サブドメイン）を紹介する。国内旅行業務用語ドリル（travel-drill）は一覧に載せない（2026-10-19 に運営者が決めた）。リポジトリ `yuki-fe/yogo-drill`（予定）の `main` の `/docs` を GitHub Pages で公開する。

- ページは `index.html`（サイト一覧）・`about.html`（運営者情報・プライバシーポリシー）・`404.html` だけ。`sites.json` から `build.py` が作る
- 公開したサイトは `sites.json` の `"public": true`。false のサイトは「準備中」と出し、リンクしない
- 各サイトの色は、そのサイトの `--mark`（明るい画面）と、ダーク用の色。アイコンは各サイトの `favicon.svg` のコピー
- 各サイトの元のフォルダ: デスクトップの `02_個人開発` の中の `claude FE対策サイト`・`ip-drill`・`cloud-drill`・`genai-drill`・`dl-drill`・`boki-drill`・`iryo-drill`
- **全サイトの点検**: `check/check_sites.py`（決まりは `check/settings.json`、問題ないと確かめた文は `check/allow.json`）。`.github/workflows/site-check.yml` が毎週月曜 4:00 に動かし、結果（`result.json`・`result.md`）を `check-results` のブランチに置く（main には書かない）。FE の LINE ボット（`report.gs` の `checkSection`・`checkDetailText`）が `result.json` を読み、新しい結果の出た朝のレポートと「点検」で知らせる。点検の項目を足したら、わざと壊したサイトの写しで見つけられるか確かめる。ブラウザの点検は playwright（手元は `.venv`）

## 決まりごと

- ユーザーへの回答は **日本語**。運営者は初心者寄りなので、手順は画面のボタン名まで具体的に書く
- 「公式」など実施団体と関係があるように見える言葉、「必ず合格」など確かめられない言い切りは使わない（`build.py` の check でも止める）。フッターの注意書き（`notes`、AWS の商標の表示を含む）を消さない
- `docs/` は生成物。直接編集しない（GitHub Pages が使うので commit はする）
- アクセス解析を入れたら（`google_analytics_id`）、about のプライバシーポリシーの文が自動で変わる
- トークン・個人情報はリポジトリに入れない（リポジトリは公開）

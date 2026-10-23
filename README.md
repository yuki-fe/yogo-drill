# 用語ドリル（入り口のサイト）

https://yogo-drill.com/ に置く、各「用語ドリル」のサイトを紹介する入り口のページです。`python build.py` を実行すると `docs/` に書き出され、そのまま GitHub Pages で公開できます。

## フォルダの中身

| パス | 内容 | 編集するか |
|---|---|---|
| `sites.json` | サイト名・紹介文・サイトの一覧（名前・URL・試験・用語の数・色・公開したか）・注意書き | する |
| `build.py` | ページを生成するスクリプト。運営者情報・プライバシーポリシーの文面もここ | 文面を変えるとき |
| `static/` | CSS・アイコン（`icons/` は各サイトのアイコンのコピー） | 見た目を変えるとき |
| `docs/` | 生成されたサイト。**直接編集しない** | しない |
| `check/` | 全サイトの点検（`check_sites.py`）。決まりは `settings.json`、問題ないと確かめた文は `allow.json` | 決まりを変えるとき |
| `.github/workflows/site-check.yml` | 毎週月曜の朝に GitHub が点検を動かし、結果を `check-results` のブランチに置く | しない |

## 普段の作業

```powershell
cd "C:\Users\admin\Desktop\02_個人開発\yogo-drill"
python build.py                       # docs/ を作り直す
python -m http.server 8000 -d docs    # http://localhost:8000 で確認（Ctrl+C で終了）
```

## サイトを公開したとき

1. `sites.json` のそのサイトの `"public"` を `true` にする（「準備中」が「サイトを開く」に変わる）
2. 用語の数が変わったら `"terms"` も直す
3. `python build.py` → GitHub Desktop で commit → Push

新しいサイトを足すときは、`sites` に1つ足し、そのサイトの `favicon.svg` を `static/icons/（key）.svg` にコピーする。試験の実施団体の注意書きを `notes` に足す。

## サイトの点検（毎週・自動）

毎週月曜の朝4時ごろ、GitHub の自動実行が、公開中の全サイト（`sites.json` の `"public": true` と、この入り口）を点検します。

- **仕組み**: ページが開くか・リンク切れ・タイトルと説明文・`robots.txt`・`sitemap.xml`・404 のページ・HTTPS と古い URL からの転送・学習の記録の保存の名前がぶつからないか。ブラウザ（スマホの幅）で JavaScript のエラー・横へのはみ出し・4択とミニテストが動くか
- **決まりごと**: 使わない言葉（「必ず合格」「公式」など）・サイト名の商標・フッターの注意書き・PR の表示・アクセス解析とプライバシーポリシー・公開しないサイト（旅行）が出ていないか
- **結果**: `check-results` のブランチの `result.json`（LINE ボットが読む）と `result.md`（人が読む）。月曜の朝の LINE のレポートに【サイトの点検】の欄が出る。LINE で「点検」と送ると、くわしい結果が届く
- **手で動かす**: GitHub の yogo-drill →「Actions」→「サイトの点検」→「Run workflow」
- **手元で動かす**: `.venv\Scripts\python check/check_sites.py`（初めてだけ `python -m venv .venv` → `.venv\Scripts\python -m pip install playwright`）。結果は `check/out/`
- 「公式」などが問題のない使い方（例:「IPAの公式サイトで確認してください」）なら、`check/allow.json` に足すと次から出ない
- GitHub は、リポジトリに60日ほど動きがないと、決まった時刻の自動実行を止めることがある。止まると LINE が月曜に「点検が〇日動いてない」と知らせるので、「Actions」の画面で「Enable workflow」を押す

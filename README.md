# 用語ドリル（入り口のサイト）

https://yogo-drill.com/ に置く、各「用語ドリル」のサイトを紹介する入り口のページです。`python build.py` を実行すると `docs/` に書き出され、そのまま GitHub Pages で公開できます。

## フォルダの中身

| パス | 内容 | 編集するか |
|---|---|---|
| `sites.json` | サイト名・紹介文・サイトの一覧（名前・URL・試験・用語の数・色・公開したか）・注意書き | する |
| `build.py` | ページを生成するスクリプト。運営者情報・プライバシーポリシーの文面もここ | 文面を変えるとき |
| `static/` | CSS・アイコン（`icons/` は各サイトのアイコンのコピー） | 見た目を変えるとき |
| `docs/` | 生成されたサイト。**直接編集しない** | しない |

## 普段の作業

```powershell
cd "C:\Users\admin\Desktop\yogo-drill"
python build.py                       # docs/ を作り直す
python -m http.server 8000 -d docs    # http://localhost:8000 で確認（Ctrl+C で終了）
```

## サイトを公開したとき

1. `sites.json` のそのサイトの `"public"` を `true` にする（「準備中」が「サイトを開く」に変わる）
2. 用語の数が変わったら `"terms"` も直す
3. `python build.py` → GitHub Desktop で commit → Push

新しいサイトを足すときは、`sites` に1つ足し、そのサイトの `favicon.svg` を `static/icons/（key）.svg` にコピーする。試験の実施団体の注意書きを `notes` に足す。

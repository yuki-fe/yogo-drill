"""試験の変更の見張り: 試験の主催者などのページを毎朝見に行き、前の日と変わったところを書き出す。

使い方:  python check/watch_exams.py --prev 前の state.json --out out
         python check/watch_exams.py --only ipa-fe,jdla-g     一部のページだけ

見に行くページ: check/watch.json。mode が text のページは本文の行、links のページはリンク（keywords を含むもの）を前の日と比べる。
結果: watch.json（LINE ボットが読む）・watch.md（人が読む）・state.json（次の日に比べるための記録）。
ふだんは GitHub の自動実行（.github/workflows/exam-watch.yml）が毎朝動かし、watch-results のブランチに置く。
変わったところ（changes）は30日分残す。LINE ボットは found_at が前に読んだときより新しいものだけを知らせる。
"""
import argparse
import difflib
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin

HERE = Path(__file__).parent
ROOT = HERE.parent
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (yogo-drill exam watch)"
KEEP_DAYS = 30        # changes を残す日数
MAX_LINES = 8         # 1ページで書き出す、増えた・消えた行の数
ERROR_DAYS = 3        # これだけ続けて取れなかったら知らせる

WATCH = json.loads((HERE / "watch.json").read_text(encoding="utf-8"))
PORTAL = json.loads((ROOT / "sites.json").read_text(encoding="utf-8"))
SITE_NAMES = {x["key"]: x["name"] for x in PORTAL["sites"]}


def fetch(url, tries=3):
    """(本文, エラー)。本文は文字列"""
    err = ""
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ja"})
            with urllib.request.urlopen(req, timeout=30) as res:
                body = res.read()
                return decode(body, res.headers.get_content_charset()), ""
        except urllib.error.HTTPError as e:
            err = f"エラー {e.code}"
            if e.code in (403, 404, 410):
                break
        except Exception as e:  # noqa: BLE001  通信のエラーはまとめて扱う
            err = type(e).__name__
        time.sleep(3 * (n + 1))
    return "", err


def decode(body, charset):
    """文字コード: ヘッダー → ページの <meta charset> → UTF-8 → Shift_JIS の順に試す"""
    if not charset:
        m = re.search(rb"""<meta[^>]+charset=["']?([\w-]+)""", body[:4096], re.I)
        charset = m.group(1).decode() if m else ""
    for cs in [charset, "utf-8", "cp932"]:
        if not cs:
            continue
        try:
            return body.decode("cp932" if cs.lower() in ("shift_jis", "sjis", "x-sjis") else cs)
        except (UnicodeDecodeError, LookupError):
            pass
    return body.decode("utf-8", errors="replace")


class PageText(HTMLParser):
    """本文の行とリンクを集める。script・style・ヘッダー・フッター・メニューは飛ばす。<main> があれば、その中だけ"""
    SKIP = {"script", "style", "noscript", "header", "footer", "nav", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "br", "td", "th", "section", "article", "table", "ul", "ol"}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.skip, self.main, self.has_main = base, 0, 0, False
        self.all_lines, self.main_lines, self.buf = [], [], []
        self.all_links, self.main_links = [], []
        self.link = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "main":
            self.main += 1
            self.has_main = True
        if tag in self.BLOCK:
            self.flush()
        if tag == "a" and not self.skip:
            href = dict(attrs).get("href") or ""
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                self.link = [urldefrag(urljoin(self.base, href))[0], []]

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.flush()
        if tag == "main" and self.main:
            self.flush()
            self.main -= 1
        if tag == "a" and self.link:
            item = [norm(" ".join(self.link[1])), self.link[0]]
            self.all_links.append(item)
            if self.main:
                self.main_links.append(item)
            self.link = None

    def handle_data(self, data):
        if self.skip:
            return
        self.buf.append(data)
        if self.link:
            self.link[1].append(data)

    def flush(self):
        t = norm("".join(self.buf))
        self.buf = []
        if len(t) >= 2:
            self.all_lines.append(t)
            if self.main:
                self.main_lines.append(t)

    def result(self):
        self.flush()
        if self.has_main and self.main_lines:
            return self.main_lines, self.main_links
        return self.all_lines, self.all_links


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def read_page(page, body):
    p = PageText(page["url"])
    p.feed(body)
    lines, links = p.result()
    ignore = [re.compile(x) for x in page.get("ignore", [])]
    lines = [x for x in lines if not any(r.search(x) for r in ignore)]
    lines = list(dict.fromkeys(lines))   # 同じ行（メニューのくり返しなど）は1つに
    kw = page.get("keywords") or []
    seen, out = set(), []
    for text, href in links:
        if kw and not any(k in text or k in href for k in kw):
            continue
        if href not in seen:
            seen.add(href)
            out.append([text, href])
    return lines, out


def compare(page, old, lines, links):
    """前の記録と比べて、変わったところ。変わっていなければ None"""
    if page["mode"] == "links":
        old_h = {h for _, h in old.get("links", [])}
        new_h = {h for _, h in links}
        added = [f"{t}（{h}）" if t else h for t, h in links if h not in old_h]
        removed = [f"{t}（{h}）" if t else h for t, h in old.get("links", []) if h not in new_h]
    else:
        old_l = old.get("lines", [])
        added, removed = [], []
        for op in difflib.SequenceMatcher(a=old_l, b=lines, autojunk=False).get_opcodes():
            tag, i1, i2, j1, j2 = op
            if tag in ("replace", "delete"):
                removed += old_l[i1:i2]
            if tag in ("replace", "insert"):
                added += lines[j1:j2]
        # 並べかわっただけの行は数えない
        a, r = set(added), set(removed)
        added, removed = [x for x in added if x not in r], [x for x in removed if x not in a]
    if not added and not removed:
        return None
    return {"added": [x[:120] for x in added[:MAX_LINES]], "removed": [x[:120] for x in removed[:MAX_LINES]],
            "added_n": len(added), "removed_n": len(removed)}


def load_prev(path):
    if not path:
        return {}
    p = Path(path)
    if not p.exists() or not p.stat().st_size:
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def to_markdown(res):
    t = datetime.fromisoformat(res["checked_at"])
    lines = [f"# 試験の変更の見張り（{t:%Y-%m-%d %H:%M}）", "",
             f"{res['pages']} ページを見た。直近 {KEEP_DAYS} 日の変更 {len(res['changes'])} 件、取れないページ {len(res['errors'])} 件。", ""]
    if res["errors"]:
        lines += ["## 取れないページ", ""] + [f"- [{e['name']}]({e['url']}): {e['error']}（{e['fail_days']} 日続けて）" for e in res["errors"]] + [""]
    lines += ["## 変更（新しい順）", ""]
    if not res["changes"]:
        lines.append("なし")
    for c in res["changes"]:
        lines += [f"### {c['found_at'][:10]} {c['name']}（{'・'.join(c['site_names'])}）", "", c["url"], ""]
        lines += [f"- 増えた: {x}" for x in c["added"]]
        if c["added_n"] > len(c["added"]):
            lines.append(f"- ほか増えた {c['added_n'] - len(c['added'])} 行")
        lines += [f"- 消えた: {x}" for x in c["removed"]]
        if c["removed_n"] > len(c["removed"]):
            lines.append(f"- ほか消えた {c['removed_n'] - len(c['removed'])} 行")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prev", default="", help="前の日の state.json")
    ap.add_argument("--out", default=str(HERE / "out-watch"))
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    now = datetime.now(JST)
    prev = load_prev(args.prev)
    old_pages = prev.get("pages", {})
    pages = WATCH["pages"]
    if args.only:
        keep = set(args.only.split(","))
        pages = [p for p in pages if p["id"] in keep]

    state = {"pages": dict(old_pages)}
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    changes = [c for c in prev.get("changes", []) if c["found_at"] >= cutoff]
    errors = []
    for page in pages:
        print(f"見に行く: {page['name']} {page['url']}", flush=True)
        old = old_pages.get(page["id"], {})
        body, err = fetch(page["url"])
        lines, links = read_page(page, body) if body else ([], [])
        if not body or (page["mode"] == "text" and not lines):
            fails = old.get("fail_days", 0) + 1
            state["pages"][page["id"]] = dict(old, fail_days=fails, error=err or "本文が空")
            if fails >= ERROR_DAYS:
                errors.append({"id": page["id"], "name": page["name"], "url": page["url"], "sites": page["sites"],
                               "error": err or "本文が空", "fail_days": fails})
            continue
        rec = {"lines": lines, "links": links, "hash": hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16],
               "seen_at": now.isoformat(timespec="seconds"), "fail_days": 0}
        if old.get("seen_at") and old.get("url") == page["url"]:
            diff = compare(page, old, lines, links)
            if diff:
                changes.insert(0, dict({"id": page["id"], "name": page["name"], "url": page["url"], "sites": page["sites"],
                                        "site_names": [SITE_NAMES.get(s, s) for s in page["sites"]],
                                        "found_at": now.isoformat(timespec="seconds")}, **diff))
                print(f"  変わった: 増えた {diff['added_n']} 行・消えた {diff['removed_n']} 行")
        else:
            print("  はじめて見たので記録だけ")
        rec["url"] = page["url"]
        state["pages"][page["id"]] = rec

    state["changes"] = changes
    res = {"checked_at": now.isoformat(timespec="seconds"), "result_url": WATCH.get("result_url", ""),
           "pages": len(pages), "changes": changes, "errors": errors}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "watch.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "watch.md").write_text(to_markdown(res), encoding="utf-8")
    (out / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    print(f"終わり: {len(pages)} ページ。直近の変更 {len(changes)} 件・取れない {len(errors)} 件 → {out}")


if __name__ == "__main__":
    sys.exit(main())

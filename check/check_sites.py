"""公開中の用語ドリルのサイトを、まとめて点検する（仕組みと決まりごと）。

使い方:  python check/check_sites.py                 公開中のサイトを点検して check/out/ に結果を書く
         python check/check_sites.py --no-browser    ブラウザの点検（JavaScript のエラー・スマホではみ出すか・クイズが動くか）を飛ばす
         python check/check_sites.py --sites fe,ip   一部のサイトだけ
         python check/check_sites.py --map cloud=http://localhost:8801/   公開前のサイトを、手元のサーバで点検する

点検するサイト: sites.json の "public": true のサイトと、入り口のサイト（key は top）。決まりは check/settings.json。
決まりに合わないが問題ないもの（例: 「〇〇の公式サイトで確かめてください」）は check/allow.json に書く。
結果: result.json（LINE ボットが読む）と result.md（人が読む）。ふだんは GitHub の自動実行（.github/workflows/site-check.yml）が毎週動かす。
ブラウザの点検には playwright が要る（pip install playwright → python -m playwright install chromium）。なければ飛ばす。
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

HERE = Path(__file__).parent
ROOT = HERE.parent
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (yogo-drill site check)"
LEVELS = ["問題", "注意", "情報"]

SETTINGS = json.loads((HERE / "settings.json").read_text(encoding="utf-8"))
ALLOW = json.loads((HERE / "allow.json").read_text(encoding="utf-8")) if (HERE / "allow.json").exists() else []
PORTAL = json.loads((ROOT / "sites.json").read_text(encoding="utf-8"))


# ---------- 取りに行く ----------

class Fetcher:
    """URL を取りに行く。--map で、公開前のサイトを手元のサーバに置き換える。同じ URL は1回だけ取る。"""

    def __init__(self, maps):
        self.maps = maps  # 本当の URL の頭 → 取りに行く URL の頭
        self.cache = {}

    def real_to_fetch(self, url):
        for real, local in self.maps.items():
            if url.startswith(real):
                return local + url[len(real):]
        return url

    def get(self, url, redirect=True, tries=3):
        key = (url, redirect)
        if key in self.cache:
            return self.cache[key]
        target = self.real_to_fetch(url)
        result = None
        for n in range(tries):
            try:
                opener = urllib.request.build_opener() if redirect else urllib.request.build_opener(NoRedirect())
                req = urllib.request.Request(target, headers={"User-Agent": UA, "Accept-Language": "ja"})
                with opener.open(req, timeout=25) as res:
                    body = res.read()
                    result = {"status": res.status, "url": res.geturl(), "body": body, "type": res.headers.get("Content-Type", "")}
            except urllib.error.HTTPError as e:
                result = {"status": e.code, "url": target, "body": e.read() if e.fp else b"", "type": e.headers.get("Content-Type", "") if e.headers else "",
                          "location": e.headers.get("Location", "") if e.headers else ""}
            except Exception as e:  # つながらない・時間切れ
                result = {"status": 0, "url": target, "body": b"", "type": "", "error": type(e).__name__ + ": " + str(e)[:120]}
            if result["status"] and result["status"] < 500 and result["status"] != 429:
                break
            time.sleep(2 * (n + 1))
        self.cache[key] = result
        return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# ---------- HTML を読む ----------

class Page(HTMLParser):
    SKIP = {"script", "style", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.desc, self.canonical, self.lang = "", "", "", ""
        self.links, self.assets = [], []
        self.text, self.footer, self.brand = [], [], []
        self.ga = False
        self.pr_box = False
        self._stack, self._in_title, self._footer, self._brand, self._skip = [], False, 0, 0, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content", "") or ""
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical = a.get("href", "")
            elif rel in ("stylesheet", "icon", "apple-touch-icon", "manifest") and a.get("href"):
                self.assets.append(a["href"])
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag in ("script", "img", "source", "video") and a.get("src"):
            self.assets.append(a["src"])
            if "googletagmanager.com" in a["src"]:
                self.ga = True
        if "pr-box" in cls:
            self.pr_box = True
        if tag in self.SKIP:
            self._skip += 1
        if tag == "footer":
            self._footer += 1
        if "brand" in cls:
            self._brand += 1
        self._stack.append((tag, tag == "footer", "brand" in cls))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        # 開いたタグの順番どおりに閉じる（HTML の書き方の乱れには強くしない）
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                for t, is_footer, is_brand in self._stack[i:]:
                    self._footer -= is_footer
                    self._brand -= is_brand
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip:
            return
        self.text.append(data)
        if self._footer > 0:
            self.footer.append(data)
        if self._brand > 0:
            self.brand.append(data)

    def all_text(self):
        return re.sub(r"\s+", " ", " ".join([self.title, self.desc] + self.text))


def parse(body):
    p = Page()
    try:
        p.feed(body.decode("utf-8", "replace"))
    except Exception:
        pass
    return p


# ---------- 点検 ----------

class Site:
    def __init__(self, key, name, url):
        self.key, self.name, self.url = key, name, url.rstrip("/") + "/"
        self.items, self.pages = [], {}

    def add(self, level, kind, page, detail):
        self.items.append({"level": level, "kind": kind, "page": page, "detail": detail})


def snippet(text, i, n, width=22):
    return text[max(0, i - width):i + n + width].strip()


def allowed(site, word, context):
    return any(a.get("word") == word and a.get("site") in (site, "*") and a.get("context", "") in context for a in ALLOW)


def check_site(site, f, all_hosts, browser_targets):
    host = urlparse(site.url).netloc
    mapped = f.real_to_fetch(site.url) != site.url
    top = f.get(site.url)
    if top["status"] != 200:
        site.add("問題", "サイトが開けない", site.url, top.get("error") or f"エラー {top['status']}")
        return
    if not mapped:
        final = urlparse(top["url"])
        if final.scheme != "https" or final.netloc != host:
            site.add("問題", "転送先がおかしい", site.url, f"{top['url']} に転送された")
        plain = f.get("http://" + host + "/", redirect=False)
        if plain["status"] not in (301, 302, 307, 308) or not plain.get("location", "").startswith("https://"):
            site.add("注意", "HTTPS に転送されない", "http://" + host + "/", "「Enforce HTTPS」にチェックが入っているか確かめる")

    # robots.txt と sitemap.xml
    robots = f.get(site.url + "robots.txt")
    if robots["status"] != 200:
        site.add("問題", "robots.txt がない", site.url + "robots.txt", f"エラー {robots['status']}")
    elif site.url + "sitemap.xml" not in robots["body"].decode("utf-8", "replace"):
        site.add("注意", "robots.txt にサイトマップがない", site.url + "robots.txt", "Sitemap の行がない")
    sm = f.get(site.url + "sitemap.xml")
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm["body"].decode("utf-8", "replace")) if sm["status"] == 200 else []
    if sm["status"] != 200:
        site.add("問題", "sitemap.xml がない", site.url + "sitemap.xml", f"エラー {sm['status']}")
    urls = list(dict.fromkeys(urls or [site.url]))
    for u in urls:
        if not u.startswith(site.url):
            site.add("問題", "サイトマップに別のサイトの URL", site.url + "sitemap.xml", u)
    urls = [u for u in urls if u.startswith(site.url)]

    # 404 のページ
    nf = f.get(site.url + "no-such-page-for-check.html")
    if nf["status"] != 404:
        site.add("注意", "存在しないページが 404 にならない", site.url + "no-such-page-for-check.html", f"エラー {nf['status']}")

    # 全ページを取る
    with ThreadPoolExecutor(16) as ex:
        results = dict(zip(urls, ex.map(f.get, urls)))
    titles = {}
    links_internal, links_external = {}, {}
    for u, r in results.items():
        if r["status"] != 200:
            site.add("問題", "ページが開けない", u, r.get("error") or f"エラー {r['status']}")
            continue
        p = parse(r["body"])
        site.pages[u] = p
        if not p.title.strip():
            site.add("問題", "タイトルがない", u, "")
        else:
            titles.setdefault(p.title.strip(), []).append(u)
        if not p.desc.strip():
            site.add("注意", "説明文（description）がない", u, "")
        if p.canonical and p.canonical.rstrip("/") != u.rstrip("/") and not (u.endswith("/index.html") and p.canonical == u[:-10]):
            site.add("注意", "canonical が自分の URL と違う", u, p.canonical)
        if p.lang != "ja":
            site.add("注意", "lang が ja でない", u, p.lang or "なし")
        for href in p.links + p.assets:
            if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
                continue
            target = urldefrag(urljoin(u, href))[0]
            tp = urlparse(target)
            if tp.scheme not in ("http", "https"):
                continue
            (links_internal if tp.netloc in all_hosts else links_external).setdefault(target, u)
    for t, us in titles.items():
        if len(us) > 1:
            site.add("注意", "同じタイトルのページ", us[0], f"「{t[:40]}」が {len(us)} ページ")

    # リンク切れ（自分たちのサイトは 問題、外のサイトは 注意）
    todo = [t for t in links_internal if t not in results]
    with ThreadPoolExecutor(16) as ex:
        for t, r in zip(todo, ex.map(f.get, todo)):
            results[t] = r
    for t, src in links_internal.items():
        r = results[t]
        if r["status"] != 200:
            site.add("問題", "リンク切れ", src, f"{t}（{r.get('error') or 'エラー ' + str(r['status'])}）")
    ext = [t for t in links_external if not urlparse(t).netloc.endswith(("fonts.googleapis.com", "fonts.gstatic.com", "googletagmanager.com"))]
    with ThreadPoolExecutor(8) as ex:
        for t, r in zip(ext, ex.map(lambda x: f.get(x, tries=2), ext)):
            if r["status"] in (401, 403, 405, 429):  # ロボットを断るサイトは数えない
                continue
            if r["status"] != 200:
                site.add("注意", "外のサイトへのリンクが開けない", links_external[t], f"{t}（{r.get('error') or 'エラー ' + str(r['status'])}）")

    check_rules(site)
    check_storage(site, f)
    pages = [u for u in site.pages if "/terms/" not in u or u.endswith("/terms/index.html")]
    terms = sorted(u for u in site.pages if re.search(r"/terms/\d+\.html$", u))
    browser_targets[site.key] = pages + (terms[:1] + terms[-1:] if terms else [])


def check_rules(site):
    """決まりごと: 使わない言葉・サイト名の商標・フッターの注意書き・PR の表示・アクセス解析・公開しないサイト"""
    ga_pages = [u for u, p in site.pages.items() if p.ga]
    seen = set()
    for u, p in site.pages.items():
        text = p.all_text()
        for level, words in SETTINGS["banned_words"].items():
            for w in words:
                for m in re.finditer(re.escape(w), text):
                    ctx = snippet(text, m.start(), len(w))
                    if allowed(site.key, w, ctx) or (w, ctx) in seen:
                        continue
                    seen.add((w, ctx))
                    site.add(level, f"使わない言葉「{w}」", u, f"…{ctx}…")
        for hidden in SETTINGS["hidden_sites"]:
            raw = " ".join(p.links + p.assets) + " " + text
            for w in hidden["words"]:
                if w in raw and ("hidden", w) not in seen:
                    seen.add(("hidden", w))
                    site.add("問題", "公開しないサイトが出ている", u, f"「{w}」（{hidden['name']}）")
        affiliate = any(h in l for l in p.links for h in SETTINGS["affiliate_hosts"])
        if (affiliate or p.pr_box) and "PR" not in text:
            site.add("問題", "広告に PR の表示がない", u, "アフィリエイトのリンクか PR の枠があるのに「PR」の文字がない")
    for w in SETTINGS["brand_forbidden"].get(site.key, []):
        brands = {re.sub(r"\s+", " ", " ".join(p.brand)).strip() for p in site.pages.values()} - {""}
        for b in brands:
            if w in b:
                site.add("問題", "サイト名に使わない言葉", site.url, f"「{b}」に「{w}」")
    need = SETTINGS["footer_must_include"]
    no_footer = [u for u, p in site.pages.items() if need not in " ".join(p.footer)]
    if no_footer:
        site.add("問題", "フッターに注意書きがない", no_footer[0], f"「{need}」の文がない（{len(no_footer)} ページ）")
    privacy = [p for u, p in site.pages.items() if re.search(r"/(privacy|about)\.html$", u)]
    if ga_pages:
        if not any("Googleアナリティクス" in p.all_text() for p in privacy):
            site.add("問題", "プライバシーポリシーにアクセス解析の説明がない", site.url, "Googleアナリティクスを使っているのに、説明がない")
        if len(ga_pages) < len(site.pages):
            site.add("注意", "アクセス解析が入っていないページ", next(u for u in site.pages if u not in ga_pages), f"{len(site.pages) - len(ga_pages)} ページ")
    else:
        site.add("情報", "アクセス解析なし", site.url, "GA4 の測定 ID が入っていない")
    if not any(re.search(r"/(about|privacy)\.html$", u) for u in site.pages):
        site.add("注意", "運営者情報のページがない", site.url, "about.html か privacy.html がサイトマップにない")


STORAGE_KEYS = {}


def check_storage(site, f):
    """学習の記録の保存の名前（localStorage）。同じドメインの中で、サイトどうしがぶつからないように"""
    names = set()
    for js in ("assets/app.js", "assets/drill.js", "assets/b.js"):
        r = f.get(site.url + js)
        if r["status"] == 200:
            names |= set(re.findall(r'["\']([a-z0-9]+(?:-[a-z0-9]+)*)-(?:v1|weak|prefs|test|abbr|kamoku)["\']', r["body"].decode("utf-8", "replace")))
    for n in names:
        STORAGE_KEYS.setdefault(n, []).append(site)


def check_redirects(sites_by_key, f):
    for r in SETTINGS["redirects"]:
        site = sites_by_key.get(r["site"])
        if not site or f.real_to_fetch(site.url) != site.url:
            continue
        res = f.get(r["from"])
        if res["status"] != 200 or not res["url"].startswith(r["to"]):
            site.add("注意", "古い URL から転送されない", r["from"], f"{res['url']} （エラー {res['status']}）" if res["status"] else res.get("error", ""))


def check_hidden(top, f):
    for h in SETTINGS["hidden_sites"]:
        r = f.get(h["url"], tries=1)
        if r["status"] == 200:
            top.add("問題", "公開しないサイトが開ける", h["url"], h["name"])


# ---------- ブラウザの点検 ----------

OVERFLOW_JS = """() => {
  const iw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  if (sw <= iw + 1) return null;
  const scrolls = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { if (/(auto|scroll|hidden)/.test(getComputedStyle(p).overflowX)) return true; } return false; };
  const wide = [...document.querySelectorAll('body *')].filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > iw + 1 && !scrolls(e); })
    .slice(0, 3).map((e) => e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\\s+/).join('.') : ''));
  return { sw, iw, wide };
}"""


def browser_checks(sites, targets, f):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sites[0].add("情報", "ブラウザの点検を飛ばした", "", "playwright が入っていない")
        return False
    with sync_playwright() as pw:
        browser = None
        for opts in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
            try:
                browser = pw.chromium.launch(**opts)
                break
            except Exception:
                continue
        if not browser:
            sites[0].add("情報", "ブラウザの点検を飛ばした", "", "ブラウザを起動できない")
            return False
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True,
                                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 (yogo-drill site check)")
        for site in sites:
            own = urlparse(f.real_to_fetch(site.url)).netloc
            for u in targets.get(site.key, []):
                page = ctx.new_page()
                errors = []
                page.on("pageerror", lambda e, errors=errors: errors.append(("問題", "JavaScript のエラー", str(e).split("\n")[0][:160])))
                page.on("console", lambda m, errors=errors: m.type == "error" and errors.append(("注意", "ブラウザのエラー表示", m.text[:160])))
                page.on("response", lambda r, errors=errors: r.status >= 400 and urlparse(r.url).netloc == own and
                        errors.append(("問題", "読み込めないファイル", f"{r.url}（エラー {r.status}）")))
                try:
                    page.goto(f.real_to_fetch(u), wait_until="load", timeout=40000)
                    page.wait_for_timeout(1500)
                    ov = page.evaluate(OVERFLOW_JS)
                    if ov:
                        site.add("注意", "スマホで横にはみ出す", u, f"幅 {ov['iw']}px に {ov['sw']}px（{', '.join(ov['wide']) or '?'}）")
                    for sel in ("#panel", "#drill"):
                        if page.locator(sel).count() and len(page.locator(sel).first.inner_text().strip()) < 5:
                            site.add("問題", "学習の画面が出ていない", u, f"{sel} が空")
                    if page.locator('.mode[data-mode="quiz"]').count():
                        page.locator('.mode[data-mode="quiz"]').first.click()
                        page.wait_for_timeout(500)
                        if page.locator("#panel .choice").count() < 2:
                            site.add("問題", "4択クイズが動かない", u, "「4択」を押しても選択肢が出ない")
                    if page.locator("#drill #start").count():
                        page.locator("#drill #start").first.click()
                        page.wait_for_timeout(500)
                        if page.locator("#drill .choice").count() < 2:
                            site.add("問題", "ミニテストが動かない", u, "「テストを始める」を押しても問題が出ない")
                except Exception as e:
                    site.add("問題", "ブラウザで開けない", u, type(e).__name__ + ": " + str(e).split("\n")[0][:140])
                for level, kind, detail in errors:
                    site.add(level, kind, u, detail)
                page.close()
        browser.close()
    return True


# ---------- 結果 ----------

def summarize(sites, started, browser_done):
    count = {lv: sum(1 for s in sites for i in s.items if i["level"] == lv) for lv in LEVELS}
    out = {
        "checked_at": started.isoformat(timespec="seconds"),
        "seconds": round(time.time() - started.timestamp()),
        "browser": browser_done,
        "result_url": SETTINGS.get("result_url", ""),
        "summary": {"sites": len(sites), "pages": sum(len(s.pages) for s in sites), "problems": count["問題"], "warnings": count["注意"], "infos": count["情報"]},
        "sites": [],
    }
    for s in sites:
        items = sorted(s.items, key=lambda i: LEVELS.index(i["level"]))
        out["sites"].append({"key": s.key, "name": s.name, "url": s.url, "pages": len(s.pages),
                             "problems": sum(i["level"] == "問題" for i in items), "warnings": sum(i["level"] == "注意" for i in items),
                             "items": items[:60], "more": max(0, len(items) - 60)})
    return out


def to_markdown(res):
    s = res["summary"]
    t = datetime.fromisoformat(res["checked_at"])
    lines = [f"# サイトの点検（{t:%Y-%m-%d %H:%M}）", "",
             f"{s['sites']} サイト・{s['pages']} ページ。問題 **{s['problems']}** 件、注意 **{s['warnings']}** 件、情報 {s['infos']} 件。"
             + ("" if res["browser"] else "（ブラウザの点検は飛ばした）"), "",
             "| サイト | ページ | 問題 | 注意 |", "|---|---:|---:|---:|"]
    lines += [f"| [{x['name']}]({x['url']}) | {x['pages']} | {x['problems']} | {x['warnings']} |" for x in res["sites"]]
    for x in res["sites"]:
        if not x["items"]:
            continue
        lines += ["", f"## {x['name']}", "", "| | 種類 | ページ | くわしく |", "|---|---|---|---|"]
        for i in x["items"]:
            page = i["page"].replace(x["url"], "/") if i["page"] else ""
            lines.append(f"| {i['level']} | {i['kind']} | {page} | {i['detail'].replace('|', '｜')} |")
        if x["more"]:
            lines.append(f"| | ほか {x['more']} 件 | | |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--sites", default="")
    ap.add_argument("--map", action="append", default=[], help="key=URL（公開前のサイトを手元のサーバで点検する）")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    started = datetime.now(JST)
    sites = [Site("top", PORTAL["site_name"] + "（入り口）", PORTAL["base_url"])]
    sites += [Site(x["key"], x["name"], x["url"]) for x in PORTAL["sites"] if x.get("public")]
    if args.sites:
        keep = set(args.sites.split(","))
        sites = [s for s in sites if s.key in keep]
    by_key = {s.key: s for s in sites}
    maps = {}
    for m in args.map:
        k, url = m.split("=", 1)
        if k in by_key:
            maps[by_key[k].url] = url.rstrip("/") + "/"
    f = Fetcher(maps)
    all_hosts = {urlparse(s.url).netloc for s in sites} | {urlparse(x["url"]).netloc for x in PORTAL["sites"] if x.get("public")}
    all_hosts |= {urlparse(PORTAL["base_url"]).netloc}

    targets = {}
    for s in sites:
        print(f"点検中: {s.name} {s.url}", flush=True)
        check_site(s, f, all_hosts, targets)
    check_redirects(by_key, f)
    if "top" in by_key:
        check_hidden(by_key["top"], f)
    for name, owners in STORAGE_KEYS.items():
        if len(owners) > 1:
            for s in owners:
                s.add("問題", "学習の記録の保存の名前がほかのサイトと同じ", s.url, f"「{name}-…」を {', '.join(o.name for o in owners)} が使っている")
    browser_done = False
    if not args.no_browser and sites:
        print("ブラウザで点検中…", flush=True)
        browser_done = browser_checks(sites, targets, f)

    res = summarize(sites, started, browser_done)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "result.md").write_text(to_markdown(res), encoding="utf-8")
    s = res["summary"]
    print(f"終わり: {s['sites']} サイト・{s['pages']} ページ。問題 {s['problems']}・注意 {s['warnings']}・情報 {s['infos']}（{res['seconds']} 秒）→ {out}")


if __name__ == "__main__":
    sys.exit(main())

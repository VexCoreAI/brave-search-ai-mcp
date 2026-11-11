#!/usr/bin/env python3
"""Brave Search AI scraper derived from the upstream project.

This implementation is based on
https://github.com/ijuttt/scrape-brave-ai and is redistributed with permission.

Original module header:
brave_search.py — Brave Search AI (chatllm) Scraper v0.0.1
===========================================================
Mimics a real Chrome browser session to extract AI answers from Brave Search.
Supports live SSE stream interception (/api/chatllm/with_ask) and DOM fallback extraction.

Default:
    Headless mode, rich Markdown terminal rendering (Sources on top, Answer below).

Usage:
    python brave_search.py "useradd or usedadd"
    python brave_search.py "syntax chmod apa aja"
    python brave_search.py "what is rust language" --json
    python brave_search.py "linux kernel" --debug
    python brave_search.py "chmod 755" --raw
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, field

__version__ = "0.1.0"

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
GRAY = "\033[90m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD + RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, RESET)
        ts = self.formatTime(record, "%H:%M:%S.%03d")
        level = f"{color}{record.levelname:<8}{RESET}"
        return f"{GRAY}{ts}{RESET} {level} {record.getMessage()}"


def setup_logger(debug: bool = False) -> logging.Logger:
    logger = logging.getLogger("brave")
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.ERROR)
    return logger


log = setup_logger(debug=False)


# ──────────────────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Citation:
    url: str
    title: str
    snippet: str = ""
    favicon: str = ""


@dataclass
class BraveAIResult:
    query: str
    has_ai_response: bool = False
    answer: str = ""
    citations: list = field(default_factory=list)
    followups: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    conversation_id: str = ""
    strategy_used: str = ""
    error_message: str = ""
    raw_events: list = field(default_factory=list)

    def print_output(self, debug_mode: bool = False, raw_mode: bool = False) -> None:
        if debug_mode:
            print(
                f"\n{BOLD}{GREEN}═══ BRAVE AI ANSWER (v{__version__}) ══════════════════════════════════════{RESET}"
            )
            print(f"{BOLD}Query:{RESET} {self.query}")
            if self.error_message:
                print(f"{BOLD}Error:{RESET}  {RED}{self.error_message}{RESET}")
            elif not self.has_ai_response:
                print(
                    f"{BOLD}Status:{RESET} {YELLOW}No AI response generated for this query{RESET}"
                )

            if self.has_ai_response:
                if self.strategy_used:
                    print(f"{BOLD}Strategy:{RESET} {CYAN}{self.strategy_used}{RESET}")
                if self.conversation_id:
                    print(f"{BOLD}Conv-ID:{RESET}  {GRAY}{self.conversation_id}{RESET}")

                if self.citations:
                    print(
                        f"\n{BOLD}{BLUE}─── Sources ({len(self.citations)}) ──────────────────────────────────{RESET}"
                    )
                    for i, c in enumerate(self.citations, 1):
                        title = c.title if c.title else c.url
                        print(f"  {CYAN}[{i}]{RESET} {BOLD}{title}{RESET}")
                        print(f"       {GRAY}{c.url}{RESET}")
                        if c.snippet:
                            prev = c.snippet[:140].replace("\n", " ")
                            print(f"       {GRAY}{prev}…{RESET}")
                print(
                    f"\n{BOLD}{BLUE}─── Answer ─────────────────────────────────────────────{RESET}"
                )
                print(self.answer)
                if self.followups:
                    print(
                        f"\n{BOLD}{MAGENTA}─── Follow-up Questions ─────────────────────────────────{RESET}"
                    )
                    for q in self.followups:
                        print(f"  • {q}")
            print(
                f"{BOLD}{GREEN}═══════════════════════════════════════════════════════════{RESET}\n"
            )
        elif raw_mode:
            if self.has_ai_response and self.answer:
                if self.citations:
                    print("Sources:")
                    for i, c in enumerate(self.citations, 1):
                        t = c.title if c.title else c.url
                        print(f"[{i}] {t}: {c.url}")
                    print()
                print("Answer:")
                print(self.answer)
            elif self.error_message:
                print(f"Error: {self.error_message}", file=sys.stderr)
            else:
                print("No AI response available for this query.", file=sys.stderr)
        else:
            # Rich Terminal Markdown rendering (Sources on TOP, Answer below)
            if self.has_ai_response and self.answer:
                try:
                    from rich.console import Console
                    from rich.markdown import Markdown

                    console = Console()

                    # 1. Print Sources FIRST
                    if self.citations:
                        console.print("[bold cyan]Sources:[/bold cyan]")
                        for i, c in enumerate(self.citations, 1):
                            t = c.title if c.title else c.url
                            console.print(
                                f"  [dim][{i}][/dim] [bold]{t}[/bold]: [blue link={c.url}]{c.url}[/blue link]"
                            )
                        console.print()

                    # 2. Print Answer SECOND
                    console.print("[bold cyan]Answer:[/bold cyan]")
                    console.print(Markdown(self.answer))

                except ImportError:
                    if self.citations:
                        print("Sources:")
                        for i, c in enumerate(self.citations, 1):
                            t = c.title if c.title else c.url
                            print(f"[{i}] {t}: {c.url}")
                        print()
                    print("Answer:")
                    print(self.answer)
            elif self.error_message:
                print(f"Error: {self.error_message}", file=sys.stderr)
            else:
                print("No AI response available for this query.", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────────────
# Stealth & Browser Configuration
# ──────────────────────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
if (!window.chrome) {
    window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
}
const _q = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (p) => p.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : _q(p);
const _gp = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel(R) Iris(TM) Plus Graphics 640';
    return _gp.call(this, p);
};
"""

DOM_TO_MARKDOWN_JS = """
(el) => {
    function getMd(node) {
        if (!node) return '';
        let res = '';
        for (let child of node.childNodes) {
            if (child.nodeType === 3) {
                res += child.textContent;
            } else if (child.nodeType === 1) {
                let tag = child.tagName.toLowerCase();
                let cls = child.className || '';

                if (cls.includes('inline-citation') || cls.includes('tap-round-footer')) continue;

                if (tag === 'p') {
                    let txt = getMd(child).trim();
                    if (txt) res += '\\n\\n' + txt + '\\n\\n';
                } else if (tag === 'strong' || tag === 'b') {
                    let txt = getMd(child).trim();
                    if (txt) res += ' **' + txt + '** ';
                } else if (tag === 'em' || tag === 'i') {
                    let txt = getMd(child).trim();
                    if (txt) res += ' *' + txt + '* ';
                } else if (tag === 'code') {
                    let txt = getMd(child).trim();
                    if (txt) res += ' `' + txt + '` ';
                } else if (tag === 'pre') {
                    let txt = getMd(child).trim();
                    if (txt) res += '\\n\\n```\\n' + txt + '\\n```\\n\\n';
                } else if (tag === 'ul' || tag === 'ol') {
                    res += '\\n\\n' + getMd(child) + '\\n\\n';
                } else if (tag === 'li') {
                    let txt = getMd(child).trim();
                    if (txt) res += '\\n- ' + txt;
                } else if (tag.startsWith('h')) {
                    let txt = getMd(child).trim();
                    if (txt) res += '\\n\\n### ' + txt + '\\n\\n';
                } else if (tag === 'table') {
                    res += '\\n\\n' + getMd(child) + '\\n\\n';
                } else if (tag === 'tr') {
                    let row = [];
                    for (let td of child.children) {
                        row.push(getMd(td).trim().replace(/\\n/g, ' '));
                    }
                    if (row.length > 0) {
                        res += '| ' + row.join(' | ') + ' |\\n';
                    }
                } else {
                    res += getMd(child);
                }
            }
        }
        return res;
    }
    let raw = getMd(el);
    return raw.replace(/\\n{3,}/g, '\\n\\n').trim();
}
"""


def parse_sse_line(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith(":"):
        return None
    if line.startswith("data:"):
        line = line[5:].strip()
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def extract_conv_id(url: str) -> str:
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return params.get("conversation", [""])[0]


# ──────────────────────────────────────────────────────────────────────────────
# Main Runner with Retries & Rate Limit Backoff Pause
# ──────────────────────────────────────────────────────────────────────────────


def run_brave_search(
    query: str,
    *,
    headless: bool = True,
    timeout_s: int = 20,
    retries: int = 3,
    slow_mo: int = 50,
) -> BraveAIResult:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed. Run the project setup instructions first."
        ) from None

    search_url = (
        f"https://search.brave.com/search?q={urllib.parse.quote_plus(query)}&source=web"
    )
    log.info("Query      : %s%s%s", BOLD, query, RESET)
    log.info("Search URL : %s", search_url)
    log.info(
        "Headless   : %s | Timeout: %ds | Retries: %d", headless, timeout_s, retries
    )

    last_exc = None
    for attempt in range(1, retries + 1):
        log.info(
            "%s── Attempt %d / %d ──────────────────────────────────────────%s",
            BOLD,
            attempt,
            retries,
            RESET,
        )
        try:
            return _single_attempt(
                query=query,
                search_url=search_url,
                headless=headless,
                timeout_s=timeout_s,
                slow_mo=slow_mo,
            )
        except Exception as exc:
            last_exc = exc
            log.error("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                is_429 = "429" in str(exc) or "Rate Limited" in str(exc)
                if is_429:
                    wait = 8 * attempt
                    sys.stderr.write(
                        f"\033[93m[Brave Search Rate Limit HTTP 429]\033[0m Pausing {wait}s before attempt {attempt + 1}/{retries}…\n"
                    )
                else:
                    wait = 3 * attempt
                    log.warning("Attempt failed — waiting %ds before retry…", wait)

                time.sleep(wait)

    result = BraveAIResult(query=query)
    if "429" in str(last_exc):
        result.error_message = "Rate limited by Brave Search (HTTP 429). Please wait 1-2 minutes before querying again."
    else:
        result.error_message = f"All {retries} attempts failed. Last error: {last_exc}"
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Single Attempt Execution
# ──────────────────────────────────────────────────────────────────────────────


def _single_attempt(
    *,
    query: str,
    search_url: str,
    headless: bool,
    timeout_s: int,
    slow_mo: int,
) -> BraveAIResult:
    from playwright.sync_api import sync_playwright

    result = BraveAIResult(query=query)
    chatllm_pattern = re.compile(r"/api/chatllm/with_ask")
    raw_body_chunks = []
    sse_done = False
    sse_error = None

    with sync_playwright() as p:
        log.debug("Launching Chrome (headless=%s, slow_mo=%dms)…", headless, slow_mo)

        # The system Chrome channel can fail on recent macOS versions
        # (path_service 1001). Playwright's bundled Chromium is the default;
        # set BRAVE_BROWSER_CHANNEL=chrome to use system Chrome instead.
        browser_channel = os.environ.get("BRAVE_BROWSER_CHANNEL", "").strip() or None
        launch_kwargs = {
            "headless": headless,
            "slow_mo": slow_mo,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
                "--lang=en-US",
            ],
        }
        if browser_channel:
            launch_kwargs["channel"] = browser_channel

        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as exc:
            if browser_channel:
                log.warning(
                    "Chrome channel %s failed (%s); falling back to bundled Chromium",
                    browser_channel,
                    exc,
                )
                launch_kwargs.pop("channel", None)
                browser = p.chromium.launch(**launch_kwargs)
            else:
                raise

        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=USER_AGENT,
            locale="en-US",
            timezone_id="Asia/Jakarta",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )

        page = context.new_page()
        page.add_init_script(STEALTH_JS)

        try:
            context.add_cookies(
                [
                    {
                        "name": "cookie_test",
                        "value": "1",
                        "domain": ".brave.com",
                        "path": "/",
                    }
                ]
            )
        except Exception:
            pass

        # ── Network Hooks ──────────────────────────────────────────────
        def on_request(req):
            if chatllm_pattern.search(req.url):
                log.info(
                    "%s→ INTERCEPT SSE REQUEST%s  %s %s",
                    GREEN,
                    RESET,
                    req.method,
                    req.url,
                )
                result.conversation_id = extract_conv_id(req.url)

        def on_response(resp):
            nonlocal sse_done, sse_error
            if chatllm_pattern.search(resp.url):
                log.info(
                    "%s← INTERCEPT SSE RESPONSE%s  HTTP %d", BLUE, RESET, resp.status
                )
                if resp.status != 200:
                    sse_error = f"HTTP {resp.status} from chatllm endpoint"
                    return
                try:
                    body = resp.body()
                    raw_body_chunks.append(body)
                    sse_done = True
                except Exception as e:
                    sse_error = f"Failed reading body: {e}"

        page.on("request", on_request)
        page.on("response", on_response)

        # ── Navigate ───────────────────────────────────────────────────
        log.info("Navigating to search page…")
        try:
            nav_resp = page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=timeout_s * 1000,
            )
            status = nav_resp.status if nav_resp else 0
            log.info("Page loaded — status=%d", status)

            if status == 429:
                context.close()
                browser.close()
                raise RuntimeError(
                    "HTTP 429 Rate Limited (Too Many Requests) by Brave Search."
                )

        except Exception as exc:
            if "429" in str(exc):
                raise
            raise RuntimeError(f"Navigation failed: {exc}") from exc

        # ── Check for AI Answer ────────────────────────────────────────
        log.info("Checking for AI response…")
        start_time = time.time()
        clicked_summarize = False
        last_dom_text = ""
        stable_count = 0

        while (time.time() - start_time) < timeout_s:
            # Strategy 1: SSE stream completed
            if sse_done and raw_body_chunks:
                log.info(
                    "%sStrategy 1 Success: Intercepted SSE stream.%s", GREEN, RESET
                )
                result.strategy_used = "SSE Network Interception"
                result.has_ai_response = True
                raw_body = b"".join(raw_body_chunks)
                result = _parse_sse_body(raw_body, result)
                context.close()
                browser.close()
                return result

            # Strategy 2: DOM element present — MUST wait for stream/text to stabilize
            el = page.query_selector(".chatllm-content, .chatllm-answer, #llm-snippet")
            if el:
                txt = el.inner_text().strip()
                if txt and len(txt) > 20:
                    is_complete_class = (
                        page.query_selector(
                            ".llm-output-complete, .chatllm-content-complete"
                        )
                        is not None
                    )

                    if txt == last_dom_text:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_dom_text = txt

                    if is_complete_class or stable_count >= 4:
                        log.info(
                            "%sStrategy 2 Success: Extracted complete answer from DOM.%s",
                            GREEN,
                            RESET,
                        )
                        result.strategy_used = "DOM Selector Extraction"
                        result.has_ai_response = True
                        result = _parse_dom_element(page, el, result)
                        context.close()
                        browser.close()
                        return result

            # Attempt to click "Summarize" or "Answer with AI" if available
            if not clicked_summarize and (time.time() - start_time) > 2.0:
                summarize_btn = page.query_selector(
                    "button:has-text('Summarize'), button:has-text('Answer with AI'), "
                    "a[href*='cluster=ask_ai'], button#answer-btn"
                )
                if summarize_btn:
                    log.info(
                        "Found 'Summarize' button on DOM — Clicking to trigger AI answer…"
                    )
                    try:
                        summarize_btn.click()
                        clicked_summarize = True
                    except Exception as e:
                        log.debug("Click summarize failed: %s", e)

            time.sleep(0.3)

        log.warning("No AI response available on Brave Search for query '%s'.", query)
        result.has_ai_response = False
        result.answer = ""
        context.close()
        browser.close()
        return result


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 1 Parser: SSE Body
# ──────────────────────────────────────────────────────────────────────────────


def _parse_sse_body(raw: bytes, result: BraveAIResult) -> BraveAIResult:
    parts = []
    lines = raw.decode("utf-8", errors="replace").splitlines()

    for line in lines:
        event = parse_sse_line(line)
        if event is None:
            continue
        result.raw_events.append(event)
        etype = event.get("type", "")

        if etype == "text_stop":
            seg = event.get("text", "")
            if seg.strip():
                parts.append(seg)

        elif etype == "augment_with_inline_citation":
            cit = Citation(
                url=event.get("url", ""),
                title=event.get("title", ""),
                snippet=event.get("snippet", ""),
                favicon=event.get("favicon", ""),
            )
            if not any(c.url == cit.url for c in result.citations):
                result.citations.append(cit)

        elif etype == "usage":
            result.prompt_tokens = event.get("prompt_tokens", 0)
            result.completion_tokens = event.get("completion_tokens", 0)

        elif etype == "followups":
            result.followups = event.get("followups", [])

        elif etype == "enrichments":
            rr = event.get("enrichments", {}).get("raw_response", "")
            if rr:
                result.answer = rr

    if not result.answer:
        result.answer = "".join(parts)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Strategy 2 Parser: DOM Element
# ──────────────────────────────────────────────────────────────────────────────


def _parse_dom_element(page, element, result: BraveAIResult) -> BraveAIResult:
    content_el = page.query_selector(".chatllm-content, .llm-output")
    target = content_el if content_el else element

    try:
        markdown_text = page.evaluate(DOM_TO_MARKDOWN_JS, target)
    except Exception as e:
        log.debug("JS Markdown conversion failed: %s — falling back to inner_text", e)
        markdown_text = target.inner_text()

    noise_patterns = [
        "AI-generated answer",
        "Please verify critical facts",
        "Copy",
        "Share",
        "More",
        "Elaborate",
    ]
    lines = []
    for line in markdown_text.splitlines():
        line_s = line.strip()
        if any(noise in line_s for noise in noise_patterns):
            continue
        if re.match(r"^\+\d+$", line_s):
            continue
        lines.append(line)

    result.answer = "\n".join(lines).strip()

    citation_selectors = [
        "#llm-snippet a[href^='http']",
        ".chatllm-answer a[href^='http']",
        ".sources a[href^='http']",
        "a.l1[href^='http']",
        "a.title[href^='http']",
    ]
    for sel in citation_selectors:
        for link in page.query_selector_all(sel):
            url = link.get_attribute("href") or ""
            title = link.inner_text().strip()
            if url and not any(
                ignored in url
                for ignored in ["brave.com", "hackerone.com", "status.brave.app"]
            ):
                clean_title = title.split("\n")[0].strip() if title else url
                if not any(c.url == url for c in result.citations):
                    result.citations.append(Citation(url=url, title=clean_title))

    followup_els = page.query_selector_all(
        "#llm-snippet button, .chatllm-answer button, .followup"
    )
    for btn in followup_els:
        txt = btn.inner_text().strip()
        if (
            txt
            and txt not in noise_patterns
            and len(txt) > 5
            and not txt.startswith("http")
        ):
            if txt not in result.followups:
                result.followups.append(txt)

    return result


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="brave_search.py",
        description=f"Brave Search AI Scraper v{__version__}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("query", help="Search query to send to Brave AI")
    p.add_argument(
        "--headful",
        dest="headless",
        action="store_false",
        default=True,
        help="Run browser in headful GUI mode (default is headless)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=20,
        metavar="SECONDS",
        help="Timeout in seconds (default: 20)",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Retry attempts (default: 3)",
    )
    p.add_argument(
        "--slow-mo",
        type=int,
        default=50,
        metavar="MS",
        help="Playwright slow_mo in ms (default: 50)",
    )
    p.add_argument("--json", action="store_true", help="Output result as JSON")
    p.add_argument(
        "--raw",
        action="store_true",
        help="Output raw plain text without Rich Markdown terminal formatting",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging and metadata framing",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s v{__version__}")
    return p


def main() -> None:
    args = build_parser().parse_args()

    global log
    log = setup_logger(debug=args.debug)

    if args.debug:
        log.info(
            "%s+--------------------------------------------------+%s", BOLD, RESET
        )
        log.info(
            "%s|    Brave Search AI Scraper (v%s) DEBUG MODE     |%s",
            BOLD,
            __version__,
            RESET,
        )
        log.info(
            "%s+--------------------------------------------------+%s", BOLD, RESET
        )

    result = run_brave_search(
        args.query,
        headless=args.headless,
        timeout_s=args.timeout,
        retries=args.retries,
        slow_mo=args.slow_mo,
    )

    if args.json:
        output = {
            "query": result.query,
            "has_ai_response": result.has_ai_response,
            "strategy": result.strategy_used,
            "conversation_id": result.conversation_id,
            "answer": result.answer,
            "citations": [
                {"url": c.url, "title": c.title, "snippet": c.snippet}
                for c in result.citations
            ],
            "followups": result.followups,
            "error": result.error_message,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        result.print_output(debug_mode=args.debug, raw_mode=args.raw)


if __name__ == "__main__":
    main()

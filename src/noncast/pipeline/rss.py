"""Parallel RSS fetch: short timeouts, two retries, no 240s stall."""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from noncast.models import Story

UA = "Non-Cast/0.1 (+https://github.com/Nonarkara/Non-Cast)"


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_feed(xml_text: str, feed_url: str) -> list[Story]:
    root = ET.fromstring(xml_text)
    items: list[Story] = []
    for node in root.iter():
        name = _local(node.tag).lower()
        if name not in {"item", "entry"}:
            continue
        title = ""
        url = ""
        summary = ""
        published = ""
        for child in list(node):
            cname = _local(child.tag).lower()
            text = (child.text or "").strip()
            if cname == "title":
                title = text
            elif cname in {"link"}:
                href = child.attrib.get("href", "")
                url = href or text or url
            elif cname in {"guid", "id"} and not url:
                url = text
            elif cname in {"description", "summary", "content"}:
                summary = text
            elif cname in {"pubdate", "published", "updated", "date"}:
                published = text
        if not title and not url:
            continue
        ident = hashlib.sha256((url or title).encode("utf-8")).hexdigest()[:16]
        items.append(
            Story(
                id=ident,
                title=title or "Untitled",
                url=url,
                summary=_strip_tags(summary)[:800],
                published=published,
                feed=feed_url,
            )
        )
    return items


def _strip_tags(html: str) -> str:
    return ET.fromstring(f"<t>{html}</t>").text if False else _cheap_strip(html)


def _cheap_strip(html: str) -> str:
    out: list[str] = []
    skip = False
    for ch in html:
        if ch == "<":
            skip = True
            continue
        if ch == ">":
            skip = False
            out.append(" ")
            continue
        if not skip:
            out.append(ch)
    return " ".join("".join(out).split())


def _open(url: str, timeout: int) -> str:
    if url.startswith("file:"):
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_one(url: str, timeout: int = 8, retries: int = 2) -> dict[str, Any]:
    started = time.perf_counter()
    last_err = "unknown"
    attempts = retries + 1
    for attempt in range(attempts):
        try:
            xml_text = _open(url, timeout=timeout)
            items = parse_feed(xml_text, url)
            return {
                "url": url,
                "ok": True,
                "item_count": len(items),
                "error": None,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "attempts": attempt + 1,
                "items": items,
            }
        except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError, ValueError) as exc:
            last_err = str(exc) or type(exc).__name__
            if attempt + 1 < attempts:
                time.sleep(0.2 * (attempt + 1))
    return {
        "url": url,
        "ok": False,
        "item_count": 0,
        "error": last_err,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "attempts": attempts,
        "items": [],
    }


def fetch_feeds(urls: list[str], timeout: int = 8, retries: int = 2) -> list[dict[str, Any]]:
    if not urls:
        return []
    # Bound the wait: each feed has a short timeout * attempts, fetched in parallel.
    deadline = timeout * (retries + 1) + 3
    workers = min(8, len(urls))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_one, url, timeout, retries): url for url in urls}
        try:
            for fut in as_completed(futs, timeout=deadline):
                results.append(fut.result())
        except TimeoutError:
            for fut, url in futs.items():
                if not fut.done():
                    fut.cancel()
                    results.append(
                        {
                            "url": url,
                            "ok": False,
                            "item_count": 0,
                            "error": "deadline exceeded",
                            "elapsed_ms": deadline * 1000,
                            "attempts": retries + 1,
                            "items": [],
                        }
                    )
                elif fut.done() and not fut.cancelled():
                    try:
                        results.append(fut.result())
                    except Exception as exc:  # pragma: no cover
                        results.append(
                            {
                                "url": url,
                                "ok": False,
                                "item_count": 0,
                                "error": str(exc),
                                "elapsed_ms": deadline * 1000,
                                "attempts": retries + 1,
                                "items": [],
                            }
                        )
    by_url = {r["url"]: r for r in results}
    return [by_url[u] for u in urls if u in by_url]

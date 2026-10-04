#!/usr/bin/env python3
"""Publish one scheduled five-image carousel to Instagram and Facebook."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
POSTS_PATH = ROOT / "data" / "posts.json"
STATE_PATH = ROOT / "data" / "state.json"
TIMEZONE = ZoneInfo("Europe/Chisinau")
SLOT_HOURS = (9, 14, 19)


class PublishError(Exception):
    pass


def load_posts() -> list[dict]:
    posts = json.loads(POSTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(posts, list) or len(posts) != 30:
        raise PublishError("Expected exactly 30 scheduled posts")
    seen = set()
    for post in posts:
        key = (post["date"], post["slot"])
        if key in seen or post["slot"] not in SLOT_HOURS:
            raise PublishError(f"Duplicate or invalid slot: {key}")
        seen.add(key)
        if len(post["images"]) != 5:
            raise PublishError(f"Post {post['id']} needs five images")
        if not post["caption"].strip():
            raise PublishError(f"Post {post['id']} has no caption")
        for image in post["images"]:
            if not (ROOT / image).is_file():
                raise PublishError(f"Missing image: {image}")
    return posts


def current_post(posts: list[dict], now: datetime) -> dict | None:
    local = now.astimezone(TIMEZONE)
    if local.hour not in SLOT_HOURS or local.minute > 20:
        return None
    return next(
        (post for post in posts if post["date"] == local.date().isoformat() and post["slot"] == local.hour),
        None,
    )


def media_urls(post: dict, base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    if not base.startswith("https://"):
        raise PublishError("MEDIA_BASE_URL must be a public HTTPS URL")
    return [f"{base}/{path}" for path in post["images"]]


def verify_media_urls(urls: list[str]) -> None:
    for url in urls:
        request = Request(url, method="HEAD", headers={"User-Agent": "TheBusinessRevealPublisher/1.0"})
        try:
            with urlopen(request, timeout=25) as response:
                content_type = response.headers.get("Content-Type", "")
                if "image/jpeg" not in content_type:
                    raise PublishError(f"Image URL returned {content_type}: {url}")
        except (HTTPError, URLError) as error:
            raise PublishError(f"Image URL is not publicly accessible: {url} ({error})") from error


class GraphAPI:
    def __init__(self, token: str, version: str = "v26.0") -> None:
        self.token = token
        self.base = f"https://graph.facebook.com/{version}"

    def request(self, method: str, path: str, params: dict | None = None) -> dict:
        url = f"{self.base}/{path.lstrip('/')}"
        payload = None
        if method == "GET" and params:
            url += "?" + urlencode(params)
        elif params:
            payload = urlencode(params).encode("utf-8")
        request = Request(
            url,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TheBusinessRevealPublisher/1.0",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                details = json.load(error)
                meta_error = details.get("error", {})
                message = meta_error.get("message", "Graph API request failed")
                code = meta_error.get("code", "unknown")
            except (ValueError, AttributeError):
                message, code = "Graph API request failed", "unknown"
            raise PublishError(f"Meta error {code}: {message}") from None
        except URLError as error:
            raise PublishError(f"Meta request did not complete: {error.reason}") from error
        if "error" in result:
            raise PublishError(f"Meta error: {result['error'].get('message', 'unknown')}")
        return result


def wait_for_container(api: GraphAPI, container_id: str) -> None:
    for _ in range(20):
        status = api.request("GET", container_id, {"fields": "status_code"}).get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram container {container_id} status: {status}")
        time.sleep(3)
    raise PublishError(f"Instagram container {container_id} did not finish in time")


def prepare_instagram(api: GraphAPI, user_id: str, urls: list[str], caption: str) -> str:
    children = []
    for url in urls:
        result = api.request("POST", f"{user_id}/media", {"image_url": url, "is_carousel_item": "true"})
        child_id = result["id"]
        wait_for_container(api, child_id)
        children.append(child_id)
    parent = api.request(
        "POST",
        f"{user_id}/media",
        {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption},
    )
    wait_for_container(api, parent["id"])
    return parent["id"]


def prepare_facebook(api: GraphAPI, page_id: str, urls: list[str]) -> list[str]:
    photo_ids = []
    for url in urls:
        result = api.request("POST", f"{page_id}/photos", {"url": url, "published": "false"})
        photo_ids.append(result["id"])
    return photo_ids


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict, message: str) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "data/state.json"], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    subprocess.run(["git", "push"], cwd=ROOT, check=True)


def publish_platform(
    api: GraphAPI,
    state: dict,
    post: dict,
    platform: str,
    prepare,
    publish,
) -> None:
    record = state.setdefault(post["id"], {})
    existing = record.get(platform, {})
    if existing.get("status") == "published":
        print(f"{platform}: already published; skipping")
        return
    if existing.get("status") == "attempting":
        raise PublishError(f"{platform}: previous publish attempt is unresolved; inspect Meta before retrying")

    prepared = prepare()
    record[platform] = {
        "status": "attempting",
        "prepared_id": prepared if isinstance(prepared, str) else None,
        "started_at": datetime.now(TIMEZONE).isoformat(),
    }
    save_state(state, f"Reserve {post['id']} {platform} publish")

    published_id = publish(prepared)
    record[platform] = {
        "status": "published",
        "media_id": published_id,
        "published_at": datetime.now(TIMEZONE).isoformat(),
    }
    save_state(state, f"Record {post['id']} {platform} publish")
    print(f"{platform}: published ID {published_id}")


def run(now: datetime, live: bool) -> int:
    posts = load_posts()
    post = current_post(posts, now)
    if post is None:
        print("No scheduled post in the current Chișinău slot; nothing published")
        return 0
    print(f"Scheduled: {post['id']} — {post['brand']} at {post['date']} {post['slot']:02d}:00")
    if not live:
        print("Dry run: no Meta requests or state changes")
        return 0

    if os.environ.get("PUBLISH_ENABLED") != "true":
        raise PublishError("PUBLISH_ENABLED is not true; live publishing is disabled")
    required = ("META_PAGE_ACCESS_TOKEN", "META_IG_USER_ID", "META_FB_PAGE_ID", "MEDIA_BASE_URL")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise PublishError("Missing configuration: " + ", ".join(missing))

    urls = media_urls(post, os.environ["MEDIA_BASE_URL"])
    verify_media_urls(urls)
    api = GraphAPI(os.environ["META_PAGE_ACCESS_TOKEN"], os.environ.get("META_GRAPH_VERSION", "v26.0"))
    state = load_state()
    user_id = os.environ["META_IG_USER_ID"]
    page_id = os.environ["META_FB_PAGE_ID"]
    publish_platform(
        api, state, post, "instagram",
        lambda: prepare_instagram(api, user_id, urls, post["caption"]),
        lambda parent: api.request("POST", f"{user_id}/media_publish", {"creation_id": parent})["id"],
    )
    publish_platform(
        api, state, post, "facebook",
        lambda: prepare_facebook(api, page_id, urls),
        lambda photos: api.request(
            "POST", f"{page_id}/feed",
            {"message": post["caption"], **{
                f"attached_media[{i}]": json.dumps({"media_fbid": photo_id})
                for i, photo_id in enumerate(photos)
            }},
        )["id"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Enable live Meta publishing")
    parser.add_argument("--at", help="ISO timestamp for dry-run inspection")
    args = parser.parse_args()
    if args.at and args.publish:
        parser.error("--at is only allowed for dry runs")
    now = datetime.fromisoformat(args.at) if args.at else datetime.now(TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=TIMEZONE)
    try:
        return run(now, live=args.publish)
    except PublishError as error:
        print(f"Publisher stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

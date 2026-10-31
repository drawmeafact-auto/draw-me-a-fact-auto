"""Hands-free upload (§ workflow): YouTube Shorts + optional Instagram Reels.

Every function degrades to a clear, non-fatal status when credentials are
missing — a dry run must never fail because YouTube is not configured.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import (
    IG_ACCESS_TOKEN,
    IG_USER_ID,
    PUBLIC_VIDEO_URL,
    TARGET_PUBLISH_HOUR,
    TARGET_PUBLISH_MINUTE,
    TARGET_TIMEZONE,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API = "https://www.googleapis.com/upload/youtube/v3/videos"


def youtube_configured() -> bool:
    return all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN])


def instagram_configured() -> bool:
    return all([IG_USER_ID, IG_ACCESS_TOKEN])


def _credentials():
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def scheduled_publish_time() -> datetime:
    tz = ZoneInfo(TARGET_TIMEZONE)
    now = datetime.now(tz)
    target = now.replace(hour=TARGET_PUBLISH_HOUR, minute=TARGET_PUBLISH_MINUTE, second=0, microsecond=0)
    if target <= now:
        target = target.fromtimestamp(target.timestamp() + 86400, tz)
    return target


def metadata_for(report: dict, ep: dict) -> dict[str, Any]:
    title = str(ep.get("title", ""))[:100]
    description = (
        f"{ep.get('hook_130','')}\n\n"
        f"{ep.get('numbers_summary','')}\n\n"
        f"Series: {ep.get('series','')} — one fact, one sheet, one minute.\n"
        f"Subscribe: <YOUR_SUBSCRIBE_LINK>\n"
    )
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [t.strip() for t in str(ep.get("tags", "")).split(",") if t.strip()][:30],
            "categoryId": "27",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def upload_youtube(video: Path, report: dict, ep: dict, publish_mode: str = "dry_run") -> dict[str, Any]:
    if publish_mode == "dry_run":
        return {"platform": "youtube", "status": "skipped", "reason": "dry_run"}
    if not youtube_configured():
        return {"platform": "youtube", "status": "skipped", "reason": "YOUTUBE_* secrets not set"}

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        yt = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
        body = metadata_for(report, ep)
        if publish_mode == "schedule_target":
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = scheduled_publish_time().astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif publish_mode == "public_now":
            body["status"]["privacyStatus"] = "public"
        elif publish_mode in ("unlisted", "private"):
            body["status"]["privacyStatus"] = publish_mode

        media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
        return {
            "platform": "youtube",
            "status": "uploaded",
            "video_id": resp.get("id"),
            "url": f"https://youtube.com/shorts/{resp.get('id')}",
            "privacy": body["status"]["privacyStatus"],
            "publish_at": body["status"].get("publishAt"),
        }
    except Exception as exc:  # pragma: no cover - network path
        return {"platform": "youtube", "status": "error", "reason": str(exc)[:400]}


def post_instagram(caption_path: Path, report: dict, publish_mode: str = "dry_run") -> dict[str, Any]:
    if publish_mode == "dry_run":
        return {"platform": "instagram", "status": "skipped", "reason": "dry_run"}
    if not instagram_configured():
        return {"platform": "instagram", "status": "skipped", "reason": "IG_* secrets not set"}
    if not PUBLIC_VIDEO_URL:
        return {"platform": "instagram", "status": "skipped", "reason": "PUBLIC_VIDEO_URL not set"}

    import requests

    try:
        base = f"https://graph.facebook.com/v21.0/{IG_USER_ID}"
        r = requests.post(
            f"{base}/media",
            data={
                "media_type": "REELS",
                "video_url": PUBLIC_VIDEO_URL,
                "caption": caption_path.read_text(encoding="utf-8")[:2100],
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=120,
        )
        r.raise_for_status()
        creation = r.json()["id"]
        pub = requests.post(
            f"{base}/media_publish",
            data={"creation_id": creation, "access_token": IG_ACCESS_TOKEN},
            timeout=120,
        )
        pub.raise_for_status()
        return {"platform": "instagram", "status": "published", "media_id": pub.json().get("id")}
    except Exception as exc:  # pragma: no cover
        return {"platform": "instagram", "status": "error", "reason": str(exc)[:400]}


def publish_episode(video: Path, report: dict, ep: dict, publish_mode: str = "dry_run") -> list[dict]:
    results = [upload_youtube(video, report, ep, publish_mode)]
    if publish_mode != "dry_run":
        cap = Path(report.get("files", {}).get("ig_caption", ""))
        if cap.exists():
            results.append(post_instagram(cap, report, publish_mode))
    return results

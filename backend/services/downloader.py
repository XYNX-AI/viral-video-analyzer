import asyncio
import json
import os
import re
import shutil
import sys

import httpx
from playwright.async_api import async_playwright

from config import settings
from models.schemas import VideoMeta


_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
_xvfb_process = None
_xvfb_display = None
_xvfb_lock = asyncio.Lock()


async def _ensure_virtual_display() -> bool:
    """Start Xvfb once so Douyin sees a headed Chromium browser in Docker."""
    global _xvfb_process, _xvfb_display
    if os.environ.get("DISPLAY"):
        return True
    if not shutil.which("Xvfb"):
        return False

    async with _xvfb_lock:
        if _xvfb_process and _xvfb_process.returncode is None:
            os.environ["DISPLAY"] = _xvfb_display
            return True

        process = await asyncio.create_subprocess_exec(
            "Xvfb", "-displayfd", "1", "-screen", "0", "1920x1080x24",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            display_number = await asyncio.wait_for(process.stdout.readline(), timeout=5)
        except asyncio.TimeoutError:
            process.terminate()
            await process.wait()
            return False

        if not display_number.strip().isdigit():
            process.terminate()
            await process.wait()
            return False

        _xvfb_process = process
        _xvfb_display = f":{display_number.decode().strip()}"
        os.environ["DISPLAY"] = _xvfb_display
        return True


def _load_cookie_file() -> list[dict]:
    """Parse a Netscape-format cookie file (DOUYIN_COOKIE_FILE) into Playwright cookies.

    Douyin returns an empty body for /aweme/v1/web/aweme/detail/ unless the request
    carries a logged-in session cookie, so this is required for downloads to work.
    """
    path = (settings.DOUYIN_COOKIE_FILE or "").strip()
    if not path:
        return []
    if not os.path.exists(path):
        print(f"[downloader] DOUYIN_COOKIE_FILE not found: {path}")
        return []

    cookies = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 7:
                continue
            domain, _flag, cpath, secure, expires, name, value = parts
            if not name:
                continue
            try:
                exp = int(float(expires))
            except ValueError:
                exp = -1
            cookie = {
                "name": name,
                "value": value,
                "domain": domain,
                "path": cpath or "/",
                "secure": secure.upper() == "TRUE",
            }
            if exp > 0:
                cookie["expires"] = exp
            cookies.append(cookie)

    print(f"[downloader] loaded {len(cookies)} cookies from {path}")
    return cookies



async def download_video(url: str, output_dir: str) -> VideoMeta:
    """Download a supported video URL and normalize metadata.

    Douyin keeps its authenticated Playwright path because it reliably handles
    the site's detail API. Other platforms use yt-dlp, which supports TikTok,
    Instagram Reels, YouTube Shorts, X, Pinterest and many more sites.
    """
    if _is_douyin_url(url):
        return await _download_douyin_video(url, output_dir)
    return await _download_ytdlp_video(url, output_dir)


def _is_douyin_url(url: str) -> bool:
    lowered = url.lower()
    return "douyin.com" in lowered or "iesdouyin.com" in lowered


async def _download_douyin_video(url: str, output_dir: str) -> VideoMeta:
    """Download Douyin video with the existing Playwright detail flow."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "video.mp4")

    # Step 1: Get detail JSON
    detail_path = os.path.join(output_dir, "detail.json")
    if os.path.exists(detail_path):
        with open(detail_path, "r", encoding="utf-8") as f:
            detail = json.load(f)
    else:
        detail = await _fetch_detail_playwright(url)
        if detail:
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(detail, f, ensure_ascii=False)

    if not detail or "aweme_detail" not in detail:
        raise RuntimeError("无法获取视频详情，请确保链接有效")

    aweme = detail["aweme_detail"]
    meta = _parse_meta(aweme)

    # Step 2: Download video
    video_url = _get_best_video_url(aweme)
    if not video_url:
        raise RuntimeError("未找到视频下载地址")

    await _download_file(video_url, output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError("视频下载失败或文件过小")

    return meta


async def _download_ytdlp_video(url: str, output_dir: str) -> VideoMeta:
    """Download non-Douyin platforms through yt-dlp and parse info JSON."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "video.mp4")
    info_path = os.path.join(output_dir, "ytdlp_info.json")

    binary = shutil.which(settings.YTDLP_BIN)
    command = [
        *( [binary] if binary else [sys.executable, "-m", "yt_dlp"] ),
        "--no-playlist",
        "--remote-components", "ejs:github",
        "--js-runtimes", "node",
        "--write-info-json",
        "--no-write-thumbnail",
        # Keep analysis downloads bounded and prefer broadly supported H.264.
        "--format", "bv*[height<=1080][vcodec^=avc1]+ba[acodec^=mp4a]/bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mp4",
        "--output", os.path.join(output_dir, "video.%(ext)s"),
        "--print-json",
    ]
    cookie_file = _get_ytdlp_cookie_file(url)
    if cookie_file:
        if not os.path.exists(cookie_file):
            raise RuntimeError(f"YTDLP_COOKIE_FILE 不存在: {cookie_file}")
        command.extend(["--cookies", cookie_file])
    proxy = (settings.YTDLP_PROXY or "").strip()
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"跨平台视频下载失败: {detail[-800:]}")

    info = _parse_ytdlp_json(stdout.decode("utf-8", errors="replace"), output_dir)
    if not os.path.exists(output_path):
        candidates = [
            path for path in (os.path.join(output_dir, name) for name in os.listdir(output_dir))
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in {".mp4", ".mkv", ".webm", ".mov"}
        ]
        if candidates:
            os.replace(candidates[0], output_path)
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError("跨平台视频下载完成但未找到有效视频文件")

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)
    return _parse_ytdlp_meta(info)


def _get_ytdlp_cookie_file(url: str) -> str:
    """Resolve a yt-dlp cookie file, preferring a platform-specific override."""
    platform = _detect_ytdlp_platform(url)
    mappings = {}
    for item in (settings.YTDLP_COOKIE_FILES or "").split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, path = item.split("=", 1)
        if name.strip() and path.strip():
            mappings[name.strip().lower()] = path.strip()
    return mappings.get(platform) or (settings.YTDLP_COOKIE_FILE or "").strip()


def _detect_ytdlp_platform(url: str) -> str:
    host = re.sub(r"^www\.", "", re.findall(r"https?://([^/]+)", url.lower())[0]) if re.findall(r"https?://([^/]+)", url.lower()) else ""
    if "tiktok.com" in host:
        return "tiktok"
    if "instagram.com" in host:
        return "instagram"
    if "youtube.com" in host or host == "youtu.be":
        return "youtube"
    if "twitter.com" in host or "x.com" in host:
        return "x"
    if "pinterest." in host:
        return "pinterest"
    return "default"


def _parse_ytdlp_json(stdout: str, output_dir: str) -> dict:
    """Parse yt-dlp's final JSON line, with info-file fallback."""
    for line in reversed(stdout.splitlines()):
        try:
            value = json.loads(line)
            if isinstance(value, dict) and (value.get("id") or value.get("title")):
                return value
        except json.JSONDecodeError:
            continue

    info_files = sorted(
        os.path.join(output_dir, name)
        for name in os.listdir(output_dir)
        if name.endswith(".info.json")
    )
    if info_files:
        with open(info_files[-1], "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _parse_ytdlp_meta(info: dict) -> VideoMeta:
    """Map common yt-dlp metadata fields into the existing VideoMeta schema."""
    duration = info.get("duration") or 0
    return VideoMeta(
        title=info.get("title") or info.get("description") or "",
        author=info.get("uploader") or info.get("channel") or "",
        author_id=info.get("uploader_id") or info.get("channel_id") or "",
        likes=info.get("like_count"),
        comments=info.get("comment_count"),
        shares=info.get("repost_count") or info.get("share_count"),
        duration=float(duration),
        thumbnail_url=info.get("thumbnail"),
    )


async def _fetch_detail_playwright(url: str) -> dict | None:
    """Use Playwright to open Douyin page and intercept the detail API response."""
    aweme_id = _extract_aweme_id(url)
    if not aweme_id:
        aweme_id = await _resolve_short_url(url)
    if not aweme_id:
        raise RuntimeError(f"无法从链接提取视频ID: {url}")

    # Ensure URL is in full format
    if "douyin.com/video/" not in url:
        url = f"https://www.douyin.com/video/{aweme_id}"

    last_failure = None
    for attempt in range(1, 4):
        detail, attempt_failure = await _fetch_detail_attempt(url, aweme_id, attempt)
        if detail:
            return detail
        if attempt_failure:
            last_failure = attempt_failure
        if attempt < 3:
            await asyncio.sleep(attempt * 2)

    if last_failure:
        raise RuntimeError(last_failure)
    return None


async def _fetch_detail_attempt(
    url: str, aweme_id: str, attempt: int
) -> tuple[dict | None, str | None]:
    detail_json = None
    failure_reason = None
    has_display = await _ensure_virtual_display()

    async with async_playwright() as p:
        # Douyin is reachable directly. Keep overseas yt-dlp proxy settings out
        # of this browser flow because changing the exit node breaks its session
        # and device verification.
        browser = await p.chromium.launch(
            headless=not has_display,
            args=["--disable-blink-features=AutomationControlled"] if has_display else [],
        )
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{browser.version} Safari/537.36"
        )
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        cookies = _load_cookie_file()
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()

        # Intercept the detail API response
        response_future = asyncio.get_event_loop().create_future()

        async def handle_response(response):
            nonlocal detail_json, failure_reason
            if response_future.done():
                return
            resp_url = response.url
            if "aweme/v1/web/aweme/detail" in resp_url and aweme_id in resp_url:
                try:
                    body = await response.json()
                    if body.get("aweme_detail"):
                        detail_json = body
                        if not response_future.done():
                            response_future.set_result(body)
                    else:
                        failure_reason = (
                            "抖音详情接口返回空数据 "
                            f"(HTTP {response.status}, status_code="
                            f"{body.get('status_code', 'unknown')})"
                        )
                        print(
                            "[downloader] Douyin detail had no video data "
                            f"(attempt {attempt}/3, http={response.status}, "
                            f"status_code={body.get('status_code', 'unknown')})"
                        )
                except Exception:
                    if response.status >= 400:
                        failure_reason = (
                            f"抖音详情接口拒绝请求 (HTTP {response.status})，"
                            "请刷新登录 Cookie 后重试"
                        )
                        print(
                            "[downloader] Douyin detail request rejected "
                            f"(attempt {attempt}/3, http={response.status})"
                        )

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="commit", timeout=30000)
            await asyncio.wait_for(asyncio.shield(response_future), timeout=18)
        except asyncio.TimeoutError:
            # Try to extract from page SSR data as fallback
            detail_json = await _extract_from_ssr(page, aweme_id)
            if not detail_json:
                failure_reason = "等待抖音详情接口超时，请稍后重试"
                print(f"[downloader] Douyin detail timed out (attempt {attempt}/3)")
        except Exception:
            pass
        finally:
            await browser.close()

    return detail_json, failure_reason


async def _extract_from_ssr(page, aweme_id: str) -> dict | None:
    """Try to extract video detail from page's SSR RENDER_DATA."""
    try:
        content = await page.evaluate("""() => {
            const el = document.querySelector('script[id="RENDER_DATA"]');
            if (!el) return null;
            return decodeURIComponent(el.textContent);
        }""")
        if not content:
            return None
        data = json.loads(content)
        # Search for video detail in the data tree
        return _find_aweme_detail(data, aweme_id)
    except Exception:
        return None


def _find_aweme_detail(data: dict, aweme_id: str) -> dict | None:
    """Recursively search for aweme_detail in SSR data."""
    if isinstance(data, dict):
        if "aweme_detail" in data or "awemeDetail" in data:
            detail = data.get("aweme_detail") or data.get("awemeDetail")
            if detail and isinstance(detail, dict):
                return {"aweme_detail": detail}
        for v in data.values():
            result = _find_aweme_detail(v, aweme_id)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_aweme_detail(item, aweme_id)
            if result:
                return result
    return None


def _extract_aweme_id(url: str) -> str | None:
    match = re.search(r"video/(\d+)", url)
    return match.group(1) if match else None


async def _resolve_short_url(url: str) -> str | None:
    """Resolve v.douyin.com short URL to get aweme_id."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": _UA},
        ) as client:
            resp = await client.head(url, timeout=10)
            final_url = str(resp.url)
            return _extract_aweme_id(final_url)
    except Exception:
        return None


def _parse_meta(aweme: dict) -> VideoMeta:
    stats = aweme.get("statistics", {})
    video = aweme.get("video", {})
    author = aweme.get("author", {})
    duration = video.get("duration", 0)
    if duration > 1000:
        duration = duration / 1000
    return VideoMeta(
        title=aweme.get("desc", ""),
        author=author.get("nickname", ""),
        author_id=author.get("sec_uid", author.get("uid", "")),
        likes=stats.get("digg_count"),
        comments=stats.get("comment_count"),
        shares=stats.get("share_count"),
        duration=duration,
        thumbnail_url=video.get("cover", {}).get("url_list", [None])[0],
    )


def _get_best_video_url(aweme: dict) -> str | None:
    video = aweme.get("video", {})
    bit_rate = video.get("bit_rate", [])
    if bit_rate:
        sorted_rates = sorted(bit_rate, key=lambda x: x.get("bit_rate", 0), reverse=True)
        for rate in sorted_rates:
            urls = rate.get("play_addr", {}).get("url_list", [])
            for u in urls:
                if "douyinvod.com" in u:
                    return u
            if urls:
                return urls[0]
    play_addr = video.get("play_addr", {})
    urls = play_addr.get("url_list", [])
    for u in urls:
        if "douyinvod.com" in u:
            return u
    return urls[0] if urls else None


async def _download_file(url: str, output_path: str):
    cmd = [
        "curl", "-L", "-o", output_path,
        "--noproxy", "*",
        "-H", f"User-Agent: {_UA}",
        "-H", "Referer: https://www.douyin.com/",
        "--max-time", "120", "--retry", "2", "-s",
        url,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"下载失败: {stderr.decode()[:200]}")

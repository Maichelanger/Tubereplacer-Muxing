import requests_cache, re, config, json, threading, time, glob
from datetime import timedelta
from modules import helpers, get

import subprocess, os, shutil

# Videos expires after 5 hours, so you don't have to worry.
session = requests_cache.CachedSession('cache/videos', expire_after=timedelta(hours=4), ignored_parameters=['key'], backend=config.backend)

# hard-coded API Key, from youtube's private API
api_key = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8'

# Get HLS URL via innertube and fetch the file, then filter to fix low quality playback error
# Much thanks for SpaceSaver.
def hls_video_url(video_id, res=None):

    # using IOS client since Apple invented HLS
    json_data = {
        "context": {"client": {
            "clientName": "IOS",
            "clientVersion": "19.16.3"
        }},
        "videoId": video_id
    }
    
    # fetch innertube
    data = session.post('https://www.youtube.com/youtubei/v1/player?key=' + api_key, json=json_data, proxies=helpers.proxies).json()
def data_to_hls_url(data, res = None):
    # get video's m3u8 to process it.
    panda = session.get(data["streamingData"]["hlsManifestUrl"], proxies=helpers.proxies).text.split("\n")

    # regex filter
    formatfilter = re.compile(r"^#EXT-X-STREAM-INF:BANDWIDTH=(?P<bandwidth>\d+),CODECS=\"(?P<codecs>[^\"]+)\",RESOLUTION=(?P<width>\d+)x(?P<height>\d+),FRAME-RATE=(?P<fps>\d+),VIDEO-RANGE=(?P<videoRange>[^,]+),AUDIO=\"(?P<audioGroup>[^\"]+)\"(,SUBTITLES=\"(?P<subGroup>[^\"]+)\")?")
    vertical = None
    maxRes = 0
    wanted_resolution = res and type(res) == int and min(max(res, 144), config.RESMAX) or config.HLS_RESOLUTION or 360
    # doesn't bother to explain the code, sooo...
    # TODO: explain the thing, lazer eyed cat.
    for x in range(len(panda)):
        line = panda[x]
        match = formatfilter.match(line)

        # dude
        if not match:
            continue
        
        # continue if codecs is not compatible (or matched?)
        if not match.group("codecs").startswith("avc"):
            panda[x] = ""
            panda[x+1] = ""
            continue
        
        # reject framerates over 30
        if int(match.group("fps")) > 30:
            panda[x] = ""
            panda[x+1] = ""
            continue
        
        if vertical is None:
            vertical = int(match.group("height")) > int(match.group("width"))
        res = 0

        # match vertical with width, because higher
        if vertical:
            res = int(match.group("width"))
        else:
            res = int(match.group("height"))

        # if resolution bigger than the expected height, skip
        if res > wanted_resolution:
            panda[x] = ""
            panda[x+1] = ""
            continue

        if res > maxRes:
           maxRes = res

    for x in range(len(panda)):
        line = panda[x]
        match = formatfilter.match(line)

        if not match:
            continue
        res = 0

        if vertical:
            res = int(match.group("width"))
        else:
            res = int(match.group("height"))

        if res < maxRes:
            panda[x] = ""
            panda[x+1] = ""

    panda = "\n".join(panda)
    return panda

# 360p (SD)
# Get HLS URL via youtubei and fetch the file, then filter to fix low quality playback error
# Much thanks for SpaceSaver.
def hls_video_url(video_id, res=None):

    # using IOS client since Apple invented HLS, duh.
    json_data = {
        "context": {"client": {
            "clientName": "IOS",
            "clientVersion": "19.16.3",
        }},
        "videoId": video_id
    }
    
    # fetch innertube
    data = session.post('https://www.youtube.com/youtubei/v1/player?key=' + api_key, json=json_data, proxies=helpers.proxies).json()
    return data_to_hls_url(data, res)

def data_to_medium_url(data):
    return data["streamingData"]['formats'][0]['url']

# play 360p
# for the kids who begged for this, here you go...
def medium_quality_video_url(video_id):

    json_data = {
        "context": {"client": {
            "clientName": "ANDROID",
            "clientVersion": "19.17.34"
        }},
        # This can play copyrighted videos.
        # See https://github.com/tombulled/innertube/issues/76
        "params": '8AEB',
        "videoId": video_id
    }

    # fetch the API.
    data = session.post('https://www.youtube.com/youtubei/v1/player?key=' + api_key, json=json_data, proxies=helpers.proxies).json()

    # i'm lazy. again.
    return data_to_medium_url(data)

class metadata:

    def simple_channel_info(id):

        json_data = {
            "context": {
                'client': {
                    'clientName': 'WEB',
                    'clientVersion': '2.20240814.00.00'
                }
            },
            "params": "EgZzaG9ydHPyBgUKA5oBAA%3D%3D",
            "browseId": id
        }

        # fetch the API.
        data = session.post('https://www.youtube.com/youtubei/v1/browse?key=' + api_key, json=json_data).json()
        try:
            subs = get.subscribers(data['header']['pageHeaderRenderer']['content']['pageHeaderViewModel']['metadata']['contentMetadataViewModel']['metadataRows'][1]['metadataParts'][0]['text']['content'])
        except:
            subs = -1
        # i'm lazy. again.
        return {
            "name": data['header']['pageHeaderRenderer']['pageTitle'],
            "channel_id": data['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['endpoint']['browseEndpoint']['browseId'],
            "profile_picture": data['header']['pageHeaderRenderer']['content']['pageHeaderViewModel']['image']['decoratedAvatarViewModel']['avatar']['avatarViewModel']['image']['sources'][0]['url'],
            "subscribers": subs
        }
    
def clear_video_cache():
    cache_dir = os.path.join(os.getcwd(), "cache_videos")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("[TubeRepair] Video cache cleared successfully.")
        except Exception as e:
            print(f"[TubeRepair] Could not clear cache folder: {e}")

def download_high_res(video_id):
    import glob

    # Set up a local folder for the high-res MP4 files
    cache_dir = os.path.join(os.getcwd(), "cache_videos")
    os.makedirs(cache_dir, exist_ok=True)
    output_file = os.path.join(cache_dir, f"{video_id}.mp4")

    # If the video was already downloaded previously, serve it instantly
    if os.path.exists(output_file):
        print(f"[TubeRepair] Serving cached file for: {video_id}")
        return output_file

    video_tmpl = os.path.join(cache_dir, f"{video_id}_video.%(ext)s")
    audio_tmpl = os.path.join(cache_dir, f"{video_id}_audio.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"

    video_cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=720][vcodec^=avc1]",
        "-o", video_tmpl,
        url
    ]
    audio_cmd = [
        "yt-dlp",
        "-f", "bestaudio[ext=m4a]",
        "-o", audio_tmpl,
        url
    ]

    print(f"[TubeRepair] Downloading 720p video+audio in parallel for: {video_id}")

    video_tmp_path = None
    audio_tmp_path = None

    try:
        # Launch both downloads at the same time instead of sequentially.
        p_video = subprocess.Popen(video_cmd)
        p_audio = subprocess.Popen(audio_cmd)

        video_rc = p_video.wait()
        audio_rc = p_audio.wait()

        if video_rc != 0 or audio_rc != 0:
            raise RuntimeError(f"yt-dlp exited non-zero (video={video_rc}, audio={audio_rc})")

        video_matches = glob.glob(os.path.join(cache_dir, f"{video_id}_video.*"))
        audio_matches = glob.glob(os.path.join(cache_dir, f"{video_id}_audio.*"))

        if not video_matches or not audio_matches:
            raise RuntimeError("Downloaded video/audio file not found after yt-dlp completed")

        video_tmp_path = video_matches[0]
        audio_tmp_path = audio_matches[0]

        print(f"[TubeRepair] Remuxing (stream copy, no re-encode) for: {video_id}")

        # -c copy = container remux only, no transcoding, so this is fast
        # regardless of video length. +faststart relocates moov to the
        # front, which requires the full file to exist first.
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", video_tmp_path,
            "-i", audio_tmp_path,
            "-c", "copy",
            "-movflags", "+faststart",
            output_file
        ]
        subprocess.run(mux_cmd, check=True)

        if os.path.exists(output_file):
            return output_file

    except Exception as e:
        print(f"[TubeRepair] yt-dlp/ffmpeg download failed: {e}")
        if os.path.exists(output_file):
            os.remove(output_file)
        return None
    finally:
        # Clean up the intermediate video/audio-only files either way
        for tmp_path in (video_tmp_path, audio_tmp_path):
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    return None


# ============================================================
# HLS LIVE SLICING
# ============================================================
# Instead of waiting for a full download, this resolves the direct
# googlevideo CDN URLs and points ffmpeg's HLS muxer straight at them,
# writing .ts segments + a growing .m3u8 playlist as it goes. iOS 6's
# AVFoundation reads the playlist and starts playing after the first
# couple of segments exist, well before the full video is retrieved.
#
# Each video gets its own ffmpeg subprocess, tracked in HLS_SESSIONS so
# concurrent requests for the same video reuse one process instead of
# spawning duplicates, and so idle sessions (user backed out of the
# video) get reaped instead of running forever.

HLS_SESSIONS = {}          # video_id -> {process, dir, last_access}
HLS_SESSIONS_LOCK = threading.Lock()
HLS_IDLE_TIMEOUT = 30       # seconds without a playlist/segment request before we kill the session
HLS_REAP_INTERVAL = 10      # how often the reaper thread checks
HLS_SEGMENT_SECONDS = 4
HLS_FIRST_SEGMENT_TIMEOUT = 20  # how long to wait for the first .ts before giving up

_hls_reaper_started = False
_hls_reaper_lock = threading.Lock()


def _resolve_direct_url(video_id, format_selector):
    """Ask yt-dlp for a direct CDN URL + the headers required to fetch it, no download."""
    cmd = [
        "yt-dlp",
        "-f", format_selector,
        "-j",
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    return {
        "url": info["url"],
        "headers": info.get("http_headers", {}),
        "duration": info.get("duration"),
    }


def _write_vod_playlist(playlist_path, duration):
    """Writes a complete VOD-type HLS playlist upfront, based on the
    video's known total duration, with #EXT-X-ENDLIST included from the
    start. This is what gives iOS 6 a real duration/scrub bar instead of
    treating the stream as live — ffmpeg's own auto-generated playlist
    has no ENDLIST until the whole encode finishes, which is what made
    it look like a live broadcast with an incrementing counter.

    The actual .ts segments are still written progressively by ffmpeg in
    the background; the playlist just describes where they'll end up."""
    full_segments = int(duration // HLS_SEGMENT_SECONDS)
    remainder = duration - (full_segments * HLS_SEGMENT_SECONDS)
    total_segments = full_segments + (1 if remainder > 0.01 else 0)
    if total_segments == 0:
        total_segments = 1

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{HLS_SEGMENT_SECONDS}",
        "#EXT-X-PLAYLIST-TYPE:VOD",
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]
    for i in range(total_segments):
        is_last = (i == total_segments - 1)
        seg_duration = remainder if (is_last and remainder > 0.01) else HLS_SEGMENT_SECONDS
        lines.append(f"#EXTINF:{seg_duration:.3f},")
        lines.append(f"index{i}.ts")
    lines.append("#EXT-X-ENDLIST")

    with open(playlist_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return total_segments


def _build_header_arg(headers):
    """ffmpeg -headers wants one CRLF-joined string, or None if there's nothing to add."""
    if not headers:
        return None
    return "".join(f"{k}: {v}\r\n" for k, v in headers.items())


def _hls_cache_dir(video_id):
    return os.path.join(os.getcwd(), "cache_videos", "hls", video_id)


def _print_log_tail(log_path, lines=15):
    """Prints the tail of an ffmpeg log to the console for quick diagnosis
    without having to go dig the file up manually."""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip().splitlines()
        if content:
            print(f"[TubeRepair]   last {min(lines, len(content))} lines of {log_path}:")
            for line in content[-lines:]:
                print(f"[TubeRepair]     {line}")
    except Exception:
        pass


def _stop_hls_process(proc):
    """Gracefully stop ffmpeg via its stdin 'q' quit command (flushes the
    playlist/segment first), falling back to a hard kill if it won't die.
    Popen.terminate() alone is unsafe here: on Windows it calls
    TerminateProcess(), which kills ffmpeg before it can finish writing."""
    if proc.poll() is not None:
        return
    try:
        if proc.stdin:
            proc.stdin.write("q")
            proc.stdin.flush()
        proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass


def _remove_hls_session(video_id, session):
    _stop_hls_process(session["process"])
    log_file = session.get("log_file")
    if log_file:
        try:
            log_file.close()
        except Exception:
            pass
    if os.path.exists(session["dir"]):
        try:
            shutil.rmtree(session["dir"])
        except Exception as e:
            print(f"[TubeRepair] Could not remove HLS cache dir for {video_id}: {e}")


def _hls_reaper_loop():
    while True:
        time.sleep(HLS_REAP_INTERVAL)
        now = time.time()
        with HLS_SESSIONS_LOCK:
            crashed_ids = [
                vid for vid, s in HLS_SESSIONS.items()
                if s["process"].poll() is not None
            ]
            idle_ids = [
                vid for vid, s in HLS_SESSIONS.items()
                if vid not in crashed_ids and now - s["last_access"] > HLS_IDLE_TIMEOUT
            ]
            sessions_to_remove = {vid: HLS_SESSIONS.pop(vid) for vid in crashed_ids + idle_ids}

        for vid in crashed_ids:
            session = sessions_to_remove[vid]
            print(f"[TubeRepair] HLS session for {vid} ffmpeg process died unexpectedly "
                  f"(exit code {session['process'].returncode}) — cleaning up")
            _print_log_tail(session.get("log_path", ""))
            _remove_hls_session(vid, session)

        for vid in idle_ids:
            print(f"[TubeRepair] Reaping idle HLS session (no requests in {HLS_IDLE_TIMEOUT}s): {vid}")
            _remove_hls_session(vid, sessions_to_remove[vid])


def _ensure_hls_reaper_started():
    global _hls_reaper_started
    with _hls_reaper_lock:
        if not _hls_reaper_started:
            t = threading.Thread(target=_hls_reaper_loop, daemon=True)
            t.start()
            _hls_reaper_started = True


def touch_hls_session(video_id):
    """Called whenever the client fetches a playlist or segment, so the
    reaper knows the session is still actively being watched."""
    with HLS_SESSIONS_LOCK:
        if video_id in HLS_SESSIONS:
            HLS_SESSIONS[video_id]["last_access"] = time.time()


def hls_session_alive(video_id):
    with HLS_SESSIONS_LOCK:
        session = HLS_SESSIONS.get(video_id)
        return bool(session and session["process"].poll() is None)


def start_hls_stream(video_id):
    """Starts (or reuses) a live HLS slicing session for a video. Blocks
    only until the first segment is written (~1-2s), not the full video.
    Returns the playlist filename relative to the session dir, or None
    if resolution/ffmpeg failed."""
    _ensure_hls_reaper_started()

    with HLS_SESSIONS_LOCK:
        existing = HLS_SESSIONS.get(video_id)
        if existing and existing["process"].poll() is None:
            existing["last_access"] = time.time()
            return existing["playlist"]

    cache_dir = _hls_cache_dir(video_id)
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir, ignore_errors=True)
    os.makedirs(cache_dir, exist_ok=True)

    # This is the playlist we actually serve to the client — written by
    # us, once, upfront (see below). ffmpeg's own auto-generated playlist
    # goes to a separate, unused filename so it can't clobber ours.
    served_playlist_path = os.path.join(cache_dir, "index.m3u8")
    ffmpeg_playlist_path = os.path.join(cache_dir, "_ffmpeg_internal.m3u8")
    segment_pattern = os.path.join(cache_dir, "index%d.ts")

    print(f"[TubeRepair] Resolving CDN URLs for HLS session: {video_id}")
    try:
        video_info = _resolve_direct_url(video_id, "bestvideo[height<=720][vcodec^=avc1]")
        audio_info = _resolve_direct_url(video_id, "bestaudio[ext=m4a]")
    except Exception as e:
        print(f"[TubeRepair] Failed to resolve HLS source URLs for {video_id}: {e}")
        return None

    duration = video_info.get("duration") or audio_info.get("duration")
    if duration:
        _write_vod_playlist(served_playlist_path, duration)
    else:
        # No duration metadata available (unusual, e.g. an actual live
        # stream) — fall back to letting ffmpeg's own live-style playlist
        # be the one we serve directly, same as before this change.
        print(f"[TubeRepair] No duration metadata for {video_id}, falling back to live-style playlist")
        served_playlist_path = ffmpeg_playlist_path

    # Reconnect flags: ffmpeg's HTTP demuxer does NOT retry a dropped
    # connection by default. Over a long pull from two separate CDN
    # connections, a single transient mid-stream blip is normal — without
    # these, that blip kills the whole ffmpeg process instead of retrying.
    #
    # Deliberately NOT using -reconnect_at_eof here: that flag makes ffmpeg
    # treat a normal, complete download's end-of-file as a possible dropped
    # connection and retry anyway. There's nothing to reconnect to at a
    # genuine EOF, so the retry fails and kills ffmpeg right as it should
    # be finishing cleanly — this is what was cutting the last few segments
    # off shorter videos.
    reconnect_opts = [
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
    ]

    cmd = ["ffmpeg", "-y"]
    video_headers = _build_header_arg(video_info["headers"])
    if video_headers:
        cmd += ["-headers", video_headers]
    cmd += reconnect_opts
    cmd += ["-i", video_info["url"]]

    audio_headers = _build_header_arg(audio_info["headers"])
    if audio_headers:
        cmd += ["-headers", audio_headers]
    cmd += reconnect_opts
    cmd += ["-i", audio_info["url"]]

    cmd += [
        "-map", "0:v", "-map", "1:a",
        # -c copy was the original approach here, but it means ffmpeg's
        # HLS muxer can only cut a segment at a keyframe boundary in the
        # SOURCE video — it can't force an exact 4-second cut without
        # re-encoding. Real keyframe spacing is usually 5-6s, not 4s, so
        # actual segments came out longer (and fewer) than our upfront
        # VOD playlist assumed, and the deficit compounded with video
        # length. That's what was leaving the last several playlist
        # entries pointing at .ts files that never got created.
        #
        # Forcing a keyframe every HLS_SEGMENT_SECONDS makes the muxer's
        # cuts land where our playlist actually says they will. Audio
        # doesn't need keyframe alignment, so it stays a stream copy.
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-force_key_frames", f"expr:gte(t,n_forced*{HLS_SEGMENT_SECONDS})",
        "-c:a", "copy",
        "-f", "hls",
        "-hls_time", str(HLS_SEGMENT_SECONDS),
        "-hls_list_size", "0",
        "-hls_flags", "append_list",
        "-hls_segment_filename", segment_pattern,
        ffmpeg_playlist_path
    ]

    print(f"[TubeRepair] Starting HLS live-slicing for: {video_id}")
    log_path = os.path.join(cache_dir, "ffmpeg.log")
    try:
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=log_file,
            text=True
        )
    except Exception as e:
        print(f"[TubeRepair] Failed to launch ffmpeg for {video_id}: {e}")
        return None

    with HLS_SESSIONS_LOCK:
        HLS_SESSIONS[video_id] = {
            "process": proc,
            "dir": cache_dir,
            "last_access": time.time(),
            "playlist": os.path.basename(served_playlist_path),
            "log_file": log_file,
            "log_path": log_path,
        }

    # Wait for the first segment to appear so we don't redirect the client
    # to a playlist that isn't playable yet.
    deadline = time.time() + HLS_FIRST_SEGMENT_TIMEOUT
    while time.time() < deadline:
        if proc.poll() is not None:
            print(f"[TubeRepair] ffmpeg exited early for {video_id} (code {proc.returncode})")
            _print_log_tail(log_path)
            with HLS_SESSIONS_LOCK:
                HLS_SESSIONS.pop(video_id, None)
            log_file.close()
            shutil.rmtree(cache_dir, ignore_errors=True)
            return None
        if glob.glob(os.path.join(cache_dir, "*.ts")):
            return os.path.basename(served_playlist_path)
        time.sleep(0.3)

    # Timed out waiting — kill this attempt rather than leaving a zombie process.
    print(f"[TubeRepair] Timed out waiting for first HLS segment: {video_id}")
    _print_log_tail(log_path)
    with HLS_SESSIONS_LOCK:
        session = HLS_SESSIONS.pop(video_id, None)
    if session:
        _remove_hls_session(video_id, session)
    return None


def hls_session_dir(video_id):
    with HLS_SESSIONS_LOCK:
        session = HLS_SESSIONS.get(video_id)
        return session["dir"] if session else None


def clear_all_hls_sessions():
    """Called on server shutdown alongside clear_video_cache()."""
    with HLS_SESSIONS_LOCK:
        sessions = dict(HLS_SESSIONS)
        HLS_SESSIONS.clear()
    for vid, session in sessions.items():
        _remove_hls_session(vid, session)
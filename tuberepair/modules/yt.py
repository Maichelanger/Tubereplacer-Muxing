import requests_cache, re, config
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
    # Set up a local folder for the high-res MP4 files
    cache_dir = os.path.join(os.getcwd(), "cache_videos")
    os.makedirs(cache_dir, exist_ok=True)
    output_file = os.path.join(cache_dir, f"{video_id}.mp4")
    
    # If the video was already downloaded previously, serve it instantly
    if os.path.exists(output_file):
        print(f"[TubeRepair] Serving cached file for: {video_id}")
        return output_file

    print(f"[TubeRepair] Downloading & Muxing 720p H.264 for: {video_id}")
    
    # Run yt-dlp to download and properly structure the container for iOS
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/best[height<=720][vcodec^=avc1]",
        "--merge-output-format", "mp4",
        "--postprocessor-args", "muxer:-movflags +faststart",
        "-o", output_file,
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    
    try:
        # Running without pipe capture lets you monitor download progress directly in PowerShell
        subprocess.run(cmd, check=True)
        if os.path.exists(output_file):
            return output_file
    except Exception as e:
        print(f"[TubeRepair] yt-dlp download failed: {e}")
    return None
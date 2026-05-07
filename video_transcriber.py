# -*- coding: utf-8 -*-
"""
视频音频转录模块
用于处理无字幕视频：下载音频 -> 本地ASR转录 -> 生成SRT
"""

import os
import sys
import time
import re
import subprocess
import tempfile
from pathlib import Path
import requests
import yt_dlp

# Keep local ASR stable when multiple numeric runtimes are present in the same environment.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from faster_whisper import WhisperModel
from modelscope.hub.snapshot_download import snapshot_download

# 添加NVIDIA库路径到环境变量
def add_nvidia_paths():
    """添加NVIDIA CUDA/cuDNN库路径到PATH环境变量"""
    # 如果是PyInstaller打包环境
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
        
        # 尝试多种可能的路径结构
        possible_paths = [
            os.path.join(base_dir, 'nvidia', 'cublas', 'bin'),
            os.path.join(base_dir, 'nvidia', 'cudnn', 'bin'),
            os.path.join(base_dir, 'nvidia', 'cublas_cu12', 'bin'), # 某些版本的包名不同
            os.path.join(base_dir, 'nvidia', 'cudnn_cu12', 'bin'),
            os.path.join(base_dir, 'bin'), # 可能被放在根目录bin下
            base_dir, # 可能直接在根目录
        ]
        
        # 递归搜索cublas64_*.dll所在的目录
        found_paths = set()
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.startswith("cublas64_") and file.endswith(".dll"):
                    found_paths.add(root)
                if file.startswith("cudnn64_") and file.endswith(".dll"):
                    found_paths.add(root)
                    
        # 合并路径
        all_paths = list(found_paths) + possible_paths
        
        for path in all_paths:
            if os.path.exists(path):
                try:
                    os.add_dll_directory(path)
                    os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
                    print(f"已添加NVIDIA库路径(Frozen): {path}")
                except Exception as e:
                    pass # 忽略错误，继续尝试
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, '.venv')
    
    # 如果是在虚拟环境中运行
    if sys.prefix != sys.base_prefix:
        venv_site_packages = os.path.join(sys.prefix, 'Lib', 'site-packages')
    else:
        # 尝试猜测虚拟环境路径
        venv_site_packages = os.path.join(venv_dir, 'Lib', 'site-packages')
    
    nvidia_paths = [
        os.path.join(venv_site_packages, 'nvidia', 'cublas', 'bin'),
        os.path.join(venv_site_packages, 'nvidia', 'cudnn', 'bin'),
    ]
    
    for path in nvidia_paths:
        if os.path.exists(path):
            os.add_dll_directory(path)
            os.environ['PATH'] = path + os.pathsep + os.environ['PATH']
            print(f"已添加NVIDIA库路径: {path}")

# 在导入faster_whisper之前添加路径
try:
    add_nvidia_paths()
except Exception as e:
    print(f"警告: 添加NVIDIA库路径失败: {e}")

def _resolve_ffmpeg_executable(ffmpeg_path=None):
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        abs_path = os.path.abspath(ffmpeg_path)
        if os.path.isdir(abs_path):
            for candidate in (
                os.path.join(abs_path, "ffmpeg.exe"),
                os.path.join(abs_path, "bin", "ffmpeg.exe"),
                os.path.join(abs_path, "ffmpeg"),
                os.path.join(abs_path, "bin", "ffmpeg"),
            ):
                if os.path.exists(candidate):
                    return candidate
        return abs_path
    return "ffmpeg"


def _write_netscape_cookie_file(cookies):
    if not cookies:
        return None
    pairs = []
    for key in ("SESSDATA", "bili_jct", "buvid3"):
        value = cookies.get(key)
        if value:
            pairs.append((key, value))
    if not pairs:
        return None
    fd, cookie_path = tempfile.mkstemp(prefix="bilibili-", suffix=".cookies.txt")
    os.close(fd)
    with open(cookie_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for key, value in pairs:
            f.write(f".bilibili.com\tTRUE\t/\tFALSE\t0\t{key}\t{value}\n")
    return cookie_path


def _extract_bvid(video_url):
    match = re.search(r"BV[a-zA-Z0-9]+", video_url or "")
    return match.group(0) if match else None


def _download_audio_via_bilibili_api(video_url, output_path, ffmpeg_path=None, cookies=None, headers=None, bvid=None, cid=None):
    bvid = bvid or _extract_bvid(video_url)
    if not bvid or not cid:
        print("B站API音频兜底失败: 缺少 bvid 或 cid")
        return False

    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        request_headers.update({key: value for key, value in headers.items() if value})

    try:
        response = requests.get(
            "https://api.bilibili.com/x/player/playurl",
            params={"bvid": bvid, "cid": cid, "qn": 0, "fnval": 16, "fourk": 1},
            headers=request_headers,
            cookies=cookies or {},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            print(f"B站API音频兜底失败: {data.get('message')}")
            return False

        audios = (((data.get("data") or {}).get("dash") or {}).get("audio") or [])
        if not audios:
            print("B站API音频兜底失败: 未找到音频流")
            return False

        audio = max(audios, key=lambda item: item.get("bandwidth") or 0)
        audio_urls = [audio.get("baseUrl") or audio.get("base_url")]
        audio_urls.extend(audio.get("backupUrl") or audio.get("backup_url") or [])
        audio_urls = [url for url in audio_urls if url]

        temp_audio = None
        for audio_url in audio_urls:
            try:
                fd, temp_audio = tempfile.mkstemp(prefix="bilibili-audio-", suffix=".m4s")
                os.close(fd)
                stream_headers = dict(request_headers)
                stream_headers["Referer"] = f"https://www.bilibili.com/video/{bvid}/"
                with requests.get(audio_url, headers=stream_headers, cookies=cookies or {}, stream=True, timeout=30) as stream:
                    stream.raise_for_status()
                    with open(temp_audio, "wb") as f:
                        for chunk in stream.iter_content(chunk_size=1024 * 256):
                            if chunk:
                                f.write(chunk)
                if os.path.getsize(temp_audio) > 0:
                    break
            except Exception as stream_error:
                print(f"B站音频直链下载失败，尝试备用链接: {stream_error}")
                if temp_audio and os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except OSError:
                        pass
                temp_audio = None

        if not temp_audio or not os.path.exists(temp_audio):
            print("B站API音频兜底失败: 音频直链全部下载失败")
            return False

        expected_path = str(Path(output_path).with_suffix(".mp3"))
        result = subprocess.run(
            [
                _resolve_ffmpeg_executable(ffmpeg_path),
                "-y",
                "-i",
                temp_audio,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-b:a",
                "192k",
                expected_path,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            os.remove(temp_audio)
        except OSError:
            pass

        if result.returncode != 0:
            print(f"FFmpeg转换音频失败: {result.stderr[-1000:]}")
            return False

        if os.path.exists(expected_path) and os.path.getsize(expected_path) > 0:
            if output_path != expected_path:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(expected_path, output_path)
            print("B站API音频兜底下载成功")
            return True

        print("B站API音频兜底失败: 未生成有效mp3文件")
        return False
    except Exception as e:
        print(f"B站API音频兜底失败: {e}")
        return False


def _download_audio_yt_dlp_legacy(video_url, output_path, ffmpeg_path=None, cookies=None, headers=None, bvid=None, cid=None):
    """
    使用yt-dlp下载视频的音频部分
    
    Args:
        video_url: 视频URL
        output_path: 输出音频文件路径 (例如 audio.mp3)
        ffmpeg_path: FFmpeg可执行文件路径（可选，为空时使用系统PATH中的ffmpeg）
    
    Returns:
        bool: 是否成功
    """
    print(f"正在下载音频: {video_url}")
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 配置yt-dlp
    # 使用bestaudio/best确保下载最佳音质
    # 转换为mp3以确保兼容性
    # 强制覆盖已存在的文件，防止并发下载时因为文件已存在而跳过处理导致后续逻辑错误
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(Path(output_path).with_suffix('')), # yt-dlp会自动添加后缀
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': False,  # 开启警告以便调试
        'overwrites': True,    # 强制覆盖
        'force_overwrites': True, # 双重保险（部分版本可能使用这个）
        'playlist_items': '1', # 强制只下载列表中的第一项（防止对于某些URL，yt-dlp尝试下载整个列表）
        # B站特定配置，防止403
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    }
    if headers:
        ydl_opts['http_headers'].update({key: value for key, value in headers.items() if value})
    
    # 如果指定了ffmpeg路径，添加到配置中
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"使用自定义FFmpeg路径: {os.path.abspath(ffmpeg_path)}")
        ydl_opts['ffmpeg_location'] = os.path.abspath(ffmpeg_path)

    cookie_file = _write_netscape_cookie_file(cookies)
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # 检查文件是否生成（yt-dlp可能会添加后缀）
        expected_path = str(Path(output_path).with_suffix('.mp3'))
        if os.path.exists(expected_path):
            # 如果用户指定的output_path不是.mp3结尾，重命名
            if output_path != expected_path:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(expected_path, output_path)
            return True
        
        return False
    except Exception as e:
        print(f"音频下载失败: {e}")
        return False

def download_audio(video_url, output_path, ffmpeg_path=None, cookies=None, headers=None, bvid=None, cid=None):
    """
    使用 yt-dlp 下载视频音频；如果页面入口下载失败，则用 B 站播放地址 API 兜底。
    """
    print(f"正在下载音频: {video_url}")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(Path(output_path).with_suffix('')),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': False,
        'overwrites': True,
        'force_overwrites': True,
        'playlist_items': '1',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    }
    if headers:
        ydl_opts['http_headers'].update({key: value for key, value in headers.items() if value})

    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"使用自定义FFmpeg路径: {os.path.abspath(ffmpeg_path)}")
        ydl_opts['ffmpeg_location'] = os.path.abspath(ffmpeg_path)

    cookie_file = _write_netscape_cookie_file(cookies)
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        expected_path = str(Path(output_path).with_suffix('.mp3'))
        if os.path.exists(expected_path):
            if output_path != expected_path:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(expected_path, output_path)
            return True

        print("yt-dlp未生成音频文件，尝试使用B站播放地址API兜底下载音频...")
        return _download_audio_via_bilibili_api(
            video_url,
            output_path,
            ffmpeg_path=ffmpeg_path,
            cookies=cookies,
            headers=headers,
            bvid=bvid,
            cid=cid,
        )
    except Exception as e:
        print(f"音频下载失败: {e}")
        print("尝试使用B站播放地址API兜底下载音频...")
        return _download_audio_via_bilibili_api(
            video_url,
            output_path,
            ffmpeg_path=ffmpeg_path,
            cookies=cookies,
            headers=headers,
            bvid=bvid,
            cid=cid,
        )
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
            except OSError:
                pass


def get_model_path(model_size="small", models_dir="models"):
    """
    获取模型路径，如果不存在则从国内镜像下载
    
    Args:
        model_size: 模型大小 (tiny, base, small, medium, large-v3)
        models_dir: 模型保存目录
        
    Returns:
        str: 模型路径
    """
    # 确定基础目录
    if getattr(sys, 'frozen', False):
        # 如果是打包后的环境，模型应该保存在EXE所在目录的models文件夹中
        # 而不是临时解压目录 _MEIPASS
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    models_dir = os.path.join(base_dir, models_dir)
    os.makedirs(models_dir, exist_ok=True)
    
    # 检查模型是否已存在 (faster-whisper下载的模型通常在 output_dir 下直接是文件，或者在子目录)
    # 使用ModelScope下载
    
    print(f"检查Whisper模型 ({model_size})...")
    
    # ModelScope模型映射
    # 用户指定: pengzhendong/faster-whisper-small
    model_id_map = {
        "tiny": "pengzhendong/faster-whisper-tiny",
        "base": "pengzhendong/faster-whisper-base",
        "small": "pengzhendong/faster-whisper-small",
        "medium": "pengzhendong/faster-whisper-medium",
        "large-v3": "pengzhendong/faster-whisper-large-v3",
    }
    
    model_id = model_id_map.get(model_size, f"pengzhendong/faster-whisper-{model_size}")
    
    try:
        print(f"正在从ModelScope下载模型: {model_id} ...")
        # snapshot_download 会自动处理缓存和下载，返回模型目录路径
        model_path = snapshot_download(model_id, cache_dir=models_dir)
        print(f"模型准备就绪: {model_path}")
        return model_path
    except Exception as e:
        print(f"模型下载失败: {e}")
        return None

def format_timestamp(seconds):
    """将秒数转换为SRT时间戳格式 (00:00:00,000)"""
    whole_seconds = int(seconds)
    milliseconds = int((seconds - whole_seconds) * 1000)
    
    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    seconds = whole_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def transcribe_to_srt(audio_path, srt_path, model_size="small", device="auto", compute_type="float16"):
    """
    将音频转录为SRT字幕
    
    Args:
        audio_path: 音频文件路径
        srt_path: 输出SRT文件路径
        model_size: 模型大小
        device: 运行设备 (cuda/cpu/auto)
        compute_type: 计算类型 (float16/int8/float32)
        
    Returns:
        bool: 是否成功
    """
    print(f"开始转录音频: {audio_path}")
    
    try:
        model_path = get_model_path(model_size)
        if not model_path:
            print("无法加载模型，转录终止")
            return False
            
        # 自动检测设备
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    print("检测到CUDA设备，将使用GPU加速")
                else:
                    device = "cpu"
                    print("未检测到CUDA设备，将使用CPU运行")
            except ImportError:
                device = "cpu"
                print("未检测到PyTorch，将使用CPU运行")
                
        # 根据设备调整compute_type
        if device == "cpu" and compute_type == "float16":
            print("CPU模式下不支持float16，自动切换为int8")
            compute_type = "int8"
            
        print(f"加载模型中 (Device: {device}, Compute Type: {compute_type})...")
        model = WhisperModel(model_path, device=device, compute_type=compute_type)

        print("正在转录...")
        segments, info = model.transcribe(audio_path, beam_size=5, language="zh")
        
        print(f"检测到语言: {info.language} (置信度: {info.language_probability:.2f})")
        
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, 1):
                start = format_timestamp(segment.start)
                end = format_timestamp(segment.end)
                text = segment.text.strip()
                
                # 写入SRT格式
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{text}\n\n")
                
                # 简单的进度显示
                if i % 10 == 0:
                    print(f"\r已生成 {i} 条字幕...", end="")
        
        print(f"\n转录完成! 字幕已保存至: {srt_path}")

        sys.stdout.flush()
        # 显式释放模型资源，防止退出时崩溃
        try:
            del model
            import gc
            gc.collect()
        except Exception as e:
            print(f"释放模型资源时出错 (非致命): {e}")
            
        return True
        
    except Exception as e:
        print(f"转录过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="视频音频转录工具")
    parser.add_argument("audio_path", help="音频文件路径")
    parser.add_argument("srt_path", help="输出SRT文件路径")
    parser.add_argument("--model_size", default="small", help="模型大小")
    parser.add_argument("--device", default="auto", help="运行设备")
    parser.add_argument("--compute_type", default="float16", help="计算类型")
    
    args = parser.parse_args()
    
    success = transcribe_to_srt(
        args.audio_path,
        args.srt_path,
        model_size=args.model_size,
        device=args.device,
        compute_type=args.compute_type
    )
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

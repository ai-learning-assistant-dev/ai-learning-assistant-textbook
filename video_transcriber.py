# -*- coding: utf-8 -*-
"""
视频音频转录模块
用于处理无字幕视频：下载音频 -> 本地ASR转录 -> 生成SRT
"""

import os
import sys
import time
from pathlib import Path
import yt_dlp
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

def download_audio(video_url, output_path, ffmpeg_path=None):
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
            'Referer': 'https://www.bilibili.com',
        }
    }
    
    # 如果指定了ffmpeg路径，添加到配置中
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        print(f"使用自定义FFmpeg路径: {os.path.abspath(ffmpeg_path)}")
        ydl_opts['ffmpeg_location'] = os.path.abspath(ffmpeg_path)
    
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

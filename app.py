#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili视频字幕下载与总结 - Web服务
"""

import os
import sys
import json
import uuid
import time
import threading
import shutil
from pathlib import Path
from datetime import datetime
from queue import Queue
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from process_generated_content import save_data_to_excel
from bilibili_subtitle_downloader import BilibiliSubtitleDownloader, load_cookies_from_file
from process_video_info import sanitize_filename
from subtitle_summarizer import SRTParser, SubtitleSummarizer, load_llm_config
from llm_client import OpenAICompatClient

# 确定模板目录
if getattr(sys, 'frozen', False):
    # 如果是PyInstaller打包环境
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False  # 支持中文JSON

# 全局变量存储任务状态
tasks = {}
tasks_lock = threading.Lock()

# 任务队列：用于限制并发数量
task_queue = Queue()
# 最大并发任务数（可以根据API限制调整）
MAX_CONCURRENT_TASKS = 2  # 默认同时最多处理2个视频
# 工作线程启动标志
worker_threads_started = False
worker_threads_lock = threading.Lock()


class TaskStatus:
    """任务状态类"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPING = "stopping"  # 正在停止中
    STOPPED = "stopped"    # 已停止


def load_models():
    """加载模型配置"""
    config_file = 'config/llm_models.json'
    if not os.path.exists(config_file):
        return []
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
        return config.get('models', [])


def save_models(models):
    """保存模型配置"""
    config_file = 'config/llm_models.json'
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({'models': models}, f, ensure_ascii=False, indent=2)


def load_app_config():
    """加载应用配置"""
    config_file = 'config/app_config.json'
    
    # 默认配置
    default_config = {
        'output_directory': 'subtitles',
        'last_selected_model': '',
        'cookies_file': 'cookies.txt',
        'auto_refresh_interval': 2000,
        'web_port': 5000,
        'download_all_parts': False,  # 默认关闭：只下载URL指定的视频，不下载所有分P
        'max_concurrent_tasks': 2  # 最大并发任务数：默认同时处理2个视频（避免API并发过高）
    }
    
    if not os.path.exists(config_file):
        # 如果配置文件不存在，创建默认配置
        save_app_config(default_config)
        return default_config
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 合并默认配置，确保所有字段都存在
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        print(f"加载配置失败: {e}，使用默认配置")
        return default_config


def save_app_config(config):
    """保存应用配置"""
    config_file = 'config/app_config.json'
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_workspaces():
    """加载工作区配置"""
    config_file = 'config/workspace.json'
    if not os.path.exists(config_file):
        return []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('workspaces', [])
    except Exception as e:
        print(f"加载工作区配置失败: {e}")
        return []


def save_workspaces(workspaces):
    """保存工作区配置"""
    config_file = 'config/workspace.json'
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump({'workspaces': workspaces}, f, ensure_ascii=False, indent=2)


def start_worker_threads():
    """启动工作线程池（确保只启动一次）"""
    global worker_threads_started
    
    with worker_threads_lock:
        if worker_threads_started:
            return
        
        # 加载配置获取并发数
        config = load_app_config()
        max_concurrent = config.get('max_concurrent_tasks', MAX_CONCURRENT_TASKS)
        
        print(f"🚀 正在启动 {max_concurrent} 个工作线程...")
        for i in range(max_concurrent):
            worker = threading.Thread(target=task_queue_worker, daemon=True, name=f"Worker-{i+1}")
            worker.start()
        
        worker_threads_started = True
        print(f"✅ 工作线程池已启动（{max_concurrent} 个线程）")


def task_queue_worker():
    """任务队列工作线程：从队列中取任务并执行"""
    thread_name = threading.current_thread().name
    print(f"[{thread_name}] 工作线程已启动，等待任务...")
    
    while True:
        try:
            # 从队列中获取任务
            task_data = task_queue.get()
            if task_data is None:  # None 是停止信号
                print(f"[{thread_name}] 收到停止信号，退出")
                break
            
            task_id = task_data['task_id']
            url = task_data['url']
            output_dir = task_data['output_dir']
            model_name = task_data['model_name']
            cookies_file = task_data['cookies_file']
            custom_folder_name = task_data.get('custom_folder_name')
            download_all_parts = task_data.get('download_all_parts', False)
            generate_options = task_data.get('generate_options')
            
            print(f"[{thread_name}] 开始处理任务 {task_id}: {url}")
            
            # 执行任务
            process_video_task(task_id, thread_name, url, output_dir, model_name, cookies_file, custom_folder_name, download_all_parts, generate_options)
            
            print(f"[{thread_name}] 任务 {task_id} 处理完成")
            
            # 任务完成后等待一小段时间再处理下一个（避免触发反爬虫）
            time.sleep(2)
            
        except Exception as e:
            print(f"[{thread_name}] 任务队列工作线程错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 标记任务完成
            task_queue.task_done()


def process_video_task(task_id, thread_name, url, output_dir, model_name, cookies_file, custom_folder_name=None, download_all_parts=False, generate_options=None):
    """处理单个视频的下载和总结任务"""
    if generate_options is None:
        generate_options = {
            'summary': True,
            'full_content': True,
            'exercises': True,
            'questions': True
        }
    try:
        # 检查停止标志
        with tasks_lock:
            if tasks[task_id].get('stop_flag'):
                tasks[task_id]['status'] = TaskStatus.STOPPED
                tasks[task_id]['message'] = '任务已停止'
                return
        
        # 更新状态：下载中
        with tasks_lock:
            tasks[task_id]['status'] = TaskStatus.DOWNLOADING
            tasks[task_id]['message'] = f'正在下载字幕: {url}'
        
        # 加载Cookie
        config_cookies = load_cookies_from_file(cookies_file)
        sessdata = config_cookies.get('sessdata')
        
        # 创建下载器
        downloader = BilibiliSubtitleDownloader(
            sessdata=sessdata,
            bili_jct=config_cookies.get('bili_jct'),
            buvid3=config_cookies.get('buvid3'),
            debug=False
        )
        
        # 下载字幕和封面
        download_result = downloader.download(
            video_url=url,
            video_index=thread_name,
            output_dir=output_dir,
            format_type='srt',
            download_cover=True,
            custom_folder_name=custom_folder_name,
            download_all_parts=download_all_parts
        )
        
        # 获取下载结果
        downloaded_files = download_result.get('subtitles', [])
        cover_path = download_result.get('cover')
        video_title = download_result.get('title', '')
        video_dir = download_result.get('video_dir', output_dir)
        
        # 检查是否成功下载了字幕
        if not downloaded_files:
            raise Exception('此视频没有字幕，无法进行总结')
        
        # 检查停止标志
        with tasks_lock:
            if tasks[task_id].get('stop_flag'):
                tasks[task_id]['status'] = TaskStatus.STOPPED
                tasks[task_id]['message'] = '任务已停止'
                return
        
        # 更新任务基本信息
        with tasks_lock:
            tasks[task_id]['video_dir'] = video_dir
            tasks[task_id]['video_title'] = video_title
        
        # 加载LLM配置
        llm_config_file = 'config/llm_models.json'
        model_config = load_llm_config(llm_config_file, model_name=model_name)
        
        # 创建LLM客户端
        llm_client = OpenAICompatClient(
            api_base=model_config['api_base'],
            api_key=model_config['api_key'],
            default_model=model_config['model_name'],
            request_timeout=500
        )
        
        # 创建总结器
        summarizer = SubtitleSummarizer(llm_client)
        
        # 存储所有生成的文件
        all_generated_files = []
        
        # 遍历所有下载的中文字幕文件
        total_files = len(downloaded_files)
        for file_index, subtitle_file in enumerate(downloaded_files, 1):
            # 检查停止标志
            with tasks_lock:
                if tasks[task_id].get('stop_flag'):
                    tasks[task_id]['status'] = TaskStatus.STOPPED
                    tasks[task_id]['message'] = '任务已停止'
                    return
            
            # 从字幕文件名中提取标题
            subtitle_filename = os.path.basename(subtitle_file)
            subtitle_name = os.path.splitext(subtitle_filename)[0]
            subtitle_title = subtitle_name.rsplit('_', 1)[0] if '_' in subtitle_name else subtitle_name
            
            # 定义所有可能生成的文件路径
            summary_json_file = os.path.join(video_dir, f'{subtitle_title}_summary.json')
            # markdown_dir = os.path.join(video_dir, 'markdown')
            # full_content_file = os.path.join(markdown_dir, f'{subtitle_title}.md')
            # 根据用户需求，Markdown文件应直接存放在video_dir下
            full_content_file = os.path.join(video_dir, f'{subtitle_title}.md')
            exercises_file = os.path.join(video_dir, f'{subtitle_title}_exercises.json')
            questions_file = os.path.join(video_dir, f'{subtitle_title}_questions.json')
            
            # 解析字幕（提前解析，供后续步骤使用）
            subtitles = None
            subtitle_text = None
            plain_text = None
            
            # ========== 1. 生成要点总结 ==========
            if generate_options.get('summary', True):
                if os.path.exists(summary_json_file):
                    with tasks_lock:
                        tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (1/4): 要点总结已存在，跳过'
                else:
                    with tasks_lock:
                        tasks[task_id]['status'] = TaskStatus.SUMMARIZING
                        tasks[task_id]['message'] = f'正在处理字幕 {file_index}/{total_files}: {subtitle_title} (1/4): 要点总结...'
                        tasks[task_id]['subtitle_file'] = subtitle_file
                    
                    # 解析字幕
                    if subtitles is None:
                        subtitles = SRTParser.parse_srt_file(subtitle_file)
                        subtitle_text = SRTParser.format_subtitles_for_llm(subtitles)
                    
                    summary = summarizer.summarize(subtitle_text, stream=False)
                    
                    with open(summary_json_file, 'w', encoding='utf-8') as f:
                        json.dump(summary, f, ensure_ascii=False, indent=2)
            else:
                with tasks_lock:
                     tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (1/4): 要点总结 (用户选择跳过)'
            
            # 检查停止标志
            with tasks_lock:
                if tasks[task_id].get('stop_flag'):
                    tasks[task_id]['status'] = TaskStatus.STOPPED
                    tasks[task_id]['message'] = '任务已停止'
                    return
            
            # ========== 2. 生成完整内容文档 ==========
            if generate_options.get('full_content', True):
                if os.path.exists(full_content_file):
                    with tasks_lock:
                        tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (2/4): 完整文档已存在，跳过'
                else:
                    with tasks_lock:
                        tasks[task_id]['message'] = f'正在处理字幕 {file_index}/{total_files}: {subtitle_title} (2/4): 完整文档...'
                    
                    # 预处理字幕文本
                    if plain_text is None:
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    full_content = summarizer.generate_full_content(
                        plain_text,
                        video_title=video_title,
                        stream=False
                    )
                    
                    # 创建markdown子目录（如果不存在）
                    # os.makedirs(markdown_dir, exist_ok=True)
                    
                    with open(full_content_file, 'w', encoding='utf-8') as f:
                        f.write(full_content)
            else:
                with tasks_lock:
                     tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (2/4): 完整文档 (用户选择跳过)'
            
            # 检查停止标志
            with tasks_lock:
                if tasks[task_id].get('stop_flag'):
                    tasks[task_id]['status'] = TaskStatus.STOPPED
                    tasks[task_id]['message'] = '任务已停止'
                    return
            
            # ========== 3. 生成练习题 ==========
            if generate_options.get('exercises', True):
                if os.path.exists(exercises_file):
                    with tasks_lock:
                        tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (3/4): 练习题已存在，跳过'
                else:
                    with tasks_lock:
                        tasks[task_id]['message'] = f'正在处理字幕 {file_index}/{total_files}: {subtitle_title} (3/4): 练习题...'
                    
                    # 预处理字幕文本（如果还没有）
                    if plain_text is None:
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    exercises = summarizer.generate_exercises(
                        plain_text,
                        video_title=video_title,
                        stream=False
                    )
                    
                    with open(exercises_file, 'w', encoding='utf-8') as f:
                        json.dump(exercises, f, ensure_ascii=False, indent=2)
            else:
                with tasks_lock:
                     tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (3/4): 练习题 (用户选择跳过)'
            
            # 检查停止标志
            with tasks_lock:
                if tasks[task_id].get('stop_flag'):
                    tasks[task_id]['status'] = TaskStatus.STOPPED
                    tasks[task_id]['message'] = '任务已停止'
                    return
            
            # ========== 4. 生成预设问题 ==========
            if generate_options.get('questions', True):
                if os.path.exists(questions_file):
                    with tasks_lock:
                        tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (4/4): 预设问题已存在，跳过'
                else:
                    with tasks_lock:
                        tasks[task_id]['message'] = f'正在处理字幕 {file_index}/{total_files}: {subtitle_title} (4/4): 预设问题...'
                    
                    # 预处理字幕文本（如果还没有）
                    if plain_text is None:
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    preset_questions = summarizer.generate_preset_questions(
                        plain_text,
                        video_title=video_title,
                        stream=False
                    )
                    
                    with open(questions_file, 'w', encoding='utf-8') as f:
                        json.dump(preset_questions, f, ensure_ascii=False, indent=2)
            else:
                with tasks_lock:
                     tasks[task_id]['message'] = f'处理字幕 {file_index}/{total_files}: {subtitle_title} (4/4): 预设问题 (用户选择跳过)'
            
            # 记录本字幕生成的所有文件
            all_generated_files.append({
                'subtitle_title': subtitle_title,
                'subtitle_file': subtitle_file,
                'summary_json': summary_json_file,
                'content_md': full_content_file,
                'exercises': exercises_file,
                'questions': questions_file
            })
        # 5. 将生成的数据写入 Excel
        with tasks_lock:
            tasks[task_id]['message'] = f'正在写入Excel: {video_title}...'
        
        # video_dir 指向 .../data 目录，Excel 文件实际上在上一级目录
        # 正确的逻辑应该是去找父目录下的 .xlsx 文件
        parent_dir = os.path.dirname(video_dir)
        # 尝试几种可能的命名方式
        possible_names = [
            f"{os.path.basename(parent_dir)}.xlsx",
            f"{sanitize_filename(video_title)}.xlsx"
        ]
        
        excel_found = False
        for name in possible_names:
            excel_path = os.path.join(parent_dir, name)
            if os.path.exists(excel_path):
                save_data_to_excel(excel_path)
                excel_found = True
                break
        
        if not excel_found:
            print(f"警告: Excel 文件未找到，尝试了: {possible_names}")
            # 如果没找到，尝试在 video_dir (即 data 目录) 下找找看，虽然这不应该发生
            excel_path_fallback = os.path.join(video_dir, f"{os.path.basename(video_dir)}.xlsx")
            if os.path.exists(excel_path_fallback):
                 save_data_to_excel(excel_path_fallback)
            else:
                 with tasks_lock:
                     tasks[task_id]['message'] += ' (Excel写入失败: 文件未找到)'

        # 更新任务状态为完成
        with tasks_lock:
            tasks[task_id]['status'] = TaskStatus.COMPLETED
            tasks[task_id]['message'] = f'全部完成！已处理 {total_files} 个字幕文件，生成了字幕、封面、总结、完整文档、练习题和预设问题'
            tasks[task_id]['files'] = {
                'video_dir': video_dir,
                'cover': cover_path,
                'generated_files': all_generated_files
            }
            tasks[task_id]['completed_at'] = datetime.now().isoformat()
        
    except Exception as e:
        # 更新状态：失败
        with tasks_lock:
            tasks[task_id]['status'] = TaskStatus.FAILED
            tasks[task_id]['message'] = f'错误: {str(e)}'
            tasks[task_id]['error'] = str(e)




# ==================== Web路由 ====================

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/models', methods=['GET'])
def get_models():
    """获取模型列表"""
    try:
        models = load_models()
        return jsonify({
            'success': True,
            'models': models
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/models', methods=['POST'])
def add_model():
    """添加模型"""
    try:
        data = request.json
        
        # 生成唯一ID
        model_id = datetime.now().strftime('%Y%m%d%H%M%S%f')
        
        new_model = {
            'id': model_id,
            'name': data.get('name'),
            'model_name': data.get('model_name'),
            'api_base': data.get('api_base'),
            'api_key': data.get('api_key')
        }
        
        models = load_models()
        models.append(new_model)
        save_models(models)
        
        return jsonify({
            'success': True,
            'model': new_model
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/models/<model_id>', methods=['PUT'])
def update_model(model_id):
    """更新模型"""
    try:
        data = request.json
        models = load_models()
        
        for model in models:
            if model['id'] == model_id:
                model['name'] = data.get('name', model['name'])
                model['model_name'] = data.get('model_name', model['model_name'])
                model['api_base'] = data.get('api_base', model['api_base'])
                model['api_key'] = data.get('api_key', model['api_key'])
                break
        
        save_models(models)
        
        return jsonify({
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    """删除模型"""
    try:
        models = load_models()
        models = [m for m in models if m['id'] != model_id]
        save_models(models)
        
        return jsonify({
            'success': True
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/workspace', methods=['POST'])
def create_workspace():
    """创建工作区"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        path = data.get('path', '').strip()
        
        if not name:
            return jsonify({
                'success': False,
                'error': '工作区名称不能为空'
            }), 400
        
        if not path:
            return jsonify({
                'success': False,
                'error': '工作区路径不能为空'
            }), 400
        
        # 加载现有工作区
        workspaces = load_workspaces()
        
        # 检查名称是否重复
        for ws in workspaces:
            if ws.get('name') == name:
                return jsonify({
                    'success': False,
                    'error': f'工作区名称 "{name}" 已存在'
                }), 400
        
        # 构建完整路径
        full_path = os.path.abspath(path)
        
        # 检查路径是否已存在
        if os.path.exists(full_path):
            return jsonify({
                'success': False,
                'error': f'路径 "{path}" 已存在'
            }), 400
        
        # 创建文件夹
        try:
            os.makedirs(full_path, exist_ok=False)
        except OSError as e:
            return jsonify({
                'success': False,
                'error': f'创建文件夹失败: {str(e)}'
            }), 500
        
        # 添加新工作区
        new_workspace = {
            'name': name,
            'path': path,
            'created_at': datetime.now().isoformat()
        }
        workspaces.append(new_workspace)
        
        # 保存到文件
        save_workspaces(workspaces)
        
        return jsonify({
            'success': True,
            'workspace': new_workspace,
            'full_path': full_path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/workspace', methods=['GET'])
def list_workspaces():
    """获取所有工作区列表"""
    try:
        workspaces = load_workspaces()
        return jsonify({
            'success': True,
            'workspaces': workspaces
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/workspace/<workspace_name>', methods=['DELETE'])
def delete_workspace(workspace_name):
    """删除工作区"""
    try:
        # 加载现有工作区
        workspaces = load_workspaces()
        
        # 查找要删除的工作区
        target_workspace = None
        for ws in workspaces:
            if ws.get('name') == workspace_name:
                target_workspace = ws
                break
        
        if not target_workspace:
            return jsonify({
                'success': False,
                'error': f'工作区 "{workspace_name}" 不存在'
            }), 404
        
        # 获取工作区路径
        workspace_path = target_workspace.get('path')
        full_path = os.path.abspath(workspace_path)
        
        # 删除文件夹（如果存在）
        if os.path.exists(full_path):
            try:
                shutil.rmtree(full_path)
            except OSError as e:
                return jsonify({
                    'success': False,
                    'error': f'删除文件夹失败: {str(e)}'
                }), 500
        
        # 从列表中删除工作区
        workspaces = [ws for ws in workspaces if ws.get('name') != workspace_name]
        
        # 保存到文件
        save_workspaces(workspaces)
        
        return jsonify({
            'success': True,
            'message': f'工作区 "{workspace_name}" 已删除',
            'deleted_path': full_path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tasks', methods=['POST'])
def create_tasks():
    """创建批量任务"""
    try:
        # 确保工作线程已启动
        start_worker_threads()
        
        data = request.json
        urls = data.get('urls', [])
        output_dir = data.get('output_dir', 'subtitles')
        model_name = data.get('model_name')
        cookies_file = data.get('cookies_file', 'cookies.txt')
        custom_folder_name = data.get('custom_folder_name', '').strip() or None
        download_all_parts = data.get('download_all_parts', False)
        generate_options = data.get('generate_options', {
            'summary': True,
            'full_content': True,
            'exercises': True,
            'questions': True
        })
        
        if not urls:
            return jsonify({
                'success': False,
                'error': '请提供至少一个URL'
            }), 400
        
        if not model_name:
            return jsonify({
                'success': False,
                'error': '请选择模型'
            }), 400
        
        # 保存配置：最后使用的输出目录和模型
        config = load_app_config()
        config['output_directory'] = output_dir
        config['last_selected_model'] = model_name
        save_app_config(config)
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载Cookie用于检测收藏夹
        config_cookies = load_cookies_from_file(cookies_file)
        
        # 处理URL列表，展开收藏夹URL
        expanded_urls = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            
            # 检查是否为收藏夹URL
            downloader = BilibiliSubtitleDownloader(
                sessdata=config_cookies.get('sessdata'),
                bili_jct=config_cookies.get('bili_jct'),
                buvid3=config_cookies.get('buvid3'),
                debug=False
            )
            
            if downloader.is_favorite_url(url):
                # 获取收藏夹ID
                fid = downloader.extract_fid(url)
                if fid:
                    print(f"检测到收藏夹URL，正在获取视频列表...")
                    # 获取收藏夹内的视频列表
                    videos = downloader.get_favorite_videos(fid)
                    for video in videos:
                        video_url = f"https://www.bilibili.com/video/{video['bvid']}"
                        expanded_urls.append(video_url)
                    print(f"收藏夹展开完成，共 {len(videos)} 个视频")
                else:
                    # 无法提取收藏夹ID，当作普通视频URL处理
                    print(f"无法从收藏夹URL中提取ID，将作为普通视频处理: {url}")
                    expanded_urls.append(url)
            else:
                # 普通视频URL
                expanded_urls.append(url)
        
        if not expanded_urls:
            return jsonify({
                'success': False,
                'error': '未找到有效的视频URL'
            }), 400
        
        # 创建任务并加入队列
        task_ids = []
        for index, url in enumerate(expanded_urls):
            task_id = str(uuid.uuid4())
            
            with tasks_lock:
                tasks[task_id] = {
                    'id': task_id,
                    'url': url,
                    'status': TaskStatus.PENDING,
                    'message': '等待队列处理（避免并发过高）',
                    'created_at': datetime.now().isoformat()
                }
            
            # 将任务放入队列，而不是直接启动线程
            task_data = {
                'task_id': task_id,
                'url': url,
                'output_dir': output_dir,
                'model_name': model_name,
                'cookies_file': cookies_file,
                'custom_folder_name': custom_folder_name,
                'download_all_parts': download_all_parts,
                'generate_options': generate_options
            }
            task_queue.put(task_data)
            
            task_ids.append(task_id)
        
        # 获取当前配置的并发数
        config = load_app_config()
        max_concurrent = config.get('max_concurrent_tasks', MAX_CONCURRENT_TASKS)
        
        return jsonify({
            'success': True,
            'task_ids': task_ids,
            'total_videos': len(expanded_urls),
            'message': f'已创建 {len(task_ids)} 个任务，最多同时处理 {max_concurrent} 个视频'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    with tasks_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'task': task
        })


@app.route('/api/tasks', methods=['GET'])
def get_all_tasks():
    """获取所有任务"""
    with tasks_lock:
        return jsonify({
            'success': True,
            'tasks': list(tasks.values())
        })


@app.route('/api/tasks/<task_id>/stop', methods=['POST'])
def stop_task(task_id):
    """停止任务"""
    try:
        with tasks_lock:
            task = tasks.get(task_id)
            if not task:
                return jsonify({
                    'success': False,
                    'error': '任务不存在'
                }), 404
            
            # 如果任务已经完成、失败或停止，则不能再停止
            if task['status'] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]:
                return jsonify({
                    'success': False,
                    'error': f'任务已经是{task["status"]}状态，无法停止'
                }), 400
            
            # 设置停止标志和更新状态
            task['stop_flag'] = True
            task['status'] = TaskStatus.STOPPING
            task['message'] = '正在停止任务，请等待当前步骤完成...'
        
        return jsonify({
            'success': True,
            'message': '停止信号已发送'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config/cookies', methods=['GET'])
def get_cookies_config():
    """获取Cookie配置"""
    try:
        cookies_file = 'cookies.txt'
        if not os.path.exists(cookies_file):
            return jsonify({
                'success': True,
                'configured': False
            })
        
        cookies = load_cookies_from_file(cookies_file)
        return jsonify({
            'success': True,
            'configured': bool(cookies.get('sessdata'))
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config', methods=['GET'])
def get_app_config():
    """获取应用配置"""
    try:
        config = load_app_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/config', methods=['POST'])
def update_app_config():
    """更新应用配置"""
    try:
        data = request.json
        
        # 加载当前配置
        config = load_app_config()
        
        # 更新配置字段
        if 'output_directory' in data:
            config['output_directory'] = data['output_directory']
        if 'last_selected_model' in data:
            config['last_selected_model'] = data['last_selected_model']
        if 'cookies_file' in data:
            config['cookies_file'] = data['cookies_file']
        if 'auto_refresh_interval' in data:
            config['auto_refresh_interval'] = data['auto_refresh_interval']
        if 'web_port' in data:
            config['web_port'] = data['web_port']
        if 'download_all_parts' in data:
            config['download_all_parts'] = data['download_all_parts']
        if 'max_concurrent_tasks' in data:
            config['max_concurrent_tasks'] = data['max_concurrent_tasks']
        
        # 保存配置
        save_app_config(config)
        
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # 确保必要的目录存在
    os.makedirs('config', exist_ok=True)
    os.makedirs('subtitles', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # 加载配置获取端口和并发数
    config = load_app_config()
    port = config.get('web_port', 5000)
    max_concurrent = config.get('max_concurrent_tasks', MAX_CONCURRENT_TASKS)
    
    print("=" * 80)
    print("Bilibili视频字幕下载与总结 - Web服务")
    print("=" * 80)
    print()
    print("服务启动中...")
    print(f"访问地址: http://127.0.0.1:{port}")
    print(f"最大并发任务数: {max_concurrent}")
    print(f"工作线程将在首次创建任务时启动")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 80)
    print()
    
    # 使用 use_reloader=False 避免Flask重新加载导致工作线程丢失
    # 使用 debug=False 在生产环境中，或者确保工作线程在每次重载后都能正确启动
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False, threaded=True)




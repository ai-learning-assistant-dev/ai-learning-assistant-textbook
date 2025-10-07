#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili视频字幕下载与总结 - Web服务
"""

import os
import sys
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from bilibili_subtitle_downloader import BilibiliSubtitleDownloader, load_cookies_from_file
from subtitle_summarizer import SRTParser, SubtitleSummarizer, load_llm_config
from llm_client import OpenAICompatClient

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文JSON

# 全局变量存储任务状态
tasks = {}
tasks_lock = threading.Lock()


class TaskStatus:
    """任务状态类"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    FAILED = "failed"


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
        'web_port': 5000
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


def process_video_task(task_id, url, output_dir, model_name, cookies_file):
    """处理单个视频的下载和总结任务"""
    try:
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
            output_dir=output_dir,
            format_type='srt',
            download_cover=True
        )
        
        # 获取下载结果
        downloaded_files = download_result.get('subtitles', [])
        cover_path = download_result.get('cover')
        video_title = download_result.get('title', '')
        video_dir = download_result.get('video_dir', output_dir)
        
        # 检查是否成功下载了字幕
        if not downloaded_files:
            raise Exception('此视频没有字幕，无法进行总结')
        
        subtitle_file = downloaded_files[0]  # 使用第一个字幕文件
        
        # 更新状态：AI处理中
        with tasks_lock:
            tasks[task_id]['status'] = TaskStatus.SUMMARIZING
            tasks[task_id]['message'] = f'正在生成AI内容 (1/4): 要点总结...'
            tasks[task_id]['subtitle_file'] = subtitle_file
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
            request_timeout=300
        )
        
        # 解析字幕
        subtitles = SRTParser.parse_srt_file(subtitle_file)
        subtitle_text = SRTParser.format_subtitles_for_llm(subtitles)
        
        # 创建总结器
        summarizer = SubtitleSummarizer(llm_client)
        
        # ========== 1. 生成要点总结 ==========
        summary = summarizer.summarize(subtitle_text, stream=False)
        
        # 保存总结（只保存JSON格式）
        summary_json_file = os.path.join(video_dir, 'summary.json')
        
        with open(summary_json_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        # ========== 2. 生成完整内容文档 ==========
        with tasks_lock:
            tasks[task_id]['message'] = f'正在生成AI内容 (2/4): 完整文档...'
        
        # 预处理字幕文本
        plain_text = SRTParser.extract_plain_text(subtitle_file)
        
        full_content = summarizer.generate_full_content(
            plain_text,
            video_title=video_title,
            stream=False
        )
        
        # 保存完整内容为Markdown文件
        full_content_file = os.path.join(video_dir, 'content.md')
        with open(full_content_file, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        # ========== 3. 生成练习题 ==========
        with tasks_lock:
            tasks[task_id]['message'] = f'正在生成AI内容 (3/4): 练习题...'
        
        exercises = summarizer.generate_exercises(
            plain_text,
            video_title=video_title,
            stream=False
        )
        
        # 保存练习题为JSON文件
        exercises_file = os.path.join(video_dir, 'exercises.json')
        with open(exercises_file, 'w', encoding='utf-8') as f:
            json.dump(exercises, f, ensure_ascii=False, indent=2)
        
        # ========== 4. 生成预设问题 ==========
        with tasks_lock:
            tasks[task_id]['message'] = f'正在生成AI内容 (4/4): 预设问题...'
        
        preset_questions = summarizer.generate_preset_questions(
            plain_text,
            video_title=video_title,
            stream=False
        )
        
        # 保存预设问题为JSON文件
        questions_file = os.path.join(video_dir, 'questions.json')
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(preset_questions, f, ensure_ascii=False, indent=2)
        
        # 更新状态：完成
        with tasks_lock:
            tasks[task_id]['status'] = TaskStatus.COMPLETED
            tasks[task_id]['message'] = '全部完成！已生成字幕、封面、总结、完整文档、练习题和预设问题'
            tasks[task_id]['summary'] = summary
            tasks[task_id]['files'] = {
                'video_dir': video_dir,
                'subtitle': subtitle_file,
                'cover': cover_path,
                'summary_json': summary_json_file,
                'content_md': full_content_file,
                'exercises': exercises_file,
                'questions': questions_file
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


@app.route('/api/tasks', methods=['POST'])
def create_tasks():
    """创建批量任务"""
    try:
        data = request.json
        urls = data.get('urls', [])
        output_dir = data.get('output_dir', 'subtitles')
        model_name = data.get('model_name')
        cookies_file = data.get('cookies_file', 'cookies.txt')
        
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
        
        # 创建任务
        task_ids = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            
            task_id = str(uuid.uuid4())
            
            with tasks_lock:
                tasks[task_id] = {
                    'id': task_id,
                    'url': url,
                    'status': TaskStatus.PENDING,
                    'message': '等待处理',
                    'created_at': datetime.now().isoformat()
                }
            
            # 启动后台线程处理任务
            thread = threading.Thread(
                target=process_video_task,
                args=(task_id, url, output_dir, model_name, cookies_file)
            )
            thread.daemon = True
            thread.start()
            
            task_ids.append(task_id)
        
        return jsonify({
            'success': True,
            'task_ids': task_ids
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
    
    # 加载配置获取端口
    config = load_app_config()
    port = config.get('web_port', 5000)
    
    print("=" * 80)
    print("Bilibili视频字幕下载与总结 - Web服务")
    print("=" * 80)
    print()
    print("服务启动中...")
    print(f"访问地址: http://127.0.0.1:{port}")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 80)
    print()
    
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)


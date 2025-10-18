#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键下载并总结Bilibili视频字幕
"""

import os
import sys
import argparse
import json
from pathlib import Path

from bilibili_subtitle_downloader import BilibiliSubtitleDownloader, load_cookies_from_file
from subtitle_summarizer import (
    SRTParser, SubtitleSummarizer, load_llm_config, format_output
)
from llm_client import OpenAICompatClient


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='一键下载Bilibili视频字幕并生成要点总结',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 列出所有可用的模型
  python download_and_summarize.py --list-models
  
  # 基本使用（使用cookies.txt和默认模型）
  python download_and_summarize.py "https://www.bilibili.com/video/BV1xx411c7mu"
  
  # 通过名称指定模型（推荐）
  python download_and_summarize.py "视频URL" -n aivmz8bq80
  
  # 通过索引指定模型
  python download_and_summarize.py "视频URL" -m 1
  
  # 使用流式输出总结过程
  python download_and_summarize.py "视频URL" -n aivmz8bq80 --stream
  
  # 指定输出目录
  python download_and_summarize.py "视频URL" -o ./output
  
  # 只下载不总结
  python download_and_summarize.py "视频URL" --download-only
        """
    )
    
    parser.add_argument('url', nargs='?', help='Bilibili视频URL')
    parser.add_argument('-o', '--output', default='subtitles',
                       help='输出目录（默认：subtitles）')
    parser.add_argument('-m', '--model-index', type=int, default=None,
                       help='使用的模型索引（默认：0）')
    parser.add_argument('-n', '--model-name', default=None,
                       help='使用的模型名称（优先级高于-m）')
    parser.add_argument('--config', default='cookies.txt',
                       help='Cookie配置文件路径（默认：cookies.txt）')
    parser.add_argument('--llm-config', default='config/llm_models.json',
                       help='LLM配置文件路径（默认：config/llm_models.json）')
    parser.add_argument('--stream', action='store_true',
                       help='使用流式输出总结')
    parser.add_argument('--download-only', action='store_true',
                       help='只下载字幕，不进行总结')
    parser.add_argument('--list-models', action='store_true',
                       help='列出所有可用的模型')
    parser.add_argument('--debug', action='store_true',
                       help='启用调试模式')
    
    args = parser.parse_args()
    
    # 如果只是列出模型
    if args.list_models:
        from subtitle_summarizer import list_available_models
        list_available_models(args.llm_config)
        return
    
    # 检查是否提供了URL
    if not args.url:
        parser.print_help()
        print("\n错误：请提供视频URL，或使用 --list-models 查看可用模型")
        sys.exit(1)
    
    print("=" * 80)
    print("Bilibili视频字幕下载与总结工具")
    print("=" * 80)
    print()
    
    # ========== 第一步：下载字幕 ==========
    print("🎬 第一步：下载视频字幕")
    print("-" * 80)
    
    try:
        # 从配置文件加载Cookie
        config_cookies = load_cookies_from_file(args.config)
        sessdata = config_cookies.get('sessdata')
        
        if not sessdata:
            print("警告：未在配置文件中找到SESSDATA，可能无法下载AI字幕")
        
        # 创建下载器（启用反爬虫保护）
        downloader = BilibiliSubtitleDownloader(
            sessdata=sessdata,
            bili_jct=config_cookies.get('bili_jct'),
            buvid3=config_cookies.get('buvid3'),
            debug=args.debug,
            request_delay=2.0,  # 请求间隔2秒
            max_retries=3       # 最多重试3次
        )
        
        # 下载字幕和封面
        print(f"视频URL: {args.url}")
        print(f"输出目录: {args.output}")
        print()
        
        download_result = downloader.download(
            video_url=args.url,
            output_dir=args.output,
            format_type='srt',
            download_cover=True
        )
        
        downloaded_files = download_result.get('subtitles', [])
        cover_path = download_result.get('cover')
        video_title = download_result.get('title', '')
        video_dir = download_result.get('video_dir', args.output)
        
        print()
        
        # 检查是否成功下载了字幕
        if not downloaded_files:
            print("❌ 此视频没有字幕，无法进行总结")
            sys.exit(0)
        
        print("✅ 字幕下载完成！")
        if cover_path:
            print(f"✅ 封面图片已保存: {cover_path}")
        print(f"✅ 所有文件保存在: {video_dir}")
        print()
        
    except Exception as e:
        print(f"❌ 下载字幕时出错: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    # 如果只需要下载，则退出
    if args.download_only:
        print("已完成下载，跳过总结步骤")
        return
    
    # ========== 第二步：AI生成要点总结 ==========
    print("🤖 第二步：AI生成要点总结")
    print("-" * 80)
    
    try:
        # 加载LLM配置
        if not os.path.exists(args.llm_config):
            print(f"❌ 错误：LLM配置文件不存在: {args.llm_config}")
            sys.exit(1)
        
        model_config = load_llm_config(
            args.llm_config, 
            model_index=args.model_index,
            model_name=args.model_name
        )
        print(f"使用模型: {model_config['name']}")
        print(f"API地址: {model_config['api_base']}")
        print()
        
        # 创建LLM客户端
        llm_client = OpenAICompatClient(
            api_base=model_config['api_base'],
            api_key=model_config['api_key'],
            default_model=model_config['model_name'],
            request_timeout=300
        )
        
        # 统计
        total_files = len(downloaded_files)
        success_count = 0
        failed_count = 0
        
        # 遍历所有下载的字幕文件，对每个都进行总结
        for index, subtitle_file in enumerate(downloaded_files, 1):
            print()
            print("=" * 80)
            if total_files > 1:
                print(f"📄 正在处理第 {index}/{total_files} 个字幕文件")
            print(f"文件: {subtitle_file}")
            print("-" * 80)
            
            try:
                # 从字幕文件名中提取标题（去除扩展名和语言后缀）
                subtitle_filename = os.path.basename(subtitle_file)
                # 去除扩展名
                subtitle_name = os.path.splitext(subtitle_filename)[0]
                # 去除语言后缀（如 _ai-zh, _zh-CN 等）
                subtitle_title = subtitle_name.rsplit('_', 1)[0] if '_' in subtitle_name else subtitle_name
                
                if args.debug:
                    print(f"[DEBUG] 字幕标题: {subtitle_title}")
                
                # 定义所有可能生成的文件路径
                summary_json_file = os.path.join(video_dir, f'{subtitle_title}_summary.json')
                markdown_dir = os.path.join(video_dir, 'markdown')
                full_content_file = os.path.join(markdown_dir, f'{subtitle_title}.md')
                exercises_file = os.path.join(video_dir, f'{subtitle_title}_exercises.json')
                questions_file = os.path.join(video_dir, f'{subtitle_title}_questions.json')
                
                # 解析字幕（提前解析，供后续步骤使用）
                subtitles = None
                subtitle_text = None
                plain_text = None
                summarizer = SubtitleSummarizer(llm_client)
                
                # ========== 1. 生成要点总结 ==========
                if os.path.exists(summary_json_file):
                    print("📝 要点总结文件已存在，跳过")
                    print(f"   JSON格式: {summary_json_file}")
                else:
                    print("📝 正在生成要点总结...")
                    
                    # 解析字幕
                    if subtitles is None:
                        subtitles = SRTParser.parse_srt_file(subtitle_file)
                        print(f"解析到 {len(subtitles)} 条字幕")
                        subtitle_text = SRTParser.format_subtitles_for_llm(subtitles)
                    
                    summary = summarizer.summarize(subtitle_text, stream=args.stream)
                    
                    with open(summary_json_file, 'w', encoding='utf-8') as f:
                        json.dump(summary, f, ensure_ascii=False, indent=2)
                    
                    print()
                    print("✅ 要点总结已保存：")
                    print(f"   JSON格式: {summary_json_file}")
                    
                    # 显示要点总结（终端输出）
                    print()
                    print("=" * 80)
                    print("📋 要点总结预览：")
                    print("=" * 80)
                    key_points = summary.get('key_points', [])
                    print(f"\n🎯 关键要点（共 {len(key_points)} 个）：\n")
                    for i, point in enumerate(key_points, 1):
                        time = point.get('time', '')
                        title = point.get('title', '')
                        print(f"{i}. [{time}] {title}")
                    print("=" * 80)
                
                # ========== 2. 生成完整内容文档 ==========
                print()
                print("=" * 80)
                if os.path.exists(full_content_file):
                    print("📚 完整内容文档已存在，跳过")
                    print(f"   Markdown格式: {full_content_file}")
                else:
                    print("📚 正在生成完整内容文档...")
                    print("-" * 80)
                    
                    # 使用预处理的文本（去除时间标签，智能分段）
                    if plain_text is None:
                        print("正在预处理字幕文本...")
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    if args.debug:
                        print(f"[DEBUG] 预处理后文本长度: {len(plain_text)} 字符")
                        print(f"[DEBUG] 预处理示例:\n{plain_text[:500]}...\n")
                    
                    full_content = summarizer.generate_full_content(
                        plain_text,  # 使用预处理后的文本
                        video_title=video_title,
                        stream=args.stream
                    )
                    
                    # 创建markdown子目录（如果不存在）
                    os.makedirs(markdown_dir, exist_ok=True)
                    
                    with open(full_content_file, 'w', encoding='utf-8') as f:
                        f.write(full_content)
                    
                    print()
                    print("✅ 完整内容已保存：")
                    print(f"   Markdown格式: {full_content_file}")
                
                # ========== 3. 生成练习题 ==========
                print()
                print("=" * 80)
                if os.path.exists(exercises_file):
                    print("📝 练习题已存在，跳过")
                    print(f"   JSON格式: {exercises_file}")
                else:
                    print("📝 正在生成练习题...")
                    print("-" * 80)
                    
                    # 预处理字幕文本（如果还没有）
                    if plain_text is None:
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    exercises = summarizer.generate_exercises(
                        plain_text,
                        video_title=video_title,
                        stream=args.stream
                    )
                    
                    with open(exercises_file, 'w', encoding='utf-8') as f:
                        json.dump(exercises, f, ensure_ascii=False, indent=2)
                    
                    print()
                    print("✅ 练习题已保存：")
                    print(f"   JSON格式: {exercises_file}")
                    
                    # 显示题目数量统计
                    mc_count = len(exercises.get('multiple_choice', []))
                    sa_count = len(exercises.get('short_answer', []))
                    print(f"   选择题: {mc_count} 道")
                    print(f"   简答题: {sa_count} 道")
                
                # ========== 4. 生成预设问题 ==========
                print()
                print("=" * 80)
                if os.path.exists(questions_file):
                    print("❓ 预设问题已存在，跳过")
                    print(f"   JSON格式: {questions_file}")
                else:
                    print("❓ 正在生成预设问题...")
                    print("-" * 80)
                    
                    # 预处理字幕文本（如果还没有）
                    if plain_text is None:
                        plain_text = SRTParser.extract_plain_text(subtitle_file)
                    
                    preset_questions = summarizer.generate_preset_questions(
                        plain_text,
                        video_title=video_title,
                        stream=args.stream
                    )
                    
                    with open(questions_file, 'w', encoding='utf-8') as f:
                        json.dump(preset_questions, f, ensure_ascii=False, indent=2)
                    
                    print()
                    print("✅ 预设问题已保存：")
                    print(f"   JSON格式: {questions_file}")
                    
                    # 显示问题数量
                    q_count = len(preset_questions.get('questions', []))
                    print(f"   问题数量: {q_count} 个")
                    
                    # 显示问题预览
                    if q_count > 0:
                        print("\n   问题预览:")
                        for q in preset_questions.get('questions', []):
                            print(f"   {q.get('id')}. {q.get('question')}")
                
                success_count += 1
                
            except Exception as e:
                print(f"❌ 处理此字幕文件时出错: {e}")
                if args.debug:
                    import traceback
                    traceback.print_exc()
                failed_count += 1
                # 继续处理下一个文件，而不是直接退出
                continue
        
        # 输出最终统计
        print()
        print("=" * 80)
        print("🎉 全部完成！")
        print("-" * 80)
        print(f"总共处理: {total_files} 个字幕文件")
        print(f"成功: {success_count} 个")
        if failed_count > 0:
            print(f"失败: {failed_count} 个")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 生成总结时出错: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()


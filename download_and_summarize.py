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
        
        # 创建下载器
        downloader = BilibiliSubtitleDownloader(
            sessdata=sessdata,
            bili_jct=config_cookies.get('bili_jct'),
            buvid3=config_cookies.get('buvid3'),
            debug=args.debug
        )
        
        # 下载字幕
        print(f"视频URL: {args.url}")
        print(f"输出目录: {args.output}")
        print()
        
        downloaded_files = downloader.download(
            video_url=args.url,
            output_dir=args.output,
            format_type='srt'
        )
        
        print()
        
        # 检查是否成功下载了字幕
        if not downloaded_files:
            print("❌ 此视频没有字幕，无法进行总结")
            sys.exit(0)
        
        print("✅ 字幕下载完成！")
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
                # 解析字幕
                subtitles = SRTParser.parse_srt_file(subtitle_file)
                print(f"解析到 {len(subtitles)} 条字幕")
                
                # 格式化字幕文本
                subtitle_text = SRTParser.format_subtitles_for_llm(subtitles)
                
                # 生成总结
                summarizer = SubtitleSummarizer(llm_client)
                summary = summarizer.summarize(subtitle_text, stream=args.stream)
                
                # 格式化并输出
                formatted_output = format_output(summary)
                print()
                print(formatted_output)
                
                # 保存总结到文件
                summary_txt_file = Path(subtitle_file).with_suffix('.summary.txt')
                summary_json_file = Path(subtitle_file).with_suffix('.summary.json')
                
                with open(summary_txt_file, 'w', encoding='utf-8') as f:
                    f.write(formatted_output)
                
                with open(summary_json_file, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
                
                print()
                print("✅ 总结已保存：")
                print(f"   文本格式: {summary_txt_file}")
                print(f"   JSON格式: {summary_json_file}")
                
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


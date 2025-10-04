#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
字幕总结工具
读取SRT字幕文件，调用大模型生成时间节点要点总结
"""

import json
import os
import re
import argparse
from typing import List, Dict, Tuple
from pathlib import Path

from llm_client import OpenAICompatClient


class SRTParser:
    """SRT字幕文件解析器"""
    
    @staticmethod
    def parse_srt_file(file_path: str) -> List[Dict[str, str]]:
        """
        解析SRT字幕文件
        
        Args:
            file_path: SRT文件路径
            
        Returns:
            字幕列表，每个元素包含 index, time_start, time_end, content
        """
        subtitles = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 按空行分割字幕块
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # 第一行是序号
            index = lines[0].strip()
            
            # 第二行是时间轴
            time_line = lines[1].strip()
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_line)
            if not time_match:
                continue
            
            time_start = time_match.group(1)
            time_end = time_match.group(2)
            
            # 剩余行是字幕内容
            text_content = '\n'.join(lines[2:])
            
            subtitles.append({
                'index': index,
                'time_start': time_start,
                'time_end': time_end,
                'content': text_content
            })
        
        return subtitles
    
    @staticmethod
    def format_subtitles_for_llm(subtitles: List[Dict[str, str]]) -> str:
        """
        将字幕格式化为适合LLM处理的文本
        
        Args:
            subtitles: 字幕列表
            
        Returns:
            格式化的字幕文本
        """
        formatted_lines = []
        for sub in subtitles:
            formatted_lines.append(f"[{sub['time_start']}] {sub['content']}")
        
        return '\n'.join(formatted_lines)


class SubtitleSummarizer:
    """字幕总结器"""
    
    def __init__(self, llm_client: OpenAICompatClient):
        """
        初始化总结器
        
        Args:
            llm_client: LLM客户端实例
        """
        self.llm_client = llm_client
    
    def create_summary_prompt(self, subtitle_text: str) -> str:
        """
        创建总结提示词
        
        Args:
            subtitle_text: 字幕文本
            
        Returns:
            提示词
        """
        prompt = f"""请分析以下视频字幕内容，提取关键要点并按时间节点总结。

要求：
1. **粗粒度总结**：将视频划分为3-8个主要段落，每个段落时长约3-10分钟
2. 每个段落提取一个大要点，涵盖该时间段的主要内容
3. 时间节点格式简化为 "MM:SS"（如 "00:07", "04:28"），取该段落开始时间
4. 标题要精炼概括该段落的核心主题（10-20字）
5. 描述要详细全面（100-300字），包含该段落的所有重要信息点、细节和逻辑关系
6. 按时间顺序排列
7. **不要**输出 video_summary 字段
8. 输出格式严格按照以下JSON格式：

```json
{{
  "key_points": [
    {{
      "time": "00:07",
      "title": "要点标题（概括性强）",
      "description": "详细描述该时间段的所有重要内容，包括具体信息、数据、步骤、注意事项等。要尽可能全面，让读者无需看视频就能了解这段内容的核心知识。"
    }},
    {{
      "time": "04:28",
      "title": "下一个要点标题",
      "description": "继续详细描述..."
    }}
  ]
}}
```

字幕内容：
{subtitle_text}

请直接输出JSON格式的总结结果，不要包含其他说明文字。每个要点的description要充分详细，涵盖该时间段的完整内容。"""
        
        return prompt
    
    def summarize(self, subtitle_text: str, stream: bool = False) -> Dict:
        """
        总结字幕内容
        
        Args:
            subtitle_text: 字幕文本
            stream: 是否使用流式输出
            
        Returns:
            总结结果
        """
        prompt = self.create_summary_prompt(subtitle_text)
        
        messages = [
            {"role": "system", "content": "你是一个专业的视频内容分析助手，擅长提取视频关键信息并进行结构化总结。"},
            {"role": "user", "content": prompt}
        ]
        
        if stream:
            print("正在生成总结（流式输出）...\n")
            full_response = ""
            for chunk in self.llm_client.chat_completions_stream(messages):
                print(chunk, end='', flush=True)
                full_response += chunk
            print("\n")
            return self._parse_response(full_response)
        else:
            print("正在生成总结...\n")
            response = self.llm_client.chat_completions(messages)
            content = response['choices'][0]['message']['content']
            return self._parse_response(content)
    
    def _parse_response(self, response_text: str) -> Dict:
        """
        解析LLM响应
        
        Args:
            response_text: LLM返回的文本
            
        Returns:
            解析后的JSON对象
        """
        # 尝试提取JSON部分
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # 如果没有代码块，尝试直接解析
            json_text = response_text.strip()
        
        try:
            result = json.loads(json_text)
            # 确保只保留 key_points 字段
            if 'key_points' in result:
                return {'key_points': result['key_points']}
            return result
        except json.JSONDecodeError as e:
            print(f"警告：无法解析JSON响应: {e}")
            print(f"原始响应：\n{response_text}\n")
            return {
                "key_points": [],
                "raw_response": response_text
            }


def load_llm_config(config_file: str = 'config/llm_models.json', 
                    model_index: int = None, 
                    model_name: str = None) -> Dict:
    """
    加载LLM配置
    
    Args:
        config_file: 配置文件路径
        model_index: 使用第几个模型（索引，从0开始）
        model_name: 模型名称（优先级高于model_index）
        
    Returns:
        模型配置字典
    """
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    models = config.get('models', [])
    if not models:
        raise ValueError("配置文件中没有找到模型")
    
    # 优先使用model_name
    if model_name:
        for model in models:
            if model.get('name') == model_name:
                print(f"找到模型: {model_name}")
                return model
        
        # 如果没找到，列出可用模型
        available_names = [m.get('name', '未命名') for m in models]
        raise ValueError(f"未找到名为 '{model_name}' 的模型。可用模型: {', '.join(available_names)}")
    
    # 使用model_index
    if model_index is None:
        model_index = 0
    
    if model_index >= len(models):
        print(f"警告：模型索引 {model_index} 超出范围，使用第一个模型")
        model_index = 0
    
    return models[model_index]


def list_available_models(config_file: str = 'config/llm_models.json') -> None:
    """
    列出所有可用的模型
    
    Args:
        config_file: 配置文件路径
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        models = config.get('models', [])
        if not models:
            print("配置文件中没有找到模型")
            return
        
        print(f"\n可用的模型（共 {len(models)} 个）：")
        print("-" * 60)
        for i, model in enumerate(models):
            name = model.get('name', '未命名')
            model_name = model.get('model_name', '未知')
            api_base = model.get('api_base', '未知')
            print(f"{i}. 名称: {name}")
            print(f"   模型: {model_name}")
            print(f"   API: {api_base}")
            print()
    except Exception as e:
        print(f"读取配置文件失败: {e}")


def format_output(summary: Dict) -> str:
    """
    格式化输出结果
    
    Args:
        summary: 总结结果
        
    Returns:
        格式化的文本
    """
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("视频内容总结")
    output_lines.append("=" * 80)
    output_lines.append("")
    
    # 关键要点
    key_points = summary.get('key_points', [])
    output_lines.append(f"🎯 关键要点（共 {len(key_points)} 个）：")
    output_lines.append("")
    
    for i, point in enumerate(key_points, 1):
        time = point.get('time', '未知')
        title = point.get('title', '无标题')
        description = point.get('description', '无描述')
        
        output_lines.append(f"{i}. [{time}] {title}")
        output_lines.append("")
        # 描述可能很长，按句子或标点符号分段显示
        # 每行最多80字符，自动换行
        desc_lines = []
        current_line = "   "
        for char in description:
            current_line += char
            if len(current_line) >= 77:  # 留3个字符的缩进
                # 找到最近的标点符号或空格来断行
                break_pos = max(
                    current_line.rfind('。'),
                    current_line.rfind('，'),
                    current_line.rfind('、'),
                    current_line.rfind(' ')
                )
                if break_pos > 3:  # 确保不是在开头
                    desc_lines.append(current_line[:break_pos + 1])
                    current_line = "   " + current_line[break_pos + 1:]
                else:
                    desc_lines.append(current_line)
                    current_line = "   "
        
        if current_line.strip():
            desc_lines.append(current_line)
        
        output_lines.extend(desc_lines)
        output_lines.append("")
    
    output_lines.append("=" * 80)
    
    return '\n'.join(output_lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='字幕总结工具 - 使用大模型分析字幕并生成要点总结',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 列出所有可用的模型
  python subtitle_summarizer.py --list-models
  
  # 基本使用（使用默认模型）
  python subtitle_summarizer.py subtitles/视频_ai-zh.srt
  
  # 通过名称指定模型（推荐）
  python subtitle_summarizer.py subtitles/视频_ai-zh.srt -n aivmz8bq80
  
  # 通过索引指定模型（0=第一个，1=第二个）
  python subtitle_summarizer.py subtitles/视频_ai-zh.srt -m 1
  
  # 使用流式输出
  python subtitle_summarizer.py subtitles/视频_ai-zh.srt -n aivmz8bq80 --stream
  
  # 保存结果到文件
  python subtitle_summarizer.py subtitles/视频_ai-zh.srt -o summary.txt
        """
    )
    
    parser.add_argument('subtitle_file', nargs='?', help='SRT字幕文件路径')
    parser.add_argument('-m', '--model-index', type=int, default=None,
                       help='使用的模型索引（默认：0，即第一个模型）')
    parser.add_argument('-n', '--model-name', default=None,
                       help='使用的模型名称（优先级高于-m）')
    parser.add_argument('-c', '--config', default='config/llm_models.json',
                       help='LLM配置文件路径（默认：config/llm_models.json）')
    parser.add_argument('-o', '--output', default=None,
                       help='输出文件路径（默认：屏幕输出）')
    parser.add_argument('--stream', action='store_true',
                       help='使用流式输出')
    parser.add_argument('--save-json', action='store_true',
                       help='同时保存JSON格式的结果')
    parser.add_argument('--list-models', action='store_true',
                       help='列出所有可用的模型')
    
    args = parser.parse_args()
    
    # 如果只是列出模型
    if args.list_models:
        list_available_models(args.config)
        return
    
    # 检查是否提供了字幕文件
    if not args.subtitle_file:
        parser.print_help()
        print("\n错误：请提供字幕文件路径，或使用 --list-models 查看可用模型")
        return
    
    # 检查字幕文件是否存在
    if not os.path.exists(args.subtitle_file):
        print(f"错误：字幕文件不存在: {args.subtitle_file}")
        return
    
    # 检查配置文件是否存在
    if not os.path.exists(args.config):
        print(f"错误：配置文件不存在: {args.config}")
        return
    
    try:
        # 加载LLM配置
        print(f"加载模型配置...")
        model_config = load_llm_config(
            args.config, 
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
            request_timeout=300  # 总结可能需要较长时间
        )
        
        # 解析字幕文件
        print(f"读取字幕文件: {args.subtitle_file}")
        subtitles = SRTParser.parse_srt_file(args.subtitle_file)
        print(f"解析到 {len(subtitles)} 条字幕")
        print()
        
        # 格式化字幕文本
        subtitle_text = SRTParser.format_subtitles_for_llm(subtitles)
        
        # 创建总结器并生成总结
        summarizer = SubtitleSummarizer(llm_client)
        summary = summarizer.summarize(subtitle_text, stream=args.stream)
        
        # 格式化输出
        formatted_output = format_output(summary)
        
        # 输出到屏幕或文件
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            print(f"✅ 总结已保存到: {args.output}")
            
            # 如果需要保存JSON
            if args.save_json:
                json_output = args.output.replace('.txt', '.json')
                with open(json_output, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
                print(f"✅ JSON结果已保存到: {json_output}")
        else:
            print(formatted_output)
        
        # 如果没有指定输出文件但要保存JSON
        if not args.output and args.save_json:
            subtitle_path = Path(args.subtitle_file)
            json_output = subtitle_path.with_suffix('.summary.json')
            with open(json_output, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"✅ JSON结果已保存到: {json_output}")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()


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
    def extract_plain_text(file_path: str) -> str:
        """
        从SRT文件中提取纯文本内容，去除时间标签和序号
        
        Args:
            file_path: SRT文件路径
            
        Returns:
            合并后的纯文本
        """
        subtitles = SRTParser.parse_srt_file(file_path)
        
        # 提取所有文本内容
        texts = []
        prev_text = ""
        
        for sub in subtitles:
            text = sub['content'].strip()
            
            # 去除算法生成标记
            text = re.sub(r'<该字幕由算法自动生成>\s*', '', text)
            
            # 跳过空文本
            if not text:
                continue
            
            # 去除重复的文本（如果与前一句完全相同或被包含）
            if text == prev_text or (prev_text and text in prev_text):
                continue
            
            texts.append(text)
            prev_text = text
        
        # 合并文本，智能添加标点
        merged_text = SRTParser._merge_with_punctuation(texts)
        
        return merged_text
    
    @staticmethod
    def _merge_with_punctuation(texts: List[str]) -> str:
        """
        智能合并文本并添加标点符号
        
        Args:
            texts: 文本列表
            
        Returns:
            合并后的文本
        """
        if not texts:
            return ""
        
        result = []
        current_sentence = ""
        
        for i, text in enumerate(texts):
            # 检查是否已经有结尾标点
            has_end_punct = text and text[-1] in '。！？；，、.!?;,'
            
            # 如果当前句子为空，直接开始新句子
            if not current_sentence:
                current_sentence = text
            else:
                # 判断是否应该连接还是分句
                # 如果前一个文本有结尾标点，开始新句子
                if current_sentence[-1] in '。！？.!?':
                    result.append(current_sentence)
                    current_sentence = text
                # 如果当前文本是英文单词或短语，直接连接
                elif text and (text[0].isupper() or not any('\u4e00' <= c <= '\u9fff' for c in text)):
                    current_sentence += " " + text
                # 中文内容，判断是否需要添加标点
                else:
                    # 检查是否是句子的延续（如"啊"、"呢"、"的"等）
                    if text and len(text) <= 2 and text in ['啊', '呢', '吧', '的', '了', '着', '过', '呃', '嗯', '哦']:
                        current_sentence += text
                    # 如果前一句以逗号、顿号结尾，直接连接
                    elif current_sentence[-1] in '，、；;':
                        current_sentence += text
                    # 否则添加逗号连接
                    else:
                        current_sentence += "，" + text
            
            # 检查是否应该结束当前句子
            if has_end_punct and text[-1] in '。！？.!?':
                result.append(current_sentence)
                current_sentence = ""
        
        # 添加最后一个句子
        if current_sentence:
            # 如果没有结尾标点，添加句号
            if current_sentence[-1] not in '。！？.!?':
                current_sentence += "。"
            result.append(current_sentence)
        
        # 合并成段落，每3-5句为一段
        paragraphs = []
        temp_para = []
        
        for i, sentence in enumerate(result):
            temp_para.append(sentence)
            # 每4句或遇到明显的主题转换标志，分段
            if len(temp_para) >= 4 or (sentence and any(marker in sentence for marker in ['那么', '接下来', '首先', '其次', '最后', '总之', '因此'])):
                paragraphs.append(''.join(temp_para))
                temp_para = []
        
        if temp_para:
            paragraphs.append(''.join(temp_para))
        
        return '\n\n'.join(paragraphs)
    
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
    
    def create_full_content_prompt(self, subtitle_text: str, video_title: str = "") -> str:
        """
        创建完整内容生成的提示词（教学导向）
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            
        Returns:
            提示词
        """
        title_part = f"视频标题：{video_title}\n\n" if video_title else ""
        
        prompt = f"""{title_part}请根据以下视频内容，编写一份**详细、专业的教学文档**（Markdown格式）。这份文档将作为学习资料，要求内容完整、易于理解、适合自学。

## 核心目标
将视频内容转化为**结构化的教学材料**，让读者无需观看视频即可完整掌握所有知识点。

## 具体要求

### 📚 1. 内容深度与完整性
- **详尽讲解**：每个知识点都要充分展开，不能只是简单罗列
- **保留细节**：
  - 所有概念定义和解释
  - 具体的例子、数据、案例
  - 方法步骤的详细说明
  - 注意事项和常见错误
  - 相关的背景知识
- **逻辑连贯**：补充必要的过渡和承接，使内容流畅易读
- **深度阐述**：对重要概念进行多角度解释（是什么、为什么、怎么做、注意什么）

### 🏗️ 2. 文档结构
- **清晰的层级**：
  - 一级标题（#）：主要章节
  - 二级标题（##）：核心主题
  - 三级标题（###）：具体知识点
  - 四级标题（####）：细分内容
- **逻辑顺序**：按照"引入→基础→进阶→总结"或视频的自然顺序组织
- **章节完整**：每个章节都应包含：
  - 概念介绍
  - 详细说明
  - 具体示例
  - 要点总结

### 📝 3. 教学表达方式
- **书面语**：去除口语化表达（"啊"、"呃"、"那个"等）
- **准确性**：使用准确的专业术语，必要时加注解
- **易读性**：
  - 长段落拆分为多个小段落
  - 复杂概念用简单语言解释
  - 适当使用类比和比喻
- **教学性**：
  - 提出启发性问题
  - 强调重点和难点
  - 说明知识的应用场景

### 🎨 4. Markdown格式运用
- **粗体**（**文字**）：关键概念、专业术语、重点内容
- **斜体**（*文字*）：强调、补充说明
- **代码块**（\`代码\`）：公式、命令、代码示例
- **引用块**（> 文字）：重要提示、警告、关键结论
- **列表**：
  - 无序列表（-）：并列的知识点、特征
  - 有序列表（1.）：步骤、流程、条件
- **表格**：对比、分类、数据展示
- **分隔线**（---）：章节之间的明确划分

### ✅ 5. 内容组织原则
- **模块化**：每个部分相对独立，便于查阅
- **可检索**：重要内容易于定位和查找
- **可扩展**：预留空间用于笔记和补充
- **实用性**：
  - 包含可操作的方法和步骤
  - 提供实际应用场景
  - 总结常用技巧和经验

### 📖 6. 建议的文档模板结构

```markdown
# [主标题]

## 概述/引言
[简要说明本文档的主题、目标、适用对象]

## 基础概念
### 核心概念1
[详细定义、解释、举例]
### 核心概念2
[详细定义、解释、举例]

## 详细内容
### 主题1
#### 1.1 子主题
[详细讲解、例子、注意事项]
#### 1.2 子主题
[详细讲解、例子、注意事项]

### 主题2
...

## 实践应用/案例分析
[具体例子、实际应用场景]

## 常见问题与注意事项
[易错点、常见问题、解决方法]

## 总结与要点回顾
[核心内容梳理、关键要点列表]
```

---

**视频原文（已预处理）：**

{subtitle_text}

---

**输出要求：**
1. 直接输出Markdown格式的完整教学文档
2. 不要包含"根据视频内容"等元说明
3. 内容要详尽、专业、适合自学
4. 确保逻辑清晰、结构完整
5. 字数充足（通常应达到原字幕的2-3倍，因为要展开和解释）

请开始编写教学文档："""
        
        return prompt
    
    def generate_full_content(self, subtitle_text: str, video_title: str = "", stream: bool = False) -> str:
        """
        生成完整内容文档
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            stream: 是否使用流式输出
            
        Returns:
            Markdown格式的完整内容
        """
        prompt = self.create_full_content_prompt(subtitle_text, video_title)
        
        messages = [
            {"role": "system", "content": "你是一个专业的学习内容整理助手，擅长将视频字幕整理成结构清晰、内容完整的学习文档。"},
            {"role": "user", "content": prompt}
        ]
        
        if stream:
            print("正在生成完整内容（流式输出）...\n")
            full_response = ""
            for chunk in self.llm_client.chat_completions_stream(messages):
                print(chunk, end='', flush=True)
                full_response += chunk
            print("\n")
            return full_response
        else:
            print("正在生成完整内容...\n")
            response = self.llm_client.chat_completions(messages)
            content = response['choices'][0]['message']['content']
            return content
    
    def create_exercises_prompt(self, subtitle_text: str, video_title: str = "") -> str:
        """
        创建练习题生成的提示词
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            
        Returns:
            提示词
        """
        title_part = f"视频标题：{video_title}\n\n" if video_title else ""
        
        prompt = f"""{title_part}请根据以下视频学习内容，设计一套练习题，用于帮助学习者检验和巩固所学知识。

## 题目要求

### 📝 选择题（5道）
- **覆盖核心知识点**：每道题对应一个重要概念或知识点
- **难度适中**：既要考查理解，也要有一定区分度
- **选项设计**：
  - 4个选项（A/B/C/D）
  - 正确答案1个
  - 干扰项要有合理性，基于常见误解
  - 避免明显错误或无关选项
- **答案解析**：说明为什么正确，其他选项错在哪里

### ✍️ 简答题（5道）
- **深度考查**：要求学习者用自己的语言阐述理解
- **题型多样**：
  - 概念解释（是什么）
  - 原因分析（为什么）
  - 方法应用（怎么做）
  - 对比分析（有何区别/联系）
  - 综合论述（谈谈理解）
- **答案要点**：
  - 列出核心要点（3-5点）
  - 每个要点有简要说明
  - 答案长度适中（100-200字）

## 输出格式

严格按照以下JSON格式输出：

```json
{{
  "multiple_choice": [
    {{
      "id": 1,
      "question": "题目内容",
      "options": {{
        "A": "选项A内容",
        "B": "选项B内容",
        "C": "选项C内容",
        "D": "选项D内容"
      }},
      "correct_answer": "A",
      "explanation": "答案解析，说明为什么A正确，其他选项为何错误"
    }}
  ],
  "short_answer": [
    {{
      "id": 1,
      "question": "题目内容",
      "answer_points": [
        "要点1：具体内容",
        "要点2：具体内容",
        "要点3：具体内容"
      ],
      "reference_answer": "参考答案的完整表述（100-200字）"
    }}
  ]
}}
```

## 设计原则

1. **知识覆盖**：题目应覆盖视频的主要知识点
2. **层次递进**：从基础到综合，由浅入深
3. **实用性**：题目要有实际意义，不是死记硬背
4. **可操作性**：学习者能够独立完成作答
5. **答案明确**：选择题答案唯一，简答题要点清晰

---

**学习内容：**

{subtitle_text}

---

请严格按照JSON格式输出练习题，不要包含其他说明文字。"""
        
        return prompt
    
    def generate_exercises(self, subtitle_text: str, video_title: str = "", stream: bool = False) -> Dict:
        """
        生成练习题
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            stream: 是否使用流式输出
            
        Returns:
            包含练习题的字典
        """
        prompt = self.create_exercises_prompt(subtitle_text, video_title)
        
        messages = [
            {"role": "system", "content": "你是一个专业的教育测评专家，擅长根据学习内容设计高质量的练习题。"},
            {"role": "user", "content": prompt}
        ]
        
        if stream:
            print("正在生成练习题（流式输出）...\n")
            full_response = ""
            for chunk in self.llm_client.chat_completions_stream(messages):
                print(chunk, end='', flush=True)
                full_response += chunk
            print("\n")
            return self._parse_exercises_response(full_response)
        else:
            print("正在生成练习题...\n")
            response = self.llm_client.chat_completions(messages)
            content = response['choices'][0]['message']['content']
            return self._parse_exercises_response(content)
    
    def _parse_exercises_response(self, response_text: str) -> Dict:
        """
        解析练习题响应
        
        Args:
            response_text: LLM返回的文本
            
        Returns:
            解析后的练习题字典
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
            return result
        except json.JSONDecodeError as e:
            print(f"警告：无法解析JSON响应: {e}")
            print(f"原始响应：\n{response_text}\n")
            return {
                "multiple_choice": [],
                "short_answer": [],
                "raw_response": response_text
            }
    
    def create_preset_questions_prompt(self, subtitle_text: str, video_title: str = "") -> str:
        """
        创建预设问题生成的提示词
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            
        Returns:
            提示词
        """
        title_part = f"视频标题：{video_title}\n\n" if video_title else ""
        
        prompt = f"""{title_part}请根据以下视频内容，设计3个预设问题，用于引导观众思考视频的核心内容。

## 问题要求

### 🎯 核心原则
1. **简短精炼**：每个问题控制在15-25字以内
2. **概括性强**：能够抓住视频的核心主题和关键内容
3. **启发思考**：引导观众主动思考，而非简单的事实问答
4. **递进关系**：3个问题应该由浅入深，逐步深入

### 📝 问题类型建议
- **问题1**：总体把握型 - 关于整体主题、核心概念
  - 例："这个视频主要讨论了什么问题？"
  - 例："XX的核心特征是什么？"

- **问题2**：深入理解型 - 关于原因、方法、关系
  - 例："为什么要采用这种方法？"
  - 例："XX和YY之间有什么关系？"

- **问题3**：应用扩展型 - 关于实践、启发、延伸
  - 例："如何将这些方法应用到实际中？"
  - 例："这个理论给你带来了什么启发？"

### ⚠️ 注意事项
- 避免过于简单的是非题
- 避免需要大量背景知识的专业问题
- 避免过于宽泛、无法聚焦的问题
- 不要包含答案，只提出问题

## 输出格式

严格按照以下JSON格式输出：

```json
{{
  "questions": [
    {{
      "id": 1,
      "question": "第一个预设问题的内容？",
      "type": "总体把握"
    }},
    {{
      "id": 2,
      "question": "第二个预设问题的内容？",
      "type": "深入理解"
    }},
    {{
      "id": 3,
      "question": "第三个预设问题的内容？",
      "type": "应用扩展"
    }}
  ]
}}
```

---

**视频内容：**

{subtitle_text}

---

请严格按照JSON格式输出3个预设问题，不要包含答案或其他说明文字。"""
        
        return prompt
    
    def generate_preset_questions(self, subtitle_text: str, video_title: str = "", stream: bool = False) -> Dict:
        """
        生成预设问题
        
        Args:
            subtitle_text: 字幕文本
            video_title: 视频标题
            stream: 是否使用流式输出
            
        Returns:
            包含预设问题的字典
        """
        prompt = self.create_preset_questions_prompt(subtitle_text, video_title)
        
        messages = [
            {"role": "system", "content": "你是一个专业的教学设计专家，擅长设计能够引导学习者思考的启发性问题。"},
            {"role": "user", "content": prompt}
        ]
        
        if stream:
            print("正在生成预设问题（流式输出）...\n")
            full_response = ""
            for chunk in self.llm_client.chat_completions_stream(messages):
                print(chunk, end='', flush=True)
                full_response += chunk
            print("\n")
            return self._parse_questions_response(full_response)
        else:
            print("正在生成预设问题...\n")
            response = self.llm_client.chat_completions(messages)
            content = response['choices'][0]['message']['content']
            return self._parse_questions_response(content)
    
    def _parse_questions_response(self, response_text: str) -> Dict:
        """
        解析预设问题响应
        
        Args:
            response_text: LLM返回的文本
            
        Returns:
            解析后的问题字典
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
            return result
        except json.JSONDecodeError as e:
            print(f"警告：无法解析JSON响应: {e}")
            print(f"原始响应：\n{response_text}\n")
            return {
                "questions": [],
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


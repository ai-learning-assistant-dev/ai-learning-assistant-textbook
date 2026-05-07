#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web服务启动脚本
"""

import os
import sys

def check_dependencies():
    """检查依赖"""
    try:
        from flask import Flask, render_template, request, jsonify
    except ImportError:
        print("\n错误: No module named 'flask'\n")
        print("请先安装依赖:\n  pip install -r requirements.txt\n")
        exit(1)


def check_config():
    """检查配置"""
    warnings = []
    
    # 检查cookies.txt
    if not os.path.exists('cookies.txt'):
        # 自动创建cookies.txt模板文件
        with open('cookies.txt', 'w', encoding='utf-8') as f:
            f.write('# Bilibili Cookie 配置文件\n')
            f.write('# 请将下面的"你的SESSDATA值"替换为实际的SESSDATA\n')
            f.write('# \n')
            f.write('# 获取方法：\n')
            f.write('# 1. 登录 bilibili.com\n')
            f.write('# 2. 按F12打开开发者工具\n')
            f.write('# 3. 切换到"应用程序/Application"标签\n')
            f.write('# 4. 左侧选择"Cookie" -> "https://www.bilibili.com"\n')
            f.write('# 5. 找到名为"SESSDATA"的项，复制它的值\n')
            f.write('# 6. 替换下面的内容并保存\n')
            f.write('# \n')
            f.write('SESSDATA=你的SESSDATA值\n')
        warnings.append("✓ 已自动创建 cookies.txt 文件")
        warnings.append("  请编辑该文件，将SESSDATA替换为实际值")
    
    # 检查config目录
    if not os.path.exists('config'):
        os.makedirs('config', exist_ok=True)
    
    # 检查llm_models.json
    if not os.path.exists('config/llm_models.json'):
        warnings.append("⚠ 未找到 config/llm_models.json 文件")
        warnings.append("  请在Web界面中添加模型配置")
        
        # 创建空配置文件
        import json
        with open('config/llm_models.json', 'w', encoding='utf-8') as f:
            json.dump({'models': []}, f, ensure_ascii=False, indent=2)
    
    # 检查app_config.json
    if not os.path.exists('config/app_config.json'):
        # 创建默认配置
        import json
        default_config = {
            'output_directory': 'subtitles',
            'last_selected_model': '',
            'cookies_file': 'cookies.txt',
            'auto_refresh_interval': 2000,
            'web_port': 7200
        }
        with open('config/app_config.json', 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    if warnings:
        print()
        print("配置检查:")
        print("-" * 80)
        for warning in warnings:
            print(warning)
        print("-" * 80)
        print()


def main():
    """主函数"""
    print("=" * 80)
    print("Bilibili视频字幕下载与总结 - Web服务启动器")
    print("=" * 80)
    print()
    
    # 检查依赖
    print("检查依赖...")
    check_dependencies()
    print("✓ 依赖检查通过")
    
    # 检查配置
    print("检查配置...")
    check_config()
    
    # 确保必要的目录存在
    os.makedirs('subtitles', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # 加载配置获取端口
    import json
    config_file = 'config/app_config.json'
    port = 7200
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                port = config.get('web_port', 7200)
        except:
            pass
    
    # 启动Flask应用
    print()
    print("=" * 80)
    print("正在启动Web服务...")
    print("=" * 80)
    print()
    print(f"访问地址: http://127.0.0.1:{port}")
    print(f"或访问: http://localhost:{port}")
    print()
    print("提示:")
    print("  - 在浏览器中打开上述地址访问Web界面")
    print("  - 按 Ctrl+C 可以停止服务")
    print(f"  - 可在 config/app_config.json 中修改端口（当前: {port}）")
    print()
    print("=" * 80)
    print()
    
    # 导入并运行Flask应用
    from app import app
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 80)
        print("👋 服务已停止")
        print("=" * 80)
        sys.exit(0)
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ 启动失败: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)

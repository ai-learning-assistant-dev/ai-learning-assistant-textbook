"""笔记制卡（services/notecard）的用例集。

由 Note2Anki 迁入，覆盖三块「界面上不暴露、但代码仍然保留」的能力：
章节汇总卡、Mock 预置数据、多模型对比。UI 不再暴露它们，
但它们随时可以被后端或脚本调用，用例就是它们的说明书。

跑法：

    python tests/run.py                       # 全部用例
    python tests/run.py -v                    # 带用例名
    python tests/notecard/test_fixtures.py --demo   # 看真实笔记在规则提取下的产出
"""

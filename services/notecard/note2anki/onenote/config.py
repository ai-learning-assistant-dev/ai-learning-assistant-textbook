"""
config.py — JSON 配置加载与校验

用法：用户只需提供 path（文件或目录），其余走默认值。
目录会被自动展开为其中所有 .one 分区文件。
所有路径支持 ${ENV_VAR} 占位符；相对路径按「配置文件所在目录」解析。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ValueError):
    """配置文件缺字段、格式错或路径不存在。"""


def expand_env(value: str) -> str:
    """把 ${VAR} 替换为环境变量；未设置的保持原样，便于报错时看清意图。"""
    return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def _resolve(raw: str, base_dir: Path) -> Path:
    p = Path(expand_env(raw))
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    return p


def discover_one_files(target: Path, recursive: bool = True) -> list[Path]:
    """把一个路径展开成 .one 文件列表。目录则递归收集 *.one。"""
    if target.is_file():
        return [target]
    if target.is_dir():
        pattern = "**/*.one" if recursive else "*.one"
        return sorted(p for p in target.glob(pattern) if p.is_file())
    return []


@dataclass
class ParserConfig:
    """单个来源（文件或目录）的解析配置。"""

    path: Path
    recursive: bool = True
    extract_images: bool = False
    image_dir: Path | None = None
    max_pages_per_file: int | None = None
    min_chars: int = 0
    include_empty_pages: bool = False
    skip_recycle_bin: bool = True

    @classmethod
    def from_dict(cls, raw: dict, base_dir: Path) -> "ParserConfig":
        if "path" not in raw:
            raise ConfigError("配置项缺少必填字段 'path'")

        raw_path = str(raw["path"])
        target = _resolve(raw_path, base_dir)

        if not target.exists():
            raise ConfigError(
                f"path 不存在：{target}\n  （配置里的原始值：{raw_path}）"
            )

        max_pages = raw.get("max_pages_per_file")
        if max_pages is not None and not isinstance(max_pages, int):
            raise ConfigError(
                f"max_pages_per_file 必须是整数，收到 {type(max_pages).__name__}"
            )

        img_raw = raw.get("image_dir")
        image_dir = _resolve(str(img_raw), base_dir) if img_raw else None

        return cls(
            path=target,
            recursive=bool(raw.get("recursive", True)),
            extract_images=bool(raw.get("extract_images", False)),
            image_dir=image_dir,
            max_pages_per_file=max_pages,
            min_chars=int(raw.get("min_chars", 0)),
            include_empty_pages=bool(raw.get("include_empty_pages", False)),
            skip_recycle_bin=bool(raw.get("skip_recycle_bin", True)),
        )

    def files(self) -> list[Path]:
        found = discover_one_files(self.path, self.recursive)
        if self.skip_recycle_bin:
            found = [p for p in found if "RecycleBin" not in p.parts]
        return found


@dataclass
class AppConfig:
    """顶层配置：来源列表 + 输出设置。"""

    sources: list[ParserConfig]
    output_dir: Path
    write_json: bool = True
    write_markdown: bool = False
    fail_fast: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, config_path: str | Path) -> "AppConfig":
        cfg_file = Path(config_path).expanduser()
        if not cfg_file.exists():
            raise ConfigError(f"配置文件不存在：{cfg_file}")

        try:
            raw = json.loads(cfg_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON 格式错误（{cfg_file}）：{exc}") from exc

        if not isinstance(raw, dict):
            raise ConfigError("配置根节点必须是 JSON 对象")

        base_dir = cfg_file.parent.resolve()

        if "sources" in raw:
            source_list = raw["sources"]
            if not isinstance(source_list, list) or not source_list:
                raise ConfigError("'sources' 必须是非空数组")
        elif "path" in raw:
            source_list = [{"path": raw["path"]}]
        else:
            raise ConfigError("配置需要 'sources' 数组，或至少一个顶层 'path'")

        sources = [ParserConfig.from_dict(item, base_dir) for item in source_list]

        out_raw = raw.get("output_dir", "./output")
        output_dir = _resolve(str(out_raw), base_dir)

        return cls(
            sources=sources,
            output_dir=output_dir,
            write_json=bool(raw.get("write_json", True)),
            write_markdown=bool(raw.get("write_markdown", False)),
            fail_fast=bool(raw.get("fail_fast", False)),
            raw=raw,
        )

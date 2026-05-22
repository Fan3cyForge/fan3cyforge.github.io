#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan 3Dlectures/**/*.md and assets/glb/**/*.glb;
將 Fan3cyAssets/2dto3d 內 PNG 轉為 WebP 寫入 assets/images/Sample（quality=90）；
並就地轉換 assets/images/ 內殘留的 .png / .jpg / .jpeg；
最後掃描所有 .webp 寫入 reference-images.json；合併 config.json 與 articles.json。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 共用 WebP 轉換（CursorAI/convert_images.py，路徑錨定 Fan3cyForge 工作區）
_FORGE_ROOT = Path(__file__).resolve().parent.parent.parent
_CURSOR_AI = _FORGE_ROOT / "CursorAI"
if str(_CURSOR_AI) not in sys.path:
    sys.path.insert(0, str(_CURSOR_AI))
from convert_images import (  # noqa: E402
    DEFAULT_DEST_DIR,
    DEFAULT_IMAGES_DIR,
    DEFAULT_QUALITY,
    DEFAULT_SOURCE_DIR,
    convert_images_dir_to_webp,
    convert_source_dir_to_dest_webp,
    iter_raster_image_files,
)


def repo_root() -> Path:
    """fan3cyforge.github.io 倉庫根（scripts/ 的上層）。"""
    return Path(__file__).resolve().parent.parent


def default_images_root() -> Path:
    """GitHub Pages 圖片目錄；與 CursorAI/convert_images.py 預設一致。"""
    return DEFAULT_IMAGES_DIR.resolve()


def strip_yaml_front_matter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def parse_yaml_frontmatter(raw: str) -> dict[str, str]:
    """單行 key: value YAML（教學檔足夠用）。"""
    if not raw.startswith("---"):
        return {}
    end = raw.find("\n---", 3)
    if end == -1:
        return {}
    block = raw[3:end].strip()
    out: dict[str, str] = {}
    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] in "\"'" and val[0] == val[-1]:
            val = val[1:-1]
        out[key] = val
    return out


def infer_category_groups(rel_posix: str, fm: dict[str, str]) -> tuple[str, str]:
    """回傳 (categoryGroup, category 標籤)。"""
    cg = fm.get("categoryGroup") or fm.get("category_group") or ""
    cat = fm.get("category") or ""

    if cg and cat:
        return cg, cat
    if cg and not cat:
        return cg, "一般"
    if cat and not cg:
        if rel_posix.startswith("_posts/"):
            return "文章與資源", cat
        if rel_posix.startswith("3Dlectures/"):
            return "教學", cat
        return "資源", cat

    if rel_posix.startswith("_posts/"):
        return "文章與資源", cat or "筆記"
    if rel_posix.startswith("3Dlectures/"):
        parts = rel_posix.split("/")
        sub = parts[1] if len(parts) > 1 else ""
        label_map = {"3DPrint": "3D 打印教學", "Blender": "Blender 教學"}
        return "教學", cat or label_map.get(sub, sub or "教學")
    return "資源", cat or "一般"


def extract_md_title(path: Path, fm: dict[str, str]) -> str:
    """YAML title > 正文第一行。"""
    if fm.get("title"):
        return fm["title"]
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[warn] cannot read {path}: {e}", file=sys.stderr)
        return path.stem

    body = strip_yaml_front_matter(raw)
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            return title if title else path.stem
        return line if line else path.stem
    return path.stem


def posix_rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def scan_markdown(root: Path, base: Path) -> list[dict]:
    out: list[dict] = []
    if not base.is_dir():
        return out
    for path in sorted(base.rglob("*.md")):
        if path.is_file():
            try:
                mtime = datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds")
            except OSError as e:
                print(f"[warn] stat failed {path}: {e}", file=sys.stderr)
                mtime = ""
            rel = posix_rel(path, root)
            try:
                raw_full = path.read_text(encoding="utf-8")
            except OSError:
                raw_full = ""
            fm = parse_yaml_frontmatter(raw_full)
            title = extract_md_title(path, fm)
            grp, cat = infer_category_groups(rel, fm)
            out.append(
                {
                    "title": title,
                    "path": rel,
                    "category": cat,
                    "categoryGroup": grp,
                    "modified": mtime,
                    "description": "",
                }
            )
    return out


def scan_glb(root: Path, base: Path) -> list[str]:
    if not base.is_dir():
        return []
    paths = sorted(base.rglob("*.glb"))
    return [posix_rel(p, root) for p in paths if p.is_file()]


def scan_webp_images(root: Path, base: Path) -> list[str]:
    """assets/images 內所有 .webp（路徑相對 repo root）。"""
    if not base.is_dir():
        return []
    paths: list[Path] = []
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() == ".webp":
            paths.append(path)
    return [posix_rel(p, root) for p in sorted(paths)]


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[error] invalid JSON {path}: {e}", file=sys.stderr)
        sys.exit(1)


def write_json(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


FALLBACK_GLB_SRC = (
    "https://modelviewer.dev/shared-assets/models/Astronaut.glb"
)


def merge_config(
    root: Path,
    glb_paths: list[str],
    existing: dict | None,
) -> dict:
    base = dict(existing) if isinstance(existing, dict) else {}
    mentor = base.get("mentorGreetings")
    if not isinstance(mentor, dict):
        mentor = {
            "morning": "啟動程式",
            "afternoon": "教學鍛造模式",
            "evening": "超頻作業模式",
        }

    mv_prev = base.get("modelViewer")
    mv: dict = dict(mv_prev) if isinstance(mv_prev, dict) else {}

    web_glbs = ["/" + p.replace("\\", "/") for p in glb_paths]
    mv["availableGlbs"] = web_glbs

    if glb_paths:
        mv["src"] = "/" + glb_paths[0].replace("\\", "/")
    else:
        mv.setdefault("src", FALLBACK_GLB_SRC)

    mv.setdefault("enabled", True)
    mv.setdefault("environmentImage", "https://modelviewer.dev/shared-assets/environments/moon_1k.hdr")
    mv.setdefault("shadowIntensity", 1)
    mv.setdefault("parts", [])

    out = {
        "mentorGreetings": mentor,
        "modelViewer": mv,
        "localModelNote": base.get(
            "localModelNote",
            "sync_assets.py 會掃描 assets/glb/；將 .glb 放入該目錄後執行 npm run sync。GitHub Pages 路徑區分大小寫。",
        ),
        "syncMeta": {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "glbCount": len(glb_paths),
        },
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync articles.json and config.json from repo assets.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=f"2dto3d PNG source (default: {DEFAULT_SOURCE_DIR})",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=None,
        help=f"Sample WebP destination (default: {DEFAULT_DEST_DIR})",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help=f"In-place WebP under assets/images (default: {DEFAULT_IMAGES_DIR})",
    )
    args = parser.parse_args()
    root = (args.root or repo_root()).resolve()

    md_roots = [root / "3Dlectures"]
    posts = root / "_posts"
    if posts.is_dir():
        md_roots.append(posts)
    glb_root = root / "assets" / "glb"

    articles: list[dict] = []
    for d in md_roots:
        articles.extend(scan_markdown(root, d))

    order = {"教學": 0, "文章與資源": 1, "資源": 2}
    articles.sort(
        key=lambda x: (
            order.get(x.get("categoryGroup") or "", 99),
            (x.get("category") or "").lower(),
            x["path"].lower(),
        )
    )

    glb_paths = scan_glb(root, glb_root)

    source_dir = (args.source_dir or DEFAULT_SOURCE_DIR).resolve()
    dest_dir = (args.dest_dir or DEFAULT_DEST_DIR).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_pending = iter_raster_image_files(source_dir) if source_dir.is_dir() else []
    print(
        f"[..] 2dto3d→Sample：{source_dir} → {dest_dir}（{len(src_pending)} 張, q={DEFAULT_QUALITY}）…"
    )
    conv_ok, conv_fail = (
        convert_source_dir_to_dest_webp(
            source_dir, dest_dir, quality=DEFAULT_QUALITY, delete_source=False
        )
        if src_pending
        else (0, 0)
    )
    print(f"[ok] 2dto3d→Sample WebP：成功 {conv_ok}，失敗 {conv_fail}")

    images_root = (args.images_dir or default_images_root()).resolve()
    if not images_root.is_dir():
        images_root = root / "assets" / "images"
    inline_pending = iter_raster_image_files(images_root) if images_root.is_dir() else []
    if inline_pending:
        print(f"[..] 就地 WebP：{images_root}（{len(inline_pending)} 張）…")
        i_ok, i_fail = convert_images_dir_to_webp(images_root, quality=DEFAULT_QUALITY)
        conv_ok += i_ok
        conv_fail += i_fail
        print(f"[ok] 就地 WebP：成功 {i_ok}，失敗 {i_fail}")

    webp_scan_root = images_root if images_root.is_dir() else (root / "assets" / "images")
    webp_rels = scan_webp_images(root, webp_scan_root)
    web_refs = ["/" + p.replace("\\", "/") for p in webp_rels]

    articles_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "markdownArticles": articles,
    }

    cfg_path = root / "config.json"
    merged = merge_config(root, glb_paths, load_json(cfg_path))

    write_json(root / "articles.json", articles_payload)
    write_json(cfg_path, merged)

    ref_img_path = root / "reference-images.json"
    write_json(
        ref_img_path,
        {
            "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "images": web_refs,
        },
    )

    print(f"[ok] articles: {len(articles)} markdown file(s)")
    print(f"[ok] glb: {len(glb_paths)} file(s) under assets/glb/")
    print(f"[ok] reference images: {len(web_refs)} .webp under assets/images/")
    if glb_paths:
        print(f"     modelViewer.src -> {merged['modelViewer']['src']}")
    else:
        print(f"     modelViewer.src -> fallback CDN (no local .glb)")
    print(f"[ok] wrote {root / 'articles.json'}")
    print(f"[ok] wrote {cfg_path}")
    print(f"[ok] wrote {ref_img_path}")


if __name__ == "__main__":
    main()

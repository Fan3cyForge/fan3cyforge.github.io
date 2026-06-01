#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan 3Dlectures/**/*.md and assets/glb/**/*.glb;
將 Fan3cyAssets/2dto3d 內 PNG 轉為 WebP 寫入 assets/images/Sample（quality=90）；
(新增) 僅當對應的 .glb 存在於 simple 目錄時，才進行轉換與歸檔；
並就地轉換 assets/images/ 內殘留的 .png / .jpg / .jpeg；
最後掃描所有 .webp 寫入 reference-images.json；合併 config.json 與 articles.json。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

# 本地常數
DEFAULT_QUALITY = 90
DEFAULT_IMAGES_DIR = Path(__file__).resolve().parent.parent / "assets" / "images"


def convert_source_dir_to_dest_webp(src_dir: Path, dest_dir: Path, glb_dir: Path, quality: int = 90):
    """將來源資料夾內的 PNG 轉成 WebP，前提是對應的 GLB 必須存在"""
    if not src_dir.is_dir():
        print(f"[warn] 來源路徑不存在: {src_dir}")
        return 0, 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok, fail = 0, 0
    for p in src_dir.glob("*.png"):
        # Validation Check: 檢查對應的 .glb 是否存在
        glb_file = glb_dir / (p.stem + ".glb")
        if not glb_file.is_file():
            continue # 如果冇 3D 模型，直接跳過，唔轉 WebP
            
        try:
            img = Image.open(p)
            out_path = dest_dir / (p.stem + ".webp")
            img.save(out_path, "WEBP", quality=quality)
            ok += 1
        except Exception as e:
            print(f"[error] 轉換失敗 {p.name}: {e}")
            fail += 1
    return ok, fail


def convert_images_dir_to_webp(images_dir: Path, quality: int = 90):
    """就地轉換資料夾內所有殘留的 PNG/JPG/JPEG 為 WebP"""
    if not images_dir.is_dir():
        return 0, 0
    ok, fail = 0, 0
    for ext in ["*.png", "*.jpg", "*.jpeg"]:
        for p in images_dir.rglob(ext):
            try:
                img = Image.open(p)
                out_path = p.with_suffix(".webp")
                img.save(out_path, "WEBP", quality=quality)
                ok += 1
            except Exception as e:
                print(f"[error] 轉換失敗 {p}: {e}", file=sys.stderr)
                fail += 1
    return ok, fail


def count_raster_images(directory: Path) -> int:
    """統計目錄內待轉換的點陣圖數量（含子目錄）。"""
    if not directory.is_dir():
        return 0
    total = 0
    for ext in ("*.png", "*.jpg", "*.jpeg"):
        total += sum(1 for _ in directory.rglob(ext))
    return total


def count_source_pngs(src_dir: Path) -> int:
    """統計來源目錄頂層 PNG 數量。"""
    if not src_dir.is_dir():
        return 0
    return sum(1 for _ in src_dir.glob("*.png"))


def repo_root() -> Path:
    """fan3cyforge.github.io 倉庫根（scripts/ 的上層）。"""
    return Path(__file__).resolve().parent.parent


def default_images_root() -> Path:
    """GitHub Pages 圖片目錄。"""
    return DEFAULT_IMAGES_DIR.resolve()


# Requirement 1: 2D/3D Asset Pipeline 固定來源與輸出絕對路徑
PINNED_SOURCE_DIR = Path(
    r"C:\Users\User\Desktop\Fan3cyForge\Fan3cyAssets\assets\images\2dto3d"
)
PINNED_DEST_DIR = Path(
    r"C:\Users\User\Desktop\Fan3cyForge\fan3cyforge.github.io\assets\images\Sample"
)
PINNED_DONE_PNG_DIR = Path(
    r"C:\Users\User\Desktop\Fan3cyForge\Fan3cyAssets\assets\images\已完成PNG"
)
# 新增: Web 端的 GLB 目錄，用作閘口驗證
PINNED_GLB_SIMPLE_DIR = Path(
    r"C:\Users\User\Desktop\Fan3cyForge\fan3cyforge.github.io\assets\glb\simple"
)

# Requirement 3: 首頁 3D 預覽僅保留 kimchi/mochi
CURATED_PREVIEW_GLB_WEB_PATHS = ["/assets/glb/kimchi.glb", "/assets/glb/mochi.glb"]


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
    out: list[str] = []
    for p in paths:
        if not p.is_file():
            continue
        rel = posix_rel(p, root)
        # Requirement 3: 排除 assets/glb/simple/ 內檔案
        if rel.startswith("assets/glb/simple/"):
            continue
        out.append(rel)
    return out


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

    # Requirement 3: 強制定義首頁可預覽模型，不依賴掃描結果
    mv["availableGlbs"] = list(CURATED_PREVIEW_GLB_WEB_PATHS)
    mv["src"] = "/assets/glb/kimchi.glb"

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
        help="(ignored) pinned by pipeline requirement",
    )
    parser.add_argument(
        "--dest-dir",
        type=Path,
        default=None,
        help="(ignored) pinned by pipeline requirement",
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

    source_dir = PINNED_SOURCE_DIR.resolve()
    dest_dir = PINNED_DEST_DIR.resolve()
    glb_simple_dir = PINNED_GLB_SIMPLE_DIR.resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    src_pending = count_source_pngs(source_dir)
    print(
        f"[..] 2dto3d→Sample：{source_dir} → {dest_dir}（{src_pending} 張, 驗證 GLB, q={DEFAULT_QUALITY}）…"
    )
    
    # 傳入 glb_simple_dir 作為驗證
    conv_ok, conv_fail = (
        convert_source_dir_to_dest_webp(source_dir, dest_dir, glb_simple_dir, quality=DEFAULT_QUALITY)
        if src_pending
        else (0, 0)
    )
    print(f"[ok] 2dto3d→Sample WebP：成功轉出 {conv_ok} 張，失敗 {conv_fail}")

    # === 增強功能：自動歸檔已處理的原始 PNG (同樣加入 GLB 驗證) ===
    if PINNED_SOURCE_DIR.is_dir():
        PINNED_DONE_PNG_DIR.mkdir(parents=True, exist_ok=True)
        moved_count = 0
        for p in PINNED_SOURCE_DIR.glob("*.png"):
            # Validation Check: GLB 存在先准搬走
            glb_file = glb_simple_dir / (p.stem + ".glb")
            if not glb_file.is_file():
                continue
                
            try:
                dest_file = PINNED_DONE_PNG_DIR / p.name
                # 如果目標資料夾已有同名檔案，直接覆蓋歸檔
                shutil.move(str(p), str(dest_file))
                moved_count += 1
            except Exception as e:
                print(f"[error] 歸檔搬移 PNG 失敗 {p.name}: {e}")
        if moved_count > 0:
            print(f"[ok] Archiving：已將 {moved_count} 張生成成功的原始 PNG 搬移至 已完成PNG 資料夾")

    images_root = (args.images_dir or default_images_root()).resolve()
    if not images_root.is_dir():
        images_root = root / "assets" / "images"
    inline_pending = count_raster_images(images_root)
    if inline_pending:
        print(f"[..] 就地 WebP：{images_root}（{inline_pending} 張）…")
        i_ok, i_fail = convert_images_dir_to_webp(images_root, quality=DEFAULT_QUALITY)
        conv_ok += i_ok
        conv_fail += i_fail
        print(f"[ok] 就地 WebP：成功 {i_ok}，失敗 {i_fail}")

    # 強制鎖定只掃描 Sample 目錄（排除 LOGO/kimchi/mochi 等 assets/images 根目錄圖片）
    sample_dir = (DEFAULT_IMAGES_DIR / "Sample").resolve()
    resolved_repo_root = root.resolve()
    web_refs: list[str] = []
    if sample_dir.is_dir():
        for p in sorted(sample_dir.rglob("*.webp")):
            if not p.is_file():
                continue
            try:
                rel_path = p.resolve().relative_to(resolved_repo_root)
                web_refs.append(f"/{rel_path.as_posix()}")
            except ValueError:
                pass

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
    print(f"[ok] reference images: {len(web_refs)} .webp under assets/images/Sample/")
    if glb_paths:
        print(f"     modelViewer.src -> {merged['modelViewer']['src']}")
    else:
        print(f"     modelViewer.src -> fallback CDN (no local .glb)")
    print(f"[ok] wrote {root / 'articles.json'}")
    print(f"[ok] wrote {cfg_path}")
    print(f"[ok] wrote {ref_img_path}")


if __name__ == "__main__":
    main()

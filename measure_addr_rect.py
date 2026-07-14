#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器头部图片地址栏区域测量工具。

用法:
  python measure_addr_rect.py [图片路径] [--config CONFIG路径]

操作:
  1. 打开浏览器头部模板图片
  2. 点击【地址栏左上角】
  3. 点击【地址栏右下角】
  4. 查看自动计算的比例 [x1, y1, x2, y2]
  5. 点击"复制到剪贴板"或"写入 config"

不带参数时默认打开 templates/browser_chrome_header.png。
"""

import argparse
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    print("错误: 需要 Pillow。请运行: pip install pillow")
    sys.exit(1)


def update_config_content(content: str, result: list) -> str:
    """在 screenshot 段内更新地址栏区域，并保留现有缩进。"""
    field_text = f"browser_chrome_addr_rect: {result}"
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("browser_chrome_addr_rect:"):
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = indent + field_text
            break
    else:
        insert_at = next(
            (i for i, line in enumerate(lines)
             if line.strip().startswith("add_browser_chrome:")),
            None,
        )
        if insert_at is None:
            lines.extend(["", "screenshot:", "  " + field_text])
        else:
            indent = lines[insert_at][:len(lines[insert_at]) - len(lines[insert_at].lstrip())]
            lines.insert(insert_at + 1, indent + field_text)
    return "\n".join(lines).rstrip("\n") + "\n"


class MeasureApp:
    def __init__(self, root, img_path, config_path):
        self.root = root
        self.img_path = img_path
        self.config_path = config_path
        self.points = []          # 已记录的点(原图坐标)
        self.rect_id = None       # 选区矩形 canvas id
        self.dot_ids = []         # 点标记 canvas id

        # 加载原图
        try:
            self.orig_img = Image.open(img_path).convert("RGB")
        except Exception as e:
            messagebox.showerror("打开图片失败", f"{img_path}\n{e}")
            root.destroy()
            return

        self.orig_w, self.orig_h = self.orig_img.size

        # 计算显示缩放(适应屏幕)
        sw = root.winfo_screenwidth() - 60
        sh = root.winfo_screenheight() - 200
        scale = min(1.0, sw / self.orig_w, sh / self.orig_h)
        self.scale = scale
        disp_w = max(1, int(self.orig_w * scale))
        disp_h = max(1, int(self.orig_h * scale))
        self.disp_w, self.disp_h = disp_w, disp_h

        self.disp_img = self.orig_img.resize((disp_w, disp_h), Image.LANCZOS)

        # UI
        root.title(f"测量地址栏区域 — {os.path.basename(img_path)} ({self.orig_w}×{self.orig_h})")
        root.geometry(f"{disp_w + 40}x{disp_h + 140}")

        # 顶部提示
        top = ttk.Frame(root, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)
        self.hint = ttk.Label(top, text="👉 请点击【地址栏左上角】", font=("Microsoft YaHei", 11))
        self.hint.pack(anchor=tk.W)

        # 画布
        self.canvas = tk.Canvas(root, width=disp_w, height=disp_h, bg="#888", cursor="crosshair")
        self.canvas.pack(side=tk.TOP, padx=20, pady=5)
        self.tk_img = ImageTk.PhotoImage(self.disp_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)

        # 底部:坐标 + 按钮
        bot = ttk.Frame(root, padding=8)
        bot.pack(side=tk.BOTTOM, fill=tk.X)
        self.coord_label = ttk.Label(bot, text="原图尺寸: 0 × 0", font=("Consolas", 10))
        self.coord_label.pack(anchor=tk.W)
        self.result_label = ttk.Label(bot, text="addr_rect: (未测量)", font=("Consolas", 10), foreground="blue")
        self.result_label.pack(anchor=tk.W, pady=(4, 4))

        btns = ttk.Frame(bot)
        btns.pack(fill=tk.X)
        self.btn_copy = ttk.Button(btns, text="复制 YAML", command=self.copy_result, state=tk.DISABLED)
        self.btn_copy.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_write = ttk.Button(btns, text="写入 config", command=self.write_config, state=tk.DISABLED)
        self.btn_write.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_reset = ttk.Button(btns, text="重新测量", command=self.reset)
        self.btn_reset.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btns, text="退出", command=root.destroy).pack(side=tk.RIGHT)

        # 当前鼠标位置(显示用)
        self.mouse_xy = None

    def on_motion(self, event):
        # 实时显示鼠标对应的原图坐标
        ox = event.x / self.scale
        oy = event.y / self.scale
        self.mouse_xy = (ox, oy)
        self.coord_label.config(
            text=f"原图尺寸: {self.orig_w} × {self.orig_h}    鼠标: ({ox:.0f}, {oy:.0f})"
        )

    def on_click(self, event):
        ox = event.x / self.scale
        oy = event.y / self.scale
        ox = max(0, min(self.orig_w, ox))
        oy = max(0, min(self.orig_h, oy))
        self.points.append((ox, oy))

        # 画点
        r = 6
        dot = self.canvas.create_oval(
            event.x - r, event.y - r, event.x + r, event.y + r,
            fill="red", outline="white", width=2,
        )
        self.dot_ids.append(dot)

        if len(self.points) == 1:
            self.hint.config(text="👉 请点击【地址栏右下角】")
        elif len(self.points) >= 2:
            x1, y1 = self.points[0]
            x2, y2 = self.points[1]
            # 画矩形选区(屏幕坐标)
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            sx1 = x1 * self.scale
            sy1 = y1 * self.scale
            sx2 = x2 * self.scale
            sy2 = y2 * self.scale
            self.rect_id = self.canvas.create_rectangle(
                sx1, sy1, sx2, sy2, outline="#00dd00", width=3
            )
            self.show_result(x1, y1, x2, y2)
            self.hint.config(text='✅ 已测量。可复制或写入 config,或点击"重新测量"重选。')
            self.btn_copy.config(state=tk.NORMAL)
            self.btn_write.config(state=tk.NORMAL)

    def show_result(self, x1, y1, x2, y2):
        # 归一化(确保 x1<x2, y1<y2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        rx1 = x1 / self.orig_w
        ry1 = y1 / self.orig_h
        rx2 = x2 / self.orig_w
        ry2 = y2 / self.orig_h
        self.result = [round(rx1, 4), round(ry1, 4), round(rx2, 4), round(ry2, 4)]
        yaml_line = f"browser_chrome_addr_rect: {self.result}"
        self.result_label.config(text=f"addr_rect: {yaml_line}")

    def reset(self):
        self.points = []
        for d in self.dot_ids:
            self.canvas.delete(d)
        self.dot_ids = []
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self.btn_copy.config(state=tk.DISABLED)
        self.btn_write.config(state=tk.DISABLED)
        self.result_label.config(text="addr_rect: (未测量)")
        self.hint.config(text="👉 请点击【地址栏左上角】")

    def copy_result(self):
        if not hasattr(self, "result"):
            return
        text = f"browser_chrome_addr_rect: {self.result}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.result_label.config(text=f"已复制 ✓  {text}")

    def write_config(self):
        if not hasattr(self, "result"):
            return
        if not self.config_path or not os.path.exists(self.config_path):
            # 让用户选
            from tkinter import filedialog
            picked = filedialog.askopenfilename(
                title="选择 screenshot-config.yaml",
                filetypes=[("YAML", "*.yaml *.yml"), ("All", "*.*")],
                initialdir=".",
            )
            if not picked:
                return
            self.config_path = picked

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("读取 config 失败", str(e))
            return

        new_content = update_config_content(content, self.result)
        try:
            tmp_path = self.config_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            os.replace(tmp_path, self.config_path)
        except Exception as e:
            messagebox.showerror("写入 config 失败", str(e))
            return

        messagebox.showinfo("成功", f"已写入 {self.config_path}\n\n{new_line}")


def main():
    parser = argparse.ArgumentParser(description="测量浏览器头部图片的地址栏区域比例")
    parser.add_argument("image", nargs="?", default="templates/browser_chrome_header.png",
                        help="浏览器头部图片路径(默认 templates/browser_chrome_header.png)")
    parser.add_argument("--config", default="templates/screenshot-config.yaml",
                        help="screenshot-config.yaml 路径(用于一键写入)")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"错误: 图片不存在: {args.image}")
        print("请先截取浏览器头部图片,保存后重试。")
        sys.exit(1)

    root = tk.Tk()
    app = MeasureApp(root, args.image, args.config)
    root.mainloop()


if __name__ == "__main__":
    main()

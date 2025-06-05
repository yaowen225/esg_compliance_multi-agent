import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import time
import xml.etree.ElementTree as ET # Import for XML parsing
import json
import re
import sys
import argparse
from pathlib import Path
import warnings
from all_material.extract_standards.gri_to_json_converter import GRIMarkdownToJsonConverter
from markitdown import MarkItDown
import shutil
from all_material.retrieve_reports.retrivel import setup_collection, add_esg_report_to_db, process_gri_standards, OpenAIEmbeddingFunction
from all_material.check_compliance.esg_compliance_agents import ComplianceAnalysisAgent, ResultIntegrationAgent, setup_database
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_core import CancellationToken
from dotenv import load_dotenv, find_dotenv
from typing import Sequence, Dict, Any, List, Tuple
import aiomysql, asyncio
import pandas as pd
import chromadb

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("檔案處理應用程式")
        self.geometry("1000x700")

        # 設定網格佈局
        self.grid_rowconfigure(0, weight=1) # Row 0: 頂部，包含檔案選擇區
        self.grid_rowconfigure(1, weight=0) # Row 1: 中間，用於放置執行進度標籤和按鈕組 (不擴展)
        self.grid_rowconfigure(2, weight=1) # Row 2: 底部，用於放置執行進度區的文本框
        self.grid_columnconfigure(0, weight=1) # Column 0: 檔案選擇區 1 和執行進度區的左側
        self.grid_columnconfigure(1, weight=1) # Column 1: 檔案選擇區 2 和執行進度區的右側

        # 設定高亮標籤樣式 (用於單擊高亮)
        self.highlight_tag_name = "highlighted_line_tag"
        self.highlight_bg_color = "#4A7C9F" # 高亮後的背景色 (比選取色更柔和，或者更顯眼)
        self.highlight_fg_color = "#FFFFFF" # 高亮後的文字顏色

        # 結果檔案的儲存目錄
        self.results_output_dir = os.path.join(os.getcwd(), "data/result")
        os.makedirs(self.results_output_dir, exist_ok=True) # 確保目錄存在

        # 檔案選擇區域 1
        self.frame_files1 = ctk.CTkFrame(self, fg_color="transparent")
        # 調整 grid 位置到 column 0
        self.frame_files1.grid(row=0, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")
        self.frame_files1.grid_rowconfigure(0, weight=0) # Label row
        self.frame_files1.grid_rowconfigure(1, weight=0) # Buttons row
        self.frame_files1.grid_rowconfigure(2, weight=1) # Textbox row
        self.frame_files1.grid_columnconfigure(0, weight=1)

        self.label_files1 = ctk.CTkLabel(self.frame_files1, text="選擇準則檔案", font=ctk.CTkFont(size=16, weight="bold"))
        self.label_files1.grid(row=0, column=0, pady=(0, 5))

        # Buttons for Area 1
        self.frame_buttons1 = ctk.CTkFrame(self.frame_files1, fg_color="transparent")
        self.frame_buttons1.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        self.frame_buttons1.grid_columnconfigure((0, 1, 2), weight=1)

        self.button_add_files1 = ctk.CTkButton(self.frame_buttons1, text="新增檔案", command=lambda: self.add_files(1))
        self.button_add_files1.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.button_remove_files1 = ctk.CTkButton(self.frame_buttons1, text="刪除選定", command=lambda: self.remove_selected_files(1))
        self.button_remove_files1.grid(row=0, column=1, padx=5, sticky="ew")

        self.button_clear_files1 = ctk.CTkButton(self.frame_buttons1, text="刪除全部", command=lambda: self.clear_all_files(1))
        self.button_clear_files1.grid(row=0, column=2, padx=(5, 0), sticky="ew")

        self.listbox_files1 = ctk.CTkTextbox(self.frame_files1, wrap="none", activate_scrollbars=True, height=200)
        self.listbox_files1.grid(row=2, column=0, sticky="nsew")
        self.listbox_files1.configure(state="disabled") # 初始設定為禁用，只能透過按鈕操作

        # 定義高亮標籤 (用於單擊高亮)
        self.listbox_files1.tag_config(self.highlight_tag_name,
                                        background=self.highlight_bg_color,
                                        foreground=self.highlight_fg_color)
        # 綁定單擊事件
        self.listbox_files1.bind("<Button-1>", lambda event, area_id=1: self._on_line_click(event, area_id))

        self.selected_files1 = []

        # 檔案選擇區域 2
        self.frame_files2 = ctk.CTkFrame(self, fg_color="transparent")
        # 調整 grid 位置到 column 1
        self.frame_files2.grid(row=0, column=1, padx=(10, 20), pady=(20, 10), sticky="nsew")
        self.frame_files2.grid_rowconfigure(0, weight=0) # Label row
        self.frame_files2.grid_rowconfigure(1, weight=0) # Buttons row
        self.frame_files2.grid_rowconfigure(2, weight=1) # Textbox row
        self.frame_files2.grid_columnconfigure(0, weight=1)

        self.label_files2 = ctk.CTkLabel(self.frame_files2, text="選擇報告檔案", font=ctk.CTkFont(size=16, weight="bold"))
        self.label_files2.grid(row=0, column=0, pady=(0, 5))

        # Buttons for Area 2
        self.frame_buttons2 = ctk.CTkFrame(self.frame_files2, fg_color="transparent")
        self.frame_buttons2.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        self.frame_buttons2.grid_columnconfigure((0, 1, 2), weight=1)

        self.button_add_files2 = ctk.CTkButton(self.frame_buttons2, text="新增檔案", command=lambda: self.add_files(2))
        self.button_add_files2.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.button_remove_files2 = ctk.CTkButton(self.frame_buttons2, text="刪除選定", command=lambda: self.remove_selected_files(2))
        self.button_remove_files2.grid(row=0, column=1, padx=5, sticky="ew")

        self.button_clear_files2 = ctk.CTkButton(self.frame_buttons2, text="刪除全部", command=lambda: self.clear_all_files(2))
        self.button_clear_files2.grid(row=0, column=2, padx=(5, 0), sticky="ew")

        self.listbox_files2 = ctk.CTkTextbox(self.frame_files2, wrap="none", activate_scrollbars=True, height=200)
        self.listbox_files2.grid(row=2, column=0, sticky="nsew")
        self.listbox_files2.configure(state="disabled") # 初始設定為禁用

        # 定義高亮標籤 (用於單擊高亮)
        self.listbox_files2.tag_config(self.highlight_tag_name,
                                        background=self.highlight_bg_color,
                                        foreground=self.highlight_fg_color)
        # 綁定單擊事件
        self.listbox_files2.bind("<Button-1>", lambda event, area_id=2: self._on_line_click(event, area_id))

        self.selected_files2 = []

        # --- 執行進度標籤和按鈕區域 (移到 row 1) ---
        self.frame_progress_controls = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_progress_controls.grid(row=1, column=0, columnspan=2, padx=20, pady=(10, 10), sticky="ew")
        # 配置列權重以實現左對齊的標籤和右對齊的按鈕
        self.frame_progress_controls.grid_columnconfigure(0, weight=1) # 讓進度標籤所在的列擴展
        self.frame_progress_controls.grid_columnconfigure((1, 2, 3), weight=0) # 按鈕的列不擴展

        # 執行進度標籤 (靠左)
        self.label_progress = ctk.CTkLabel(self.frame_progress_controls, text="執行進度", font=ctk.CTkFont(size=16, weight="bold"))
        self.label_progress.grid(row=0, column=0, sticky="w", padx=20) # 靠左對齊

        # 啟動按鈕
        self.button_start_process = ctk.CTkButton(self.frame_progress_controls, text="啟動處理程序", command=self.start_process_threaded)
        self.button_start_process.grid(row=0, column=1, padx=(0, 10), sticky="e")

        # 顯示結果按鈕
        self.button_show_results = ctk.CTkButton(self.frame_progress_controls, text="顯示結果", command=self.show_results_window)
        self.button_show_results.grid(row=0, column=2, padx=(0, 10), sticky="e")
        self.button_show_results.configure(state="disabled") # 初始禁用

        # 開啟結果目錄按鈕
        self.button_open_results_folder = ctk.CTkButton(self.frame_progress_controls, text="開啟結果目錄", command=self.open_results_folder)
        self.button_open_results_folder.grid(row=0, column=3, padx=(0, 0), sticky="e")
        self.button_open_results_folder.configure(state="disabled") # 初始禁用

        # --- 執行進度顯示區域 (文本框) ---
        # 這個文本框現在獨自佔據了 row 2
        self.textbox_progress = ctk.CTkTextbox(self, wrap="word", activate_scrollbars=True, height=150)
        self.textbox_progress.grid(row=2, column=0, columnspan=2, padx=20, pady=(10, 20), sticky="nsew")
        self.textbox_progress.configure(state="disabled") # 初始為禁用

    def add_files(self, area_id):
        """開啟檔案選擇對話框，將選擇的檔案新增到對應的區域"""
        file_paths = filedialog.askopenfilenames()
        if file_paths:
            if area_id == 1:
                current_files = self.selected_files1
                listbox = self.listbox_files1
            else:
                current_files = self.selected_files2
                listbox = self.listbox_files2

            for path in file_paths:
                if path not in current_files:
                    current_files.append(path)
            self._update_file_listbox(area_id)
            self._clear_all_tags(area_id) # 添加檔案後清除所有高亮和選取

    def remove_selected_files(self, area_id):
        if area_id == 1:
            listbox = self.listbox_files1
            current_files = self.selected_files1
        else:
            listbox = self.listbox_files2
            current_files = self.selected_files2

        try:
            line_start_index = listbox.index("insert linestart")
            line_end_index = listbox.index("insert lineend")
            selected_text = listbox.get(line_start_index, line_end_index).strip()

            if selected_text:
                if selected_text in current_files:
                    current_files.remove(selected_text)
                    self._update_file_listbox(area_id)
                    messagebox.showinfo("完成", f"檔案 '{os.path.basename(selected_text)}' 已刪除。")
                    self._clear_all_tags(area_id) # 刪除後清除所有高亮和選取
                else:
                    messagebox.showwarning("警告", "選取的內容不是有效的檔案路徑。")
            else:
                messagebox.showwarning("警告", "請先選取要刪除的檔案行。")
        except: # Catch any error that might occur if no line is selected or if "insert" is invalid
            messagebox.showwarning("警告", "請先選取要刪除的檔案行。")

    def _update_file_listbox(self, area_id):
        """更新對應區域的檔案列表顯示"""
        if area_id == 1:
            listbox = self.listbox_files1
            files = self.selected_files1
        else:
            listbox = self.listbox_files2
            files = self.selected_files2

        listbox.configure(state="normal") # 允許寫入
        listbox.delete("1.0", "end") # 清空現有內容
        for file_path in files:
            listbox.insert("end", file_path + "\n")
        listbox.configure(state="disabled") # 重新設定為禁用
        self._clear_all_tags(area_id)

    def _on_line_click(self, event, area_id):
        """處理 Textbox 的單擊事件，高亮點擊的行"""
        if area_id == 1:
            listbox = self.listbox_files1
        else:
            listbox = self.listbox_files2

        listbox.configure(state="normal") # 暫時啟用，才能操作標籤

        # 清除所有現有的高亮和選取標籤
        listbox.tag_remove(self.highlight_tag_name, "1.0", "end")
        # 清除 Tkinter 內建的選取
        listbox.tag_remove("sel", "1.0", "end")


        # 獲取點擊位置的行號 (例如 "3.0" 代表第3行第0個字元)
        index = listbox.index(f"@{event.x},{event.y}")
        line_start = index.split('.')[0] + ".0"
        line_end = index.split('.')[0] + ".end"

        # 獲取點擊行的內容
        clicked_line_content = listbox.get(line_start, line_end).strip()

        # 只有當點擊的行有內容時才進行高亮
        if clicked_line_content:
            listbox.tag_add(self.highlight_tag_name, line_start, line_end)

        listbox.configure(state="disabled") # 重新禁用

    def _clear_all_tags(self, area_id):
        """清除指定區域 Textbox 上的所有自定義和內建標籤"""
        if area_id == 1:
            listbox = self.listbox_files1
        else:
            listbox = self.listbox_files2

        listbox.configure(state="normal")
        listbox.tag_remove(self.highlight_tag_name, "1.0", "end")
        # 清除 Tkinter 內建的選取標籤
        listbox.tag_remove("sel", "1.0", "end")
        listbox.configure(state="disabled")

    def clear_all_files(self, area_id):
        """清空指定區域的所有檔案"""
        if area_id == 1:
            if not self.selected_files1:
                messagebox.showinfo("資訊", "區域 1 沒有檔案可供刪除。")
                return
            response = messagebox.askyesno("確認", "您確定要清空區域 1 的所有檔案嗎？")
            if response:
                self.selected_files1.clear()
                self._update_file_listbox(1)
                messagebox.showinfo("完成", "區域 1 的所有檔案已清空。")
                self._clear_all_tags(1) # 清空後清除所有高亮和選取
        else:
            if not self.selected_files2:
                messagebox.showinfo("資訊", "區域 2 沒有檔案可供刪除。")
                return
            response = messagebox.askyesno("確認", "您確定要清空區域 2 的所有檔案嗎？")
            if response:
                self.selected_files2.clear()
                self._update_file_listbox(2)
                messagebox.showinfo("完成", "區域 2 的所有檔案已清空。")
                self._clear_all_tags(2) # 清空後清除所有高亮和選取

    def append_progress_message(self, message):
        """
        將傳入的文字加到執行進度顯示區域的最下方。
        這個函式設計為可以在任何執行緒中安全呼叫。
        """
        # 使用 self.after 將更新操作排程到主執行緒，避免多執行緒操作 Tkinter 介面錯誤
        self.after(0, lambda: self._append_message_to_textbox(self.textbox_progress, message))

    def _append_message_to_textbox(self, textbox_widget, message):
        """實際將訊息追加到指定 Textbox 的內部函式 (在主執行緒執行)"""
        textbox_widget.configure(state="normal") # 允許寫入
        textbox_widget.insert("end", message + "\n")
        textbox_widget.see("end") # 自動捲動到最底部
        textbox_widget.configure(state="disabled") # 重新設定為禁用

    def start_process_threaded(self):
        """啟動處理程序，使用多執行緒避免阻塞 GUI"""
        if not self.selected_files1 or not self.selected_files2:
            messagebox.showwarning("警告", "請至少選擇一份準則和一份報告書。")
            return

        # 清空之前的執行進度
        self.textbox_progress.configure(state="normal")
        self.textbox_progress.delete("1.0", "end")
        self.textbox_progress.configure(state="disabled")

        # 禁用按鈕以避免重複點擊
        self.button_start_process.configure(state="disabled")
        self.button_add_files1.configure(state="disabled")
        self.button_remove_files1.configure(state="disabled")
        self.button_clear_files1.configure(state="disabled")
        self.button_add_files2.configure(state="disabled")
        self.button_remove_files2.configure(state="disabled")
        self.button_clear_files2.configure(state="disabled")
        self.button_show_results.configure(state="disabled") # 禁用結果按鈕
        self.button_open_results_folder.configure(state="disabled") # 禁用開啟目錄按鈕


        # 創建一個新的執行緒來運行耗時的操作
        thread = threading.Thread(target=self._run_long_process)
        thread.start()

    def move_file_to_folder(self, source_file_path: str, destination_folder_path: str) -> bool:
        if not os.path.exists(source_file_path):
            self.append_progress_message(f"錯誤: 來源檔案不存在 - {source_file_path}")
            return False

        if not os.path.isdir(destination_folder_path):
            self.append_progress_message(f"錯誤: 目標資料夾不存在或不是一個資料夾 - {destination_folder_path}")
            # 如果目標資料夾不存在，可以選擇在這裡創建它，但為了安全預設不自動創建
            # os.makedirs(destination_folder_path, exist_ok=True)
            # self.append_progress_message(f"已創建目標資料夾: {destination_folder_path}")
            return False

        try:
            # 構建目標檔案的路徑
            file_name = os.path.basename(source_file_path)
            destination_file_path = os.path.join(destination_folder_path, file_name)

            # 執行檔案移動
            shutil.copy2(source_file_path, destination_file_path)
            self.append_progress_message(f"檔案已成功從 '{source_file_path}' 移動到 '{destination_file_path}'")
            return True
        except shutil.Error as e:
            self.append_progress_message(f"移動檔案時發生 shutil 錯誤: {e}")
            return False
        except Exception as e:
            self.append_progress_message(f"移動檔案時發生未知錯誤: {e}")
            return False

    def gri_to_json(self):
        try:
            import pytesseract
            import cv2
            import numpy as np
            from PIL import Image
            OCR_AVAILABLE = True
            
            # 🔧 Windows環境下設定Tesseract執行檔路徑
            import platform
            import os
            if platform.system() == "Windows":
                # 常見的Tesseract安裝路徑
                tesseract_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                    r"C:\Tesseract-OCR\tesseract.exe"
                ]
                
                for path in tesseract_paths:
                    if Path(path).exists():
                        pytesseract.pytesseract.tesseract_cmd = path
                        self.append_progress_message(f"✅ 找到Tesseract執行檔: {path}")
                        
                        # 🔧 同時設定TESSDATA_PREFIX環境變數
                        tessdata_dir = str(Path(path).parent / "tessdata")
                        if Path(tessdata_dir).exists():
                            os.environ['TESSDATA_PREFIX'] = tessdata_dir
                            self.append_progress_message(f"✅ 設定TESSDATA_PREFIX: {tessdata_dir}")
                        
                        break
                else:
                    self.append_progress_message("⚠️  未在常見路徑找到Tesseract，請確認安裝位置")
            
        except ImportError:
            OCR_AVAILABLE = False
            warnings.warn("OCR功能不可用: 請安裝 pytesseract, opencv-python-headless 和 Pillow")
            
        parser = argparse.ArgumentParser(description='將GRI PDF檔案轉換為JSON格式（包含PDF→MD→JSON完整流程）')
        parser.add_argument('--input_pdf_dir', default='data/gri_pdf', help='輸入PDF檔案的目錄')
        parser.add_argument('--md_dir', default='data/gri_pdf_to_md', help='中間Markdown檔案的目錄')
        parser.add_argument('--output_dir', default='data/gri_json', help='輸出JSON檔案的目錄')
        parser.add_argument('--skip_pdf_conversion', action='store_true', help='跳過PDF轉換步驟，直接處理已存在的Markdown檔案')
        
        args = parser.parse_args()
        
        self.append_progress_message("🚀 GRI PDF轉JSON完整流程啟動!")
        self.append_progress_message("=" * 60)
        
        input_pdf_dir = Path(args.input_pdf_dir)
        md_dir = Path(args.md_dir)
        output_dir = Path(args.output_dir)
        
        # 🆕 自動創建必要的目錄
        self.append_progress_message("\n📁 檢查並創建必要的目錄...")
        
        # 檢查並創建 pdf_to_md 目錄
        if not md_dir.exists():
            self.append_progress_message(f"📂 創建 Markdown 目錄: {md_dir}")
            md_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.append_progress_message(f"✅ Markdown 目錄已存在: {md_dir}")
        
        # 檢查並創建 output_json 目錄
        if not output_dir.exists():
            self.append_progress_message(f"📂 創建 JSON 輸出目錄: {output_dir}")
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.append_progress_message(f"✅ JSON 輸出目錄已存在: {output_dir}")
        
        # 檢查並創建 input_pdf 目錄（如果需要進行PDF轉換）
        if not args.skip_pdf_conversion and not input_pdf_dir.exists():
            self.append_progress_message(f"📂 創建 PDF 輸入目錄: {input_pdf_dir}")
            input_pdf_dir.mkdir(parents=True, exist_ok=True)
            self.append_progress_message(f"💡 請將要轉換的PDF檔案放入 {input_pdf_dir} 目錄中")
        
        # 步驟1: PDF轉Markdown（如果沒有跳過的話）
        if not args.skip_pdf_conversion:
            self.append_progress_message("\n📋 步驟1: PDF轉Markdown")
            self.append_progress_message("-" * 40)
            
            # 檢查input_pdf目錄是否存在
            if not input_pdf_dir.exists():
                self.append_progress_message(f"❌ 輸入目錄不存在: {input_pdf_dir}")
                return
            
            # 查找所有PDF檔案
            pdf_files = list(input_pdf_dir.glob("*.pdf"))
            
            if not pdf_files:
                self.append_progress_message(f"❌ 在 {input_pdf_dir} 中沒有找到 .pdf 檔案")
                return
            
            self.append_progress_message(f"📄 找到 {len(pdf_files)} 個PDF檔案:")
            for pdf_file in pdf_files:
                self.append_progress_message(f"   • {pdf_file.name}")
            
            # 使用marker轉換所有PDF（目錄已在前面創建）
            self.append_progress_message(f"\n🔄 使用marker轉換PDF檔案...")
            try:
                import subprocess
                result = subprocess.run([
                    'marker', str(input_pdf_dir), '--output_dir', str(md_dir)
                ], capture_output=True, text=True, cwd=str(Path.cwd()))
                
                if result.returncode == 0:
                    self.append_progress_message("✅ PDF轉換完成!")
                    self.append_progress_message(f"📁 Markdown檔案已保存到: {md_dir}")
                else:
                    self.append_progress_message(f"❌ PDF轉換失敗: {result.stderr}")
                    return
                    
            except FileNotFoundError:
                self.append_progress_message("❌ 找不到marker指令，請確認marker已正確安裝")
                self.append_progress_message("💡 您可以使用 --skip_pdf_conversion 參數跳過此步驟")
                return
            except Exception as e:
                self.append_progress_message(f"❌ PDF轉換過程發生錯誤: {str(e)}")
                return
        else:
            self.append_progress_message("\n⏭️  跳過PDF轉換步驟，直接處理已存在的Markdown檔案")
        
        # 步驟2: Markdown轉JSON（包含OCR處理）
        self.append_progress_message("\n📋 步驟2: Markdown轉JSON（包含OCR圖片處理）")
        self.append_progress_message("-" * 50)
        
        # 查找所有markdown檔案
        md_files = list(md_dir.rglob("*.md"))
        
        if not md_files:
            self.append_progress_message(f"❌ 在 {md_dir} 中沒有找到 .md 檔案")
            self.append_progress_message("💡 請確認PDF轉換步驟是否成功完成")
            return
        
        self.append_progress_message(f"📄 找到 {len(md_files)} 個Markdown檔案:")
        for md_file in md_files:
            self.append_progress_message(f"   • {md_file}")
        
        # 處理每個markdown檔案（目錄已在前面創建）
        success_count = 0
        total_items = 0
        
        for md_file in md_files:
            self.append_progress_message(f"\n🔄 處理檔案: {md_file}")
            self.append_progress_message("-" * 30)
            
            converter = GRIMarkdownToJsonConverter()
            result = converter.convert_md_to_json(md_file, output_dir)
            
            if result:
                converter.display_preview()
                self.append_progress_message(f"✅ {md_file.name} -> {Path(result).name}")
                success_count += 1
                total_items += sum(len(group['items']) for group in converter.groups)
            else:
                self.append_progress_message(f"❌ 處理失敗: {md_file.name}")
        
        # 最終統計
        self.append_progress_message("\n" + "=" * 60)
        self.append_progress_message("🎉 完整流程處理完成!")
        self.append_progress_message(f"📊 處理統計:")
        self.append_progress_message(f"   • 成功處理: {success_count}/{len(md_files)} 個檔案")
        self.append_progress_message(f"   • 總提取項目數: {total_items}")
        self.append_progress_message(f"📁 JSON檔案已保存到: {output_dir}")
        
        # 列出生成的JSON檔案
        json_files = list(output_dir.glob("*.json"))
        if json_files:
            self.append_progress_message(f"\n📋 生成的JSON檔案:")
            for json_file in json_files:
                self.append_progress_message(f"   • {json_file.name}")
        
        self.append_progress_message("\n✨ 所有準則轉換完成! 您可以在output_json目錄中查看轉換結果。")
        
        return

    def report_to_md(self, file):
        output_dir = 'data/report_md'
        supported_formats = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']
        md = MarkItDown()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # 檢查檔案格式是否支援
        file_short = os.path.split(file)[1]
        file_ext = os.path.splitext(file_short)[1].lower()
        if file_ext in supported_formats:
            # 產生輸出檔案名稱（保持原名但改副檔名為 .md）
            base_name = os.path.splitext(file_short)[0]
            output_file_name = f"{base_name}.md"
            output_file_path = os.path.join(output_dir, output_file_name)
            
            try:
                self.append_progress_message(f"MarkDown轉換中: {file}")
                
                # 轉換檔案
                result = md.convert(file)
                
                # 寫入輸出檔案
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(result.text_content)
                
                self.append_progress_message(f"完成: {output_file_path}")
                return output_file_path
                
            except Exception as e:
                self.append_progress_message(f"轉換失敗 {file}: {str(e)}")

    def setup_collection():
        # 設定資料庫路徑
        db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
        
        # 建立 ChromaDB 客戶端，指定持久化路徑
        client = chromadb.PersistentClient(path=db_path)
        
        try:
            # 嘗試獲取已存在的集合
            collection = client.get_collection(
                name="esg_gri_collection",
                embedding_function=OpenAIEmbeddingFunction()
            )
            print(f"已載入現有的向量資料庫，路徑：{db_path}")
        except Exception as e:
            # 如果集合不存在，創建新的集合
            print(f"建立新的向量資料庫，路徑：{db_path}")
            collection = client.create_collection(
                name="esg_gri_collection",
                embedding_function=OpenAIEmbeddingFunction(),
                metadata={"description": "ESG報告水資源管理段落與GRI準則對應"}
            )
        
        return collection

    def ReportRetriverAgent(self, gri_path, report_file_path):

        # 初始化集合
        collection = setup_collection()
        report_metadata = {
        "report_year": "2023",
        "company": "台積電",
        "section": "GRI 203, 303, 403"
    }
        
        # 將ESG報告書內容添加到資料庫
        add_esg_report_to_db(collection, report_file_path, report_metadata)
        self.append_progress_message("ESG報告書內容已添加到資料庫")
        
        # 處理GRI準則並查詢相關內容
        self.append_progress_message("\n開始處理GRI準則...")
        
        self.append_progress_message(f"\n正在處理 {gri_path}...")
        output_data = process_gri_standards(gri_path, collection)
        gri_name = os.path.splitext(os.path.split(gri_path)[1])[0]
        report_name = os.path.splitext(os.path.split(report_file_path)[1])[0]
    
        # 將結果寫入輸出檔案
        self.append_progress_message("\n將結果寫入檔案...")
        with open(f"data/content_pair/{report_name}_{gri_name}.json", encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        self.append_progress_message("RAG搜尋完成")
        return f"data/content_pair/{report_name}_{gri_name}.json"

    async def setup_database(self, cfg: Dict[str, Any], *, recreate: bool = True) -> bool:
        ddl_columns = {
            "gri_standard_title": "VARCHAR(255) NOT NULL",
            "gri_clause"        : "VARCHAR(50)  NOT NULL",
            "gri_query"         : "TEXT         NOT NULL",
            "report_sentence"   : "MEDIUMTEXT   NOT NULL",
            "analysis_result"   : "TEXT         NOT NULL",
            "is_compliant"      : "TINYINT(1)   NOT NULL",
            "analysis_timestamp": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        }
        db_cfg, db_name = cfg.copy(), cfg["db"]; db_cfg.pop("db")
        try:
            conn = await aiomysql.connect(**db_cfg)
            async with conn.cursor() as cur:
                await cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
                await cur.execute(f"USE {db_name}")

                if recreate:
                    await cur.execute("DROP TABLE IF EXISTS compliance_reports")

                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_reports (
                        id INT AUTO_INCREMENT PRIMARY KEY
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """)

                await cur.execute("SHOW COLUMNS FROM compliance_reports")
                exist = {r[0] for r in await cur.fetchall()}
                for col, defi in ddl_columns.items():
                    if col not in exist:
                        await cur.execute(
                            f"ALTER TABLE compliance_reports ADD COLUMN {col} {defi}"
                        )
            await conn.ensure_closed()
            print("✅ 資料庫和資料表已確認/更新。")
            return True
        except Exception as e:
            print("❌ 資料庫設定失敗:", e)
            return False

    async def compilance_agent(self, content_path):
        env_path = Path(__file__).resolve().parent / ".env"
        load_dotenv(dotenv_path=env_path if env_path.exists() else find_dotenv(), override=False)

        API_KEY = os.getenv("OPENAI_API_KEY")
        if not API_KEY:
            raise RuntimeError("缺少 OPENAI_API_KEY，請檢查 .env")

        MYSQL_CONFIG = dict(
            host="127.0.0.1", port=3306, user="root", password="55665566",
            db="esg_reports", autocommit=True, charset="utf8mb4",
        )
        if not await self.setup_database(MYSQL_CONFIG): return
        TEST_PAIRS_JSON      = content_path
        content_pair_name = os.path.splitext(os.path.split(content_path)[1])[0]
        TEST_EXCEL_OUTPUT    = f"data/result/{content_pair_name}_compliance_summary_report.xlsx"
        MODEL_NAME           = "gpt-4.1"
        model = OpenAIChatCompletionClient(model=MODEL_NAME, api_key=API_KEY)
        comp = ComplianceAnalysisAgent("ComplianceAnalyzer", MYSQL_CONFIG, model)
        integ= ResultIntegrationAgent("ReportIntegrator", MYSQL_CONFIG, TEST_EXCEL_OUTPUT)

        with open(TEST_PAIRS_JSON,"r",encoding="utf-8") as f:
            raw=f.read()
        self.append_progress_message("\n--- 🎬 開始 LLM 分析流程 ---")
        await comp.on_messages([TextMessage(content=raw,source="Orchestrator")], CancellationToken())
        self.append_progress_message("--- ✅ 分析結束 ---\n")

        self.append_progress_message("--- 🎬 產生 Excel ---")
        await integ.on_messages([TextMessage(content="export",source="Orchestrator")], CancellationToken())
        self.append_progress_message("--- ✅ 流程完成 ---")
        await model.close()

    def _run_long_process(self):
        try:
            self.append_progress_message(f"準則檔案數量: {len(self.selected_files1)}")
            self.append_progress_message(f"報告檔案數量: {len(self.selected_files2)}")
            self.append_progress_message("開始執行任務...")

            # 讀取和處理準則
            for i, file_path in enumerate(self.selected_files1):
                self.append_progress_message(f"處理中: 準則 - {os.path.basename(file_path)}...")
                self.move_file_to_folder(file_path, 'data/gri_pdf')
            
            self.gri_to_json()

            # 讀取和處理報告書
            for i, file_path in enumerate(self.selected_files2):
                self.append_progress_message(f"處理中: 報告 - {os.path.basename(file_path)}...")
                md_path = self.report_to_md(file_path)
            
                for root, dir, gri_files in os.walk('data/gri_json'):
                    for gri_file in gri_files:
                        gri_path = os.path.join('data/gri_json', gri_file)
                        content_path = self.ReportRetriverAgent(gri_path, md_path)
                        print(content_path)
                        asyncio.run(self.compilance_agent(content_path))
                
            self.append_progress_message("\n--- 所有檔案已處理完成 ---")
            # messagebox.showinfo("完成", "檔案處理程序已成功完成！")

        except Exception as e:
            error_message = f"處理程序發生錯誤: {e}"
            self.append_progress_message(f"--- 錯誤: {error_message} ---")
            messagebox.showerror("錯誤", error_message)
        finally:
            self.append_progress_message("--- 處理程序結束 ---")
            # 重新啟用按鈕
            self.button_start_process.configure(state="normal")
            self.button_add_files1.configure(state="normal")
            self.button_remove_files1.configure(state="normal")
            self.button_clear_files1.configure(state="normal")
            self.button_add_files2.configure(state="normal")
            self.button_remove_files2.configure(state="normal")
            self.button_clear_files2.configure(state="normal")
            self.button_show_results.configure(state="normal") # 啟用結果按鈕
            self.button_open_results_folder.configure(state="normal") # 啟用開啟目錄按鈕

    def show_results_window(self):
        """開啟一個新視窗來顯示處理結果 (XLSX 檔案內容使用 Treeview 呈現)"""
        results_window = ctk.CTkToplevel(self)
        results_window.title("處理結果")
        results_window.geometry("800x600") # 調整視窗大小以容納表格
        results_window.grab_set() # 讓新視窗獨佔焦點

        results_window.grid_rowconfigure(0, weight=1)
        results_window.grid_columnconfigure(0, weight=1)

        found_excel = False
        for filename in os.listdir(self.results_output_dir):
            if filename.endswith(".xlsx"):
                file_path = os.path.join(self.results_output_dir, filename)
                try:
                    df = pd.read_excel(file_path)

                    # 創建一個框架來包含 Treeview 和滾動條
                    tree_frame = ctk.CTkFrame(results_window)
                    tree_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
                    tree_frame.grid_rowconfigure(0, weight=1)
                    tree_frame.grid_columnconfigure(0, weight=1)

                    # 獲取列名作為 Treeview 的 columns
                    columns = list(df.columns)
                    # 設置 Treeview 的列標識符
                    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")

                    # 設置每一列的標題和寬度
                    for col in columns:
                        tree.heading(col, text=col)
                        tree.column(col, width=100, anchor="w") # 預設寬度，可調整

                    # 插入數據到 Treeview
                    for index, row in df.iterrows():
                        tree.insert("", "end", values=list(row))

                    # 添加垂直滾動條
                    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                    vsb.grid(row=0, column=1, sticky="ns")
                    tree.configure(yscrollcommand=vsb.set)

                    # 添加水平滾動條
                    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                    hsb.grid(row=1, column=0, sticky="ew")
                    tree.configure(xscrollcommand=hsb.set)

                    tree.grid(row=0, column=0, sticky="nsew")

                    found_excel = True
                    # 如果找到並顯示了第一個 Excel 檔案，就跳出迴圈，因為通常只需要顯示一個結果
                    break
                except Exception as e:
                    # 如果讀取失敗，在主進度文本框中顯示錯誤
                    self.append_progress_message(f"錯誤: 讀取或處理 Excel 檔案 '{filename}' 失敗: {e}")
                    # 在結果視窗中顯示錯誤訊息 (如果 Treeview 沒有成功創建)
                    error_label = ctk.CTkLabel(results_window, text=f"錯誤: 無法顯示檔案 '{filename}' - {e}", text_color="red")
                    error_label.grid(row=0, column=0, padx=20, pady=20)


        if not found_excel:
            no_file_label = ctk.CTkLabel(results_window, text="在結果目錄中找不到任何 XLSX 檔案。請先執行處理程序。", text_color="orange")
            no_file_label.grid(row=0, column=0, padx=20, pady=20)


    def open_results_folder(self):
        """開啟結果檔案所在的目錄"""
        try:
            if not os.path.exists(self.results_output_dir):
                self.append_progress_message(f"錯誤: 結果目錄 '{self.results_output_dir}' 不存在。")
                messagebox.showerror("錯誤", f"結果目錄不存在: {self.results_output_dir}")
                return

            if os.name == 'nt':  # Windows
                os.startfile(self.results_output_dir)
            elif os.uname().sysname == 'Darwin':  # macOS
                os.system(f'open "{self.results_output_dir}"')
            else:  # Linux/Unix
                os.system(f'xdg-open "{self.results_output_dir}"')
            self.append_progress_message(f"已開啟結果目錄: {self.results_output_dir}")
        except Exception as e:
            self.append_progress_message(f"開啟目錄失敗: {e}")
            messagebox.showerror("錯誤", f"無法開啟結果目錄: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
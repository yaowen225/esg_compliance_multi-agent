#!/usr/bin/env python3
"""
GRI Markdown轉JSON轉換器
解析GRI markdown檔案並轉換為標準JSON格式
支援英文字母編號（a, b, c, d）和羅馬數字子項目（i, ii, iii, iv, v）的合併
包含OCR功能處理被錯誤識別為圖片的文字內容
"""

import json
import re
import sys
import argparse
from pathlib import Path
import warnings

# OCR相關imports
try:
    import pytesseract
    import cv2
    import numpy as np
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    warnings.warn("OCR功能不可用: 請安裝 pytesseract, opencv-python-headless 和 Pillow")

class GRIMarkdownToJsonConverter:
    def __init__(self):
        self.section = ""
        self.groups = []
        self.ocr_reader = None
        
        # 初始化OCR閱讀器（支援中文和英文）
        if OCR_AVAILABLE:
            try:
                print("🔄 初始化Tesseract OCR...")
                # 測試tesseract是否可用
                pytesseract.get_tesseract_version()
                self.ocr_available = True
                print("✅ Tesseract OCR初始化完成")
            except Exception as e:
                print(f"⚠️  Tesseract初始化失敗: {e}")
                print("💡 請確認已安裝Tesseract並正確設定路徑")
                self.ocr_available = False
        else:
            print("⚠️  OCR功能不可用，跳過圖片文字提取")
            self.ocr_available = False
        
    def clean_text(self, text):
        """清理文字，移除多餘空格、星號標記和換行"""
        # 移除markdown粗體標記
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        # 移除列表符號
        text = re.sub(r'^[-•]\s*', '', text.strip())
        # 合併多個空格
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text
    
    def extract_section_number(self, content):
        """從內容中提取section編號 - 優先從揭露項目標題提取"""
        
        # 優先級1: 從揭露項目標題中提取（最可靠的方法）
        # 匹配 "揭露項目 **405-1**" 或 "揭露項目 405-1" 格式
        disclosure_patterns = [
            r'揭露項目\s*\*\*(\d+)-\d+\*\*',    # 揭露項目 **405-1**
            r'揭露項目\s*(\d+)-\d+',             # 揭露項目 405-1
            r'# 揭露項目\s*\*\*(\d+)-\d+\*\*',   # # 揭露項目 **405-1**
            r'## 揭露項目\s*\*\*(\d+)-\d+\*\*',  # ## 揭露項目 **405-1**
        ]
        
        for pattern in disclosure_patterns:
            match = re.search(pattern, content)
            if match:
                section_num = match.group(1)
                print(f"🎯 從揭露項目標題提取section: {section_num}")
                return section_num
        
        # 優先級2: 從 "GRI XXX" 格式中提取
        match = re.search(r'GRI\s+(\d+)', content)
        if match:
            section_num = match.group(1)
            print(f"🎯 從GRI標記提取section: {section_num}")
            return section_num
        
        # 優先級3: 從檔案路徑中提取（如果前面的方法都失敗）
        # 尋找路徑中的 "GRI 405" 格式
        file_path_match = re.search(r'GRI\s+(\d+)', content)
        if file_path_match:
            section_num = file_path_match.group(1)
            print(f"🎯 從檔案路徑提取section: {section_num}")
            return section_num
        
        # 優先級4: 從任何 XXX-X 格式中提取section部分
        match = re.search(r'(\d+)-\d+', content)
        if match:
            section_num = match.group(1)
            print(f"🎯 從編號格式提取section: {section_num}")
            return section_num
        
        # 最後備案：尋找3位數編號（避免匹配單個數字如"2"）
        matches = re.findall(r'\b(\d{3,})\b', content)  # 只匹配3位或以上的數字
        for number in matches:
            if 200 <= int(number) <= 999:  # GRI標準的合理範圍
                print(f"🎯 從3位數編號提取section: {number}")
                return number
        
        # 如果都失敗，返回預設值並警告
        print("⚠️  無法從內容中提取section編號，使用預設值")
        return "000"
    
    def parse_markdown_content(self, content):
        """解析markdown內容，支援多種格式（標準格式、OCR文字、混合格式）"""
        lines = content.split('\n')
        
        # 提取section編號
        self.section = self.extract_section_number(content)
        if self.section == "3":  # 如果只提取到"3"，設定為"303"
            self.section = "303"
        
        print(f"🔍 識別section: {self.section}")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 方法1: 檢測標準格式揭露項目
            disclosure_match, title_text, disclosure_number = self.detect_standard_disclosure(line)
            if disclosure_match:
                print(f"📋 標準格式揭露項目: {disclosure_number}")
                items, next_i = self.extract_requirement_items(lines, i + 1, disclosure_number)
                
                if items:
                    group = {
                        "title": f"{disclosure_number} {title_text}",
                        "items": items
                    }
                    self.groups.append(group)
                    print(f"✅ 提取了 {len(items)} 個項目")
                
                i = next_i
                continue
            
            # 方法2: 檢測OCR提取的文字
            if "**[從圖片提取的文字]**" in line:
                print(f"🖼️  發現OCR文字區塊")
                ocr_items, next_i = self.extract_items_from_ocr_text_enhanced(lines, i)
                
                for item_group in ocr_items:
                    self.groups.append(item_group)
                    print(f"✅ OCR提取了 {len(item_group['items'])} 個項目")
                
                i = next_i
                continue
            
            # 方法3: 檢測混合格式（markdown + 不標準格式）
            mixed_match, mixed_items = self.detect_mixed_format_disclosure(lines, i)
            if mixed_match:
                for item_group in mixed_items:
                    self.groups.append(item_group)
                    print(f"✅ 混合格式提取了 {len(item_group['items'])} 個項目")
                i += 1
                continue
            
            i += 1
    
    def detect_standard_disclosure(self, line):
        """檢測標準格式的揭露項目"""
        disclosure_patterns = [
            r'^#+\s*揭露項目\s*\*\*(\d+-\d+)\*\*\s*(.+)',   # ## 揭露項目 **303-1** 標題
            r'^#+\s*揭露項目\s*(\d+-\d+)\s*(.+)',           # ## 揭露項目 303-1 標題
            r'^揭露項目\s*\*\*(\d+-\d+)\*\*\s*(.+)',        # 揭露項目 **303-1** 標題
            r'^揭露項目\s*(\d+-\d+)\s*(.+)',                # 揭露項目 303-1 標題
            r'^\*\*(\d+-\d+)\*\*\s*(.+)',                   # **303-1** 標題
            r'^(\d+-\d+)\s*(.+)',                           # 303-1 標題
        ]
        
        for pattern in disclosure_patterns:
            match = re.match(pattern, line)
            if match:
                disclosure_number = match.group(1)
                title_text = self.clean_text(match.group(2))
                return True, title_text, disclosure_number
        
        return False, None, None
    
    def extract_requirement_items(self, lines, start_index, disclosure_number):
        """提取要求區段的項目"""
        items = []
        i = start_index
        in_requirements_section = False
        
        print(f"🔍 開始提取 {disclosure_number} 的要求項目，從行 {start_index} 開始")
        
        # 尋找到下一個揭露項目或文件結束
        while i < len(lines):
            line = lines[i].strip()
            
            if i < start_index + 15:  # 增加調試輸出範圍
                print(f"   行 {i}: {line[:100]}")
            
            # 如果遇到下一個揭露項目，停止
            if self.is_new_disclosure_item(line):
                print(f"   遇到新揭露項目，停止於行 {i}")
                break
            
            # 檢查是否進入要求區段
            if self.is_requirements_section_start(line):
                in_requirements_section = True
                print(f"   找到要求區段開始，行 {i}")
                i += 1
                continue
            
            # 檢測OCR文字區塊
            if "**[從圖片提取的文字]**" in line:
                print(f"   找到OCR文字區塊，行 {i}")
                # 處理OCR文字中的要求
                ocr_items, next_i = self.extract_items_from_ocr_text_enhanced(lines, i)
                for item_group in ocr_items:
                    items.extend(item_group['items'])
                    print(f"   從OCR提取了 {len(item_group['items'])} 個項目")
                i = next_i
                continue
            
            # 如果在要求區段中，提取項目
            if in_requirements_section:
                # 檢查彙編要求 - 但不停止，確保所有項目都被收集
                if re.search(r"^#+\s*彙編要求", line):
                    print(f"   遇到彙編要求，進行最終項目回溯檢查，行 {i}")
                    # 向前回溯檢查是否有遺漏的項目（擴展到h項目）
                    for back_i in range(max(0, i-30), i):
                        back_line = lines[back_i].strip()
                        # 檢查是否有未收集的標準項目格式
                        if re.search(r'^\s*-\s*\*\*[a-h]\.\*\*', back_line):
                            back_item, _ = self.extract_single_item_with_subitems(lines, back_i, disclosure_number)
                            if back_item and not any(existing['clause'] == back_item['clause'] for existing in items):
                                items.append(back_item)
                                print(f"   🔄 回溯收集項目: {back_item['clause']}")
                        # 也檢查深層縮進項目格式（可能被遺漏）
                        elif re.search(r'^\s*[a-h]\.\s*', back_line) and disclosure_number in back_line:
                            back_item, _ = self.extract_single_item_with_subitems(lines, back_i, disclosure_number)
                            if back_item and not any(existing['clause'] == back_item['clause'] for existing in items):
                                items.append(back_item)
                                print(f"   🔄 回溯收集深層項目: {back_item['clause']}")
                    
                    # 完成收集後停止
                    print(f"   ✅ 完成彙編要求前的項目收集，停止於行 {i}")
                    break
                
                # 檢查是否遇到其他強烈結束信號
                if self.is_strong_section_end(line):
                    print(f"   要求區段結束，行 {i}")
                    break
                
                # 特殊處理：檢查深層縮進結構（如403-9 a的情況）
                if self.is_deep_indented_item(lines, i, disclosure_number):
                    deep_item, next_index = self.extract_deep_indented_item(lines, i, disclosure_number)
                    if deep_item:
                        # 避免重複項目
                        if not any(existing['clause'] == deep_item['clause'] for existing in items):
                            items.append(deep_item)
                            print(f"   提取深層縮進項目: {deep_item['clause']}")
                        i = next_index - 1
                    i += 1
                    continue
                
                # 檢查各種可能的項目格式，並提取子項目
                item, next_index = self.extract_single_item_with_subitems(lines, i, disclosure_number)
                if item:
                    # 避免重複項目
                    if not any(existing['clause'] == item['clause'] for existing in items):
                        items.append(item)
                        print(f"   提取項目: {item['clause']}")
                    i = next_index - 1  # 調整索引，因為下面會 i += 1
            
            i += 1
        
        print(f"🔍 結束前最終檢查：掃描是否有遺漏的項目")
        # 最終檢查：向後掃描是否有遺漏的f、g、h項目
        for final_i in range(start_index, min(len(lines), start_index + 100)):
            final_line = lines[final_i].strip()
            
            # 檢查新的揭露項目或章節分隔符
            if self.is_new_disclosure_item(final_line) or re.search(r'^#+\s*(指引|背景)', final_line):
                break
                
            # 檢查遺漏的項目（特別是f、g、h）
            for pattern in [
                r'^\s*-\s*\*\*([f-h])\.\*\*\s*(.*)',  # - **f.** 內容
                r'^\s*\*\*([f-h])\.\*\*\s*(.*)',      # **f.** 內容
                r'^\s*([f-h])\.\s*(.*)',              # f. 內容
            ]:
                match = re.search(pattern, final_line)
                if match:
                    letter = match.group(1)
                    clause = f"{disclosure_number} {letter}"
                    
                    # 檢查是否已經收集過
                    if not any(existing['clause'] == clause for existing in items):
                        content = match.group(2).strip()
                        # 簡單清理格式
                        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
                        
                        item = {
                            "clause": clause,
                            "query": content
                        }
                        items.append(item)
                        print(f"   🔍 最終檢查發現項目: {clause} - {content[:50]}...")
                        
        print(f"✅ {disclosure_number} 總共提取了 {len(items)} 個項目")
        return items, i
    
    def is_new_disclosure_item(self, line):
        """檢查是否是新的揭露項目"""
        patterns = [
            r'^#+\s*揭露項目\s*\*\*\d+-\d+\*\*',
            r'^#+\s*揭露項目\s*\d+-\d+',
            r'^揭露項目\s*\*\*\d+-\d+\*\*',
            r'^揭露項目\s*\d+-\d+',
            r'^\*\*\d+-\d+\*\*\s+\S+'
        ]
        
        for pattern in patterns:
            if re.match(pattern, line):
                return True
        return False
    
    def is_requirements_section_start(self, line):
        """檢查是否是要求區段的開始"""
        patterns = [
            r"要求",
            r"報導組織應報導以下資訊",
            r"報導組織應報導以下資訊.*要求",
            r"要求.*報導組織應報導以下資訊"
        ]
        
        # 特殊檢查：避免將403-8 a項目誤判為要求區段
        # 如果行包含 "**a.**" 或 "**b.**" 等項目標記，不應該被認為是要求區段開始
        if re.search(r'\*\*[a-e]\.\*\*', line):
            return False
        
        for pattern in patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def is_requirements_section_end(self, line):
        """檢查是否是要求區段的結束"""
        end_patterns = [
            r"建議",
            r"指引",
            r"背景",
            r"彙編要求",
            r"^#+\s*(建議|指引|背景)",
            r"^\d+\.\d+\s+"  # 如 2.1, 2.2 等編號
        ]
        
        for pattern in end_patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def extract_single_item(self, line, disclosure_number):
        """從單行中提取項目（增強版，支援更多格式變化）"""
        # 跳過空行
        if not line.strip():
            return None
        
        # 格式1: 開頭有 a., b., c., d., e. (包括粗體格式)
        patterns_start = [
            r'^\s*-\s*\*\*([a-e])\.\*\*\s+(.+)',       # - **a.** 內容
            r'^\s*-\s*([a-e])\.\s+(.+)',               # - a. 內容
            r'^\s*\*\*([a-e])\.\*\*\s+(.+)',           # **a.** 內容
            r'^\s*([a-e])\.\s+(.+)',                   # a. 內容
        ]
        
        for pattern in patterns_start:
            match = re.match(pattern, line)
            if match:
                clause_letter = match.group(1)
                query_text = self.clean_text(match.group(2))
                if query_text and len(query_text) > 5:
                    return {
                        "clause": f"{disclosure_number} {clause_letter}",
                        "query": query_text
                    }
        
        # 格式2: 結尾有 a., b., c., d., e. (包括粗體格式) - 增強版
        patterns_end = [
            r'^\s*-\s*(.+?)\s+\*\*([a-e])\.\*\*\s*$',  # - 內容 **a.**
            r'^\s*-\s*(.+?)\s+([a-e])\.\s*$',          # - 內容 a.
            r'^\s*(.+?)\s+\*\*([a-e])\.\*\*\s*$',      # 內容 **a.**
            r'^\s*(.+?)\s+([a-e])\.\s*$',              # 內容 a.
            # 新增：處理冒號後面接字母編號的情況
            r'^\s*-\s*(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$',  # - 內容: **a.**
            r'^\s*-\s*(.+?)[：:]\s*([a-e])\.\s*$',          # - 內容: a.
            # 新增：處理特殊的冒號前置格式
            r'^\s*-?\s*#+?\s*(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$',  # #### 內容: **a.**
            r'^\s*-?\s*(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$',       # 內容: **a.**
            r'^\s*-?\s*(.+?)[：:]\s*([a-e])\.\s*$',               # 內容: a.
        ]
        
        for pattern in patterns_end:
            match = re.search(pattern, line)
            if match:
                query_text = self.clean_text(match.group(1))
                clause_letter = match.group(2)
                if query_text and len(query_text) > 5:
                    return {
                        "clause": f"{disclosure_number} {clause_letter}",
                        "query": query_text
                    }
        
        return None
    
    def extract_roman_subitem(self, line):
        """提取羅馬數字子項目的文字（增強版，支援開頭和結尾位置）"""
        # 匹配羅馬數字格式，支援開頭和結尾位置
        patterns = [
            # 開頭位置的羅馬數字
            r'^\s*-\s*\*\*([ivx]+)\.\*\*\s+(.+?)；?$',      # - **i.** 內容；
            r'^\s*-\s*\*\*([ivx]+)\.\*\*\s+(.+?)$',         # - **i.** 內容
            r'^\s*\*\*([ivx]+)\.\*\*\s+(.+?)；?$',          # **i.** 內容；
            r'^\s*\*\*([ivx]+)\.\*\*\s+(.+?)$',             # **i.** 內容
            r'^\s*-\s*([ivx]+)\.\s+(.+?)；?$',              # - i. 內容；
            r'^\s*-\s*([ivx]+)\.\s+(.+?)$',                 # - i. 內容
            r'^\s*([ivx]+)\.\s+(.+?)；?$',                  # i. 內容；
            r'^\s*([ivx]+)\.\s+(.+?)$',                     # i. 內容
            
            # 結尾位置的羅馬數字 - 新增
            r'^\s*-\s*(.+?)\s+\*\*([ivx]+)\.\*\*\s*；?$',   # - 內容 **ii.**；
            r'^\s*-\s*(.+?)\s+\*\*([ivx]+)\.\*\*\s*$',      # - 內容 **ii.**
            r'^\s*(.+?)\s+\*\*([ivx]+)\.\*\*\s*；?$',       # 內容 **ii.**；
            r'^\s*(.+?)\s+\*\*([ivx]+)\.\*\*\s*$',          # 內容 **ii.**
            r'^\s*-\s*(.+?)\s+([ivx]+)\.\s*；?$',           # - 內容 ii.；
            r'^\s*-\s*(.+?)\s+([ivx]+)\.\s*$',              # - 內容 ii.
            r'^\s*(.+?)\s+([ivx]+)\.\s*；?$',               # 內容 ii.；
            r'^\s*(.+?)\s+([ivx]+)\.\s*$',                  # 內容 ii.
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.match(pattern, line)
            if match:
                if i < 8:  # 開頭位置的模式
                    roman_num = match.group(1)
                    content = self.clean_text(match.group(2))
                else:  # 結尾位置的模式
                    content = self.clean_text(match.group(1))
                    roman_num = match.group(2)
                
                # 驗證是否是有效的羅馬數字（i, ii, iii, iv, v）
                if roman_num in ['i', 'ii', 'iii', 'iv', 'v']:
                    # 移除結尾的分號，統一格式
                    content = content.rstrip('；;')
                    return content
        
        return None
    
    def extract_single_item_with_subitems(self, lines, current_index, disclosure_number):
        """從單行中提取項目，並收集其子項目（羅馬數字）- 增強版，支援標題格式"""
        line = lines[current_index].strip()
        
        # 跳過空行
        if not line.strip():
            return None, current_index + 1
        
        # 特殊處理：403-8 a 這種格式 "描述: **a.**"
        special_403_8_match = re.search(r'^-\s*(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$', line)
        if special_403_8_match and disclosure_number == "403-8":
            main_content = self.clean_text(special_403_8_match.group(1))
            clause_letter = special_403_8_match.group(2)
            
            print(f"   🎯 找到403-8特殊格式主項目: {disclosure_number} {clause_letter} - {main_content[:50]}...")
            
            # 收集縮進的羅馬數字子項目
            subitems = []
            i = current_index + 1
            
            while i < len(lines):
                subline = lines[i].strip()
                original_line = lines[i]
                
                # 跳過空行
                if not subline:
                    i += 1
                    continue
                
                # 檢查是否是縮進的羅馬數字子項目
                if original_line.startswith('\t'):
                    # 特殊處理：提取 "描述; **i.**" 格式
                    roman_match = re.search(r'^(.+?);\s*\*\*([ivx]+)\.\*\*\s*$', subline)
                    if roman_match:
                        subitem_content = self.clean_text(roman_match.group(1))
                        roman_num = roman_match.group(2)
                        
                        if roman_num in ['i', 'ii', 'iii', 'iv', 'v']:
                            subitems.append(subitem_content)
                            print(f"     📌 403-8子項目: {subitem_content[:50]}...")
                            i += 1
                            continue
                    
                    # 標準的羅馬數字提取
                    subitem_text = self.extract_roman_subitem(subline)
                    if subitem_text:
                        subitems.append(subitem_text)
                        print(f"     📌 標準子項目: {subitem_text[:50]}...")
                        i += 1
                        continue
                
                # 檢查是否遇到新的主項目或其他停止條件
                if (self.is_main_item(subline) or 
                    self.is_new_disclosure_item(subline) or 
                    self.is_strong_section_end(subline)):
                    print(f"     ⏹️  403-8停止收集，遇到: {subline[:50]}...")
                    break
                
                i += 1
            
            # 組合最終結果
            if subitems:
                subitems_text = "、".join(subitems)
                final_query = f"{main_content}：{subitems_text}"
            else:
                final_query = main_content
            
            item = {
                "clause": f"{disclosure_number} {clause_letter}",
                "query": final_query
            }
            
            print(f"   ✅ 403-8特殊格式合併結果: {item['query']}")
            return item, i
        
        # 新增：支援標題格式的項目（如 ### **a.** 或 #### **b.**）
        title_item_match = re.search(r'^#+\s*\*\*([a-h])\.\*\*\s*(.+)', line)
        if title_item_match:
            clause_letter = title_item_match.group(1)
            main_content = self.clean_text(title_item_match.group(2))
            
            print(f"   🎯 找到標題格式項目: {disclosure_number} {clause_letter} - {main_content[:50]}...")
            
            item = {
                "clause": f"{disclosure_number} {clause_letter}",
                "query": main_content
            }
            
            print(f"   ✅ 標題格式項目: {item['query']}")
            return item, current_index + 1
        
        # 標準的項目提取邏輯
        item = self.extract_single_item(line, disclosure_number)
        if not item:
            return None, current_index + 1
        
        print(f"   🎯 找到主項目: {item['clause']} - {item['query'][:50]}...")
        
        # 如果找到了主項目，檢查是否有子項目（羅馬數字）
        subitems = []
        i = current_index + 1
        
        # 收集子項目 - 增強版邏輯
        while i < len(lines):
            subline = lines[i].strip()
            
            # 跳過空行
            if not subline:
                i += 1
                continue
            
            # 檢查是否是縮進的羅馬數字子項目（tab縮進、多個空格縮進、或多層縮進）
            original_line = lines[i]
            is_indented = (original_line.startswith('\t') or 
                          original_line.startswith('    ') or
                          original_line.startswith('\t\t') or
                          original_line.startswith('        '))  # 8個空格也算縮進
            
            if is_indented and subline:
                subitem_text = self.extract_roman_subitem(subline)
                if subitem_text:
                    subitems.append(subitem_text)
                    print(f"     📌 子項目(縮進): {subitem_text[:50]}...")
                    i += 1
                    continue
            
            # 檢查是否是非縮進的羅馬數字子項目
            subitem_text = self.extract_roman_subitem(subline)
            if subitem_text:
                subitems.append(subitem_text)
                print(f"     📌 子項目(非縮進): {subitem_text[:50]}...")
                i += 1
                continue
            
            # 改進停止條件：只有在遇到明確的新主項目時才停止
            # 不要被標題、指引等中斷
            if self.is_main_item(subline):
                print(f"     ⏹️  停止收集子項目，遇到新主項目: {subline[:50]}...")
                break
            
            # 檢查是否是新的揭露項目
            if self.is_new_disclosure_item(subline):
                print(f"     ⏹️  停止收集子項目，遇到新揭露項目: {subline[:50]}...")
                break
            
            # 檢查是否是要求區段結束（但要更謹慎）
            if self.is_strong_section_end(subline):
                print(f"     ⏹️  停止收集子項目，遇到強烈區段結束信號: {subline[:50]}...")
                break
            
            i += 1
        
        # 如果有子項目，將它們合併到主項目的query中
        if subitems:
            print(f"   🔗 合併 {len(subitems)} 個子項目到主項目")
            # 將子項目用"、"連接
            subitems_text = "、".join(subitems)
            
            # 找到合適的位置插入子項目
            main_query = item['query']
            
            # 根據不同情況組合最終的query
            if "並按以下來源" in main_query:
                item['query'] = re.sub(r'並按以下來源[^。]*', f'並按{subitems_text}', main_query)
            elif "並按以下終點類別" in main_query:
                item['query'] = re.sub(r'並按以下終點類別[^。]*', f'並按{subitems_text}', main_query)
            elif "包括：" in main_query or "包括:" in main_query:
                item['query'] = re.sub(r'包括：?', f'包括{subitems_text}', main_query)
            elif "包括是否" in main_query:
                # 針對403-1的特殊情況：包括是否: **a.**
                item['query'] = re.sub(r'包括是否[：:]?\s*$', f'包括是否{subitems_text}', main_query)
            elif main_query.endswith(':') or main_query.endswith('：'):
                # 在冒號後插入子項目
                item['query'] = main_query + f'{subitems_text}'
            elif "細分總量" in main_query:
                item['query'] = re.sub(r'細分總量', f'按{subitems_text}細分總量', main_query)
            elif main_query.endswith('(若適用):') or main_query.endswith('（若適用）:'):
                item['query'] = re.sub(r'\(?若適用\)?:', f'，並按{subitems_text}細分(若適用)', main_query)
            else:
                # 在句子末尾添加子項目
                if main_query.endswith('。'):
                    item['query'] = main_query[:-1] + f'，包括{subitems_text}。'
                else:
                    item['query'] = main_query + f':{subitems_text}'
            
            print(f"   ✅ 合併結果: {item['query']}")
        
        return item, i
    
    def is_main_item(self, line):
        """檢查是否是主項目（a., b., c., d., e.）- 支援多種格式"""
        # 檢查標準列表格式的項目標記
        standard_formats = (
            re.search(r'\*\*[a-e]\.\*\*', line) is not None or 
            re.search(r'^[a-e]\.\s+', line) is not None or 
            re.search(r'[a-e]\.$', line) is not None
        )
        
        # 檢查標題格式的項目標記（如 ### **a.** 或 #### **b.**）
        title_formats = re.search(r'^#+\s*\*\*[a-e]\.\*\*', line) is not None
        
        return standard_formats or title_formats
    
    def extract_text_from_image(self, image_path):
        """使用Tesseract OCR從圖片中提取文字（針對條目項目優化）"""
        if not self.ocr_available or not OCR_AVAILABLE:
            return ""
        
        try:
            print(f"🔍 正在從圖片提取文字: {image_path}")
            
            # 讀取圖片
            image = cv2.imread(str(image_path))
            if image is None:
                print(f"❌ 無法讀取圖片: {image_path}")
                return ""
            
            # 圖片預處理以提高OCR效果
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 降噪處理
            denoised = cv2.medianBlur(gray, 5)
            
            # 二值化處理
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形態學操作去除噪點
            kernel = np.ones((1, 1), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # 轉換為PIL Image格式
            pil_image = Image.fromarray(cleaned)
            
            # 設定Tesseract配置
            # 使用繁體中文和英文，優化為文字行識別
            config = '--oem 3 --psm 6 -l chi_tra+eng'
            
            # 使用Tesseract提取文字
            extracted_text = pytesseract.image_to_string(pil_image, config=config)
            
            if extracted_text.strip():
                # 清理提取的文字
                cleaned_text = self.clean_ocr_text(extracted_text)
                print(f"✅ 成功提取文字（{len(cleaned_text)}字元）")
                print(f"   前100字元: {cleaned_text[:100]}{'...' if len(cleaned_text) > 100 else ''}")
                return cleaned_text
            else:
                print(f"⚠️  未能從圖片中提取到文字")
                return ""
                
        except Exception as e:
            print(f"❌ OCR處理失敗: {e}")
            return ""
    
    def clean_ocr_text(self, text):
        """清理Tesseract OCR提取的文字"""
        if not text:
            return ""
        
        # 移除多餘的空白行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 修復常見的OCR錯誤
        cleaned_lines = []
        for line in lines:
            # 修復常見錯誤
            line = line.replace('衝聲', '衝擊')
            line = line.replace('衝繫', '衝擊') 
            line = line.replace('衝軗', '衝擊')
            line = line.replace('關係入', '關係人')
            line = line.replace('利雪關係人', '利害關係人')
            line = line.replace('標竿', '標準')
            line = line.replace('例女口', '例如')
            line = line.replace('國豕', '國家')
            line = line.replace('團際', '國際')
            
            # 標準化標點符號
            line = line.replace('. ', '。')
            line = line.replace(', ', '，')
            line = line.replace(': ', '：')
            line = line.replace('; ', '；')
            
            # 清理多餘空格
            line = re.sub(r'\s+', ' ', line).strip()
            
            if len(line) > 2:  # 過濾太短的行
                cleaned_lines.append(line)
        
        # 重新組織文字，保持段落結構
        result = '\n'.join(cleaned_lines)
        
        # 特別處理：確保"要求"部分格式正確
        if '要求' in result and '報導組織應報導以下資訊' in result:
            result = re.sub(r'要求.*?報導組織應報導以下資訊', '要求：報導組織應報導以下資訊', result)
        
        return result
    
    def organize_ocr_text_enhanced(self, text_blocks):
        """增強版OCR文字組織，針對條目項目優化"""
        if not text_blocks:
            return ""
        
        print(f"🔧 組織 {len(text_blocks)} 個文字塊...")
        
        # 首先收集所有重要內容
        important_blocks = []
        for block in text_blocks:
            text = block['text']
            is_important = block.get('is_important', False)
            
            if is_important:
                print(f"   🎯 重要內容: {text} (置信度: {block['confidence']:.3f})")
                important_blocks.append(block)
        
        # 分析並重組文字
        organized_parts = []
        
        # 尋找要求部分
        has_requirement = any('要求' in block['text'] for block in important_blocks)
        if has_requirement:
            organized_parts.append("要求：報導組織應報導以下資訊：")
        
        # 特別處理a項目（組織已鑑別）
        a_content = None
        for block in important_blocks:
            if '組織已鑑別' in block['text']:
                # 修復OCR錯誤並格式化
                content = block['text'].replace('衝聲', '衝擊').replace(',', '，')
                if not content.startswith('a.'):
                    content = 'a. ' + content
                a_content = content
                break
        
        if a_content:
            organized_parts.append(a_content)
        
        # 特別處理b項目
        b_content = None
        b_parts = []
        
        # 尋找b項目標記
        has_b_marker = any('b.' in block['text'] for block in important_blocks)
        
        # 收集b項目相關內容
        for block in important_blocks:
            text = block['text']
            if ('利害關係人' in text or '外部標' in text or '國際標準' in text) and 'b.' not in text:
                b_parts.append(text.replace('衝聲', '衝擊').replace(',', '，'))
        
        if has_b_marker and b_parts:
            b_content = 'b. ' + '，'.join(b_parts)
            organized_parts.append(b_content)
        
        result = '\n'.join(organized_parts)
        print(f"📝 最終組織結果: {result}")
        return result
    
    def format_ocr_output_enhanced(self, lines):
        """增強版OCR輸出格式化，針對條目項目優化"""
        formatted_parts = []
        
        for line in lines:
            # 特殊處理要求行
            if line.startswith('要求'):
                formatted_parts.append('要求：報導組織應報導以下資訊：')
            # 處理項目行 - 增強版條目檢測
            elif re.search(r'[a-e]\.\s*', line):
                # 確保條目格式正確
                # 將 "組織已鑑別的重大間接經濟衝聲例子,包括正面與負面的衝聲." 
                # 格式化為 "a. 組織已鑑別的重大間接經濟衝擊例子，包括正面與負面的衝擊。"
                
                # 修復OCR常見錯誤
                line = line.replace('衝聲', '衝擊')
                line = line.replace(',', '，')
                line = line.replace('.', '。')
                
                # 檢查是否包含a項目內容
                if '組織已鑑別' in line and 'a.' not in line:
                    line = 'a. ' + line
                
                formatted_parts.append(line)
            # 處理指引行（通常忽略，因為不在要求範圍內）
            elif line.startswith('指引'):
                break  # 停止處理，因為已經超出要求範圍
            # 其他行可能是項目的延續
            else:
                if formatted_parts and not formatted_parts[-1].startswith('要求'):
                    # 合併到上一行
                    formatted_parts[-1] += ' ' + line
                else:
                    formatted_parts.append(line)
        
        result = '\n'.join(formatted_parts)
        print(f"📝 格式化結果: {result}")
        return result
    
    def is_line_start_marker(self, text):
        """檢查是否是行開始標記"""
        line_start_patterns = [
            r'^要求\s*[：:]?',      # 要求:
            r'^[a-e]\.\s*',         # a. b. c.
            r'^指引\s*[：:]?',      # 指引:
            r'^揭露項目',           # 揭露項目
        ]
        
        for pattern in line_start_patterns:
            if re.match(pattern, text):
                return True
        return False
    
    def should_continue_line(self, text, current_line):
        """檢查是否應該繼續當前行"""
        # 如果當前行是空的，不繼續
        if not current_line.strip():
            return False
        
        # 如果文字是新的重要標記，不繼續
        if self.is_line_start_marker(text):
            return False
        
        # 如果當前行已經是完整的項目格式，檢查是否應該繼續
        if re.match(r'^[a-e]\.\s*', current_line):
            # 如果文字看起來是項目內容的延續，繼續
            if not re.match(r'^[a-e]\.\s*', text) and not text.startswith('指引'):
                return True
        
        # 如果當前行是"要求"開頭，繼續收集相關內容
        if current_line.startswith('要求'):
            if not self.is_line_start_marker(text):
                return True
        
        return False
    
    def fix_ocr_errors(self, text):
        """修復常見的OCR錯誤"""
        # 常見錯誤替換
        corrections = {
            '衝聲': '衝擊',
            '衝繫': '衝擊', 
            '衝軗': '衝擊',
            '關係入': '關係人',
            '利雪關係人': '利害關係人',
            '標竿': '標準',
            '協定': '協定',
            '例女口': '例如',
            '國豕': '國家',
            '團際': '國際',
            '標竿': '標準',
            '. ': '。',  # 修復句號
            ', ': '，',  # 修復逗號
            ': ': '：',  # 修復冒號
        }
        
        fixed_text = text
        for wrong, correct in corrections.items():
            fixed_text = fixed_text.replace(wrong, correct)
        
        # 清理多餘空格
        fixed_text = re.sub(r'\s+', ' ', fixed_text).strip()
        
        return fixed_text
    
    def process_images_in_markdown(self, md_file_path):
        """處理markdown中的圖片，使用Tesseract OCR提取文字並直接修改原始文件"""
        print(f"🔎 開始處理圖片，檔案: {md_file_path}")
        print(f"🔎 Tesseract OCR 狀態: {self.ocr_available}")
        print(f"🔎 OCR_AVAILABLE: {OCR_AVAILABLE}")
        
        if not self.ocr_available:
            print("❌ Tesseract OCR 未初始化，跳過圖片處理")
            return False
        
        # 找到markdown檔案所在的目錄
        md_dir = Path(md_file_path).parent
        print(f"🔎 檔案目錄: {md_dir}")
        
        # 讀取原始內容
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"🔎 檔案內容長度: {len(content)}")
        
        # 尋找圖片引用的模式
        image_pattern = r'!\[\]\(([^)]+\.(?:jpeg|jpg|png|gif))\)'
        
        # 先檢查是否有圖片引用
        matches = re.findall(image_pattern, content)
        print(f"🔎 找到的圖片引用: {matches}")
        
        if not matches:
            print("ℹ️  沒有找到圖片引用，跳過OCR處理")
            return False
        
        modified = False
        
        def replace_image_with_text(match):
            nonlocal modified
            image_filename = match.group(1)
            image_path = md_dir / image_filename
            
            print(f"🔎 處理圖片: {image_filename}")
            print(f"🔎 圖片路徑: {image_path}")
            print(f"🔎 圖片存在: {image_path.exists()}")
            
            if image_path.exists():
                # 提取圖片中的文字
                print(f"🔄 開始OCR處理...")
                extracted_text = self.extract_text_from_image(image_path)
                print(f"🔎 OCR結果長度: {len(extracted_text) if extracted_text else 0}")
                
                if extracted_text:
                    # 將提取的文字格式化並替換圖片引用
                    formatted_text = f"\n\n**[從圖片提取的文字]**\n{extracted_text}\n\n"
                    modified = True
                    
                    # 💾 保留圖片檔案以供debug（不刪除）
                    print(f"🖼️  已處理圖片檔案: {image_filename}（保留原檔案供debug）")
                    
                    return formatted_text
                else:
                    print(f"⚠️  OCR無法提取文字，保留原圖片引用")
                    # 如果無法提取文字，保留原始圖片引用
                    return match.group(0)
            else:
                print(f"⚠️  找不到圖片檔案: {image_path}")
                return match.group(0)
        
        # 替換所有圖片引用
        print(f"🔄 開始替換圖片引用...")
        processed_content = re.sub(image_pattern, replace_image_with_text, content)
        
        # 如果有修改，寫回原始文件
        if modified:
            print(f"💾 寫回修改後的檔案...")
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            print(f"✅ 已更新原始 Markdown 文件: {md_file_path}")
        else:
            print(f"ℹ️  沒有進行任何修改")
        
        return modified
    
    def convert_md_to_json(self, md_file_path, output_dir):
        """將Markdown檔案轉換為JSON"""
        try:
            print(f"📄 開始處理: {md_file_path}")
            
            # 處理圖片中的文字（直接修改原始文件）
            images_processed = self.process_images_in_markdown(md_file_path)
            
            # 讀取（可能已修改的）Markdown檔案
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析內容
            self.parse_markdown_content(content)
            
            # 建立JSON結構
            json_structure = {
                "section": self.section,
                "groups": self.groups
            }
            
            # 生成輸出檔名
            md_filename = Path(md_file_path).stem
            output_filename = Path(output_dir) / f"{md_filename}_converted.json"
            
            # 確保輸出目錄存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # 保存JSON檔案
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(json_structure, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 轉換完成!")
            print(f"📝 JSON檔案: {output_filename}")
            print(f"🔢 Section: {self.section}")
            print(f"📊 Groups數量: {len(self.groups)}")
            
            # 顯示處理結果摘要
            total_items = sum(len(group['items']) for group in self.groups)
            print(f"📋 總項目數: {total_items}")
            
            if images_processed:
                print(f"🖼️  已處理圖片並更新原始文件")
            
            return str(output_filename)
            
        except Exception as e:
            print(f"❌ 轉換失敗: {str(e)}")
            return None
    
    def display_preview(self):
        """顯示轉換結果預覽"""
        if self.groups:
            print("\n🔍 轉換結果預覽:")
            print("=" * 50)
            for i, group in enumerate(self.groups):
                print(f"\n{i+1}. {group['title']}")
                for item in group['items']:
                    clause = item['clause']
                    query = item['query'][:80] + "..." if len(item['query']) > 80 else item['query']
                    print(f"   • {clause}: {query}")
    
    def extract_items_from_ocr_text_enhanced(self, lines, start_index):
        """增強版OCR文字解析，支援多種格式（通用方法）"""
        items_groups = []
        i = start_index + 1
        
        # 合併OCR文字內容，保留換行符以便分析
        ocr_lines = []
        while i < len(lines) and lines[i].strip():
            ocr_lines.append(lines[i].strip())
            i += 1
        
        # 保留行結構和合併文字兩種版本
        ocr_text_with_lines = "\n".join(ocr_lines)
        ocr_text_merged = " ".join(ocr_lines)
        
        print(f"🔍 OCR文字行數: {len(ocr_lines)}")
        print(f"🔍 OCR前100字元: {ocr_text_merged[:100]}...")
        
        # 方法1: 基於實際OCR文字解析
        parsed_groups = self.parse_ocr_content(ocr_text_merged)
        if parsed_groups:
            items_groups.extend(parsed_groups)
            print(f"✅ OCR解析成功，提取了 {len(parsed_groups)} 個群組")
            return items_groups, i
        
        # 方法2: 檢測簡單的a.、b.、c.格式（OCR常見格式）
        # 優先使用保留行結構的版本
        simple_items = self.extract_simple_letter_items_from_ocr(ocr_text_with_lines)
        if not simple_items:
            # 如果失敗，再嘗試合併版本
            simple_items = self.extract_simple_letter_items_from_ocr(ocr_text_merged)
            
        if simple_items:
            # 嘗試從上下文中獲取揭露項目編號
            disclosure_number = self.extract_disclosure_number_from_context_enhanced(lines, start_index)
            
            # 嘗試從上下文中提取標題
            title = self.extract_title_from_context(lines, start_index, disclosure_number)
            
            # 轉換為正確的JSON格式
            formatted_items = []
            for item in simple_items:
                formatted_items.append({
                    "clause": f"{disclosure_number} {item['letter']}",
                    "query": item['content']
                })
            
            group = {
                "title": f"{disclosure_number} {title}",
                "items": formatted_items
            }
            items_groups.append(group)
            print(f"✅ 簡單格式OCR提取了 {len(simple_items)} 個項目")
            return items_groups, i
        
        # 方法3: 尋找明確的揭露項目標識
        disclosure_patterns = [
            r'揭露項目\s*(\d+-\d+)(?:的指引|.*?)',
            r'(\d+-\d+)\s*([^。]{10,50})',  # 簡單的編號+標題模式
        ]
        
        found_disclosures = []
        for pattern in disclosure_patterns:
            matches = re.finditer(pattern, ocr_text_merged)
            for match in matches:
                disclosure_number = match.group(1)
                # 確認編號符合當前section
                if disclosure_number.startswith(self.section):
                    found_disclosures.append((disclosure_number, match.start(), match.end()))
        
        if found_disclosures:
            print(f"🎯 在OCR中找到 {len(found_disclosures)} 個揭露項目")
            for disclosure_number, start_pos, end_pos in found_disclosures:
                # 提取該揭露項目的相關文字
                items = self.parse_disclosure_from_ocr_segment(ocr_text_merged, disclosure_number, start_pos)
                if items:
                    # 提取標題
                    title = self.extract_title_from_ocr(ocr_text_merged, disclosure_number)
                    group = {
                        "title": f"{disclosure_number} {title}",
                        "items": items
                    }
                    items_groups.append(group)
        else:
            print("❌ 在OCR文字中沒有找到標準格式的揭露項目，嘗試其他解析方法...")
            # 方法4: 基於要求文字結構解析
            other_items = self.parse_ocr_requirements(ocr_text_merged)
            if other_items:
                items_groups.extend(other_items)
        
        return items_groups, i
    
    def parse_ocr_content(self, ocr_text):
        """基於實際OCR內容解析，不進行推斷或補全"""
        groups = []
        
        # 步驟1: 檢測是否包含"要求"和"報導組織應報導以下資訊"
        if not re.search(r'要求.*報導組織應報導以下資訊|報導組織應報導以下資訊.*要求', ocr_text):
            return groups
        
        print("🎯 檢測到標準的要求格式，提取實際存在的項目")
        
        # 步驟2: 提取揭露項目編號（如果存在）
        disclosure_number = self.extract_disclosure_number_from_ocr(ocr_text)
        if not disclosure_number:
            disclosure_number = f"{self.section}-?"  # 無法確定時使用問號
        
        # 步驟3: 只提取實際存在的項目，不進行補全
        existing_items = self.extract_existing_items_from_ocr(ocr_text)
        
        # 步驟4: 直接使用提取到的項目，不補全缺失項目
        complete_items = []
        for item in existing_items:
            complete_items.append({
                "clause": f"{disclosure_number} {item['letter']}",
                "query": item['content']
            })
        
        if complete_items:
            # 嘗試從OCR文字中提取標題
            title = self.extract_title_from_ocr(ocr_text, disclosure_number)
            group = {
                "title": f"{disclosure_number} {title}",
                "items": complete_items
            }
            groups.append(group)
            print(f"✅ 提取了 {disclosure_number}，共 {len(complete_items)} 個實際項目")
        
        return groups
    
    def extract_disclosure_number_from_ocr(self, ocr_text):
        """從OCR文字中提取揭露項目編號"""
        # 嘗試多種模式
        patterns = [
            rf'揭露項目\s*({self.section}-\d+)',
            rf'({self.section}-\d+)\s*的指引',
            rf'({self.section}-\d+)',  # 最後嘗試任何符合的編號
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ocr_text)
            if match:
                return match.group(1)
        
        return None
    
    def extract_existing_items_from_ocr(self, ocr_text):
        """從OCR文字中提取已存在的項目"""
        items = []
        
        # 尋找 a., b., c., d., e. 格式的項目
        item_pattern = r'([a-e])\.\s*([^a-e\.]{10,}?)(?=[a-e]\.|指引|例如|$)'
        matches = re.finditer(item_pattern, ocr_text, re.DOTALL)
        
        for match in matches:
            letter = match.group(1)
            content = self.clean_text(match.group(2))
            
            # 清理內容，移除不相關的片段
            content = self.clean_ocr_item_content(content)
            
            if len(content) > 10:  # 確保內容足夠長
                items.append({
                    'letter': letter,
                    'content': content,
                    'found_in_ocr': True
                })
                print(f"   📌 找到OCR項目 {letter}: {content[:50]}...")
        
        return items
    
    def clean_ocr_item_content(self, content):
        """清理OCR項目內容"""
        # 移除常見的OCR錯誤和無關文字
        content = re.sub(r'指引.*$', '', content)  # 移除"指引"後的內容
        content = re.sub(r'例如[:：].*$', '', content)  # 移除"例如:"後的內容
        content = re.sub(r'揭露項目.*$', '', content)  # 移除"揭露項目"後的內容
        content = re.sub(r'\s+', ' ', content)  # 合併多個空格
        content = content.strip(' ,，。.;；')  # 移除結尾的標點符號
        
        return content
    
    def extract_title_from_ocr(self, ocr_text, disclosure_number):
        """從OCR文字中實際提取標題，不使用預設對應"""
        # 嘗試從OCR文字中尋找標題
        title_patterns = [
            rf'揭露項目\s*{re.escape(disclosure_number)}\s*(.+?)(?:要求|指引|$)',
            rf'{re.escape(disclosure_number)}\s*(.+?)(?:要求|指引|$)',
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, ocr_text)
            if match:
                title = self.clean_text(match.group(1))
                if title and len(title) > 3:  # 確保標題有意義
                    return title
        
        # 如果無法從OCR提取標題，返回空字串
        return ""
    
    def parse_disclosure_from_ocr_segment(self, text, disclosure_number, start_pos):
        """從OCR文字段落中解析特定揭露項目的要求"""
        items = []
        
        # 尋找要求部分
        requirements_patterns = [
            r'要求[：:]?\s*報導組織應報導以下資訊[：:]?\s*([^指引]+)',
            r'報導組織應報導以下資訊[：:]?\s*([^指引]+)',
            r'要求[：:]?\s*(.+?)(?:指引|建議|背景|$)',
        ]
        
        for pattern in requirements_patterns:
            match = re.search(pattern, text[start_pos:start_pos+1000])  # 限制搜尋範圍
            if match:
                requirements_text = match.group(1)
                print(f"📋 找到要求文字: {requirements_text[:100]}...")
                
                # 解析要求中的項目
                items = self.parse_requirements_from_text_enhanced(requirements_text, disclosure_number)
                if items:
                    print(f"📊 成功解析出 {len(items)} 個項目")
                    break
        
        return items
    
    def parse_requirements_from_text_enhanced(self, text, disclosure_number):
        """增強版要求文字解析"""
        items = []
        
        # 方法1: 標準的 a. b. c. 格式
        item_pattern = r'([a-e])\.\s*([^a-e\.]{20,}?)(?=[a-e]\.|$)'
        matches = re.finditer(item_pattern, text, re.DOTALL)
        
        for match in matches:
            clause_letter = match.group(1)
            item_text = self.clean_text(match.group(2))
            
            if len(item_text) > 10:  # 過濾太短的內容
                items.append({
                    "clause": f"{disclosure_number} {clause_letter}",
                    "query": item_text
                })
        
        # 方法2: 如果沒找到標準格式，嘗試其他模式
        if not items:
            # 嘗試尋找其他分割模式（如分號、句號等）
            segments = re.split(r'[；;。]\s*', text)
            for i, segment in enumerate(segments):
                segment = self.clean_text(segment)
                if len(segment) > 20:  # 足夠長的段落
                    items.append({
                        "clause": f"{disclosure_number} {chr(97+i)}",  # a, b, c...
                        "query": segment
                    })
                    if i >= 4:  # 最多5個項目 (a-e)
                        break
        
        return items
    
    def parse_ocr_requirements(self, ocr_text):
        """基於要求文字結構解析"""
        items_groups = []
        
        # 基於文字結構尋找揭露項目
        # 模式：尋找可能的項目編號和描述
        
        # 先嘗試找到任何看起來像要求的文字段落
        requirement_indicators = [
            r'要求.*?報導.*?資訊',
            r'報導組織應報導',
            r'應報導以下',
        ]
        
        for pattern in requirement_indicators:
            matches = re.finditer(pattern, ocr_text, re.IGNORECASE)
            for match in matches:
                # 提取要求周圍的文字
                start_pos = max(0, match.start() - 50)
                end_pos = min(len(ocr_text), match.end() + 500)
                requirement_segment = ocr_text[start_pos:end_pos]
                
                # 嘗試從這個段落中提取項目
                items = self.extract_items_from_segment(requirement_segment)
                if items:
                    # 從上下文中提取揭露項目編號
                    disclosure_number = self.extract_disclosure_number_from_context(ocr_text, match.start())
                    title = self.extract_title_from_ocr(ocr_text, disclosure_number)
                    
                    group = {
                        "title": f"{disclosure_number} {title}",
                        "items": items
                    }
                    items_groups.append(group)
                    break  # 找到一個就停止
        
        return items_groups
    
    def extract_items_from_segment(self, segment):
        """從文字段落中提取項目"""
        items = []
        
        # 嘗試多種分割方式
        split_patterns = [
            r'[a-e]\.\s*',  # a. b. c.
            r'[；;]\s*',    # 分號分割
            r'[。]\s*',     # 句號分割
            r'[：]\s*',    # 冒號分割
        ]
        
        for pattern in split_patterns:
            segments = re.split(pattern, segment)
            if len(segments) > 1:  # 找到了分割
                for i, seg in enumerate(segments[1:], 1):  # 跳過第一個空段
                    seg = self.clean_text(seg)
                    if len(seg) > 15:  # 足夠長的內容
                        items.append({
                            "clause": f"{self.section}-? {chr(96+i)}",  # 未知項目編號
                            "query": seg
                        })
                        if i >= 5:  # 最多5個項目
                            break
                if items:
                    break  # 如果找到了項目就停止嘗試其他模式
        
        return items
    
    def extract_disclosure_number_from_context(self, text, position):
        """從上下文中提取揭露項目編號"""
        # 在位置周圍尋找可能的編號
        search_range = text[max(0, position-100):position+100]
        
        # 尋找 XXX-X 格式的編號
        number_pattern = rf'({self.section}-\d+)'
        match = re.search(number_pattern, search_range)
        if match:
            return match.group(1)
        
        # 如果找不到，返回未知格式
        return f"{self.section}-?"
    
    def detect_mixed_format_disclosure(self, lines, current_index):
        """檢測混合格式的揭露項目（非標準但有結構的格式）"""
        line = lines[current_index].strip()
        
        # 檢測可能的格式變化
        # 例如：某些格式可能標題和內容在同一行，或者格式略有不同
        
        # 這裡可以添加更多混合格式的檢測邏輯
        # 目前返回空結果
        return False, []
    
    def is_strong_section_end(self, line):
        """檢查是否是強烈的區段結束信號（比is_requirements_section_end更嚴格）"""
        # 只有在遇到明確的大標題或新section時才認為是結束
        strong_end_patterns = [
            r"^#+\s*(建議|指引|背景)",  # 明確的標題（移除彙編要求）
            r"^揭露項目\s*\*\*\d+-\d+\*\*",     # 新的揭露項目標題
            r"^#.*揭露項目.*\d+-\d+",            # 其他揭露項目格式
        ]
        
        for pattern in strong_end_patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def is_deep_indented_item(self, lines, current_index, disclosure_number):
        """檢查是否是深層縮進項目結構（如 403-9 a）"""
        line = lines[current_index].strip()
        
        # 檢查當前行是否是冒號前置格式（如 "所有員工: **a.**"）
        if re.search(r'(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$', line):
            # 檢查下一行是否有縮進的羅馬數字
            if current_index + 1 < len(lines):
                next_line = lines[current_index + 1]
                if (next_line.startswith('\t') and 
                    re.search(r'\*\*([ivx]+)\.\*\*', next_line.strip())):
                    return True
        
        return False
    
    def extract_deep_indented_item(self, lines, current_index, disclosure_number):
        """提取深層縮進項目（特別處理 403-9 a 這樣的結構）"""
        line = lines[current_index].strip()
        
        # 解析主項目
        match = re.search(r'(.+?)[：:]\s*\*\*([a-e])\.\*\*\s*$', line)
        if not match:
            return None, current_index + 1
        
        main_content = self.clean_text(match.group(1))
        clause_letter = match.group(2)
        
        print(f"   🎯 找到深層縮進主項目: {disclosure_number} {clause_letter} - {main_content[:50]}...")
        
        # 收集縮進的子項目
        subitems = []
        i = current_index + 1
        
        while i < len(lines):
            subline = lines[i].strip()
            original_line = lines[i]
            
            # 跳過空行
            if not subline:
                i += 1
                continue
            
            # 檢查是否是縮進的子項目
            if original_line.startswith('\t'):
                subitem_text = self.extract_roman_subitem(subline)
                if subitem_text:
                    subitems.append(subitem_text)
                    print(f"     📌 深層子項目: {subitem_text[:50]}...")
                    i += 1
                    continue
            
            # 如果遇到不縮進的行，檢查是否是新的主項目
            if self.is_main_item(subline) or self.is_new_disclosure_item(subline):
                print(f"     ⏹️  深層縮進停止，遇到: {subline[:50]}...")
                break
            
            i += 1
        
        # 組合最終結果
        if subitems:
            subitems_text = "、".join(subitems)
            final_query = f"{main_content}:{subitems_text}"
        else:
            final_query = main_content
        
        item = {
            "clause": f"{disclosure_number} {clause_letter}",
            "query": final_query
        }
        
        print(f"   ✅ 深層縮進合併結果: {item['query']}")
        
        return item, i
    
    def extract_simple_letter_items_from_ocr(self, ocr_text):
        """從OCR文字中提取簡單的字母項目格式（a.、b.、c.等）"""
        items = []
        
        print(f"🔍 分析簡單字母格式項目...")
        
        # 按行分割OCR文字進行處理
        lines = ocr_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 檢查是否是簡單的字母項目格式
            # 支援: "a. 內容", "b. 內容" 等
            simple_item_match = re.match(r'^([a-e])\.\s*(.+)', line)
            if simple_item_match:
                letter = simple_item_match.group(1)
                content = simple_item_match.group(2).strip()
                
                # 清理內容
                content = self.clean_text(content)
                if len(content) > 10:  # 確保內容足夠長
                    items.append({
                        "letter": letter,
                        "content": content
                    })
                    print(f"   📌 找到簡單項目 {letter}: {content[:50]}...")
        
        # 如果沒找到分行的格式，嘗試在整個文字中尋找
        if not items:
            # 使用正則表達式匹配所有a.、b.、c.格式
            # 改進：使用更精確的正則表達式來分離項目
            pattern = r'([a-e])\.\s*([^a-e\.]*?)(?=\s*[a-e]\.|$)'
            matches = re.finditer(pattern, ocr_text, re.DOTALL)
            
            for match in matches:
                letter = match.group(1)
                content = self.clean_text(match.group(2))
                
                # 進一步清理內容，移除下一個項目的開頭
                content = re.sub(r'\s*[a-e]\.\s.*$', '', content, flags=re.DOTALL)
                content = content.strip(' .，。')
                
                if len(content) > 10:
                    items.append({
                        "letter": letter,
                        "content": content
                    })
                    print(f"   📌 找到連續項目 {letter}: {content[:50]}...")
        
        return items
    
    def extract_disclosure_number_from_context_enhanced(self, lines, ocr_start_index):
        """從OCR文字周圍的上下文中提取揭露項目編號（增強版）"""
        # 向上搜尋最近的揭露項目標題
        for i in range(ocr_start_index - 1, max(0, ocr_start_index - 10), -1):
            line = lines[i].strip()
            
            # 尋找揭露項目標題
            disclosure_patterns = [
                rf'揭露項目\s*\*\*({self.section}-\d+)\*\*',
                rf'揭露項目\s*({self.section}-\d+)',
                rf'#+\s*揭露項目\s*\*\*({self.section}-\d+)\*\*',
                rf'#+\s*揭露項目\s*({self.section}-\d+)',
            ]
            
            for pattern in disclosure_patterns:
                match = re.search(pattern, line)
                if match:
                    disclosure_number = match.group(1)
                    print(f"🎯 從上下文找到揭露項目編號: {disclosure_number}")
                    return disclosure_number
        
        # 如果找不到，返回未知格式
        return f"{self.section}-?"
    
    def extract_title_from_context(self, lines, ocr_start_index, disclosure_number):
        """從OCR文字周圍的上下文中提取標題"""
        # 向上搜尋最近的揭露項目標題
        for i in range(ocr_start_index - 1, max(0, ocr_start_index - 10), -1):
            line = lines[i].strip()
            
            # 尋找包含disclosure_number的標題行
            title_patterns = [
                rf'#+\s*揭露項目\s*\*\*{re.escape(disclosure_number)}\*\*\s*(.+)',
                rf'#+\s*揭露項目\s*{re.escape(disclosure_number)}\s*(.+)',
                rf'揭露項目\s*\*\*{re.escape(disclosure_number)}\*\*\s*(.+)',
                rf'揭露項目\s*{re.escape(disclosure_number)}\s*(.+)',
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, line)
                if match:
                    title = self.clean_text(match.group(1))
                    print(f"🎯 從上下文找到標題: {title}")
                    return title
        
        # 如果找不到標題，返回預設值
        return "未知項目"

def main():
    parser = argparse.ArgumentParser(description='將GRI PDF檔案轉換為JSON格式（包含PDF→MD→JSON完整流程）')
    parser.add_argument('--input_pdf_dir', default='input_pdf', help='輸入PDF檔案的目錄')
    parser.add_argument('--md_dir', default='pdf_to_md', help='中間Markdown檔案的目錄')
    parser.add_argument('--output_dir', default='output_json', help='輸出JSON檔案的目錄')
    parser.add_argument('--skip_pdf_conversion', action='store_true', help='跳過PDF轉換步驟，直接處理已存在的Markdown檔案')
    
    args = parser.parse_args()
    
    print("🚀 GRI PDF轉JSON完整流程啟動!")
    print("=" * 60)
    
    input_pdf_dir = Path(args.input_pdf_dir)
    md_dir = Path(args.md_dir)
    output_dir = Path(args.output_dir)
    
    # 🆕 自動創建必要的目錄
    print("\n📁 檢查並創建必要的目錄...")
    
    # 檢查並創建 pdf_to_md 目錄
    if not md_dir.exists():
        print(f"📂 創建 Markdown 目錄: {md_dir}")
        md_dir.mkdir(parents=True, exist_ok=True)
    else:
        print(f"✅ Markdown 目錄已存在: {md_dir}")
    
    # 檢查並創建 output_json 目錄
    if not output_dir.exists():
        print(f"📂 創建 JSON 輸出目錄: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        print(f"✅ JSON 輸出目錄已存在: {output_dir}")
    
    # 檢查並創建 input_pdf 目錄（如果需要進行PDF轉換）
    if not args.skip_pdf_conversion and not input_pdf_dir.exists():
        print(f"📂 創建 PDF 輸入目錄: {input_pdf_dir}")
        input_pdf_dir.mkdir(parents=True, exist_ok=True)
        print(f"💡 請將要轉換的PDF檔案放入 {input_pdf_dir} 目錄中")
    
    # 步驟1: PDF轉Markdown（如果沒有跳過的話）
    if not args.skip_pdf_conversion:
        print("\n📋 步驟1: PDF轉Markdown")
        print("-" * 40)
        
        # 檢查input_pdf目錄是否存在
        if not input_pdf_dir.exists():
            print(f"❌ 輸入目錄不存在: {input_pdf_dir}")
            return
        
        # 查找所有PDF檔案
        pdf_files = list(input_pdf_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"❌ 在 {input_pdf_dir} 中沒有找到 .pdf 檔案")
            return
        
        print(f"📄 找到 {len(pdf_files)} 個PDF檔案:")
        for pdf_file in pdf_files:
            print(f"   • {pdf_file.name}")
        
        # 使用marker轉換所有PDF（目錄已在前面創建）
        print(f"\n🔄 使用marker轉換PDF檔案...")
        try:
            import subprocess
            result = subprocess.run([
                'marker', str(input_pdf_dir), '--output_dir', str(md_dir)
            ], capture_output=True, text=True, cwd=str(Path.cwd()))
            
            if result.returncode == 0:
                print("✅ PDF轉換完成!")
                print(f"📁 Markdown檔案已保存到: {md_dir}")
            else:
                print(f"❌ PDF轉換失敗: {result.stderr}")
                return
                
        except FileNotFoundError:
            print("❌ 找不到marker指令，請確認marker已正確安裝")
            print("💡 您可以使用 --skip_pdf_conversion 參數跳過此步驟")
            return
        except Exception as e:
            print(f"❌ PDF轉換過程發生錯誤: {str(e)}")
            return
    else:
        print("\n⏭️  跳過PDF轉換步驟，直接處理已存在的Markdown檔案")
    
    # 步驟2: Markdown轉JSON（包含OCR處理）
    print("\n📋 步驟2: Markdown轉JSON（包含OCR圖片處理）")
    print("-" * 50)
    
    # 查找所有markdown檔案
    md_files = list(md_dir.rglob("*.md"))
    
    if not md_files:
        print(f"❌ 在 {md_dir} 中沒有找到 .md 檔案")
        print("💡 請確認PDF轉換步驟是否成功完成")
        return
    
    print(f"📄 找到 {len(md_files)} 個Markdown檔案:")
    for md_file in md_files:
        print(f"   • {md_file}")
    
    # 處理每個markdown檔案（目錄已在前面創建）
    success_count = 0
    total_items = 0
    
    for md_file in md_files:
        print(f"\n🔄 處理檔案: {md_file}")
        print("-" * 30)
        
        converter = GRIMarkdownToJsonConverter()
        result = converter.convert_md_to_json(md_file, output_dir)
        
        if result:
            converter.display_preview()
            print(f"✅ {md_file.name} -> {Path(result).name}")
            success_count += 1
            total_items += sum(len(group['items']) for group in converter.groups)
        else:
            print(f"❌ 處理失敗: {md_file.name}")
    
    # 最終統計
    print("\n" + "=" * 60)
    print("🎉 完整流程處理完成!")
    print(f"📊 處理統計:")
    print(f"   • 成功處理: {success_count}/{len(md_files)} 個檔案")
    print(f"   • 總提取項目數: {total_items}")
    print(f"📁 JSON檔案已保存到: {output_dir}")
    
    # 列出生成的JSON檔案
    json_files = list(output_dir.glob("*.json"))
    if json_files:
        print(f"\n📋 生成的JSON檔案:")
        for json_file in json_files:
            print(f"   • {json_file.name}")
    
    print("\n✨ 所有任務完成! 您可以在output_json目錄中查看轉換結果。")

if __name__ == "__main__":
    main() 
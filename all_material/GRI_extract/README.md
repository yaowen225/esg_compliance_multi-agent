# GRI PDF轉JSON轉換器

🌱 一個專為GRI（Global Reporting Initiative）永續報告書設計的PDF轉JSON自動化工具

## 📋 專案簡介

這個工具能夠將GRI永續報告書的PDF文件自動轉換為結構化的JSON格式，支援：
- 📄 **PDF自動轉換**：使用marker工具將PDF轉為Markdown
- 🖼️ **圖片OCR處理**：自動識別並提取圖片中的文字內容
- 🔍 **智能項目提取**：精確提取揭露項目的條款項目（a, b, c, d）和羅馬數字子項目
- 📊 **結構化輸出**：產生標準JSON格式，便於後續資料分析

## ✨ 功能特色

### 🎯 核心功能
- **完整流程自動化**：PDF → Markdown → JSON 一鍵完成
- **多格式支援**：支援列表格式、標題格式、簡單格式等多種markdown結構
- **OCR增強**：高品質圖片自動OCR，智能跳過低品質圖片
- **智能解析**：自動識別GRI編號、項目標題和內容結構

### 📈 處理能力
- ✅ **GRI 203**：經濟績效相關項目（2群組5項目）
- ✅ **GRI 303**：水與污水相關項目（5群組18項目）  
- ✅ **GRI 403**：職業安全衛生項目（10群組26項目）
- 🔄 **總計**：17群組49項目完整提取

### 🛠️ 技術特點
- **通用邏輯設計**：能處理不同格式變化並提供回退機制
- **錯誤容忍**：多層級回溯檢查確保不遺漏項目
- **中文友善**：完整中文界面和提示信息
- **新手友善**：自動創建目錄，無需手動設置

## 🚀 快速開始

### 📋 系統需求
- Python 3.7+
- Windows 10/11（測試環境）
- 至少2GB可用磁碟空間

### 🔧 安裝步驟

1. **克隆專案**
```bash
git clone <專案網址>
cd <專案目錄>
```

2. **安裝Python依賴**
```bash
pip install -r requirements.txt
```

3. **安裝marker工具**（用於PDF轉換）
```bash
pip install marker-pdf
```

### 📖 使用方法

#### 🎯 完整流程（PDF → JSON）
```bash
# 將PDF檔案放入 input_pdf 目錄
# 執行完整轉換流程
python gri_to_json_converter.py
```

#### ⚡ 僅處理Markdown檔案
```bash
# 如果已有Markdown檔案，跳過PDF轉換
python gri_to_json_converter.py --skip_pdf_conversion
```

#### 🛠️ 自訂目錄
```bash
python gri_to_json_converter.py \
    --input_pdf_dir "我的PDF目錄" \
    --md_dir "我的MD目錄" \
    --output_dir "我的輸出目錄"
```

### 📁 目錄結構
程式會自動創建以下目錄：
```
專案目錄/
├── input_pdf/          # PDF輸入目錄
├── pdf_to_md/          # 中間Markdown檔案
├── output_json/        # JSON輸出目錄
├── gri_to_json_converter.py
├── requirements.txt
└── README.md
```

## 📊 輸出格式

生成的JSON檔案格式：
```json
{
  "section": "303",
  "groups": [
    {
      "title": "303-1 與水共享資源的相互影響",
      "items": [
        {
          "clause": "303-1 a",
          "query": "組織如何與水互動的描述..."
        }
      ]
    }
  ]
}
```

## 🔍 處理範例

### 輸入範例
```markdown
## 揭露項目 **303-1** 與水共享資源的相互影響

要求：報導組織應報導以下資訊：

- **a.** 組織如何與水互動的描述，包括：
    - **i.** 用水量
    - **ii.** 耗水量
    - **iii.** 排水量
```

### 輸出結果
```json
{
  "clause": "303-1 a",
  "query": "組織如何與水互動的描述：用水量、耗水量、排水量"
}
```

## 🛠️ 技術細節

### 🧠 解析邏輯
1. **Section識別**：從揭露項目標題中提取GRI編號
2. **項目提取**：支援 a, b, c, d, e 等字母編號項目
3. **子項目合併**：自動合併羅馬數字子項目（i, ii, iii, iv, v）
4. **OCR處理**：使用EasyOCR提取圖片文字並智能合併

### 🔧 核心模組
- `GRIMarkdownToJsonConverter`：主要轉換器類別
- `extract_requirement_items`：項目提取核心邏輯
- `extract_items_from_ocr_text_enhanced`：OCR文字處理
- `extract_single_item_with_subitems`：項目與子項目合併

## 🎯 使用場景

### 📈 適用對象
- **ESG顧問公司**：大量處理客戶永續報告書
- **研究機構**：分析GRI報告趨勢和內容
- **企業永續部門**：整理和分析自家報告內容
- **資料科學家**：建立永續報告資料庫

### 📊 處理規模
- **單檔處理**：1-2分鐘完成單個PDF轉換
- **批次處理**：支援同時處理多個PDF檔案
- **OCR處理**：平均每張圖片2-5秒處理時間

## ⚠️ 注意事項

1. **PDF品質**：建議使用文字清晰的PDF檔案
2. **圖片內容**：OCR主要處理包含文字的圖片，圖表效果有限
3. **格式變化**：部分特殊格式可能需要手動調整
4. **記憶體使用**：處理大型PDF時建議至少4GB記憶體

## 🔧 疑難排解

### 常見問題

**Q: marker安裝失敗？**
```bash
# 嘗試指定版本安裝
pip install marker-pdf==0.2.15
```

**Q: OCR無法識別中文？**
```bash
# 確認安裝了中文語言包
pip install easyocr --upgrade
```

**Q: 處理速度很慢？**
- 檢查PDF檔案大小（建議<50MB）
- 關閉不必要的背景程式
- 考慮使用SSD硬碟

## 🤝 貢獻指南

歡迎提交Bug報告和功能建議！

1. Fork專案
2. 創建功能分支
3. 提交變更
4. 發起Pull Request

## 📄 授權協議

本專案採用 MIT 授權協議 - 詳見 [LICENSE](LICENSE) 檔案

## 📞 技術支援

如有問題或建議，請通過以下方式聯繫：
- 📧 Email: [您的email]
- 💬 Issue: [GitHub Issues連結]

---

⭐ 如果這個工具對您有幫助，請給我們一個Star！

📚 更多GRI相關工具和資源，請關注我們的專案。 
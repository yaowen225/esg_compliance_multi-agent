# GRI PDF轉JSON轉換器

🌱 一個專為GRI（Global Reporting Initiative）永續報告書設計的PDF轉JSON自動化工具

## 📋 專案簡介

這個工具能夠將GRI永續報告書的PDF文件自動轉換為結構化的JSON格式，支援：
- 📄 **PDF自動轉換**：使用marker工具將PDF轉為Markdown
- 🖼️ **高品質OCR處理**：使用Tesseract OCR自動識別並提取圖片中的繁體中文文字內容
- 🔍 **智能項目提取**：精確提取揭露項目的條款項目（a, b, c, d）和羅馬數字子項目
- 📊 **結構化輸出**：產生標準JSON格式，便於後續資料分析

## ✨ 功能特色

### 🎯 核心功能
- **完整流程自動化**：PDF → Markdown → JSON 一鍵完成
- **多格式支援**：支援列表格式、標題格式、簡單格式等多種markdown結構
- **高品質OCR增強**：使用Tesseract OCR進行繁體中文圖片文字提取，支援跨行內容合併
- **智能解析**：自動識別GRI編號、項目標題和內容結構

### 📈 處理能力
- ✅ **GRI 203**：間接經濟衝擊相關項目（2群組5項目）
- ✅ **GRI 303**：水與污水相關項目（5群組18項目）  
- ✅ **GRI 403**：職業安全衛生項目（10群組26項目）
- 🔄 **總計**：17群組49項目完整提取

### 🛠️ 技術特點
- **超高解析度OCR**：6倍放大處理，CLAHE對比度增強，優化繁體中文識別
- **多配置OCR引擎**：7種不同的Tesseract配置，自動選擇最佳結果
- **跨行內容合併**：智能識別和合併分散在多行的項目內容
- **通用邏輯設計**：能處理不同格式變化並提供回退機制
- **錯誤容忍**：多層級回溯檢查確保不遺漏項目
- **中文友善**：完整中文界面和提示信息
- **新手友善**：自動創建目錄，無需手動設置

## 🚀 快速開始

### 📋 系統需求
- Python 3.7+
- Windows 10/11（測試環境）
- 至少4GB可用記憶體
- 至少2GB可用磁碟空間

### 🔧 安裝步驟

#### 步驟1：安裝Python依賴
```bash
# 1. 克隆專案
git clone <專案網址>
cd <專案目錄>

# 2. 建立虛擬環境（推薦）
python -m venv gri_env
# 啟動虛擬環境
gri_env\Scripts\activate  # Windows
# 或者使用
source gri_env/bin/activate  # macOS/Linux

# 3. 安裝Python依賴
pip install -r requirements.txt

# 4. 安裝marker工具（用於PDF轉換）
pip install marker-pdf
```

#### 步驟2：安裝Tesseract OCR（繁體中文支援）

##### Windows安裝方法

**方法A：使用官方安裝包（推薦）**
```bash
# 1. 下載Tesseract安裝包
# 前往：https://github.com/UB-Mannheim/tesseract/wiki
# 下載最新版本的tesseract-ocr-w64-setup-v5.x.x.exe

# 2. 執行安裝包，選擇安裝目錄
# 推薦安裝到：C:\Program Files\Tesseract-OCR\

# 3. 安裝過程中確保勾選"Additional language data"
# 特別確保選擇了"Chinese Traditional (chi_tra)"

# 4. 驗證安裝
C:\Program Files\Tesseract-OCR\tesseract.exe --version
```

**方法B：使用Chocolatey包管理器**
```powershell
# 1. 安裝Chocolatey（如果尚未安裝）
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# 2. 安裝Tesseract和繁體中文語言包
choco install tesseract
choco install tesseract-chinese-traditional
```

**方法C：使用Conda（適用於Anaconda用戶）**
```bash
# 在conda環境中安裝
conda install -c conda-forge tesseract
# 或者
conda install -c simonflueckiger tesseract
```

##### 繁體中文語言包安裝

如果安裝過程中沒有包含繁體中文語言包，需要手動添加：

```bash
# 1. 下載繁體中文語言包
# 前往：https://github.com/tesseract-ocr/tessdata
# 下載 chi_tra.traineddata

# 2. 複製到Tesseract安裝目錄
# 將下載的chi_tra.traineddata複製到：
# C:\Program Files\Tesseract-OCR\tessdata\

# 3. 驗證語言包
C:\Program Files\Tesseract-OCR\tesseract.exe --list-langs
# 應該會看到 chi_tra 在列表中
```

#### 步驟3：安裝Python OCR依賴

```bash
# 在虛擬環境中安裝
pip install pytesseract opencv-python-headless pillow numpy

# 驗證安裝
python -c "import pytesseract; print('✅ pytesseract安裝成功')"
python -c "import cv2; print('✅ opencv安裝成功')"
```

#### 步驟4：環境變數配置（可選）

如果程式無法自動找到Tesseract，可以手動設置環境變數：

**Windows方法A：系統環境變數**
```powershell
# 添加到系統PATH
$env:PATH += ";C:\Program Files\Tesseract-OCR"
# 設置TESSDATA_PREFIX
$env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"
```

**Windows方法B：在虛擬環境中設置**
```powershell
# 在虛擬環境的activate.bat中添加
echo "set PATH=%PATH%;C:\Program Files\Tesseract-OCR" >> gri_env\Scripts\activate.bat
echo "set TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata" >> gri_env\Scripts\activate.bat
```

#### 步驟5：驗證完整安裝

```bash
# 測試Tesseract OCR功能
python -c "
import pytesseract
import cv2
import numpy as np
from PIL import Image

# 測試基本功能
print('✅ 所有OCR依賴安裝成功')
print('✅ 可用語言:', pytesseract.get_languages())
print('✅ Tesseract版本:', pytesseract.get_tesseract_version())
"
```

### 📖 使用方法

#### 🎯 完整流程（PDF → JSON）
```bash
# 確保虛擬環境已啟動
gri_env\Scripts\activate  # Windows

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
├── gri_env/               # 虛擬環境目錄
├── input_pdf/             # PDF輸入目錄
├── pdf_to_md/             # 中間Markdown檔案
├── output_json/           # JSON輸出目錄
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
          "query": "組織如何與水互動的描述：用水量、耗水量、排水量"
        }
      ]
    }
  ]
}
```

## 🔍 處理範例

### 輸入範例（含OCR圖片處理）
```markdown
## 揭露項目 **303-1** 與水共享資源的相互影響

要求：報導組織應報導以下資訊：

![](image_001.png)
```

### OCR處理過程
```
🖼️ 發現OCR文字區塊
🔍 正在從圖片提取繁體中文文字: image_001.png
🎯 使用超高解析度處理策略
📏 超高解析度處理: 800x600 -> 4800x3600
🎯 最佳配置: 高精度單行 (長度: 156)
✅ OCR成功提取繁體中文文字（156字元）
```

### 輸出結果
```json
{
  "clause": "303-1 a",
  "query": "組織如何與水互動的描述，包括用水量、耗水量、排水量"
}
```

## 🛠️ 技術細節

### �� OCR增強策略
1. **超高解析度處理**：6倍圖片放大，確保至少1000像素
2. **對比度增強**：CLAHE自適應直方圖均衡化
3. **降噪處理**：中值濾波保留邊緣細節
4. **多配置引擎**：7種Tesseract配置自動選擇最佳結果

### 🔧 核心模組
- `GRIMarkdownToJsonConverter`：主要轉換器類別
- `extract_requirement_items`：項目提取核心邏輯
- `extract_simple_letter_items_from_ocr`：OCR文字處理與跨行合併
- `extract_single_item_with_subitems`：項目與子項目合併

### 📋 支援的OCR配置
| 配置名稱 | PSM模式 | OEM引擎 | 適用場景 |
|---------|---------|---------|----------|
| 高精度單行 | PSM 6 | OEM 3 | 標準文字行 |
| 垂直文字專用 | PSM 5 | OEM 3 | 垂直排列文字 |
| 稀疏文字處理 | PSM 8 | OEM 3 | 分散的文字 |
| 自動分割優化 | PSM 3 | OEM 3 | 複雜版面 |
| 混合語言處理 | PSM 6 | chi_tra+eng | 中英文混合 |
| 單字符優化 | PSM 10 | OEM 3 | 個別字符 |
| LSTM引擎 | PSM 6 | OEM 1 | 原始LSTM |

## 🎯 使用場景

### 📈 適用對象
- **ESG顧問公司**：大量處理客戶永續報告書
- **研究機構**：分析GRI報告趨勢和內容
- **企業永續部門**：整理和分析自家報告內容
- **資料科學家**：建立永續報告資料庫

### 📊 處理規模
- **單檔處理**：1-2分鐘完成單個PDF轉換
- **批次處理**：支援同時處理多個PDF檔案
- **OCR處理**：平均每張圖片3-8秒處理時間（含超高解析度處理）

## ⚠️ 注意事項

1. **PDF品質**：建議使用文字清晰的PDF檔案
2. **圖片內容**：OCR主要處理包含繁體中文文字的圖片，圖表效果有限
3. **格式變化**：部分特殊格式可能需要手動調整
4. **記憶體使用**：處理大型PDF時建議至少4GB記憶體
5. **虛擬環境**：強烈建議使用虛擬環境避免套件衝突

## 🔧 疑難排解

### 常見問題

**Q: Tesseract OCR安裝失敗？**
```bash
# 方法1：檢查PATH環境變數
echo $env:PATH | Select-String "Tesseract"

# 方法2：手動指定路徑
$env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"

# 方法3：重新安裝指定版本
choco uninstall tesseract
choco install tesseract --version=5.3.0
```

**Q: 找不到繁體中文語言包？**
```bash
# 檢查語言包
C:\Program Files\Tesseract-OCR\tesseract.exe --list-langs
# 如果沒有chi_tra，手動下載並放置到tessdata目錄
```

**Q: OCR無法識別中文？**
```bash
# 測試OCR功能
python -c "
import pytesseract
print('可用語言:', pytesseract.get_languages())
# 確認 'chi_tra' 在列表中
"
```

**Q: marker安裝失敗？**
```bash
# 嘗試指定版本安裝
pip install marker-pdf==0.2.15
# 或更新pip
pip install --upgrade pip
```

**Q: 處理速度很慢？**
- 檢查PDF檔案大小（建議<50MB）
- 關閉不必要的背景程式
- 考慮使用SSD硬碟
- 調整OCR圖片解析度設定

**Q: 虛擬環境中找不到Tesseract？**
```bash
# 在虛擬環境的activate腳本中添加路徑
echo "set PATH=%PATH%;C:\Program Files\Tesseract-OCR" >> gri_env\Scripts\activate.bat
# 重新啟動虛擬環境
deactivate
gri_env\Scripts\activate
```

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
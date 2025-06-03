from markitdown import MarkItDown
import os
import shutil

# 設定輸入和輸出資料夾
input_folder = "C:\\Users\\USER\\Desktop\\code\\esg_compliance_multi-agent\\all_material\\user_input"      # 你的輸入資料夾名稱
output_folder = "C:\\Users\\USER\\Desktop\\code\\esg_compliance_multi-agent\\all_material\\preprocessing_data\\output"    # 你的輸出資料夾名稱

# 支援的檔案格式
supported_formats = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls']

# 建立 MarkItDown 實例
md = MarkItDown()

# 建立輸出資料夾（如果不存在的話）
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 遍歷輸入資料夾中的所有檔案和子資料夾
for root, dirs, files in os.walk(input_folder):
    for file in files:
        # 檢查檔案格式是否支援
        file_ext = os.path.splitext(file)[1].lower()
        if file_ext in supported_formats:
            
            # 建立完整的輸入檔案路徑
            input_file_path = os.path.join(root, file)
            
            # 計算相對於輸入資料夾的路徑
            relative_path = os.path.relpath(root, input_folder)
            
            # 建立對應的輸出資料夾路徑
            if relative_path == ".":  # 如果檔案在根目錄
                output_dir = output_folder
            else:
                output_dir = os.path.join(output_folder, relative_path)
            
            # 確保輸出目錄存在
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 產生輸出檔案名稱（保持原名但改副檔名為 .md）
            base_name = os.path.splitext(file)[0]
            output_file_name = f"{base_name}.md"
            output_file_path = os.path.join(output_dir, output_file_name)
            
            try:
                print(f"轉換中: {input_file_path}")
                
                # 轉換檔案
                result = md.convert(input_file_path)
                
                # 寫入輸出檔案
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(result.text_content)
                
                print(f"完成: {output_file_path}")
                
            except Exception as e:
                print(f"轉換失敗 {input_file_path}: {str(e)}")

print("批次轉換完成！")
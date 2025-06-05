from openai import OpenAI
import chromadb
import json
import re
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

# 載入.env檔案
load_dotenv()

class OpenAIEmbeddingFunction:
    def __init__(self, model="text-embedding-ada-002"):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    def name(self):
        return "openai"

    def __call__(self, input):
        # 確保輸入是列表
        if isinstance(input, str):
            input = [input]
        
        # 獲取 embeddings
        embeddings = []
        for text in input:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embeddings.append(response.data[0].embedding)
        
        return embeddings

# 建立向量資料庫結構
def setup_collection():
    # 設定資料庫路徑
    db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
    
    # 建立 ChromaDB 客戶端，指定持久化路徑
    client = chromadb.PersistentClient(path=db_path)
    
    # 檢查集合是否存在
    collections = client.list_collections()
    collection_exists = any(col.name == "esg_gri_collection" for col in collections)
    
    if collection_exists:
        # 如果集合存在，直接獲取
        collection = client.get_collection(
            name="esg_gri_collection",
            embedding_function=OpenAIEmbeddingFunction()
        )
        print(f"已載入現有的向量資料庫，路徑：{db_path}")
    else:
        # 如果集合不存在，創建新的集合
        print(f"建立新的向量資料庫，路徑：{db_path}")
        collection = client.create_collection(
            name="esg_gri_collection",
            embedding_function=OpenAIEmbeddingFunction(),
            metadata={"description": "ESG報告水資源管理段落與GRI準則對應"}
        )
    
    return collection

def add_esg_report_content(collection, report_content, metadata, index):
    """
    添加 ESG 報告書內容到資料庫
    
    參數:
    - report_content: 報告書內容（可以是段落或句子）
    - metadata: {
        "report_year": "2023",
        "company": "台積電",
        "section": "水資源管理"
    }
    - index: 段落的索引編號
    """
    collection.add(
        documents=[report_content],
        metadatas=[metadata],
        ids=[f"{metadata['company']}_{metadata['report_year']}_{metadata.get('section', 'unknown')}_{index}"]
    )

def optimize_query_with_llm(query_text):
    """
    使用 LLM 優化查詢文本
    
    參數:
    - query_text: 原始查詢文本
    
    返回:
    - 優化後的查詢文本
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"""
        你是一個專業的ESG報告分析助手。以下的查詢文本是GRI準則的內容，我們的目的是要利用這個文本，將它當作QUERY去檢索esg報告書確保是否有符合的內容，所以請幫我優化這個文本，使其更適合用於搜尋ESG報告中的相關內容。
        請保持原始查詢的核心意圖，但使用更精確和專業的詞彙。
        
        原始查詢：{query_text}
        
        請直接返回優化後的查詢文本，不需要其他說明。
        """
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一個專業的ESG報告分析助手，負責優化查詢文本。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        optimized_query = response.choices[0].message.content.strip()
        return optimized_query
    except Exception as e:
        print(f"LLM優化查詢時發生錯誤: {str(e)}")
        return query_text

def filter_results_by_relevance(results, threshold=0.8):
    """
    根據相關性分數過濾查詢結果
    
    參數:
    - results: 查詢結果
    - threshold: 相關性閾值
    
    返回:
    - 過濾後的結果
    """
    if not results["documents"] or not results["distances"]:
        return results
    
    filtered_docs = []
    filtered_distances = []
    
    for doc, distance in zip(results["documents"][0], results["distances"][0]):
        # 將距離轉換為相關性分數 (0-1)
        relevance_score = 1 - (distance / 2)  # 假設最大距離為2
        
        if relevance_score >= threshold:
            filtered_docs.append(doc)
            filtered_distances.append(distance)
    
    return {
        "documents": [filtered_docs],
        "distances": [filtered_distances]
    }

def query_by_gri_standard(collection, query_text, n_results=5):
    """
    根據GRI準則查詢相關的報告書段落
    
    參數:
    - collection: ChromaDB集合
    - query_text: GRI準則的查詢內容
    - n_results: 返回結果數量
    
    返回:
    - 符合條件的報告書段落列表
    """
    try:
        # 使用 LLM 優化查詢文本
        optimized_query = optimize_query_with_llm(query_text)
        
        # 優化查詢文本格式
        optimized_query = re.sub(r'[，。、；：！？]', ' ', optimized_query)
        optimized_query = re.sub(r'\s+', ' ', optimized_query).strip()
        
        print(f"\n原始查詢: {query_text}")
        print(f"優化後查詢: {optimized_query}")
        
        # 執行查詢
        results = collection.query(
            query_texts=[optimized_query],
            include=["documents", "distances"],
            n_results=n_results
        )
        
        # 過濾結果
        filtered_results = filter_results_by_relevance(results)
        
        print(f"查詢結果數量: {len(filtered_results['documents'][0])}")
        return filtered_results
    except Exception as e:
        print(f"查詢時發生錯誤: {str(e)}")
        return {"documents": [[]], "distances": [[]]}

def process_gri_standards(input_file, collection):
    """
    處理GRI準則並查詢相關內容
    
    參數:
    - input_file: GRI準則的JSON檔案路徑
    - collection: ChromaDB集合
    """
    print(f"\n開始處理檔案: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        input_data = json.load(f)
    
    print(f"讀取到 {len(input_data['groups'])} 個群組")
    output_data = {"rag_results": []}
    
    for group in input_data["groups"]:
        print(f"\n處理群組: {group['title']}")
        group_result = {
            "title": group["title"],
            "items": []
        }
        
        for item in group["items"]:
            clause = item["clause"]
            query = item["query"]
            
            # 使用GRI準則的查詢內容進行搜索
            results = query_by_gri_standard(collection, query)
            
            # 整理查詢結果，保留所有結果
            answers = []
            if results["documents"] and len(results["documents"]) > 0:
                documents = results["documents"][0]
                distances = results["distances"][0]
                
                print(f"找到 {len(documents)} 個結果")
                for doc, distance in zip(documents, distances):
                    answers.append({
                        "content": doc
                    })
            else:
                print("沒有找到任何結果")
            
            item_result = {
                "clause": clause,
                "query": query,
                "answers": answers
            }
            
            group_result["items"].append(item_result)
        
        output_data["rag_results"].append(group_result)
    
    return output_data

def process_markdown_content(md_content):
    """
    處理Markdown內容，將其分割成適當的段落
    
    參數:
    - md_content: Markdown格式的文本內容
    
    返回:
    - 處理後的段落列表
    """
    print("\n開始處理Markdown內容...")
    print(f"原始內容長度: {len(md_content)} 字元")
    
    # 移除Markdown標記
    content = re.sub(r'#+ ', '', md_content)  # 移除標題標記
    content = re.sub(r'\*\*|\*|__|_', '', content)  # 移除粗體和斜體標記
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # 移除連結標記
    
    # 過濾掉包含 .png 的行
    lines = content.split('\n')
    filtered_lines = [line for line in lines if '.png' not in line]
    content = '\n'.join(filtered_lines)
    
    # 先按標題分割
    sections = re.split(r'(?m)^(?=#)', content)
    
    cleaned_paragraphs = []
    
    for section in sections:
        # 移除空行並分割段落
        lines = [line.strip() for line in section.split('\n') if line.strip()]
        
        # 合併相關的段落
        current_paragraph = []
        for line in lines:
            tmp_text = ' '.join(current_paragraph)
            if len(tmp_text)+len(line) >= 8100:
                cleaned_paragraphs.append(' '.join(current_paragraph))
                current_paragraph = [line]
            # 如果遇到句號、問號或驚嘆號，可能是段落結束
            if re.search(r'[。？！]$', line):
                current_paragraph.append(line)
                if current_paragraph:
                    cleaned_paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
            # 其他情況，繼續當前段落
            else:
                current_paragraph.append(line)
        
        # 處理最後一個段落
        if current_paragraph:
            cleaned_paragraphs.append(' '.join(current_paragraph))
    
    # 過濾太短的段落
    cleaned_paragraphs = [para for para in cleaned_paragraphs if len(para) > 10]
    
    print(f"清理後保留 {len(cleaned_paragraphs)} 個段落")
    
    # 顯示前幾個段落的內容
    print("\n前3個段落的內容:")
    for i, para in enumerate(cleaned_paragraphs[:3]):
        print(f"\n段落 {i}:")
        print(para)
    
    return cleaned_paragraphs

def add_esg_report_to_db(collection, md_file, metadata):

    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 處理Markdown內容
    paragraphs = process_markdown_content(md_content)
    print(f"從檔案中提取出 {len(paragraphs)} 個段落")
    
    # 將每個段落添加到資料庫
    for i, paragraph in enumerate(paragraphs):
        add_esg_report_content(collection, paragraph, metadata, i)
    
    print(f"已將 {len(paragraphs)} 個段落添加到資料庫")

def ReportRetriverAgent():

    # 初始化集合
    collection = setup_collection()

    
    # 設定報告書元數據
    report_metadata = {
        "report_year": "2023",
        "company": "台積電",
        "section": "GRI 203, 303, 403"
    }
    
    # 將ESG報告書內容添加到資料庫
    report_path = os.path.join(os.path.dirname(__file__), "marker方法", "部分之ESG報告書", "esg_report.md")
    add_esg_report_to_db(collection, report_path, report_metadata)
    print("ESG報告書內容已添加到資料庫")
    
    # 處理GRI準則並查詢相關內容
    print("\n開始處理GRI準則...")
    output_data = process_gri_standards("data/gri_json/GRI 203_converted.json", collection)
    
    # 將結果寫入輸出檔案
    print("\n將結果寫入檔案...")
    with open("real_output.json", 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print("程式執行完成")

if __name__ == "__main__":
    ReportRetriverAgent()

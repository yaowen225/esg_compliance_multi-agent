from openai import OpenAI
import os

def test_openai_api():
    # 設定API金鑰
    api_key = "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"
    
    try:
        # 初始化OpenAI客戶端
        client = OpenAI(api_key=api_key)
        
        # 測試1：測試embeddings功能
        print("測試embeddings功能...")
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input="這是一個測試句子"
        )
        print("Embeddings測試成功！")
        print(f"Embedding向量長度: {len(response.data[0].embedding)}")
        
        # 測試2：測試completions功能
        print("\n測試completions功能...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "請說你好"}
            ]
        )
        print("Completions測試成功！")
        print(f"回應內容: {response.choices[0].message.content}")
        
        return True
        
    except Exception as e:
        print(f"測試失敗！錯誤訊息：{str(e)}")
        return False

if __name__ == "__main__":
    print("開始測試OpenAI API...")
    success = test_openai_api()
    if success:
        print("\n所有測試都成功完成！API金鑰運作正常。")
    else:
        print("\n測試過程中發生錯誤，請檢查API金鑰或網路連接。")

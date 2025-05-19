graph TD
    A[用戶] -->|輸入ESG報告| B[協調代理 CoordinatorAgent]
    
    B -->|初始化任務清單| J[(任務狀態庫)]
    B -->|開始分析流程| L[GRI標準選擇代理 GRISelectionAgent]
    
    subgraph "GRI驅動迭代分析循環"
        L -->|選擇下一個GRI標準<br>例如GRI 305-1| D[GRI標準提取代理 GRIRetrieverAgent]
        D <-->|檢索GRI標準詳細要求| O[(GRI標準RAG知識庫)]
        
        D -->|提供GRI要求清單| C[報告內容檢索代理 ReportRetrieverAgent]
        C <-->|檢索相關報告內容| P[(ESG報告RAG知識庫)]
        
        C -->|定位並提取報告<br>相關段落| N[合規分析代理 ComplianceAnalysisAgent]
        
        N -->|逐項分析結果| J
        J -->|更新待分析清單| L
    end
    
    L -->|所有GRI標準<br>分析完成| H[結果整合代理 ResultsIntegrationAgent]
    H -->|整合分析結果| B
    B -->|生成最終報告| A

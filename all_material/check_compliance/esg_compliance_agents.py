import asyncio, json, os, re, aiomysql, pandas as pd
from pathlib import Path
from typing import Sequence, Dict, Any, List, Tuple

from dotenv import load_dotenv, find_dotenv
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_agentchat.base import Response
from autogen_core import CancellationToken
from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

# ──────────────────────────────────── 基本設定 ────────────────────────────────────
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path if env_path.exists() else find_dotenv(), override=False)

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("缺少 OPENAI_API_KEY，請檢查 .env")

MYSQL_CONFIG = dict(
    host="127.0.0.1", port=3306, user="root", password="55665566",
    db="esg_reports", autocommit=True, charset="utf8mb4",
)

TEST_PAIRS_JSON      = "test_pairs.json"
TEST_EXCEL_OUTPUT    = "compliance_summary_report.xlsx"
MODEL_NAME           = "gpt-4.1"

# ─────────────────────────────── 資料庫：建立 / 更新 ───────────────────────────────
async def setup_database(cfg: Dict[str, Any], *, recreate: bool = True) -> bool:
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

# ──────────────────────────────── 工具：解析 JSON ────────────────────────────────
def extract_json(raw: str) -> Dict[str, Any] | None:
    """從 GPT 回覆中抓第一個 JSON 物件"""
    # 移除 ```json ... ``` fence
    cleaned = re.sub(r"```json\s*([\s\S]*?)```", r"\1", raw, flags=re.I).strip()
    # 嘗試直接 loads
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # 抓第 1 個 {...}
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try: return json.loads(m.group())
            except json.JSONDecodeError: return None
    return None

def heuristic_compliance(txt: str) -> bool | None:
    lower = txt.lower()
    if any(k in lower for k in ("不符合", "不足", "false")): return False
    if any(k in lower for k in ("符合", "true")):            return True
    return None

# ──────────────────────────── ComplianceAnalysisAgent ───────────────────────────
class ComplianceAnalysisAgent(BaseChatAgent):
    def __init__(self, name, db_cfg, model_client):
        super().__init__(name, description="使用 LLM 分析 ESG 與 GRI 的合規性")
        self.db_cfg, self.model = db_cfg, model_client

    async def _save(self, *vals):
        try:
            conn = await aiomysql.connect(**self.db_cfg)
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO compliance_reports
                        (gri_standard_title, gri_clause, gri_query,
                         report_sentence, analysis_result, is_compliant)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, vals)
            await conn.ensure_closed()
            print(f"💾 [{self.name}] 已儲存: {vals[0]} - {vals[1]}")
        except Exception as e:
            print(f"❌ [{self.name}] 寫入失敗:", e)

    async def _analyze(self, title, clause, query, report_txt) -> Tuple[str,bool,bool]:
        prompt = f"""
你是一位 ESG 合規分析師。根據下列資訊判斷報告內容是否回應 GRI 子句要求，
並輸出 JSON：{{"analysis_reason": "...", "is_compliant": true/false}}

GRI 標題: {title}
子句: {clause}
子句要求: {query}

--- 報告內容 ---
{report_txt}
--- 內容結束 ---
"""
        try:
            rsp = await self.model.create(
                messages=[UserMessage(content=prompt, source="user")]
            )
            gpt_text = rsp.content if hasattr(rsp, "content") else rsp.model_dump()["choices"][0]["message"]["content"]
            print("   LLM 回應:", gpt_text[:60], "...")
            data = extract_json(gpt_text)
            if data:
                return data.get("analysis_reason",""), bool(data.get("is_compliant",False)), True
            # fallback
            hint = heuristic_compliance(gpt_text)
            if hint is not None:
                return gpt_text, hint, True
            return gpt_text, False, False
        except Exception as e:
            return f"LLM 呼叫錯誤: {e}", False, False

    async def on_messages(self, msgs: Sequence[BaseChatMessage], token: CancellationToken) -> Response:
        if not msgs: return Response(chat_message=TextMessage(content="缺少訊息",source=self.name))
        data = json.loads(msgs[-1].content)
        processed=saved=0
        for sec in data.get("rag_results", []):
            title = sec.get("title","未知")
            for item in sec.get("items", []):
                clause=item.get("clause","無")
                query =item.get("query","")
                answers=item.get("answers",[])
                content="\n\n---\n\n".join(a.get("content","") for a in answers if isinstance(a,dict))
                if not content.strip(): continue
                processed+=1
                reason, ok, succ = await self._analyze(title, clause, query, content)
                neg_hit = any(k in reason for k in ("不足", "不符合", "不完全", "矛盾"))
                if neg_hit:
                    ok = False
                if succ:
                    await self._save(title, clause, query, content, reason, int(ok))
                    if ok:
                        saved += 1
                elif not succ:
                    print(f"   ⚠️ 解析失敗略過: {title}-{clause}")
        return Response(chat_message=TextMessage(
            content=f"已處理 {processed} 子句，已儲存 {saved} 條合規紀錄。", source=self.name))

    async def on_reset(self,*a,**k): pass
    @property
    def produced_message_types(self): return (TextMessage,)

# ─────────────────────────────── ResultIntegrationAgent ─────────────────────────
class ResultIntegrationAgent(BaseChatAgent):
    def __init__(self,name,db_cfg,out_file):
        super().__init__(name, description="彙整合規結果並輸出 Excel")
        self.db_cfg,self.out_file=db_cfg,out_file

    async def _fetch(self)->List[Dict]:
        conn=await aiomysql.connect(**self.db_cfg)
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""SELECT * 
                                 FROM compliance_reports 
                                 ORDER BY gri_standard_title, gri_clause""")
            data=await cur.fetchall()
        await conn.ensure_closed()
        print(f"📊 [{self.name}] 取回 {len(data)} 筆")
        return data

    def _excel(self,reports:List[Dict[str,Any]]):
        if not reports:
            print("⚠️ 無資料")
            return
        df=pd.DataFrame([{
            "GRI 標準細項":f"{r['gri_standard_title']} - {r['gri_clause']}",
            "驗證狀態":"驗證通過，有完整揭露" if r['is_compliant'] else "驗證不通過或資訊不足",
            "判斷理由 (AI生成)":r['analysis_result']
        } for r in reports])
        with pd.ExcelWriter(self.out_file,engine="openpyxl") as w:
            df.to_excel(w,index=False,sheet_name="合規分析總結")
        print(f"📄 [{self.name}] 已輸出 {self.out_file}")

    async def on_messages(self,msgs,token):
        self._excel(await self._fetch())
        return Response(chat_message=TextMessage(
            content=f"Excel 已產生 {self.out_file}",source=self.name))

    async def on_reset(self,*a,**k):pass
    @property
    def produced_message_types(self):return(TextMessage,)

# ──────────────────────────────────── Main ──────────────────────────────────────
async def main():
    if not await setup_database(MYSQL_CONFIG): return
    model = OpenAIChatCompletionClient(model=MODEL_NAME, api_key=API_KEY)
    comp = ComplianceAnalysisAgent("ComplianceAnalyzer", MYSQL_CONFIG, model)
    integ= ResultIntegrationAgent("ReportIntegrator", MYSQL_CONFIG, TEST_EXCEL_OUTPUT)

    with open(TEST_PAIRS_JSON,"r",encoding="utf-8") as f:
        raw=f.read()
    print("\n--- 🎬 開始 LLM 分析流程 ---")
    await comp.on_messages([TextMessage(content=raw,source="Orchestrator")], CancellationToken())
    print("--- ✅ 分析結束 ---\n")

    print("--- 🎬 產生 Excel ---")
    await integ.on_messages([TextMessage(content="export",source="Orchestrator")], CancellationToken())
    print("--- ✅ 流程完成 ---")
    await model.close()

if __name__=="__main__":
    asyncio.run(main())

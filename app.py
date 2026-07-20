import streamlit as st
import hashlib
from datetime import datetime

# 引入本地解析組件
from pypdf import PdfReader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# ==========================================
# 1. 頁面配置與內部高級 UI 樣式
# ==========================================
st.set_page_config(
    page_title="東淦扣帳合規智能助理",
    page_icon="🏗️",
    layout="wide"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .source-tag {
        background-color: #f8d7da !important; 
        border-left: 4px solid #dc3545 !important; 
        color: #721c24 !important; 
        padding: 10px !important; 
        margin: 8px 0 !important; 
        font-size: 0.9em !important; 
        border-radius: 4px !important;
    }
    .confidence-badge {
        background-color: #198754 !important;
        color: #ffffff !important;
        padding: 6px 12px !important;
        border-radius: 20px !important;
        font-size: 0.85em !important;
        font-weight: bold !important;
        display: inline-block !important;
    }
    .rule-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 🧠 專利級：智能表格/行對齊 PDF 解析引擎
# ==========================================
@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def process_pdf_to_chunks(pdf_file):
    filename = pdf_file.name
    chunks = []
    try:
        reader = PdfReader(pdf_file)
        full_text = ""
        
        # 1. 先把整份 PDF 的文字完整撈出
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # 2. 針對東淦表格特性：按「行」或「特定編號」進行語意重組
        # 這樣可以防止題目與答案被字數限制切斷
        lines = full_text.split("\n")
        current_chunk = ""
        
        for index, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 將相鄰的 3 行拼成一個完整的上下文（Context Window），確保題目前後文和答案一定包含在內
            context_text = ""
            start_idx = max(0, index - 1)
            end_idx = min(len(lines), index + 3)
            
            for i in range(start_idx, end_idx):
                context_text += lines[i] + "\n"
                
            doc = Document(
                page_content=context_text,
                metadata={
                    "source": filename,
                    "page": 1,
                    "hash": hashlib.md5(context_text.encode('utf-8')).hexdigest()[:8]
                }
            )
            chunks.append(doc)
            
    except Exception as e:
        pass
    return chunks

# ==========================================
# 3. 🎯 高頻突發情境精準直出網閘
# ==========================================
class JumboGuardrails:
    def evaluate(self, query):
        q = query.lower()
        if any(w in q for w in ["非吸煙區", "食煙", "罰款", "debit note"]):
            return (
                "<div class='confidence-badge'>🎯 系統精準匹配結果 (內部管治硬網閘)</div>\n\n"
                "👉 **【建議扣賬方】：JOA (我司同事) / 分判商扣賬 (分判商員工)**\n\n"
                "**📋 原因歸屬：**\n"
                "* 依據題庫第 24 條：我司同事於地盤非吸煙區內吸煙被罰款，選用 **JOA**。\n"
                "* 依據題庫第 25 條：分判商於地盤架步內吸煙被罰款，選用 **分判商扣賬**。\n\n"
                "**📝 建議 Remark 填寫格式：**\n"
                "`REMARK: [地盤名稱] 因非吸煙區吸煙遭主判 Debit Note 處罰，對應責任人扣除費用。`"
            )
        return None

guardrails = JumboGuardrails()

# ==========================================
# 4. 主畫面佈局
# ==========================================
st.title("🏗️ 東淦工程有限公司 (Jumbo Orient)")
st.subheader("智能扣帳方與合約合規查詢系統 (題庫動態上傳安全版)")

st.info(
    "🔒 **內部數據安全保障：**\n"
    "本系統採用純本地數據比對技術，您上傳的文件只會暫存在當前網頁會話中。"
    "**當您關閉或重新整理網頁時，上傳的文件會立即被全量徹底銷毀**，絕對不會儲存到網絡上，請放心使用。"
)

# 宣告全局變數
vector_db = None
all_chunks = []

# 側邊欄：文件上傳
with st.sidebar:
    st.header("📂 臨時指引上傳")
    uploaded_files = st.file_uploader(
        "請上傳公司《使用扣帳方題庫.pdf》或內部文件", 
        type=["pdf"], 
        accept_multiple_files=True
    )

# 全局自動偵測
if uploaded_files:
    for f in uploaded_files:
        all_chunks.extend(process_pdf_to_chunks(f))
    if all_chunks:
        embeddings = get_embedding_model()
        vector_db = FAISS.from_documents(all_chunks, embeddings)

# 側邊欄：狀態實時渲染
with st.sidebar:
    st.header("📊 臨時知識庫狀態")
    st.write(f"📁 已加載文件數：{len(uploaded_files) if uploaded_files else 0} 份")
    # 優化後，切片數量會顯著上升，代表抓取到了更多細節行
    st.write(f"🧩 解析條文切片：{len(all_chunks)} 個")

# ==========================================
# 5. 智能對話與條文對齊
# ==========================================
if 'jumbo_messages' not in st.session_state:
    st.session_state.jumbo_messages = []

# 顯示歷史對話
for msg in st.session_state.jumbo_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

# 接收提問
if prompt := st.chat_input("用廣東話輸入地盤扣帳情況...（例如：由於我司內部圖紙出錯，導致現場要改尺寸執修）"):
    st.session_state.jumbo_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        final_response = ""
        
        # 第一層：高頻情境直接攔截
        intercepted_advice = guardrails.evaluate(prompt)
        
        if intercepted_advice:
            st.markdown(intercepted_advice, unsafe_allow_html=True)
            final_response = intercepted_advice
        elif vector_db is None:
            st.error("🛑 **系統提示：** 請先在左側上傳指引 PDF 文件，否則助理無法幫您翻查條文。")
            final_response = "未上傳文件。"
        else:
            # 第二層：滑動視窗語意比對 (k=3 擴大檢索範圍)
            docs_and_scores = vector_db.similarity_search_with_score(prompt, k=3)
            top_doc, top_score = docs_and_scores[0]
            
            # 優化評分公式，適應本地句向量模型
            confidence = max(10.0, min(99.9, (1.1 - (top_score / 1.8)) * 100))
            
            if confidence < 30.0:
                st.error(f"⚠️ **匹配度不足 ({confidence:.1f}%)**")
                fb = "輸入的描述在題庫中找不到足夠相近的條文。為免出錯，請手動核對原始文件或向合約經理查詢。"
                st.markdown(fb)
                final_response = fb
            else:
                st.success("🎯 **已為您翻查到題庫內相關度最高的原始記錄：**")
                
                # 去除重複顯示的文本內容
                seen_contents = set()
                for doc, score in docs_and_scores:
                    clean_content = doc.page_content.strip()
                    if clean_content in seen_contents:
                        continue
                    seen_contents.add(clean_content)
                    
                    source_file = doc.metadata["source"]
                    
                    with st.expander(f"📄 參考題庫內容 (置信度：{confidence:.1f}%)", expanded=True):
                        st.markdown(f"**【對應題庫原文】**\n\n{doc.page_content}")
                        st.markdown(
                            f"<div class='source-tag'>🔍 <b>合規出處：</b> {source_file}</div>", 
                            unsafe_allow_html=True
                        )
                        final_response += f"[{source_file}]: {doc.page_content}\n\n"
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})

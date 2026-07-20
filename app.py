import streamlit as st
import os
import hashlib
import logging
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 本地安全查詢引擎 (數據不上網，不燒 Token)
# ==========================================
@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def process_pdf_to_chunks(pdf_file):
    filename = pdf_file.name
    chunks = []
    try:
        reader = PdfReader(pdf_file)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text:
                continue
            
            chunk_size = 400
            overlap = 80
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end]
                
                doc = Document(
                    page_content=chunk_text,
                    metadata={
                        "source": filename,
                        "page": page_num,
                        "hash": hashlib.md5(chunk_text.encode('utf-8')).hexdigest()[:8]
                    }
                )
                chunks.append(doc)
                start += (chunk_size - overlap)
    except Exception as e:
        pass
    return chunks

# ==========================================
# 3. 🎯 高頻突發情境精準直出 (免翻查網閘)
# ==========================================
class JumboGuardrails:
    def evaluate(self, query):
        q = query.lower()
        if any(w in q for w in ["非吸煙區", "食煙", "罰款", "debit note"]):
            return (
                "<div class='confidence-badge'>🎯 系統精準匹配結果</div>\n\n"
                "👉 **【建議扣賬方】：JOA (因公司內部問題/違規導致之行政費用/罰款)**\n\n"
                "**📋 原因歸屬：**\n"
                "地盤非吸煙區吸煙遭主判罰款，屬於內部員工行為違規，依公司管治指引，必須歸入 **JOA**。\n\n"
                "**📝 系統 Remark 填寫指引：**\n"
                "`REMARK: [地盤名稱] 因非吸煙區吸煙遭主判 Debit Note 處罰，對應責任人扣除行政費。`"
            )
        return None

guardrails = JumboGuardrails()

# ==========================================
# 4. 主畫面佈局與全局數據流優化
# ==========================================
st.title("🏗️ 東淦工程有限公司 (Jumbo Orient)")
st.subheader("智能扣帳方與合約合規查詢系統")

st.info(
    "🔒 **內部數據安全保障：**\n"
    "本系統採用純本地數據比對技術，您上傳的文件只會暫存在當前網頁會話中。"
    "**當您關閉或重新整理網頁時，上傳的文件會立即被全量徹底銷毀**，絕對不會儲存到網絡上，請放心使用。"
)

# 宣告全局變數，防止側邊欄生命週期將其鎖死
vector_db = None
all_chunks = []

# 側邊欄：文件上傳
with st.sidebar:
    st.header("📂 臨時指引上傳")
    uploaded_files = st.file_uploader(
        "請上傳公司《如何選擇扣賬方.pdf》或內部題庫文件", 
        type=["pdf"], 
        accept_multiple_files=True
    )

# 全局自動偵測：只要前線同事有上傳檔案，立刻在最外層建立向量庫
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
if prompt := st.chat_input("用廣東話輸入地盤扣帳情況...（例如：牛房門被撞爛但無SI，費歸哪裡？）"):
    st.session_state.jumbo_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        final_response = ""
        
        # 第一層：高頻情境直接攔截（優先度最高）
        intercepted_advice = guardrails.evaluate(prompt)
        
        if intercepted_advice:
            st.markdown(intercepted_advice, unsafe_allow_html=True)
            final_response = intercepted_advice
        elif vector_db is None:
            st.error("🛑 **系統提示：** 請先在左側上傳指引 PDF 文件，否則助理無法幫您翻查條文。")
            final_response = "未上傳文件。"
        else:
            # 第二層：全局本地語意翻查
            docs_and_scores = vector_db.similarity_search_with_score(prompt, k=2)
            top_doc, top_score = docs_and_scores[0]
            confidence = max(10.0, min(99.9, (1.2 - (top_score / 2.0)) * 100))
            
            if confidence < 35.0:
                st.error(f"⚠️ **匹配度不足 ({confidence:.1f}%)**")
                fb = "輸入的描述在現有扣帳指引中找不到足夠相近的條文。為免出錯，請手動核對原始文件或詢問合約經理。"
                st.markdown(fb)
                final_response = fb
            else:
                st.success("🎯 **已為您翻查到指引內相關度最高的原始條文：**")
                
                for doc, score in docs_and_scores:
                    source_file = doc.metadata["source"]
                    page_num = doc.metadata["page"]
                    
                    with st.expander(f"📄 來源指引：{source_file} (第 {page_num} 頁)", expanded=True):
                        st.markdown(f"**【指引原文內容】**\n\n{doc.page_content}")
                        st.markdown(
                            f"<div class='source-tag'>🔍 <b>合規追溯：</b> 出處自 {source_file} 第 {page_num} 頁</div>", 
                            unsafe_allow_html=True
                        )
                        final_response += f"[{source_file} P.{page_num}]: {doc.page_content}\n\n"
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})

import streamlit as st
import hashlib
import re
import pandas as pd

# 引入本地解析組件
from pypdf import PdfReader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# ==========================================
# 1. 頁面配置與 UI 樣式
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
    .answer-box {
        background-color: #e8f5e9;
        border-left: 5px solid #2e7d32;
        padding: 15px;
        border-radius: 4px;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 🛡️ 文字模糊比對清理工具
# ==========================================
def clean_text_for_matching(text):
    if not text:
        return ""
    text = re.sub(r'[^\w\u4e00-\u9fa5]', '', str(text))
    return text.lower().strip()

@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# ==========================================
# 🧠 核心優化：雙驅動文件解析引擎 (完美支援 Excel 與 PDF)
# ==========================================
def process_file_to_chunks(uploaded_file):
    filename = uploaded_file.name
    chunks = []
    
    try:
        # 驅動 A：如果上傳的是 Excel 檔案
        if filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
            # 將所有列名和內容轉為字串，方便搜尋
            for index, row in df.iterrows():
                # 組合整行內容變成一句話
                row_str = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                if len(row_str.strip()) < 5:
                    continue
                
                doc = Document(
                    page_content=row_str,
                    metadata={
                        "source": filename,
                        "raw_cleaned": clean_text_for_matching(row_str)
                    }
                )
                chunks.append(doc)
                
        # 驅動 B：如果上傳的是 PDF 檔案
        elif filename.endswith('.pdf'):
            reader = PdfReader(uploaded_file)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            
            lines = full_text.split("\n")
            for line in lines:
                line_text = line.strip()
                if not line_text or len(line_text) < 8:
                    continue
                doc = Document(
                    page_content=line_text,
                    metadata={
                        "source": filename,
                        "raw_cleaned": clean_text_for_matching(line_text)
                    }
                )
                chunks.append(doc)
    except Exception as e:
        st.error(f"解析文件時出錯: {str(e)}")
    return chunks

# ==========================================
# 3. 主畫面佈局
# ==========================================
st.title("🏗️ 東淦工程有限公司 (Jumbo Orient)")
st.subheader("智能扣帳方與合約合規查詢系統 (Excel / PDF 智能版)")

st.info(
    "🔒 **內部數據安全保障：**\n"
    "本系統採用純本地數據比對技術，您上傳的 Excel 或 PDF 文件只會暫存在當前網頁會話中。"
    "**當您關閉或重新整理網頁時，數據會立即被徹底銷毀**，絕對不會儲存到互聯網上，請放心使用。"
)

vector_db = None
all_chunks = []

with st.sidebar:
    st.header("📂 臨時指引上傳")
    # 解鎖支援 xlsx, xls 和 pdf
    uploaded_files = st.file_uploader(
        "請直拖上傳公司《使用扣帳方題庫.xlsx》或 PDF 文件", 
        type=["xlsx", "xls", "pdf"], 
        accept_multiple_files=True
    )

if uploaded_files:
    for f in uploaded_files:
        all_chunks.extend(process_file_to_chunks(f))
    if all_chunks:
        embeddings = get_embedding_model()
        vector_db = FAISS.from_documents(all_chunks, embeddings)

with st.sidebar:
    st.header("📊 臨時知識庫狀態")
    st.write(f"📁 已加載文件數：{len(uploaded_files) if uploaded_files else 0} 份")
    st.write(f"🧩 解析精準數據行：{len(all_chunks)} 條")

# ==========================================
# 4. 智能比對引擎
# ==========================================
if 'jumbo_messages' not in st.session_state:
    st.session_state.jumbo_messages = []

for msg in st.session_state.jumbo_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)

if prompt := st.chat_input("用廣東話輸入地盤扣帳情況..."):
    st.session_state.jumbo_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        final_response = ""
        
        if vector_db is None or not all_chunks:
            st.error("🛑 **系統提示：** 請先在左側上傳 Excel 題庫或 PDF 文件，否則助理無法幫您翻查條文。")
            final_response = "未上傳文件。"
        else:
            user_clean = clean_text_for_matching(prompt)
            
            # 優先進行強效關鍵字命中
            keyword_matched_docs = []
            for chunk in all_chunks:
                chunk_clean = chunk.metadata["raw_cleaned"]
                if len(user_clean) >= 4 and (user_clean in chunk_clean or chunk_clean in user_clean):
                    keyword_matched_docs.append(chunk)
            
            if keyword_matched_docs:
                st.success("🎯 **系統已為您精準命中題庫內對應的原始記錄：**")
                st.markdown("<div class='confidence-badge'>🎯 Excel 行精準對齊：100% 命中</div>", unsafe_allow_html=True)
                
                best_doc = keyword_matched_docs[0]
                st.markdown(
                    f"<div class='answer-box'>"
                    f"<b>📋 匹配題庫原始紀錄：</b><br>{best_doc.page_content}"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                final_response = best_doc.page_content
            else:
                # 備用：語意向量相似度檢索
                docs_and_scores = vector_db.similarity_search_with_score(prompt, k=1)
                top_doc, top_score = docs_and_scores[0]
                confidence = max(10.0, min(99.9, (1.3 - (top_score / 1.8)) * 100))
                
                st.success(f"🎯 **已為您翻查到題庫內相關度最高的原始記錄：**")
                st.markdown(
                    f"<div class='answer-box'>"
                    f"<b>📋 參考題庫紀錄 (置信度 {confidence:.1f}%)：</b><br>{top_doc.page_content}"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                final_response = top_doc.page_content
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})

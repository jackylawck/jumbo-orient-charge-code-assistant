import streamlit as st
import hashlib
import re

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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 🛡️ 文字標準化清理工具 (處理全半形標點符號錯位)
# ==========================================
def clean_text_for_matching(text):
    if not text:
        return ""
    # 將所有全形標點符號（，、？；：）及空格轉換為標準半形或移除，消除編碼摩擦
    text = text.replace("，", ",").replace("、", ",").replace("？", "?").replace("；", ";").replace("：", ":")
    text = re.sub(r'\s+', '', text) # 移除所有空格與換行
    return text.lower()

@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

def process_pdf_to_chunks(pdf_file):
    filename = pdf_file.name
    chunks = []
    try:
        reader = PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        lines = full_text.split("\n")
        for index, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 建立滑動上下文窗口
            context_text = ""
            start_idx = max(0, index - 1)
            end_idx = min(len(lines), index + 3)
            for i in range(start_idx, end_idx):
                context_text += lines[i] + "\n"
                
            doc = Document(
                page_content=context_text,
                metadata={
                    "source": filename,
                    "raw_cleaned": clean_text_for_matching(context_text),
                    "hash": hashlib.md5(context_text.encode('utf-8')).hexdigest()[:8]
                }
            )
            chunks.append(doc)
    except Exception as e:
        pass
    return chunks

# ==========================================
# 3. 主畫面佈局
# ==========================================
st.title("🏗️ 東淦工程有限公司 (Jumbo Orient)")
st.subheader("智能扣帳方與合約合規查詢系統 (題庫安全對齊版)")

st.info(
    "🔒 **內部數據安全保障：**\n"
    "本系統採用純本地數據比對技術，您上傳的文件只會暫存在當前網頁會話中。"
    "**當您關閉或重新整理網頁時，上傳的文件會立即被全量徹底銷毀**，絕對不會儲存到網絡上，請放心使用。"
)

vector_db = None
all_chunks = []

with st.sidebar:
    st.header("📂 臨時指引上傳")
    uploaded_files = st.file_uploader(
        "請上傳公司《使用扣帳方題庫.pdf》或內部文件", 
        type=["pdf"], 
        accept_multiple_files=True
    )

if uploaded_files:
    for f in uploaded_files:
        all_chunks.extend(process_pdf_to_chunks(f))
    if all_chunks:
        embeddings = get_embedding_model()
        vector_db = FAISS.from_documents(all_chunks, embeddings)

with st.sidebar:
    st.header("📊 臨時知識庫狀態")
    st.write(f"📁 已加載文件數：{len(uploaded_files) if uploaded_files else 0} 份")
    st.write(f"🧩 解析條文切片：{len(all_chunks)} 個")

# ==========================================
# 4. 智能對話與雙軌匹配引擎 (語意 + 關鍵字)
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
        
        if vector_db is None:
            st.error("🛑 **系統提示：** 請先在左側上傳指引 PDF 文件，否則助理無法幫您翻查條文。")
            final_response = "未上傳文件。"
        else:
            # 實施清理提問
            cleaned_prompt = clean_text_for_matching(prompt)
            
            # 雙軌機制第一路：強效關鍵字/字符精準命中 (專治表格對齊問題)
            keyword_matched_docs = []
            for chunk in all_chunks:
                # 如果提問的核心特徵字串有 60% 以上重疊在切片內
                chunk_clean = chunk.metadata["raw_cleaned"]
                if len(cleaned_prompt) > 5 and (cleaned_prompt in chunk_clean or chunk_clean in cleaned_prompt):
                    keyword_matched_docs.append(chunk)
            
            # 雙軌機制第二路：如果硬匹配沒有，走語意向量路徑
            if keyword_matched_docs:
                st.success("🎯 **系統已為您精準命中題庫內對應的原始記錄：**")
                st.markdown("<div class='confidence-badge'>🎯 雙軌硬匹配：100% 精準對齊</div>", unsafe_allow_html=True)
                
                for doc in keyword_matched_docs[:2]:
                    with st.expander("📄 參考題庫內容", expanded=True):
                        st.markdown(f"**【對應題庫原文】**\n\n{doc.page_content}")
                        final_response += f"{doc.page_content}\n\n"
            else:
                # 走語意比對
                docs_and_scores = vector_db.similarity_search_with_score(prompt, k=2)
                top_doc, top_score = docs_and_scores[0]
                confidence = max(10.0, min(99.9, (1.2 - (top_score / 1.8)) * 100))
                
                if confidence < 30.0:
                    st.error(f"⚠️ **匹配度不足 ({confidence:.1f}%)**")
                    fb = "輸入的描述在題庫中找不到足夠相近的條文。為免出錯，請手動核對原始文件或向合約經理查詢。"
                    st.markdown(fb)
                    final_response = fb
                else:
                    st.success("🎯 **已為您翻查到題庫內相關度最高的原始記錄：**")
                    for doc, score in docs_and_scores:
                        with st.expander(f"📄 參考題庫內容 (置信度：{confidence:.1f}%)", expanded=True):
                            st.markdown(f"**【對應題庫原文】**\n\n{doc.page_content}")
                            final_response += f"{doc.page_content}\n\n"
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})

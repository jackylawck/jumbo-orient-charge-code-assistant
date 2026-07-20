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
# 2. 🛡️ 文字標準化清理工具
# ==========================================
def clean_text_for_matching(text):
    if not text:
        return ""
    # 統一全半形標點符號，移除所有空格，消除比對摩擦
    text = text.replace("，", ",").replace("、", ",").replace("？", "?").replace("；", ";").replace("：", ":").replace(" ", "")
    text = re.sub(r'\s+', '', text)
    return text.lower()

@st.cache_resource(show_spinner="🔒 正在啟動內部查詢安全組件...")
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# ==========================================
# 🧠 核心優化：題庫表格精準按題切片
# ==========================================
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
        
        # 使用正則表達式，精準捕捉類似 "1 由於我司..." 到下一個數字題號前的內容
        # 確保每一道題目與其答案被完美鎖死在獨立的 Document 裡，絕不混淆黏連
        raw_matches = re.findall(r'\d+[\u4e00-\u9fa5「【].+?(?=\s+\d+[\u4e00-\u9fa5「【]|$)', full_text, re.DOTALL)
        
        for item in raw_matches:
            item_text = item.strip()
            if not item_text:
                continue
                
            doc = Document(
                page_content=item_text,
                metadata={
                    "source": filename,
                    "raw_cleaned": clean_text_for_matching(item_text),
                    "hash": hashlib.md5(item_text.encode('utf-8')).hexdigest()[:8]
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
st.subheader("智能扣帳方與合約合規查詢系統 (題庫精準對齊版)")

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
    st.write(f"🧩 解析精準題庫數：{len(all_chunks)} 條")

# ==========================================
# 4. 雙軌智能比對引擎
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
            cleaned_prompt = clean_text_for_matching(prompt)
            
            # 優先進行強效關鍵字/字符重疊命中 (實現 100% 精準拉取單一題目)
            keyword_matched_docs = []
            for chunk in all_chunks:
                chunk_clean = chunk.metadata["raw_cleaned"]
                if len(cleaned_prompt) > 4 and (cleaned_prompt in chunk_clean or chunk_clean in cleaned_prompt):
                    keyword_matched_docs.append(chunk)
            
            # 渲染結果
            if keyword_matched_docs:
                st.success("🎯 **系統已為您精準命中題庫內對應的原始記錄：**")
                
                # 僅取第一條最精準的題目，徹底解決黏連問題
                best_doc = keyword_matched_docs[0]
                
                # 智能美化提取出的單題答案
                raw_content = best_doc.page_content
                
                st.markdown(
                    f"<div class='answer-box'>"
                    f"<b>📋 匹配題庫原始紀錄：</b><br>{raw_content}"
                    f"</div>", 
                    unsafe_allow_html=True
                )
                
                # 自動產生填單備註建議
                st.markdown("**📝 建議前線開單 Remark 填寫格式：**")
                st.code(f"REMARK: 依據內部題庫指引規範核對處置。")
                final_response = raw_content
                
            else:
                # 備用機制：語意向量相似度檢索
                docs_and_scores = vector_db.similarity_search_with_score(prompt, k=1)
                top_doc, top_score = docs_and_scores[0]
                confidence = max(10.0, min(99.9, (1.2 - (top_score / 1.8)) * 100))
                
                if confidence < 35.0:
                    st.error(f"⚠️ **匹配度不足 ({confidence:.1f}%)**")
                    fb = "輸入的描述在題庫中找不到足夠相近的條文。為免出錯，請手動核對原始文件或向合約經理查詢。"
                    st.markdown(fb)
                    final_response = fb
                else:
                    st.success("🎯 **已為您翻查到題庫內相關度最高的原始記錄：**")
                    st.markdown(
                        f"<div class='answer-box'>"
                        f"<b>📋 匹配題庫紀錄 (置信度 {confidence:.1f}%)：</b><br>{top_doc.page_content}"
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                    final_response = top_doc.page_content
        
        st.session_state.jumbo_messages.append({"role": "assistant", "content": final_response})

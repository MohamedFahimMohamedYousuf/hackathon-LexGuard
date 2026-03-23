import streamlit as st
import base64
import time

st.set_page_config(page_title="LexGuard", layout="wide")

# Custom CSS for drag-drop uploader
st.markdown("""
<style>
div[data-testid="stFileUploader"] > section[data-testid="stFileUploadDropzone"] > button[data-testid="baseButton-secondary"] {
    color: #FF8C00;
}
div[data-testid="stFileUploader"] > section[data-testid="stFileUploadDropzone"] > button[data-testid="baseButton-secondary"]::after {
    content: "Browse files";
    color: #333;
    display: block;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: create(-50%, -50%);
}
div[data-testid="stFileDropzoneInstructions"] > div > span {
    visibility: hidden;
}
div[data-testid="stFileDropzoneInstructions"] > div > span::after {
    content: "Drag & drop to upload";
    visibility: visible;
    display: block;
    font-weight: 500;
}
div[data-testid="stFileDropzoneInstructions"] > div > small {
    visibility: hidden;
}
div[data-testid="stFileDropzoneInstructions"] > div > small::before {
    content: "Only PDF files with max 15MB";
    visibility: visible;
    display: block;
    color: #666;
}
</style>
""", unsafe_allow_html=True)

# Initialize ALL session state at top
if 'show_uploader' not in st.session_state:
    st.session_state.show_uploader = True
if 'uploaded_pdf' not in st.session_state:
    st.session_state.uploaded_pdf = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'stage1' not in st.session_state:
    st.session_state.stage1 = None
if 'stage2' not in st.session_state:
    st.session_state.stage2 = None
if 'stage3' not in st.session_state:
    st.session_state.stage3 = None
if 'result' not in st.session_state:
    st.session_state.result = None

# TOP: Drag-drop uploader (only show when needed)
if st.session_state.show_uploader:
    st.title("📄 LexGuard - PDF Processing")
    st.markdown("**Upload your PDF to analyze**")
    
    # Centered uploader
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        uploaded_file = st.file_uploader("Upload PDF", type="pdf", 
                                       help="", label_visibility="collapsed")
    
    if uploaded_file is not None:
        st.session_state.uploaded_pdf = uploaded_file
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                st.session_state.show_uploader = False
                st.rerun()
        with col_b:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.uploaded_pdf = None
                st.rerun()

# MAIN LAYOUT after upload (left: stages, right: PDF preview)
else:
    left_col, right_col = st.columns([2, 1])
    
    # RIGHT: PDF Preview (always visible)
    with right_col:
        st.header("📄 PDF Preview")
        if st.session_state.uploaded_pdf:
            pdf_bytes = st.session_state.uploaded_pdf.getvalue()
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
            pdf_display = f'''
                <iframe src="data:application/pdf;base64,{base64_pdf}" 
                        width="100%" height="600" 
                        style="border: 1px solid #ddd; border-radius: 12px;">
                </iframe>
            '''
            st.markdown(pdf_display, unsafe_allow_html=True)
            st.caption(f"*{st.session_state.uploaded_pdf.name}*")

    # LEFT: Processing controls + stages
    with left_col:
        st.header("⚙️ Processing Pipeline")
        
        # Process button (if not started)
        if not st.session_state.processing_complete:
            if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                # CREATE all placeholders FIRST
                st.session_state.stage1 = st.empty()
                st.session_state.stage2 = st.empty()
                st.session_state.stage3 = st.empty()
                st.session_state.result = st.empty()
                
                # Run stages
                with st.spinner("Processing..."):
                    # Stage 1
                    st.session_state.stage1.info("🔄 **Stage 1: Loading PDF**")
                    time.sleep(1)
                    st.session_state.stage1.empty()
                    
                    # Stage 2
                    st.session_state.stage2.info("⚙️ **Stage 2: Extracting text**")
                    time.sleep(1.5)
                    st.session_state.stage2.empty()
                    
                    # Stage 3
                    st.session_state.stage3.info("🤖 **Stage 3: AI Analysis**")
                    time.sleep(2)
                    st.session_state.stage3.empty()
                
                # Show result
                st.session_state.result.success("✅ **Analysis Complete!**")
                st.session_state.result.metric("📄 File", st.session_state.uploaded_pdf.name)
                st.session_state.result.metric("📏 Size", f"{len(st.session_state.uploaded_pdf.getvalue())/1024/1024:.1f} MB")
                st.session_state.processing_complete = True
        
        # Show result if complete
        elif st.session_state.result:
            st.session_state.result.markdown("""
                <div style='background: #daf8e6; padding: 15px; border-radius: 8px; border-left: 4px solid #10b981'>
                    <h3>✅ Analysis Complete!</h3>
                    <p><strong>📄 File:</strong> {}</p>
                    <p><strong>📏 Size:</strong> {:.1f} MB</p>
                </div>
            """.format(st.session_state.uploaded_pdf.name, 
                      len(st.session_state.uploaded_pdf.getvalue())/1024/1024),
            unsafe_allow_html=True)
        
        # NEW PDF BUTTON (always at bottom)
        if st.button("📤 Process New PDF", type="secondary", use_container_width=True):
            # Full reset
            st.session_state.show_uploader = True
            st.session_state.uploaded_pdf = None
            st.session_state.processing_complete = False
            # Clear placeholders safely
            for key in ['stage1', 'stage2', 'stage3', 'result']:
                if key in st.session_state and st.session_state[key] is not None:
                    try:
                        st.session_state[key].empty()
                    except:
                        pass
                    st.session_state[key] = None
            st.rerun()

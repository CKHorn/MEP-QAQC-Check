import streamlit as st
import anthropic
import base64
import asyncio
import concurrent.futures

# ── Page config ──────────────────────────────────────────
st.set_page_config(
    page_title="HVAC QC Review",
    page_icon="🔍",
    layout="wide"
)

# ── Styles ────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #F7F8FA; }
    .stApp { font-family: 'Segoe UI', Arial, sans-serif; }
    .review-header {
        background: #1E3A5F;
        color: white;
        padding: 20px 28px;
        border-radius: 10px;
        margin-bottom: 24px;
    }
    .review-header h1 { color: white; margin: 0; font-size: 26px; }
    .review-header p { color: rgba(255,255,255,0.7); margin: 4px 0 0; font-size: 13px; }
    .finding-critical {
        background: #FEF2F2;
        border-left: 4px solid #DC2626;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .finding-major {
        background: #FFFBEB;
        border-left: 4px solid #D97706;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .finding-minor {
        background: #EFF6FF;
        border-left: 4px solid #2563EB;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .finding-rec {
        background: #F0FDF4;
        border-left: 4px solid #059669;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .category-header {
        background: #F0F2F5;
        border: 1px solid #E2E6EA;
        border-radius: 8px;
        padding: 10px 16px;
        margin: 16px 0 8px;
        font-weight: 600;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────
st.markdown("""
<div class="review-header">
    <h1>🔍 HVAC QC Review</h1>
    <p>AI-powered mechanical drawing review — General · Code · MEP · Energy · Constructability · Presentation</p>
</div>
""", unsafe_allow_html=True)

# ── QC Categories ─────────────────────────────────────────
QC_CATS = {
    "General Review": {
        "icon": "🔍",
        "prompt": "Review this mechanical drawing/document for general completeness, coordination issues, missing information, and any errors or inconsistencies."
    },
    "Code Compliance": {
        "icon": "📜",
        "prompt": "Review this mechanical drawing for code compliance issues. Check against IMC, ASHRAE 62.1, ASHRAE 90.1, NFPA 90A, and applicable mechanical codes. List any violations or concerns with specific code sections."
    },
    "MEP Coordination": {
        "icon": "🔗",
        "prompt": "Review this mechanical drawing for MEP coordination issues. Identify potential conflicts with electrical, plumbing, or structural systems. Note missing coordination notes or unclear interfaces between disciplines."
    },
    "Energy Compliance": {
        "icon": "⚡",
        "prompt": "Review for ASHRAE 90.1 energy code compliance: insulation requirements, equipment efficiencies, controls sequences, economizer requirements, and energy recovery."
    },
    "Constructability": {
        "icon": "🏗️",
        "prompt": "Review for constructability issues: difficult installations, missing clearances, access issues, maintenance access, and field coordination problems that could cause issues during construction."
    },
    "Drawing Presentation": {
        "icon": "🎨",
        "prompt": "Review drawing presentation quality: text overlapping other text or linework, background patterns cluttering the drawing, font compliance (should be Arial), inconsistent text sizes, missing leaders or callouts, and general drawing clarity."
    },
}

PHASES = ["SD", "50% DD", "100% DD", "50% CD", "90% CD", "100% IFC"]

# ── Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📋 Project Info")
    project_name = st.text_input("Project Name", placeholder="e.g. Main Street Office")
    project_location = st.text_input("Project Location", placeholder="e.g. Austin, TX")
    reviewer = st.text_input("Reviewer Initials", placeholder="e.g. JD")

    st.markdown("---")
    st.markdown("### 📐 Design Phase")
    phase = st.radio("Select current phase", PHASES, index=0)

    st.markdown("---")
    st.markdown("### ✅ Review Types")
    selected_cats = {}
    for cat, info in QC_CATS.items():
        selected_cats[cat] = st.checkbox(f"{info['icon']} {cat}", value=(cat == "General Review"))

    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    run_parallel = st.toggle("Run reviews in parallel", value=True)
    show_raw = st.toggle("Show raw AI response", value=False)

# ── Main area ─────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader(
        "Upload Mechanical Drawing or Document (PDF)",
        type=["pdf"],
        help="Accepts mechanical drawings, calculations, specifications, or any PDF document"
    )

with col2:
    if uploaded_file:
        st.success(f"✅ {uploaded_file.name}")
        st.caption(f"Size: {uploaded_file.size / 1024:.1f} KB")

active_cats = [cat for cat, checked in selected_cats.items() if checked]

if not uploaded_file:
    st.info("👆 Upload a PDF drawing to get started")
elif not active_cats:
    st.warning("⚠️ Please select at least one review type in the sidebar")
else:
    btn_label = f"Run {len(active_cats)} Review{'s' if len(active_cats) != 1 else ''}"
    run_btn = st.button(btn_label, type="primary", use_container_width=True)

    if run_btn:
        # Read and encode PDF
        pdf_bytes = uploaded_file.read()
        b64_pdf = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        # Build context
        phase_txt = f"\n\nDesign Phase: {phase}\nFor each finding indicate when it should be resolved."
        loc_txt = f"\nProject Location: {project_location} — apply local codes, climate zone, jurisdiction amendments." if project_location else ""
        proj_txt = f"\nProject: {project_name}" if project_name else ""
        rev_txt = f"\nReviewer: {reviewer}" if reviewer else ""

       import os
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        def run_single_review(cat_name):
            cat = QC_CATS[cat_name]
            full_prompt = cat["prompt"] + proj_txt + loc_txt + phase_txt + rev_txt
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=2000,
                    system="You are an expert mechanical engineer performing QC review of HVAC drawings and documents. Organize your findings into these exact sections:\n\nCRITICAL ISSUES:\n[numbered list]\n\nMAJOR COMMENTS:\n[numbered list]\n\nMINOR COMMENTS:\n[numbered list]\n\nRECOMMENDATIONS:\n[numbered list]\n\nBe specific about locations, sheet numbers, and detail references where visible. Include applicable code sections for code-related findings.",
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": b64_pdf
                                }
                            },
                            {
                                "type": "text",
                                "text": full_prompt
                            }
                        ]
                    }]
                )
                return cat_name, response.content[0].text, None
            except Exception as e:
                return cat_name, None, str(e)

        # Run reviews
        results = {}
        if run_parallel and len(active_cats) > 1:
            progress = st.progress(0, text="Running reviews in parallel...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(run_single_review, cat): cat for cat in active_cats}
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    cat_name, text, error = future.result()
                    results[cat_name] = {"text": text, "error": error}
                    completed += 1
                    progress.progress(completed / len(active_cats), text=f"Completed {completed}/{len(active_cats)} reviews...")
            progress.empty()
        else:
            progress = st.progress(0)
            for i, cat in enumerate(active_cats):
                with st.spinner(f"Running {cat}..."):
                    cat_name, text, error = run_single_review(cat)
                    results[cat_name] = {"text": text, "error": error}
                progress.progress((i + 1) / len(active_cats))
            progress.empty()

        # Display results
        st.markdown("---")

        # Summary header
        proj_str = f" — {project_name}" if project_name else ""
        phase_str = f" · {phase}" if phase else ""
        rev_str = f" · Reviewer: {reviewer}" if reviewer else ""
        st.markdown(f"## 📋 QC Review Results{proj_str}")
        st.caption(f"{uploaded_file.name}{phase_str}{rev_str}")

        def parse_and_display(text, cat_name, icon):
            sections = [
                ("CRITICAL ISSUES", "🚨 Critical Issues", "finding-critical", "#DC2626"),
                ("MAJOR COMMENTS", "⚠️ Major Comments", "finding-major", "#D97706"),
                ("MINOR COMMENTS", "ℹ️ Minor Comments", "finding-minor", "#2563EB"),
                ("RECOMMENDATIONS", "💡 Recommendations", "finding-rec", "#059669"),
            ]

            st.markdown(f"<div class='category-header'>{icon} {cat_name}</div>", unsafe_allow_html=True)

            found_any = False
            for key, label, css_class, color in sections:
                import re
                pattern = rf"{key}[:\s]*(.*?)(?={('|'.join([s[0] for s in sections if s[0] != key]))}|$)"
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    if content and content not in ["None", "N/A", "—", "-", "None identified."]:
                        found_any = True
                        st.markdown(f"**{label}**")
                        st.markdown(f"<div class='{css_class}'>{content}</div>", unsafe_allow_html=True)

            if not found_any:
                st.markdown(f"<div class='finding-rec'>{text}</div>", unsafe_allow_html=True)

            if show_raw:
                with st.expander("Raw AI Response"):
                    st.text(text)

        # Display each result
        for cat_name in active_cats:
            result = results.get(cat_name, {})
            icon = QC_CATS[cat_name]["icon"]
            if result.get("error"):
                st.error(f"**{icon} {cat_name}** — Error: {result['error']}")
            elif result.get("text"):
                parse_and_display(result["text"], cat_name, icon)

        # Export button
        st.markdown("---")
        export_text = f"HVAC QC REVIEW REPORT\n{'='*60}\n"
        export_text += f"Project: {project_name or '---'}\n"
        export_text += f"Location: {project_location or '---'}\n"
        export_text += f"Design Phase: {phase}\n"
        export_text += f"File: {uploaded_file.name}\n"
        export_text += f"Reviewer: {reviewer or '---'}\n"
        export_text += f"{'='*60}\n\n"
        for cat_name in active_cats:
            result = results.get(cat_name, {})
            if result.get("text"):
                export_text += f"{'-'*60}\n{QC_CATS[cat_name]['icon']} {cat_name.upper()}\n{'-'*60}\n"
                export_text += result["text"] + "\n\n"

        st.download_button(
            label="📥 Download Report (.txt)",
            data=export_text,
            file_name=f"QC_Review_{project_name or 'Report'}.txt",
            mime="text/plain",
            use_container_width=True
        )

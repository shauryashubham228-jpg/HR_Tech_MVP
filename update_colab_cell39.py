"""Update Colab cell 39 with voice/freetext/clarification features."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

nb = json.load(open('AI_Recruiter_Copilot_Colab.ipynb', encoding='utf-8'))
cell = nb['cells'][39]
src = ''.join(cell.get('source', ''))

# ── 1. New helper functions ─────────────────────────────────────────────────
NEW_FUNCTIONS = r"""
def process_voice_jd(audio):
    if audio is None:
        return '❌ No audio recorded.', '', gr.update(visible=False)
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.AudioFile(audio) as src_:
            audio_data = r.record(src_)
        text = r.recognize_google(audio_data)
    except Exception as e:
        return f'❌ Transcription failed: {e}', '', gr.update(visible=False)
    return app_process_jd(text)

def run_freetext_search(query):
    if not query.strip():
        return '❌ Enter a search query.', None, gr.update(choices=[])
    s = extract_jd(query)
    s['_raw_jd'] = query
    s['job_id'] = f'JOB-{str(uuid.uuid4())[:6].upper()}'
    _app_state['structured_jd'] = s
    return app_run_search()

def ask_clarification(sel, question):
    if not sel or not question.strip():
        return '❌ Select a candidate and enter a question.'
    cid = _cid(sel)
    c = get_candidate(cid)
    jd = _app_state.get('structured_jd', {})
    jid = _app_state.get('job_id', '')
    ans = answer_recruiter_question(cid, question, jd, c)
    save_recruiter_memory(jid, cid, question, ans, '')
    return f'**A:** {ans}'

"""

TAB1_MARKER = '# ── Tab 1: JD Upload ──'
src = src.replace(TAB1_MARKER, NEW_FUNCTIONS + TAB1_MARKER)

# ── 2. Tab 1: voice widget ──────────────────────────────────────────────────
OLD_TAB1 = "            jd_btn.click(app_process_jd, jd_in, [jd_st, jd_dp, jd_sb])"
NEW_TAB1 = (
    "            jd_btn.click(app_process_jd, jd_in, [jd_st, jd_dp, jd_sb])\n"
    "            gr.Markdown('---')\n"
    "            gr.Markdown('**Or record voice:**')\n"
    "            voice_in  = gr.Audio(sources=['microphone'], type='filepath', label='Record Voice JD')\n"
    "            voice_btn = gr.Button('\U0001f3d9️ Transcribe & Parse Voice', variant='secondary')\n"
    "            voice_btn.click(process_voice_jd, voice_in, [jd_st, jd_dp, jd_sb])"
)
src = src.replace(OLD_TAB1, NEW_TAB1)

# ── 3. Tab 2: free-text search ─────────────────────────────────────────────
OLD_S_BTN = "            s_btn  = gr.Button('\U0001f50e Run Hybrid Search (SQL + Semantic)', variant='primary')"
NEW_S_BTN = (
    "            ft_in  = gr.Textbox(label='Free-Text Search (plain English)', lines=2,\n"
    "                                placeholder='e.g. Senior Python developer in Mumbai with 5+ years...')\n"
    "            ft_btn = gr.Button('\U0001f50e Search by Plain Text', variant='secondary')\n"
    "            ft_btn.click(run_freetext_search, ft_in, [s_st, s_tbl, s_dd])\n"
    "            gr.Markdown('---')\n"
    "            s_btn  = gr.Button('\U0001f50e Run Hybrid Search (SQL + Semantic)', variant='primary')"
)
src = src.replace(OLD_S_BTN, NEW_S_BTN)

# ── 4. Tab 3: clarification Q&A ────────────────────────────────────────────
OLD_M_CLICK = "            m_btn.click(app_match_details, m_dd, [m_mt, m_ms, m_sm, m_ev])"
NEW_M_CLICK = (
    "            m_btn.click(app_match_details, m_dd, [m_mt, m_ms, m_sm, m_ev])\n"
    "            gr.Markdown('---')\n"
    "            gr.Markdown('**Ask a clarification about any gap (answered from profile by AI):**')\n"
    "            clarif_in  = gr.Textbox(label='Your Question', lines=2,\n"
    "                                     placeholder='e.g. Has this candidate worked on microservices?')\n"
    "            clarif_btn = gr.Button('\U0001f4ac Ask Clarification', variant='secondary')\n"
    "            clarif_ans = gr.Markdown(label='AI Answer (from profile)')\n"
    "            clarif_btn.click(ask_clarification, [m_dd, clarif_in], clarif_ans)"
)
src = src.replace(OLD_M_CLICK, NEW_M_CLICK)

# ── 5. Assessment: pass verdict/feedback/req to save_assessment ────────────
OLD_SAVE = (
    "    save_assessment(jid, cid, question, answer,\n"
    "                    result.get('assessment_score', 0), impact)\n"
    "    update_assessment_score(jid, cid, new_score)\n"
    "    save_recruiter_memory(jid, cid, question, answer, '')"
)
NEW_SAVE = (
    "    save_assessment(jid, cid, question, answer,\n"
    "                    result.get('assessment_score', 0), impact,\n"
    "                    verdict=result.get('verdict', ''),\n"
    "                    feedback=result.get('feedback', ''),\n"
    "                    targets_requirement=req)\n"
    "    update_assessment_score(jid, cid, new_score)"
)
src = src.replace(OLD_SAVE, NEW_SAVE)

# ── 6. Report: use generate_submission_report ──────────────────────────────
OLD_RPT_FN = "    r   = generate_report(jid, cid)\n\n    # Override displayed score with updated_score (post-assessment)\n"
NEW_RPT_FN = "    r   = generate_submission_report(jid, cid)\n\n    # Inject updated_score as displayed final score\n"
src = src.replace(OLD_RPT_FN, NEW_RPT_FN)

OLD_RPT_FORMAT = "    _app_state['submission_report'] = r\n    return '✅ Submission report ready.', _format_report_with_updated_score(r), gr.update(interactive=True)"
NEW_RPT_FORMAT = "    _app_state['submission_report'] = r\n    return '✅ Submission report ready.', format_report(r), gr.update(interactive=True)"
src = src.replace(OLD_RPT_FORMAT, NEW_RPT_FORMAT)

# ── 7. Dropdown sync for all search buttons ────────────────────────────────
OLD_SYNC = (
    "    # ── Sync all candidate dropdowns after search ─────────────\n"
    "    s_btn.click(app_run_search, outputs=[s_st, s_tbl, s_dd]).then(\n"
    "        fn=lambda: [gr.update(choices=_candidate_choices())] * 7,\n"
    "        outputs=[m_dd, a_dd, w_dd, n_dd, r_dd, fb_dd, s_dd]\n"
    "    )"
)
NEW_SYNC = (
    "    # ── Sync all candidate dropdowns after ANY search ────────────\n"
    "    def _sync_all():\n"
    "        ch = _candidate_choices()\n"
    "        return [gr.update(choices=ch)] * 7\n\n"
    "    for _search_btn in [s_btn, jd_sb, ft_btn, voice_btn]:\n"
    "        _search_btn.click(fn=_sync_all, outputs=[m_dd, a_dd, w_dd, n_dd, r_dd, fb_dd, s_dd])"
)
src = src.replace(OLD_SYNC, NEW_SYNC)

# ── Write back ──────────────────────────────────────────────────────────────
cell['source'] = src
with open('AI_Recruiter_Copilot_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f'Done. Cell 39 updated. New length: {len(src)} chars')

# Verify key phrases present
checks = [
    'process_voice_jd',
    'run_freetext_search',
    'ask_clarification',
    'voice_btn',
    'ft_btn',
    'clarif_btn',
    'generate_submission_report',
    'format_report(r)',
    '_sync_all',
    'targets_requirement=req',
]
for c in checks:
    ok = c in src
    print(f'  {"OK" if ok else "MISSING"} {c}')

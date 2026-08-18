#!/usr/bin/env python3
"""Generate a self-contained HTML quiz from a quiz JSON (with auto-report).

Usage:
    python3 make_quiz.py quiz.json [out.html]

Quiz JSON schema:
{
  "quiz_id": "ch13-demo",
  "title": "Chapter 13 — Divisibility & Primes",
  "source": "Manhattan 5lb, pp. 483-490",
  "questions": [
    {
      "type": "mc" | "multi" | "qc" | "num",
      "prompt": "HTML with KaTeX math ($\\frac{65}{x}$ or \\(...\\))",
      "options": ["(A) Four", "(B) Six", ...],   // mc/multi/qc (qc defaults A-D if omitted)
      "answer": "A" | ["A","C"] | 4,             // letter(s) for mc/multi/qc, numeric for num
      "explanation": "HTML (may include KaTeX)",
      "src": "Manhattan 5lb · Ch 13 · p. 483 · Q1"   // optional textbook ref;
                                                      // omitted -> shows "Custom question (not from Manhattan 5lb)"
    }
  ]
}

Output: single-file HTML with KaTeX via CDN, styled after the real GRE test
delivery interface (ETS PowerPrep): one question on screen at a time inside a
charcoal chrome bar (Calculator / Review / Back / Next / Exit Section), a
dusty-mauve "Question N of M" status strip, and a single large white content
panel per question -- not stacked cards. A Review overlay shows a grid of
question numbers (answered / skipped / unmarked) for jumping between
questions. Circular ETS-style radio rows, per-type footer hints ("Select one
answer choice."), per-question check + explanations, running score (surfaced
in the Review overlay), and a "Submit & save results" button that POSTs to
/submit on the serving host (see quiz_server.py).

Also ships the basic on-screen calculator ETS provides on the Quant sections:
a "Calculator" button in the header opens a top-right panel with the four
operations, square root, and MC/MR/M+/M- memory. Expressions are evaluated by a
small recursive-descent parser over a whitelisted grammar (digits, '.', + - * /,
parentheses) -- never eval() -- and every calculator control preventDefault()s
so it cannot touch quiz answers.
"""
import datetime
import html
import json
import sys

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'$',right:'$',display:false}},{{left:'\\(',right:'\\)',display:false}},{{left:'\\[',right:'\\]',display:true}}]}});"></script>
<style>
  /* GRE / ETS PowerPrep delivery theme: charcoal chrome, mauve status strip, one big panel */
  :root {{
    --page: #bdbdbd;
    --card: #ffffff;
    --foreground: #1a1a1f;
    --border: #c8c8d2;
    --border-soft: #e2e2e9;
    --muted: #f4f4f7;
    --muted-foreground: #6b6b78;
    --ets-dark: #2a2a2e;
    --ets-dark-2: #1e1e21;
    --ets-strip: #d5c6c9;
    --ets-strip-fg: #3a2c30;
    --ets-blue: #2b5ea7;
    --ets-blue-hover: #234c88;
    --panel-border: #55555c;
    --radius: 3px;
    --topbar-h: 46px;
  }}
  * {{ box-sizing: border-box; }}
  html {{ color-scheme: light; }}
  body {{
    margin: 0;
    background: var(--page);
    color: var(--foreground);
    font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}

  /* ---- ETS top chrome ---- */
  .gretop {{
    position: sticky; top: 0; z-index: 20;
    min-height: var(--topbar-h);
    background: var(--ets-dark);
    border-bottom: 1px solid var(--ets-dark-2);
    color: #f2f1f6;
  }}
  .gretop-in {{
    max-width: 1000px; margin: 0 auto; min-height: var(--topbar-h);
    display: flex; align-items: center; gap: 14px; padding: 6px 16px;
    flex-wrap: wrap;
  }}
  .wordmark {{
    font-size: 1.15rem; font-weight: 700; letter-spacing: -0.03em;
    color: #ffffff; flex: 0 0 auto;
  }}
  .wordmark i {{ font-style: normal; color: #b9a8d8; margin-right: 1px; }}
  .gtitle {{
    flex: 1 1 auto; min-width: 0;
    font-size: .88rem; font-weight: 500; color: #cfcbdd;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  .gnav {{
    flex: 0 0 auto;
    font-size: .78rem; font-weight: 600; letter-spacing: .02em;
    padding: 5px 12px; border-radius: 3px;
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.16);
    color: #e8e6f0;
  }}
  .gretop-actions {{
    flex: 0 0 auto; margin-left: auto;
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  }}
  .gbtn {{
    font-family: inherit; font-size: .76rem; font-weight: 700; letter-spacing: .02em;
    padding: 7px 13px; border-radius: 3px; cursor: pointer;
    background: #55555c; color: #f2f1f6; border: 1px solid #6d6d76;
    transition: background .12s ease, opacity .12s ease;
  }}
  .gbtn:hover {{ background: #64646c; }}
  .gbtn:active {{ background: #48484e; }}
  .gbtn:disabled {{ opacity: .4; cursor: not-allowed; }}
  .gbtn.gbtn-blue {{ background: var(--ets-blue); border-color: var(--ets-blue-hover); color: #ffffff; }}
  .gbtn.gbtn-blue:hover {{ background: var(--ets-blue-hover); }}
  .gbtn.gbtn-blue:disabled {{ opacity: .5; }}

  .wrap {{ max-width: 1000px; margin: 0 auto; padding: 18px 16px 40px; }}

  /* ---- Question panel: one big ETS panel, only the current .q is shown ---- */
  .q {{
    background: var(--card);
    border: 1px solid var(--panel-border);
    border-radius: var(--radius);
    overflow: hidden;
  }}
  .statusstrip {{
    background: var(--ets-strip);
    color: var(--ets-strip-fg);
    font-size: .82rem; font-weight: 700; letter-spacing: .01em;
    padding: 8px 18px;
    display: flex; align-items: center; gap: 8px;
    border-bottom: 1px solid #b9a4a9;
  }}
  .statusstrip .tag {{
    font-weight: 600; color: rgba(58,44,48,0.72);
    text-transform: uppercase; letter-spacing: .06em; font-size: .68rem;
  }}
  .qbody {{ padding: 36px 40px 4px; min-height: 420px; display: flex; flex-direction: column; }}
  .q .stem {{ font-size: 1.02rem; margin: 0 auto 22px; max-width: 720px; width: 100%; }}

  /* ---- Quantitative Comparison: underlined labels, two plain columns ---- */
  .q .qc {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin: 8px auto 22px; max-width: 720px; width: 100%; text-align: center; }}
  .q .qc > div {{ padding: 0; font-size: 1.05rem; }}
  .q .qc b {{
    display: block; font-size: .92rem; font-weight: 600;
    color: var(--foreground); margin-bottom: 14px;
    text-decoration: underline; text-underline-offset: 3px;
  }}

  .ets-instruct {{
    margin: 0 auto 18px; max-width: 720px; width: 100%;
    padding: 8px 12px; background: #d8d8d8; color: #1a1a1a;
    font-size: .88rem; font-weight: 600; line-height: 1.35;
  }}
  .tc-cols {{
    display: flex; justify-content: center; gap: 28px; flex-wrap: wrap;
    margin: 8px auto 18px; max-width: 860px; width: 100%;
  }}
  .tc-col {{ min-width: 160px; text-align: center; }}
  .tc-col .tclab {{ display: block; font-size: .88rem; margin-bottom: 6px; color: #333; }}
  .tc-col .opts {{ border: 1px solid #444; max-width: 220px; margin: 0 auto; gap: 0; }}
  .tc-col label.opt {{ padding: 6px 10px; border-radius: 0; border: 0; justify-content: center; }}
  .tc-col label.opt .dot {{ display: none; }}
  .tc-col label.opt:hover {{ background: #ececec; }}
  .tc-col label.opt:has(input:checked) {{ background: #111; color: #fff; }}
  .tc-col label.opt:has(input:checked):hover {{ background: #111; }}

  .rc {{
    display: grid; grid-template-columns: 1fr 1fr; gap: 0;
    flex: 1 1 auto; min-height: 380px; margin: 0 -40px;
    border-top: 1px solid #8a8a8a;
  }}
  .rc-pass {{
    border-right: 1px solid #8a8a8a; overflow: auto; background: #fff;
    display: flex; flex-direction: column;
  }}
  .rc-bar {{
    background: #1a3a8a; color: #fff; font-size: .82rem; font-weight: 600;
    padding: 4px 10px; flex: 0 0 auto;
  }}
  .rc-text {{ padding: 12px 16px 20px; font-size: .95rem; line-height: 1.55; }}
  .rc-q {{ padding: 16px 18px 8px; overflow: auto; display: flex; flex-direction: column; }}
  .rc-q .stem {{ margin: 0 0 14px; max-width: none; }}
  .rc-q .opts {{ max-width: none; }}
  .q[data-kind="verbal"] .qbody {{ padding-top: 18px; }}


  /* ---- ETS answer rows ---- */
  .q .opts {{ display: flex; flex-direction: column; gap: 2px; margin: 0 auto 14px; max-width: 720px; width: 100%; }}
  .q label.opt {{
    display: flex; align-items: flex-start; gap: 12px;
    padding: 10px 12px;
    border: 1px solid transparent; border-radius: var(--radius);
    cursor: pointer; position: relative;
    transition: background .12s ease, border-color .12s ease;
  }}
  .q label.opt input {{
    position: absolute; opacity: 0; width: 1px; height: 1px; margin: 0; pointer-events: none;
  }}
  .q label.opt .dot {{
    flex: 0 0 auto; width: 19px; height: 19px; margin-top: 2px;
    border: 1.5px solid #8a8a99; border-radius: 50%;
    background: #ffffff;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.07);
    transition: background .12s ease, border-color .12s ease;
    position: relative;
  }}
  .q label.opt input[type=checkbox] ~ .dot {{ border-radius: 3px; }}
  .q label.opt .otext {{ flex: 1 1 auto; }}
  .q label.opt:hover {{ background: #f2f3f7; }}
  .q label.opt:focus-within .dot {{ box-shadow: 0 0 0 3px rgba(47,95,168,0.30); }}
  .q label.opt input:checked ~ .dot {{
    background: var(--ets-dark); border-color: var(--ets-dark);
    box-shadow: inset 0 1px 2px rgba(255,255,255,0.18);
  }}
  .q label.opt input[type=checkbox]:checked ~ .dot::after {{
    content: '✓'; position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    color: #ffffff; font-size: .72rem; font-weight: 700; line-height: 1;
  }}
  .q label.opt:has(input:disabled) {{ cursor: default; }}
  .q label.opt:has(input:disabled):hover {{ background: transparent; }}

  .q .numrow {{
    display: flex; align-items: center; justify-content: center; gap: 8px;
    margin: 4px auto 14px; font-size: 1.05rem;
  }}
  .q .numinput {{
    width: 160px; padding: 8px 11px; font-size: 1.05rem;
    background: var(--card); color: var(--foreground);
    border: 1.5px solid #6b6b74; border-radius: 2px;
    margin: 0;
  }}
  .q .numinput:focus {{ outline: none; border-color: var(--ets-blue); box-shadow: 0 0 0 3px rgba(43,94,167,0.22); }}

  /* ---- ETS footer hint: small centered gray chip ---- */
  .qfoot {{
    margin: auto auto 0; padding: 6px 14px;
    background: #d8d8d8;
    text-align: center;
    font-size: .78rem; color: #222;
    display: inline-block; align-self: center;
  }}
  /* ---- practice-only Check / Skip rail: compact, demoted below the ETS chip ---- */
  .qbtns {{ padding: 10px 0 16px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }}
  .qbtns .btn {{ font-size: .78rem; padding: 6px 14px; }}

  details.hint {{ font-size: .78rem; margin-bottom: 12px; }}
  details.hint summary {{ cursor: pointer; color: var(--muted-foreground); user-select: none; display: inline-block; font-weight: 500; }}
  details.hint summary:hover {{ text-decoration: underline; }}
  details.hint[open] summary {{ margin-bottom: 4px; }}
  details.hint .hint-body {{ color: var(--muted-foreground); padding: 8px 12px; background: var(--muted); border: 1px solid var(--border-soft); border-radius: var(--radius); margin-top: 4px; }}

  .btn {{
    background: var(--ets-blue); color: #ffffff;
    border: 1px solid var(--ets-blue-hover);
    padding: 8px 20px; border-radius: var(--radius);
    cursor: pointer; font-size: .875rem; font-weight: 600;
    font-family: inherit;
    transition: background .12s ease;
  }}
  .btn:hover {{ background: var(--ets-blue-hover); }}
  .btn:active {{ background: #204477; }}
  .btn.ghost {{ background: #ffffff; color: #3f3d4c; border: 1px solid var(--border); font-weight: 500; }}
  .btn.ghost:hover {{ background: var(--muted); }}

  .result {{ margin: 0 0 14px; padding: 12px 14px; border-radius: var(--radius); display: none; font-size: .92rem; }}
  .result.correct {{ background: #edf7ee; border: 1px solid #a8d5ad; color: #1d5c2a; }}
  .result.wrong {{ background: #fbeeee; border: 1px solid #e2b0b0; color: #8a2224; }}
  .result.skipped {{ background: #eef2fa; border: 1px solid #b4c4e2; color: #274a86; }}
  .result .expl {{ margin-top: 8px; color: var(--foreground); font-size: .9rem; }}
  .q.correct-q {{ border-color: #6aa872; }}
  .q.wrong-q {{ border-color: #c07d7d; }}
  .q.skipped-q {{ border-color: #8ba3cc; }}
  .q.correct-q .statusstrip {{ background: #2f6b39; color: #ffffff; }}
  .q.wrong-q .statusstrip {{ background: #8a2f36; color: #ffffff; }}
  .q.skipped-q .statusstrip {{ background: #3a4f7a; color: #ffffff; }}
  .q.correct-q .statusstrip .tag,
  .q.wrong-q .statusstrip .tag,
  .q.skipped-q .statusstrip .tag {{ color: rgba(255,255,255,0.82); }}

  .savebar {{ margin: 4px 0 0; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  #saveStatus {{ font-size: .86rem; color: var(--muted-foreground); }}
  .reset {{ margin-top: 0; }}

  /* ---- Review overlay: grid of question numbers + score summary ---- */
  .review-overlay {{
    position: fixed; inset: 0; z-index: 50;
    background: rgba(18,18,20,0.55);
    display: flex; align-items: center; justify-content: center;
    padding: 20px;
  }}
  .review-overlay[hidden] {{ display: none; }}
  .review-panel {{
    background: #f4f4f4; border: 1px solid var(--panel-border); border-radius: 4px;
    width: min(600px, 100%); max-height: 86vh; overflow: auto;
  }}
  .review-head {{
    background: var(--ets-dark); color: #ffffff;
    padding: 12px 18px; font-weight: 700; font-size: .95rem;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0;
  }}
  .review-close {{
    background: transparent; border: none; color: #ffffff;
    font-size: 1.3rem; line-height: 1; cursor: pointer; padding: 2px 6px;
  }}
  .review-summary {{ padding: 12px 18px; font-size: .86rem; color: #333; border-bottom: 1px solid #cfcfcf; }}
  .review-summary b {{ color: var(--ets-dark); }}
  .review-summary .meta {{ color: var(--muted-foreground); font-size: .78rem; margin-top: 6px; }}
  .review-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(42px,1fr));
    gap: 8px; padding: 16px 18px;
  }}
  .review-cell {{
    font-family: inherit; font-size: .82rem; font-weight: 700;
    padding: 9px 0; border-radius: 2px; cursor: pointer;
    border: 1px solid #8a8a90; background: #ffffff; color: #222;
  }}
  .review-cell.is-answered {{ background: #e5f0e8; border-color: #7fa98a; }}
  .review-cell.is-skipped {{ background: #eaf0fa; border-color: #8ba3cc; }}
  .review-cell.is-current {{ outline: 2px solid var(--ets-blue); outline-offset: 1px; }}
  .review-legend {{ display: flex; gap: 16px; padding: 0 18px 12px; font-size: .76rem; color: #555; flex-wrap: wrap; }}
  .review-legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }}
  .review-legend i.dot-answered {{ background: #7fa98a; }}
  .review-legend i.dot-skipped {{ background: #8ba3cc; }}
  .review-legend i.dot-unmarked {{ background: #ffffff; border: 1px solid #8a8a90; }}
  .review-actions {{ padding: 14px 18px 18px; border-top: 1px solid #cfcfcf; }}

  /* ---- ETS on-screen calculator ---- */
  .gcalc {{
    flex: 0 0 auto; font-family: inherit;
    display: inline-flex; align-items: center; gap: 6px;
    font-size: .78rem; font-weight: 600; letter-spacing: .02em;
    padding: 5px 11px; border-radius: 3px;
    background: linear-gradient(180deg, #4b5d84 0%, #3b4a6b 100%);
    border: 1px solid #5b6c92;
    color: #eef0f7; cursor: pointer;
    transition: background .12s ease, border-color .12s ease;
  }}
  .gcalc:hover {{ background: linear-gradient(180deg, #586a92 0%, #45557a 100%); border-color: #6d7ea6; }}
  .gcalc[aria-expanded="true"] {{
    background: #d9dde8; border-color: #b3bacd; color: #2b3350;
  }}
  .gcalc .gcalc-ico {{ font-size: .9rem; line-height: 1; }}

  .calc-panel {{
    position: fixed; z-index: 60;
    top: calc(var(--topbar-h) + 10px); right: 14px;
    width: 268px;
    background: #eceef4;
    border: 1px solid #969db2;
    border-radius: 5px;
    box-shadow: 0 12px 30px rgba(22,20,32,0.34), 0 2px 6px rgba(22,20,32,0.22);
    user-select: none; -webkit-user-select: none;
    font-variant-numeric: tabular-nums;
  }}
  .calc-panel[hidden] {{ display: none; }}
  .calc-bar {{
    display: flex; align-items: center; gap: 8px;
    padding: 5px 6px 5px 9px;
    background: linear-gradient(180deg, #3a3749 0%, var(--ets-dark) 100%);
    border-bottom: 1px solid var(--ets-dark-2);
    border-radius: 4px 4px 0 0;
    cursor: move;
    touch-action: none;
  }}
  .calc-grip {{
    flex: 0 0 auto; width: 14px; height: 10px;
    background-image: radial-gradient(circle, rgba(255,255,255,0.55) 1px, transparent 1.2px);
    background-size: 4px 4px;
  }}
  .calc-title {{
    flex: 1 1 auto; color: #e9e7f1;
    font-size: .74rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase;
  }}
  .calc-close {{
    flex: 0 0 auto; width: 22px; height: 20px; padding: 0;
    background: rgba(255,255,255,0.10); color: #efedf5;
    border: 1px solid rgba(255,255,255,0.18); border-radius: 3px;
    font-family: inherit; font-size: .92rem; line-height: 1; cursor: pointer;
  }}
  .calc-close:hover {{ background: rgba(255,255,255,0.22); }}

  .calc-screen {{
    position: relative;
    margin: 8px 8px 2px; padding: 7px 10px;
    background: #ffffff;
    border: 1px solid #9aa0b3; border-radius: 3px;
    box-shadow: inset 0 1px 3px rgba(30,28,40,0.14);
  }}
  .calc-mem {{
    position: absolute; left: 8px; top: 50%; transform: translateY(-50%);
    font-size: .64rem; font-weight: 700; letter-spacing: .05em; color: var(--ets-blue);
  }}
  .calc-display {{
    text-align: right;
    font-size: 1.18rem; font-weight: 600; line-height: 1.5;
    color: #1a1a1f;
    min-height: 1.5em;
    overflow-x: auto; white-space: nowrap;
    direction: ltr;
  }}
  .calc-display.err {{ color: #8a2224; font-size: 1rem; }}

  .calc-keys {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 5px; padding: 6px 8px 9px;
  }}
  .calc-key {{
    font-family: inherit; font-size: .95rem; font-weight: 600;
    min-height: 34px; padding: 0 2px;
    color: #22222b;
    background: linear-gradient(180deg, #ffffff 0%, #f1f2f6 100%);
    border: 1px solid #a9aec0; border-radius: 3px;
    cursor: pointer;
    transition: background .1s ease, border-color .1s ease;
  }}
  .calc-key:hover {{ background: #e8eaf1; border-color: #8f96ac; }}
  .calc-key:active {{ background: #d7dae5; }}
  .calc-key:focus-visible {{ outline: none; border-color: var(--ets-blue); box-shadow: 0 0 0 2px rgba(47,95,168,0.35); }}
  .calc-key.fn {{
    font-size: .78rem; font-weight: 600; color: #3f4353;
    background: linear-gradient(180deg, #e6e8ef 0%, #d9dce6 100%);
    border-color: #a3a9bc;
  }}
  .calc-key.fn:hover {{ background: #ced2df; }}
  .calc-key.op {{
    color: #24304a;
    background: linear-gradient(180deg, #e3e8f3 0%, #d2d9ea 100%);
    border-color: #9ea7c0;
  }}
  .calc-key.op:hover {{ background: #c6cfe4; }}
  .calc-key.eq {{
    color: #ffffff;
    background: linear-gradient(180deg, #3a6cb5 0%, var(--ets-blue) 100%);
    border-color: var(--ets-blue-hover);
  }}
  .calc-key.eq:hover {{ background: var(--ets-blue-hover); }}
  .calc-key.wide {{ grid-column: span 2; }}

  @media (max-width: 560px) {{
    body {{ font-size: 15px; }}
    .gtitle {{ display: none; }}
    .gnav {{ display: none; }}
    .gretop-in {{ gap: 8px; padding: 6px 10px; }}
    .gretop-actions {{ gap: 5px; }}
    .gbtn {{ padding: 7px 9px; font-size: .72rem; }}
    .wrap {{ padding: 14px 10px 40px; }}
    .qbody {{ padding: 20px 16px 4px; min-height: 320px; }}
    .qfoot {{ margin: auto auto 0; padding: 6px 12px; }}
    .q .qc {{ grid-template-columns: 1fr; gap: 16px; }}
    .rc {{ grid-template-columns: 1fr; margin: 0 -16px; min-height: 0; }}
    .rc-pass {{ border-right: 0; border-bottom: 1px solid #8a8a8a; max-height: 38vh; }}
    .tc-cols {{ gap: 16px; }}
    .gcalc {{ padding: 5px 9px; }}
    .gcalc .gcalc-label {{ display: inline; }}
    .calc-panel {{ width: min(300px, calc(100vw - 20px)); right: 10px; }}
    .calc-key {{ min-height: 44px; font-size: 1rem; }}
    .calc-key.fn {{ font-size: .82rem; }}
    .review-grid {{ grid-template-columns: repeat(auto-fill, minmax(36px,1fr)); }}
  }}
</style>
</head>
<body>
<div class="gretop">
  <div class="gretop-in">
    <span class="wordmark"><i>✻</i>gre.</span>
    <span class="gtitle">{title}</span>
    <span class="gnav" id="gnav">1 / {qcount}</span>
    <div class="gretop-actions">
      <button type="button" class="gcalc" id="calcToggle" aria-expanded="false" aria-controls="calcPanel"
              title="On-screen calculator">
        <span class="gcalc-ico" aria-hidden="true">▤</span><span class="gcalc-label">Calculator</span>
      </button>
      <button type="button" class="gbtn" id="btnReview">Review</button>
      <button type="button" class="gbtn" id="btnBack">Back</button>
      <button type="button" class="gbtn gbtn-blue" id="btnNext">Next</button>
      <button type="button" class="gbtn" id="btnExit">Exit Section</button>
    </div>
  </div>
</div>
<div class="calc-panel" id="calcPanel" role="dialog" aria-label="On-screen calculator" hidden>
  <div class="calc-bar">
    <span class="calc-grip" aria-hidden="true"></span>
    <span class="calc-title">Calculator</span>
    <button type="button" class="calc-close" id="calcClose" aria-label="Close calculator">&times;</button>
  </div>
  <div class="calc-screen">
    <span class="calc-mem" id="calcMem"></span>
    <div class="calc-display" id="calcDisplay" role="status" aria-live="polite" aria-atomic="true">0</div>
  </div>
  <div class="calc-keys" id="calcKeys">
    <button type="button" class="calc-key fn" data-k="MC">MC</button>
    <button type="button" class="calc-key fn" data-k="MR">MR</button>
    <button type="button" class="calc-key fn" data-k="M+">M+</button>
    <button type="button" class="calc-key fn" data-k="M-">M&minus;</button>
    <button type="button" class="calc-key fn" data-k="C">C</button>
    <button type="button" class="calc-key fn" data-k="BS" aria-label="Backspace">&#9003;</button>
    <button type="button" class="calc-key fn" data-k="SQRT" aria-label="Square root">&radic;</button>
    <button type="button" class="calc-key op" data-k="/" aria-label="Divide">&divide;</button>
    <button type="button" class="calc-key" data-k="7">7</button>
    <button type="button" class="calc-key" data-k="8">8</button>
    <button type="button" class="calc-key" data-k="9">9</button>
    <button type="button" class="calc-key op" data-k="*" aria-label="Multiply">&times;</button>
    <button type="button" class="calc-key" data-k="4">4</button>
    <button type="button" class="calc-key" data-k="5">5</button>
    <button type="button" class="calc-key" data-k="6">6</button>
    <button type="button" class="calc-key op" data-k="-" aria-label="Minus">&minus;</button>
    <button type="button" class="calc-key" data-k="1">1</button>
    <button type="button" class="calc-key" data-k="2">2</button>
    <button type="button" class="calc-key" data-k="3">3</button>
    <button type="button" class="calc-key op" data-k="+" aria-label="Plus">+</button>
    <button type="button" class="calc-key wide" data-k="0">0</button>
    <button type="button" class="calc-key" data-k=".">.</button>
    <button type="button" class="calc-key eq" data-k="=" aria-label="Equals">=</button>
  </div>
</div>
<div class="wrap">
  {questions_html}
</div>
<div class="review-overlay" id="reviewOverlay" hidden role="dialog" aria-label="Review section">
  <div class="review-panel">
    <div class="review-head">
      <span>Review Section — {title}</span>
      <button type="button" class="review-close" id="reviewClose" aria-label="Close review">&times;</button>
    </div>
    <div class="review-summary">
      Score: <b id="score">0</b> / {qcount} · <span id="done">0</span> answered · <span id="skipped">0</span> skipped
      <div class="meta">{source} · generated {date}</div>
    </div>
    <div class="review-grid" id="reviewGrid"></div>
    <div class="review-legend">
      <span><i class="dot-answered"></i>Answered</span>
      <span><i class="dot-skipped"></i>Skipped</span>
      <span><i class="dot-unmarked"></i>Unanswered</span>
    </div>
    <div class="review-actions savebar">
      <button class="btn" onclick="submitQuiz()">Submit &amp; save results</button>
      <span id="saveStatus"></span>
      <button class="btn ghost reset" onclick="resetQuiz()">Reset quiz</button>
    </div>
  </div>
</div>
<script>
const answers = {answers_json};
const quizId = {quiz_id_json};
let clientId = localStorage.getItem('quizClientId');
if (!clientId) {{
  clientId = (crypto.randomUUID && crypto.randomUUID()) || ('c' + Date.now() + Math.random().toString(16).slice(2));
  localStorage.setItem('quizClientId', clientId);
}}
let done = 0, score = 0, skipped = 0;
function letterInputs(qid) {{
  const q = document.getElementById(qid);
  return q.querySelectorAll('input[type=radio], input[type=checkbox]');
}}
function pickAnswer(q, ans) {{
  const cols = q.querySelectorAll('.tc-col');
  if (cols.length) {{
    return [...cols].map(col => {{
      const sel = col.querySelector('input:checked');
      return sel ? sel.value : null;
    }});
  }}
  if (typeof ans === 'number') {{
    const v = q.querySelector('input[type=number]');
    return v.value.trim() === '' ? null : parseFloat(v.value);
  }}
  const inputs = letterInputs(q.id);
  if (Array.isArray(ans)) {{
    const picked = [...inputs].filter(i => i.checked).map(i => i.value);
    picked.sort();
    return picked;
  }}
  const sel = [...inputs].find(i => i.checked);
  return sel ? sel.value : null;
}}
function answersMatch(picked, ans, q) {{
  if (q.querySelector('.tc-col')) return JSON.stringify(picked) === JSON.stringify(ans);
  if (Array.isArray(ans)) return JSON.stringify(picked) === JSON.stringify([...ans].sort());
  return picked === ans;
}}
function afterLock(q) {{
  q.querySelectorAll('.btn-check, .btn-skip').forEach(b => {{ b.hidden = true; }});
  const n = q.querySelector('.btn-gonext');
  if (!n) return;
  n.hidden = false;
  n.textContent = (typeof currentIdx === 'number' && currentIdx === qEls.length - 1) ? 'Review' : 'Next';
}}
function goAfterLock() {{
  if (currentIdx === qEls.length - 1) openReview();
  else showQuestion(currentIdx + 1);
}}
function check(qid, idx) {{
  const q = document.getElementById(qid);
  if (q.dataset.done === '1' || q.dataset.done === 's') return;
  const inputs = letterInputs(qid);
  const ans = answers[idx];
  const res = q.querySelector('.result');
  const picked = pickAnswer(q, ans);
  const ok = answersMatch(picked, ans, q);
  q.dataset.done = '1';
  inputs.forEach(i => i.disabled = true);
  const n = q.querySelector('input[type=number]');
  if (n) n.disabled = true;
  q.classList.add(ok ? 'correct-q' : 'wrong-q');
  res.classList.remove('correct','wrong');
  res.classList.add(ok ? 'correct' : 'wrong');
  res.innerHTML = (ok ? '<b>✓ Correct</b>' : '<b>✗ Incorrect</b>') +
                  '<div class="expl">' + q.querySelector('.expl-src').innerHTML + '</div>';
  res.style.display = 'block';
  done++; if (ok) score++;
  document.getElementById('score').textContent = score;
  document.getElementById('done').textContent = done;
  afterLock(q);
  buildReviewGrid();
}}
function skip(qid, idx) {{
  const q = document.getElementById(qid);
  if (q.dataset.done === '1' || q.dataset.done === 's') return;
  const inputs = letterInputs(qid);
  inputs.forEach(i => i.disabled = true);
  const n = q.querySelector('input[type=number]');
  if (n) n.disabled = true;
  q.dataset.done = 's';
  q.classList.add('skipped-q');
  const res = q.querySelector('.result');
  res.classList.remove('correct','wrong');
  res.classList.add('skipped');
  res.innerHTML = '<b>⏭ Skipped — review the explanation</b>' +
                  '<div class="expl">' + q.querySelector('.expl-src').innerHTML + '</div>';
  res.style.display = 'block';
  skipped++;
  document.getElementById('skipped').textContent = skipped;
  afterLock(q);
  buildReviewGrid();
}}
function submitQuiz() {{
  const qs = document.querySelectorAll('.q');
  const submitted = [];
  qs.forEach((q, idx) => {{
    const srcEl = q.querySelector('.q-src');
    const src = srcEl ? srcEl.textContent : '';
    const answered = q.dataset.done === '1';
    const isSkipped = q.dataset.done === 's';
    let picked = null;
    if (answered) {{
      picked = pickAnswer(q, answers[idx]);
    }}
    submitted.push({{
      q: 'q' + (idx + 1),
      src,
      answered,
      skipped: isSkipped,
      picked,
      correct: answered ? q.classList.contains('correct-q') : null
    }});
  }});
  const statusEl = document.getElementById('saveStatus');
  statusEl.textContent = 'Saving…';
  fetch('/submit', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{
      quiz_id: quizId,
      client_id: clientId,
      timestamp: new Date().toISOString(),
      answers: submitted
    }})
  }})
    .then(r => r.json())
    .then(d => {{
      statusEl.textContent = d.saved
        ? 'Saved ✓ — attempt ' + d.attempt + ' · ' + d.score + '/' + d.total + ' correct'
        : 'Save failed: ' + JSON.stringify(d);
    }})
    .catch(() => {{ statusEl.textContent = 'Save failed (server unreachable)'; }});
}}
function resetQuiz() {{
  document.querySelectorAll('.q').forEach(q => {{
    q.dataset.done = '0';
    q.classList.remove('correct-q','wrong-q','skipped-q');
    q.querySelectorAll('input').forEach(i => {{ i.checked = false; i.disabled = false; }});
    const r = q.querySelector('.result'); r.style.display = 'none';
    q.querySelectorAll('.btn-check, .btn-skip').forEach(b => {{ b.hidden = false; }});
    const gn = q.querySelector('.btn-gonext'); if (gn) gn.hidden = true;
  }});
  done = 0; score = 0; skipped = 0;
  document.getElementById('score').textContent = '0';
  document.getElementById('done').textContent = '0';
  document.getElementById('skipped').textContent = '0';
  buildReviewGrid();
}}

/* ---- index-based nav: exactly one .q visible at a time ---- */
const gnavEl = document.getElementById('gnav');
const qEls = [...document.querySelectorAll('.q')];
const btnBack = document.getElementById('btnBack');
const btnNext = document.getElementById('btnNext');
const btnReview = document.getElementById('btnReview');
const btnExit = document.getElementById('btnExit');
const toggleCalcBtn = document.getElementById('calcToggle');
const reviewOverlay = document.getElementById('reviewOverlay');
const reviewGrid = document.getElementById('reviewGrid');
const reviewClose = document.getElementById('reviewClose');
let currentIdx = 0;

function showQuestion(i) {{
  if (i < 0 || i >= qEls.length) return;
  currentIdx = i;
  qEls.forEach((el, idx) => {{ el.style.display = (idx === currentIdx) ? '' : 'none'; }});
  gnavEl.textContent = (currentIdx + 1) + ' / ' + qEls.length;
  btnBack.disabled = (currentIdx === 0);
  btnNext.disabled = (currentIdx === qEls.length - 1);
  const verbal = qEls[currentIdx].dataset.kind === 'verbal';
  if (toggleCalcBtn) toggleCalcBtn.hidden = verbal;
  const calcPanel = document.getElementById('calcPanel');
  if (verbal && calcPanel) {{
    calcPanel.hidden = true;
    if (toggleCalcBtn) toggleCalcBtn.setAttribute('aria-expanded', 'false');
  }}
  window.scrollTo(0, 0);
}}

function buildReviewGrid() {{
  reviewGrid.innerHTML = '';
  qEls.forEach((q, idx) => {{
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'review-cell';
    if (idx === currentIdx) b.className += ' is-current';
    if (q.dataset.done === '1') b.className += ' is-answered';
    else if (q.dataset.done === 's') b.className += ' is-skipped';
    b.textContent = idx + 1;
    b.addEventListener('click', function () {{ closeReview(); showQuestion(idx); }});
    reviewGrid.appendChild(b);
  }});
}}
function openReview() {{
  buildReviewGrid();
  reviewOverlay.hidden = false;
}}
function closeReview() {{ reviewOverlay.hidden = true; }}

btnBack.addEventListener('click', function () {{ showQuestion(currentIdx - 1); }});
btnNext.addEventListener('click', function () {{ showQuestion(currentIdx + 1); }});
btnReview.addEventListener('click', openReview);
btnExit.addEventListener('click', function () {{ submitQuiz(); }});
reviewClose.addEventListener('click', closeReview);
reviewOverlay.addEventListener('click', function (e) {{ if (e.target === reviewOverlay) closeReview(); }});

showQuestion(0);
buildReviewGrid();

/* ---- GRE on-screen calculator: four functions + square root, safe parser ---- */
(function () {{
  const panel = document.getElementById('calcPanel');
  const toggle = document.getElementById('calcToggle');
  const closeBtn = document.getElementById('calcClose');
  const keys = document.getElementById('calcKeys');
  const display = document.getElementById('calcDisplay');
  const memInd = document.getElementById('calcMem');
  if (!panel || !toggle || !keys || !display) return;

  // expr only ever holds the safe grammar: digits . + - * / ( )
  let expr = '0';
  let memory = 0, hasMem = false, errored = false;
  let fresh = true;   // display holds a finished result; next digit starts fresh

  const PRETTY = {{'*': ' × ', '/': ' ÷ ', '+': ' + ', '-': ' − '}};
  function pretty(s) {{
    return s.replace(/[*\/+\-]/g, function (c) {{ return PRETTY[c]; }});
  }}

  function tokenize(s) {{
    const out = [];
    let i = 0;
    while (i < s.length) {{
      const c = s.charAt(i);
      if (c === ' ') {{ i++; continue; }}
      if ((c >= '0' && c <= '9') || c === '.') {{
        let j = i, dot = false, digits = 0;
        while (j < s.length) {{
          const d = s.charAt(j);
          if (d >= '0' && d <= '9') {{ digits++; j++; }}
          else if (d === '.' && !dot) {{ dot = true; j++; }}
          else break;
        }}
        if (!digits) throw new Error('bad number');
        out.push({{t: 'n', v: parseFloat(s.slice(i, j))}});
        i = j;
      }} else if (c === '+' || c === '-' || c === '*' || c === '/' || c === '(' || c === ')') {{
        out.push({{t: c}});
        i++;
      }} else {{
        throw new Error('bad character');
      }}
    }}
    return out;
  }}

  // recursive descent: expr := term (('+'|'-') term)* ; term := unary (('*'|'/') unary)*
  function evaluate(s) {{
    const tk = tokenize(s);
    let p = 0;
    function peek() {{ return p < tk.length ? tk[p].t : null; }}
    function parsePrimary() {{
      const t = peek();
      if (t === 'n') return tk[p++].v;
      if (t === '(') {{
        p++;
        const v = parseExpr();
        if (peek() !== ')') throw new Error('unbalanced parentheses');
        p++;
        return v;
      }}
      throw new Error('unexpected token');
    }}
    function parseUnary() {{
      if (peek() === '-') {{ p++; return -parseUnary(); }}
      if (peek() === '+') {{ p++; return parseUnary(); }}
      return parsePrimary();
    }}
    function parseTerm() {{
      let v = parseUnary();
      while (peek() === '*' || peek() === '/') {{
        const op = tk[p++].t;
        const r = parseUnary();
        if (op === '/') {{
          if (r === 0) throw new Error('division by zero');
          v = v / r;
        }} else {{
          v = v * r;
        }}
      }}
      return v;
    }}
    function parseExpr() {{
      let v = parseTerm();
      while (peek() === '+' || peek() === '-') {{
        const op = tk[p++].t;
        const r = parseTerm();
        v = (op === '+') ? v + r : v - r;
      }}
      return v;
    }}
    const val = parseExpr();
    if (p !== tk.length) throw new Error('trailing input');
    if (!isFinite(val)) throw new Error('not finite');
    return val;
  }}

  function fmt(v) {{
    if (!isFinite(v)) throw new Error('not finite');
    const r = parseFloat(v.toPrecision(12));
    if (r === 0) return '0';
    const a = Math.abs(r);
    if (a >= 1e12 || a < 1e-9) return r.toExponential(6).replace(/e\+/, 'e');
    return String(r);
  }}

  function render() {{
    display.textContent = errored ? 'Error' : pretty(expr);
    display.classList.toggle('err', errored);
    memInd.textContent = hasMem ? 'M' : '';
  }}

  function reset() {{ expr = '0'; errored = false; fresh = true; }}
  function endsWithOp() {{ return /[+\-*\/]$/.test(expr); }}
  function trimTrailingOps(s) {{
    while (/[+\-*\/]$/.test(s)) s = s.slice(0, -1);
    return s === '' ? '0' : s;
  }}

  function inputDigit(ch) {{
    if (errored) reset();
    if (fresh) {{ expr = (ch === '.') ? '0.' : ch; fresh = false; return; }}
    if (ch === '.') {{
      const tail = /(\d*\.?\d*)$/.exec(expr)[1];
      if (tail.indexOf('.') >= 0) return;
      if (tail === '') {{ expr += '0.'; return; }}
      expr += '.';
      return;
    }}
    if (expr === '0') {{ expr = ch; return; }}
    expr += ch;
  }}

  function inputOp(op) {{
    if (errored) return;
    fresh = false;
    if (endsWithOp()) {{ expr = expr.slice(0, -1) + op; return; }}
    expr += op;
  }}

  function inputSqrt() {{
    if (errored) return;
    try {{
      const m = /(\d+(?:\.\d+)?|\.\d+)$/.exec(expr);
      if (m) {{
        const v = parseFloat(m[0]);
        if (v < 0) throw new Error('domain');
        expr = expr.slice(0, m.index) + fmt(Math.sqrt(v));
        fresh = (m.index === 0);
      }} else {{
        const v = evaluate(trimTrailingOps(expr));
        if (v < 0) throw new Error('domain');
        expr = fmt(Math.sqrt(v));
        fresh = true;
      }}
    }} catch (e) {{
      errored = true;
    }}
  }}

  function backspace() {{
    if (errored) {{ reset(); return; }}
    expr = expr.slice(0, -1);
    if (expr === '') {{ expr = '0'; fresh = true; }} else {{ fresh = false; }}
  }}

  function equals() {{
    if (errored) return;
    try {{
      expr = fmt(evaluate(trimTrailingOps(expr)));
    }} catch (e) {{
      errored = true;
    }}
    fresh = true;
  }}

  function memOp(k) {{
    if (k === 'MC') {{ memory = 0; hasMem = false; return; }}
    if (k === 'MR') {{
      if (errored) reset();
      const s = fmt(memory);
      if (endsWithOp()) expr += s; else expr = s;
      fresh = false;
      return;
    }}
    if (errored) return;
    try {{
      const v = evaluate(trimTrailingOps(expr));
      memory = (k === 'M+') ? memory + v : memory - v;
      hasMem = (memory !== 0);
      fresh = true;
    }} catch (e) {{
      errored = true;
    }}
  }}

  function press(k) {{
    if (k === 'C') reset();
    else if (k === 'BS') backspace();
    else if (k === 'SQRT') inputSqrt();
    else if (k === '=') equals();
    else if (k === 'MC' || k === 'MR' || k === 'M+' || k === 'M-') memOp(k);
    else if (k === '+' || k === '-' || k === '*' || k === '/') inputOp(k);
    else if (k === '.' || (k.length === 1 && k >= '0' && k <= '9')) inputDigit(k);
    render();
  }}

  function isOpen() {{ return !panel.hidden; }}
  function openCalc() {{
    panel.hidden = false;
    toggle.setAttribute('aria-expanded', 'true');
    render();
  }}
  function closeCalc() {{
    panel.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  }}

  toggle.addEventListener('click', function (e) {{
    e.preventDefault();
    e.stopPropagation();
    if (isOpen()) closeCalc(); else openCalc();
  }});
  closeBtn.addEventListener('click', function (e) {{
    e.preventDefault();
    e.stopPropagation();
    closeCalc();
  }});
  keys.addEventListener('click', function (e) {{
    const btn = e.target.closest ? e.target.closest('.calc-key') : null;
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    press(btn.getAttribute('data-k'));
  }});
  // never let calculator interaction reach the quiz or the outside-click closer
  panel.addEventListener('click', function (e) {{ e.stopPropagation(); }});
  panel.addEventListener('mousedown', function (e) {{
    e.stopPropagation();
    // don't leave a key focused after a mouse press, so Enter stays "="
    if (e.target.closest && e.target.closest('.calc-key')) e.preventDefault();
  }});
  document.addEventListener('click', function (e) {{
    if (dragMoved) {{ dragMoved = false; return; }}
    if (isOpen() && !panel.contains(e.target) && !toggle.contains(e.target)) closeCalc();
  }});

  /* drag by the title bar — mouse + touch, clamped to the viewport */
  const bar = panel.querySelector('.calc-bar');
  let drag = null, dragMoved = false;
  function clamp(n, lo, hi) {{ return Math.max(lo, Math.min(hi, n)); }}
  function place(x, y) {{
    const r = panel.getBoundingClientRect();
    const left = clamp(x, 4, Math.max(4, window.innerWidth - r.width - 4));
    const top = clamp(y, 4, Math.max(4, window.innerHeight - r.height - 4));
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    panel.style.right = 'auto';
  }}
  function pt(e) {{ return (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0]) || e; }}
  function onDown(e) {{
    if (e.target.closest && e.target.closest('.calc-close')) return;
    const p = pt(e);
    const r = panel.getBoundingClientRect();
    drag = {{ dx: p.clientX - r.left, dy: p.clientY - r.top }};
    dragMoved = false;
    e.preventDefault();
    e.stopPropagation();
  }}
  function onMove(e) {{
    if (!drag) return;
    const p = pt(e);
    place(p.clientX - drag.dx, p.clientY - drag.dy);
    dragMoved = true;
    e.preventDefault();
  }}
  function onUp() {{ drag = null; }}
  if (bar) {{
    bar.addEventListener('mousedown', onDown);
    bar.addEventListener('touchstart', onDown, {{passive: false}});
  }}
  document.addEventListener('mousemove', onMove);
  document.addEventListener('touchmove', onMove, {{passive: false}});
  document.addEventListener('mouseup', onUp);
  document.addEventListener('touchend', onUp);

  const KEYMAP = {{'/': '/', '*': '*', 'x': '*', 'X': '*', '-': '-', '+': '+', '.': '.', ',': '.'}};
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape' && isOpen()) {{ e.preventDefault(); closeCalc(); return; }}
    if (!isOpen() || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    const tag = (t && t.tagName) ? t.tagName.toLowerCase() : '';
    // don't hijack typing in the numeric-entry boxes
    if (!panel.contains(t) && (tag === 'input' || tag === 'textarea' || (t && t.isContentEditable))) return;
    // let a keyboard-focused calculator key activate itself with Space
    if (panel.contains(t) && tag === 'button' && e.key === ' ') return;
    const k = e.key;
    if (k.length === 1 && k >= '0' && k <= '9') {{ e.preventDefault(); press(k); return; }}
    if (k === 'Enter' || k === '=') {{ e.preventDefault(); press('='); return; }}
    if (k === 'Backspace') {{ e.preventDefault(); press('BS'); return; }}
    if (k === 'Delete' || k === 'c' || k === 'C') {{ e.preventDefault(); press('C'); return; }}
    if (k === 'r' || k === 'R') {{ e.preventDefault(); press('SQRT'); return; }}
    if (Object.prototype.hasOwnProperty.call(KEYMAP, k)) {{ e.preventDefault(); press(KEYMAP[k]); return; }}
  }});

  render();
}})();
</script>
</body>
</html>
"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def qc_choices():
    return ["(A) Quantity A is greater.",
            "(B) Quantity B is greater.",
            "(C) The two quantities are equal.",
            "(D) The relationship cannot be determined from the information given."]


FOOTER_HINTS = {
    "mc": "Select one answer choice.",
    "qc": "Select one answer choice.",
    "multi": "Select one or more answer choices.",
    "num": "Enter your answer as an integer or a decimal in the answer box. Backspace to erase.",
    "tc": "Select one entry from each column.",
    "se": "Select two answer choices.",
    "rc": "Select one answer choice.",
}

TC_INSTRUCT = ("For each blank select one entry from the corresponding column of choices. "
               "Fill all blanks in the way that best completes the text.")
SE_INSTRUCT = ("Select the two answer choices that, when used to complete the sentence, "
               "fit the meaning of the sentence as a whole and produce completed sentences "
               "that are alike in meaning.")

LETTERS = "ABCDEFGHIJ"


def _opt_rows(qid: str, opts: list, kind: str) -> str:
    rows = ""
    for o in opts:
        letter = o.split(")")[0].lstrip("(").strip() if ")" in o else o
        rows += (f'<label class="opt"><input type="{kind}" name="{qid}" value="{esc(letter)}">'
                 f'<span class="dot"></span><span class="otext">{o}</span></label>')
    return f'<div class="opts">{rows}</div>'


def render_question(i: int, q: dict, total: int) -> str:
    qid = f"q{i}"
    t = q.get("type", "mc")
    tag = {
        "mc": "Multiple Choice", "multi": "Select All", "qc": "Quant Comparison",
        "num": "Numeric Entry", "tc": "Text Completion", "se": "Sentence Equivalence",
        "rc": "Reading Comp",
    }[t]
    kind = "verbal" if t in ("tc", "se", "rc") else "quant"
    src = q.get("src", "").strip()
    if src:
        src_html = (f'<details class="hint"><summary>Topic / source</summary>'
                    f'<div class="hint-body">{esc(src)}</div></details>')
    else:
        src_html = ('<details class="hint"><summary>Topic / source</summary>'
                    '<div class="hint-body">Custom question — not from Manhattan 5lb</div></details>')
    opts = q.get("options")
    if t == "qc" and not opts:
        opts = qc_choices()
    if t == "tc":
        cols = ""
        for bi, blank in enumerate(q.get("blanks") or []):
            brow = ""
            for oi, word in enumerate(blank.get("options") or []):
                letter = LETTERS[oi]
                brow += (f'<label class="opt"><input type="radio" name="{qid}b{bi}" value="{letter}">'
                         f'<span class="dot"></span><span class="otext">{word}</span></label>')
            cols += (f'<div class="tc-col"><span class="tclab">{esc(blank.get("label", f"Blank ({bi+1})"))}</span>'
                     f'<div class="opts">{brow}</div></div>')
        body = (f'<div class="ets-instruct">{TC_INSTRUCT}</div>'
                f'<div class="stem">{q["prompt"]}</div>'
                f'<div class="tc-cols">{cols}</div>')
    elif t == "se":
        body = (f'<div class="ets-instruct">{SE_INSTRUCT}</div>'
                f'<div class="stem">{q["prompt"]}</div>'
                f'{_opt_rows(qid, opts or [], "checkbox")}')
    elif t == "rc":
        rc_kind = "checkbox" if isinstance(q.get("answer"), list) else "radio"
        foot_rc = "Select one or more answer choices." if rc_kind == "checkbox" else FOOTER_HINTS["rc"]
        body = (f'<div class="rc"><div class="rc-pass">'
                f'<div class="rc-bar">{esc(q.get("passage_label", "This question is based on this passage."))}</div>'
                f'<div class="rc-text">{q.get("passage", "")}</div></div>'
                f'<div class="rc-q"><div class="stem">{q["prompt"]}</div>'
                f'{_opt_rows(qid, opts or [], rc_kind)}</div></div>')
    elif t == "qc":
        qa = q.get("qa", "")
        qb = q.get("qb", "")
        body = f'<div class="stem">{q["prompt"]}</div>' \
               f'<div class="qc"><div><b>Quantity A</b>{qa}</div><div><b>Quantity B</b>{qb}</div></div>'
        if opts:
            body += _opt_rows(qid, opts, "radio")
    else:
        body = f'<div class="stem">{q["prompt"]}</div>'
        if t == "num":
            body += '<div class="numrow"><span class="numlabel"><i>x</i> =</span><input type="number" class="numinput" aria-label="Numeric answer"></div>'
        elif opts:
            kind_in = "radio" if t == "mc" else "checkbox"
            body += _opt_rows(qid, opts, kind_in)
    foot = foot_rc if t == "rc" and isinstance(q.get("answer"), list) else FOOTER_HINTS[t]
    expl = f'<div class="expl-src" style="display:none">{q.get("explanation", "")}</div>'
    srcdata = f'<div class="q-src" style="display:none">{esc(src)}</div>'
    return (f'<div class="q" id="{qid}" data-done="0" data-kind="{kind}">'
            f'<div class="statusstrip">Question {i+1} of {total}'
            f'<span class="tag">· {tag}</span></div>'
            f'<div class="qbody">'
            f'{src_html}{body}{srcdata}{expl}'
            f'<div class="result"></div>'
            f'<div class="qfoot">{foot}</div>'
            f'<div class="qbtns">'
            f'<button class="btn btn-check" onclick="check(\'{qid}\',{i})">Check</button>'
            f'<button class="btn ghost btn-skip" onclick="skip(\'{qid}\',{i})">Skip / Don\'t know</button>'
            f'<button type="button" class="btn btn-gonext" hidden onclick="goAfterLock()">Next</button>'
            f'</div></div></div>')


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1]) as f:
        quiz = json.load(f)
    out = sys.argv[2] if len(sys.argv) > 2 else "quiz.html"
    questions = quiz["questions"]
    qhtml = "\n".join(render_question(i, q, len(questions)) for i, q in enumerate(questions))
    answers = [q["answer"] for q in questions]
    html_out = TEMPLATE.format(
        title=esc(quiz.get("title", "GRE Quiz")),
        source=esc(quiz.get("source", "")),
        qcount=len(questions),
        date=datetime.date.today().isoformat(),
        questions_html=qhtml,
        answers_json=json.dumps(answers),
        quiz_id_json=json.dumps(quiz.get("quiz_id", "default")),
    )
    with open(out, "w") as f:
        f.write(html_out)
    print(f"Wrote {out} ({len(html_out)} bytes, {len(questions)} questions)")


if __name__ == "__main__":
    main()

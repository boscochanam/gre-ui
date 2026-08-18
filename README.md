# gre-test-ui

Unofficial **on-screen GRE section UI**.  
Not a question bank. You bring the items; this is the chrome: one question at a time, Back / Next / Review, Quant calculator, Text Completion columns, Sentence Equivalence boxes, Reading Comp split pane.

**Not affiliated with ETS.** GRE® is a registered trademark of ETS. This is an independent practice shell, not an official test, not POWERPREP®, and it does not include official items or scores.

## Why it exists

The computer-delivered GRE has a specific muscle memory (header, status strip, footer hint, calculator). Most HTML quizzes look like blogs. This generator emits a self-contained page that *feels* like a section so drills transfer. Content is yours — JSON in, HTML out.

## Quick start

```bash
python3 scripts/make_quiz.py examples/sample.json examples/sample.html
# open examples/sample.html
```

Collect answers (optional):

```bash
python3 scripts/make_quiz.py examples/sample.json /tmp/drill/index.html
python3 scripts/quiz_server.py 8899 /tmp/drill ~/drill-results
```

`POST /submit` stores one record per `(quiz_id, client_id)`.

## Question JSON

`type` is one of: `mc` · `multi` · `qc` · `num` · `tc` · `se` · `rc`

```json
{
  "quiz_id": "my-drill",
  "title": "Algebra section",
  "source": "my notes",
  "questions": [
    {
      "type": "mc",
      "prompt": "If $2x = 10$, what is $x$?",
      "options": ["(A) 3", "(B) 5", "(C) 7"],
      "answer": "B",
      "explanation": "$x = 5$.",
      "src": "home brew · Q1"
    }
  ]
}
```

| Type | Extra fields | `answer` |
|------|----------------|----------|
| `mc` | `options` | `"B"` |
| `multi` | `options` | `["A","C"]` |
| `qc` | `qa`, `qb` (A–D choices filled in) | `"C"` |
| `num` | — | `60` |
| `tc` | `blanks: [{label, options}]` | `["B","A"]` in blank order |
| `se` | six `options` | two letters |
| `rc` | `passage`, `passage_label` | letter or list |

Prompts/explanations may include KaTeX (`$...$`). After Check or Skip, those buttons become **Next** (last item → **Review**). Calculator is hidden on verbal items.

`examples/sample.json` is **original demo copy** written for this repo. Do not add real test-publisher items.

## What this is not

- Not an official GRE, POWERPREP, or ETS product
- Not a question bank and not a scoring service
- Not a pixel-for-pixel reproduction of any ETS asset or logo

Trademarks mentioned here belong to their owners and are used only to describe the kind of practice the shell is for.

## License

MIT. See `LICENSE`.

# gre-ui

Unofficial GRE-style section interface. JSON in, one HTML file out. You supply the questions.

Not affiliated with ETS. Not POWERPREP. Sample items in this repo are original.

<p align="center">
  <img src="docs/screenshots/qc-calc.png" alt="Quant comparison with the on-screen calculator open" width="920">
</p>

## Sample

```bash
git clone https://github.com/boscochanam/gre-ui.git
cd gre-ui
```

Open `examples/sample.html`, or rebuild it:

```bash
python3 scripts/make_quiz.py examples/sample.json examples/sample.html
```

## Build a section

```bash
python3 scripts/make_quiz.py my-section.json out.html
```

To record answers:

```bash
python3 scripts/make_quiz.py my-section.json /tmp/section/index.html
python3 scripts/quiz_server.py 8899 /tmp/section ~/section-results
```

`POST /submit` stores one record per `(quiz_id, client_id)`. Resubmit overwrites. Older attempts stay in `history.jsonl`.

## Screenshots

|  |  |
|--|--|
| ![Text Completion](docs/screenshots/tc.png) | ![Calculator](docs/screenshots/qc-calc.png) |
| ![Reading Comp](docs/screenshots/rc.png) | ![Review](docs/screenshots/review.png) |

<p align="center">
  <img src="docs/screenshots/mobile-tc.png" alt="Text Completion on a phone" width="320">
</p>

Layout: one question at a time, Back / Next / Review. Calculator on Quant only (drag the title bar). After Check or Skip, those buttons become Next (Review on the last question).

Types: `mc`, `multi`, `qc`, `num`, `tc`, `se`, `rc`.

## JSON

```json
{
  "quiz_id": "wk3-algebra",
  "title": "Algebra section",
  "source": "my notes",
  "questions": [
    {
      "type": "qc",
      "prompt": "$n$ is a positive integer.",
      "qa": "$2n + 2$",
      "qb": "$2(n + 1)$",
      "answer": "C",
      "explanation": "Both are $2n+2$."
    }
  ]
}
```

| Type | Extra fields | `answer` |
|------|--------------|----------|
| `mc` | `options` | `"B"` |
| `multi` | `options` | `["A","C"]` |
| `qc` | `qa`, `qb` (A–D filled in) | `"C"` |
| `num` | | `60` |
| `tc` | `blanks: [{label, options}]` | `["B","A"]` in blank order |
| `se` | six `options` | two letters |
| `rc` | `passage`, `passage_label` | letter, or a list for select-all |

KaTeX is allowed in prompts (`$...$`).

## Trademark

GRE® is a trademark of ETS. This is not their software and does not include their questions.

## License

MIT. [LICENSE](LICENSE).

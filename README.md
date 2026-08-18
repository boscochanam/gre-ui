# gre-ui

Practice pages I was using looked like blog posts. The real GRE does not. I wanted the same buttons and layout so I stop wasting a few seconds reorienting every time I switch.

This script reads a JSON file and writes one HTML page. One question on screen. Back, Next, Review. Calculator on Quant (drag the title bar). Text completions as columns, sentence equivalence as six boxes, reading comp with the passage on the left.

You write the questions. I did not include anyone else's.

<p align="center">
  <img src="docs/screenshots/qc-calc.png" alt="Quant comparison with the on-screen calculator open" width="920">
</p>

Unofficial. Not ETS, not POWERPREP, not a scored test.

## Sample

```bash
git clone https://github.com/boscochanam/gre-ui.git
cd gre-ui
```

Open `examples/sample.html`. The items in there are ones I wrote for the demo.

Rebuild it with:

```bash
python3 scripts/make_quiz.py examples/sample.json examples/sample.html
```

## Your own section

```bash
python3 scripts/make_quiz.py my-section.json out.html
```

Put `out.html` wherever you serve static files.

If you want answers saved, use the tiny server:

```bash
python3 scripts/make_quiz.py my-section.json /tmp/section/index.html
python3 scripts/quiz_server.py 8899 /tmp/section ~/section-results
```

It posts to `/submit`. One record per quiz and browser (`quiz_id` + `client_id`). Resubmit overwrites; older attempts stay in `history.jsonl`.

## Screenshots

|  |  |
|--|--|
| ![Text Completion](docs/screenshots/tc.png) | ![Calculator](docs/screenshots/qc-calc.png) |
| ![Reading Comp](docs/screenshots/rc.png) | ![Review](docs/screenshots/review.png) |

Phone:

<p align="center">
  <img src="docs/screenshots/mobile-tc.png" alt="Text Completion on a phone" width="320">
</p>

After you hit Check or Skip, those two buttons go away and you get Next. Last question says Review instead. Calculator stays off on verbal questions.

## JSON

Types: `mc`, `multi`, `qc`, `num`, `tc`, `se`, `rc`.

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
| `qc` | `qa`, `qb` (A–D are filled in for you) | `"C"` |
| `num` | | `60` |
| `tc` | `blanks: [{label, options}]` | `["B","A"]` in blank order |
| `se` | six `options` | two letters |
| `rc` | `passage`, `passage_label` | a letter, or a list if it's select-all |

Math in prompts can be KaTeX (`$...$`).

## Trademark

GRE® belongs to ETS. I'm using the name so people know which screen this is for. This is not their software and it does not ship their questions.

## License

MIT. [LICENSE](LICENSE).


⸻

PRD — Local Japanese Receipt OCR to Excel using YomiToku

0) One line

Batch-process ~700 Japanese PDF receipts on Apple Silicon, extract Date, Amount, Category, Description, and export to Excel with a review queue. All local. OCR by YomiToku.

1) Objective and success
	•	Day-1 goal: End-to-end CLI that ingests a folder of PDFs and produces:
	•	transactions.xlsx with sheet Transactions having exactly 4 columns: Date, Amount, Category, Description.
	•	Review sheet listing items the system was not confident about.
	•	Good enough: You will spot-check 50 receipts. If ≥95 percent of Date and Amount are correct and ≥80 percent of Category are correct, call it a win for v1.

2) Non-goals
	•	No bank or card statement matching.
	•	No accounting journal export.
	•	No line-item breakdown per receipt for v1.
	•	No cloud services.

3) Inputs
	•	Source: a local folder synced from Google Drive. Assume single-page PDFs plus a few multi-page outliers.
	•	Language: ~98 percent Japanese, some English possible.
	•	Handwriting: negligible.
	•	Resolution: unknown. Expect a mix of scans and photographed receipts.

4) Outputs

4.1 Transactions sheet
	•	Date: ISO YYYY-MM-DD. If only 和暦 exists, convert, e.g., 令和6年7月12日 → 2024-07-12.
	•	Amount: grand total 税込 in JPY, no decimals, digits only. If multiple totals exist, pick the value next to keywords like 合計, 総合計, お買上げ, 税込.
	•	Category: one of the following labels, exact spelling:
	•	meetings, entertainment, travel, outsourced fees, communications (phone, internet, postage), Office supplies, Equipment, Professional fees, Other, Utilities, Rent, Advertising, Repairs, Memberships
	•	Description: short free text like 「セブンイレブン」ドリンク他 or JR東日本 交通系. Keep under 60 chars.

4.2 Review sheet
	•	Columns: File, Reason, Suggested Date, Suggested Amount, Suggested Category, Raw Snippet.
	•	Populated when any core field confidence < threshold or parsing conflict detected.
	•	You will manually fix and re-run with a --apply-fixes option later.

4.3 Artifacts
	•	data/ocr_json/ one JSON per receipt with full OCR blocks for debugging.
	•	logs/run.log with progress and warnings.

5) System design

5.1 Pipeline
	1.	Ingest: Walk the input folder. Hash each PDF. Skip duplicates by hash.
	2.	PDF precheck: If embedded text density is high, extract text directly. Else, OCR.
	3.	OCR: Use YomiToku DocumentAnalyzer, device mps on Apple Silicon. Export JSON per page. YomiToku supports pdf, jpeg, png, tiff, layout and table parsing, multiple output formats, and can run offline after initial model download. It recommends short edge ≥1000 px and supports mps/cuda/cpu device flags.  ￼ ￼
	4.	Field extraction:
	•	Date: regex over Japanese date patterns, including 和暦, plus fallback to English month forms.
	•	Amount: pick largest candidate near trigger tokens 合計, 税込合計, 総計. Reject values inside parentheses or clearly marked as 小計 unless no 合計 found.
	•	Description: vendor name + 1 to 2 keywords from near the amount line.
	5.	Categorisation: Hybrid rules:
	•	Dictionary rules in rules/categories.yml mapping vendor tokens and keywords to a category.
	•	Heuristics for common receipts:
	•	JR, 地下鉄, タクシー, 高速, Suica → travel
	•	NTT, ソフトバンク, KDDI, Wi-Fi, インターネット → communications (phone, internet, postage)
	•	アマゾン, Amazon, ヨドバシ, ビックカメラ, 文具 → Office supplies
	•	スターバックス, ドトール, 珈琲館, 喫茶, 居酒屋, レストラン → meetings or entertainment based on presence of 会議/打合せ vs nightlife keywords
	•	外注, 委託, 請負 → outsourced fees
	•	修理, 交換, メンテ → Repairs
	•	会費, 年会費, メンバーシップ → Memberships
	•	広告, Google Ads, Meta, チラシ → Advertising
	•	家賃, 賃料 → Rent
	•	電気, ガス, 水道 → Utilities
	•	Equipment words PC, ノートパソコン, ディスプレイ, プリンタ, 機材 → Equipment
	•	If multiple match or none, mark Other and push to Review.
	6.	Confidence: Compute naive confidence by combining:
	•	OCR block confidence from YomiToku where available.
	•	Regex strength and token distance for date and amount.
	•	Rule hit strength for category.
If any core field < threshold, send to Review.
	7.	Export: Build transactions.xlsx and add pivot sheet if --summary is passed.

5.2 CLI
	•	receipts run --in <folder> --out out/ --device mps --summary
	•	Options:
	•	--device [mps|cpu]
	•	--lite to use YomiToku lite models for speed
	•	--rules rules/categories.yml
	•	--max-workers 4
	•	--combine-pdf if you want per-file combined page parsing
	•	--encoding utf-8-sig when dumping text
YomiToku CLI and API support format selection, lite mode, device selection, combining multi-page PDFs, and various encodings.  ￼ ￼

5.3 Env and install
	•	Python 3.10+, PyTorch with Metal (Apple Silicon).
	•	Install YomiToku
	•	pip install yomitoku
	•	First run downloads model weights from Hugging Face, then it can run offline.  ￼ ￼
	•	License: source is CC BY-NC 4.0 for non-commercial; commercial requires a separate paid license. This internal tool is fine, but do not ship it to clients without clearing licensing.  ￼

5.4 Repo structure

/receipt-ocr
  /rules/categories.yml
  /src
    ocr.py           # YomiToku wrapper
    parse.py         # date, amount, vendor blocks
    classify.py      # rules + heuristics
    review.py        # review queue generator
    export.py        # Excel writer
    cli.py           # click/typer CLI
  /data/ocr_json/
  /out/
  logs/

6) Core logic details

6.1 Date parsing
	•	Patterns:
	•	YYYY年MM月DD日, YYYY/MM/DD, YYYY-MM-DD
	•	和暦: (令和|平成)(\d+)年(\d+)月(\d+)日
	•	Normalise to ISO. Reject impossible dates. If multiple, pick the one nearest any of 発行, 領収, 日付.

6.2 Amount parsing
	•	Extract all numbers with , and 円. Normalise commas. Reject obvious subtotals. Prefer candidates near total tokens.
	•	Negative values: if 返品 or 返金, keep absolute amount and add Description note 返金.
	•	If both 税抜 and 税込 present, choose 税込 as your single Amount field.

6.3 Vendor detection
	•	From header blocks and store name tokens like 株式会社, 有限会社, 店, 支店, 堂, 屋. If none, take top-left largest font line.

6.4 Category rules file

rules/categories.yml example:

travel:
  any: ["JR", "JR東日本", "地下鉄", "タクシー", "高速", "Suica", "Pasmo", "新幹線"]
communications (phone, internet, postage):
  any: ["NTT", "KDDI", "ソフトバンク", "郵便", "切手", "Wi-Fi", "インターネット"]
Office supplies:
  any: ["アマゾン", "Amazon", "ヨドバシ", "ビックカメラ", "文具", "トナー", "コピー用紙"]
Equipment:
  any: ["ノートパソコン", "PC", "Mac", "ディスプレイ", "プリンタ", "機材", "カメラ"]
Advertising:
  any: ["Google Ads", "Facebook Ads", "Meta", "広告", "リスティング", "チラシ"]
...

You can extend this over time.

7) Review workflow
	•	Heuristics for review:
	•	No valid date found or conflicting dates.
	•	Multiple total candidates within 3 percent of each other.
	•	Category unresolved or multiple category hits of equal score.
	•	OCR low confidence region around the amount line.
	•	You’ll correct directly in the Review sheet. A helper script can reapply fixes by filename key.

8) Performance
	•	Process in parallel with a worker pool. For 700 PDFs on M2, plan for 1 to 3 hours in normal mode, faster with --lite but with lower accuracy. YomiToku notes CPU is slower and GPU or MPS is recommended.  ￼

9) Quality gates
	•	Hard fail a receipt if:
	•	No date after all strategies.
	•	No amount token after all strategies.
	•	Write these to Review and continue. Never crash the batch.

10) Observability
	•	Progress bar per file.
	•	For every exception, log file path and stage.
	•	Save YomiToku visualisation images for the first 50 receipts when --debug-vis is set, using its built-in visualise.  ￼

11) Edge cases and mitigations
	•	Text-PDFs vs scanned PDFs: detect embedded text first to avoid unnecessary OCR.
	•	Faded thermal paper: increase contrast and sharpen before OCR; warn if contrast ratio too low.
	•	Vertical text: let YomiToku auto reading order. It allows explicit reading order flags if needed.  ￼
	•	和暦: include mapping tables for 令和, 平成.
	•	Multiple totals on invoices: prefer the last 合計 block on the page. If both 税抜 and 税込 present, pick 税込.
	•	Multi-page PDFs: use --combine to merge page results and then run one extraction pass.  ￼
	•	Licensing drift: do not redistribute. If you later wrap this into a client deliverable, obtain a commercial license.  ￼

12) Dev tasks checklist
	1.	Scaffold
	•	Set up repo, venv, dependencies: pip install yomitoku openpyxl pandas pikepdf pdfminer.six rapidfuzz python-dateutil click
	2.	OCR wrapper
	•	Implement DocumentAnalyzer call with device="mps", export JSON per file.
	3.	PDF text sniff
	•	If pdf_has_text(path) == True, extract text blocks via pdfminer to speed up.
	4.	Parsers
	•	parse_date(text_blocks) with JP and 和暦 regex.
	•	parse_amount(text_blocks) with trigger token proximity.
	•	parse_vendor(text_blocks) heuristics.
	5.	Categoriser
	•	Load rules/categories.yml, fuzzy-match tokens, compute a score, return top category or Other.
	6.	Confidence and review
	•	Score and push to review when uncertain.
	7.	Exporter
	•	Write transactions.xlsx with strict 4 columns.
	•	Append Review sheet with metadata.
	8.	CLI
	•	receipts run --in ./drive/receipts --out ./out --device mps --summary
	9.	Smoke tests
	•	Drop 10 mixed PDFs in samples/, run batch, eyeball the Excel.
	10.	Docs

	•	README.md with setup, known issues, and license reminder.


	•	A --dedupe that uses vendor+date+amount to kill duplicates that slipped through.

⸻



**LLM Prompt Guide: Creating Flashcards for PyAnki CSV (Strict Formatting)**

**Your Goal:**

Analyze the provided lecture notes and generate flashcards as a single CSV file block. The output format **must strictly adhere** to the pattern shown in the "Example Output Row" below.

**Input:**

Lecture notes (text, potentially with slide numbers or other structural information).

**Output:**

A single block of text representing the content of a CSV file.

**Core Task:**

1.  **Identify Key Information:** Extract core concepts, definitions, formulas, key facts, calculation steps/results (from examples), comparisons, etc.
2.  **Formulate Flashcards:** Create clear Question (`front`) / Answer (`back`) pairs for each piece of information.
3.  **Generate CSV Rows:** Format each flashcard into a single CSV row following the strict rules below.

**Formatting Rules (Strict Adherence Required - Match Example EXACTLY):**

1.  **File Encoding:** Ensure output is UTF-8 compatible.
2.  **Header Row:** The first line **must** be exactly:
    ```csv
    front,back,next_review_date,interval_days,ease_factor,lapses,reviews,tags,notes
    ```
3.  **Data Rows (One per Card):** Each subsequent line is one flashcard.
4.  **Delimiter:** Use a single comma (`,`) between fields.
5.  **Field Formatting (CRITICAL - Match Example):**
    *   `front`: **Must** be enclosed in double quotes (`"..."`). Handle internal double quotes by doubling them (`""`).
    *   `back`: **Must** be enclosed in double quotes (`"..."`). Handle internal double quotes (`""`) and use `\n` for intended line breaks within the text.
    *   `next_review_date`: **Must** be empty (resulting in `,,`).
    *   `interval_days`: **Must** be empty (resulting in `,,`).
    *   `ease_factor`: **Must** be the number `2.5` (no quotes).
    *   `lapses`: **Must** be the number `0` (no quotes).
    *   `reviews`: **Must** be the number `0` (no quotes).
    *   `tags`: **Must** be enclosed in double quotes (`"..."`). Separate multiple tags with commas *inside* the quotes.
    *   `notes`: **Must** be enclosed in double quotes (`"..."`).
6.  **Math Notation:** Use LaTeX-style math within single dollar signs (`$ ... $`) inside the quoted `front` or `back` fields.
7.  **Tags Content:** Tags within the quoted `tags` field should be lowercase, comma-separated, using underscores (`_`) for spaces.
8.  **Notes Content:** The quoted `notes` field should reference the source (e.g., slide number).

**Flashcard Content Principles (Very Important!):**

1.  **Atomicity:** One distinct concept per card.
2.  **Clarity:** Unambiguous questions, direct answers.
3.  **Self-Containment (CRITICAL):** Understandable without external reference. Include necessary context/parameters from examples directly on the card. *Avoid* "refer to slide X" type questions.
4.  **Avoid HTML/Unsupported Syntax:** Do not use `<br>` or other HTML. Use `\n` within quoted fields for line breaks.

**Example Output Row (Your output rows MUST follow this pattern):**

```csv
"What is the formula for Reynolds Number ($Re$) for pipe flow?","It is $Re = \frac{\rho v D}{\mu}$, where:\n$\rho$ is density\n$v$ is velocity\n$D$ is diameter\n$\mu$ is dynamic viscosity.",,,2.5,0,0,"fluid_dynamics,pipe_flow,definitions","Slide 12"
```

---

Now, please process the following lecture notes and generate the CSV content according to these **strict** instructions, matching the example format precisely:

[PASTE LECTURE NOTES HERE]
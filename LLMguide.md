

**LLM Prompt Guide: Creating Flashcards for PyAnki CSV (Strict Formatting)**

**Your Goal:**

Analyze the provided lecture notes and generate flashcards as a single CSV file block. The output format **must strictly adhere** to the pattern shown in the "Example Output Row" below. Every generated flashcard must be understandable *on its own*.

**Input:**

Lecture notes (text, potentially with slide numbers or other structural information).

**Output:**

A single block of text representing the content of a CSV file.

**Core Task:**

1.  **Identify Key Information:** Extract core concepts, definitions, formulas, key facts, calculation steps/processes (from examples), comparisons, underlying principles demonstrated by examples, etc.
2.  **Formulate Flashcards:** Create clear Question (`front`) / Answer (`back`) pairs for each piece of information, ensuring **absolute self-containment** (see Principles below).
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
    *   `front`: **Must** be enclosed in double quotes (`"..."`). Handle internal double quotes by doubling them (`""`). **Must contain all necessary context.**
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

**Flashcard Content Principles (ABSOLUTELY CRITICAL!):**

1.  **Atomicity:** One distinct concept, definition, formula, or principle per card.
2.  **Clarity:** Unambiguous questions, direct and complete answers.
3.  **Self-Containment (MANDATORY):** Each flashcard (Question/Answer pair) **must** be fully understandable without referring back to the lecture notes or any other flashcard.
    *   **Context from Examples:** If a question refers to data, parameters, results, or steps from a specific example within the lecture notes, the `front` (question) field **must explicitly embed sufficient context *within the question text itself*** to identify that scenario uniquely. The user must not need to guess or remember the context of "the example".
        *   *Poor (Lacks Context):* `"What is the compressor pressure ratio?"` (If this value was only given within a specific example context).
        *   *Good (Includes Context):* `"For the simple turbojet example operating at M=0.8 and 10km altitude, what was the specified compressor pressure ratio?"`
        *   *Poor (Lacks Context):* `"What was the calculated exit velocity?"`
        *   *Good (Includes Context):* `"For the SLS turbofan example, what was the calculated cold nozzle exit velocity ($C_8$), and what principle/equation was used to find it?"`
4.  **Focus on Concepts, Not Just Numbers:** Avoid creating flashcards where the question *only* asks for a numerical value derived from a specific example. Flashcards should promote understanding of *why* and *how*.
    *   Focus on the underlying concept, definition, formula, comparison, or calculation *process* demonstrated by the example.
    *   If a numerical result from an example is included in the `back` (answer), it should typically support or illustrate the explanation of the concept, formula, or process. The number itself should rarely be the sole focus of the question.
        *   *Poor (Just a Number):* `"What was the total thrust calculated in the SLS turbofan example?"`
        *   *Good (Focus on Process/Formula):* `"What is the formula for total thrust ($F$) for a turbofan with separate nozzles, and what was the resulting value in the SLS turbofan example (given $F_c=52,532 N, F_h=18,931 N$)?` (Answer provides formula *and* result).
        *   *Good (Focus on Concept/Decision):* `"For the SLS turbofan example, was the cold nozzle found to be choked or unchoked? Explain based on its calculated pressure ratio (1.65) vs. critical pressure ratio (1.965)."` (Focuses on the *decision* and *reasoning*).
5.  **Avoid HTML/Unsupported Syntax:** Do not use `<br>` or other HTML. Use `\n` within quoted fields (`front` or `back`) for intended line breaks.
6.  **No External References in Q/A:** Do not include instructions like "Refer to slide X" or "See Lecture 4" *within the `front` or `back` fields*. The `notes` field is for source tracking only.

**Example Output Row (Your output rows MUST follow this pattern precisely):**

```csv
"What is the formula for Reynolds Number ($Re$) for pipe flow, and what do the variables represent?","The formula is $Re = \frac{\rho v D}{\mu}$.\nWhere:\n$\rho$ = fluid density\n$v$ = fluid velocity\n$D$ = characteristic length (e.g., pipe diameter)\n$\mu$ = dynamic viscosity",,,2.5,0,0,"fluid_dynamics,pipe_flow,definitions,formulas","Slide 12"
```
*Self-contained: Defines the formula AND the variables within the card itself.*

---

Now, please process the following lecture notes and generate the CSV content according to these **strict** instructions, matching the example format precisely. Ensure **every single card** adheres to the Self-Containment and Concept Focus principles, especially when dealing with examples. If context cannot be adequately embedded in the question, **do not create the card.**

[PASTE LECTURE NOTES HERE]
# PyAnki - Enhanced SRS + Mgmt

![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Choose your license -->
[![status: active](https://img.shields.io/badge/status-active-success.svg)]() <!-- Or beta, wip, etc. -->

**PyAnki CSV** is a desktop Spaced Repetition System (SRS) application inspired by Anki, but using simple CSV files for deck storage. It features a modern graphical user interface built with CustomTkinter, an SM-2 based algorithm for scheduling reviews, support for LaTeX-style math rendering (using Matplotlib), deck statistics, and card management capabilities.

---

**Note:** This project is not affiliated with the official Anki SRS software. It provides a standalone, CSV-based alternative workflow.

---

## Table of Contents

*   [Screenshots](#screenshots) <!-- Add this section once you have images -->
*   [Key Features](#key-features)
*   [Why PyAnki CSV?](#why-pyanki-csv)
*   [Dependencies](#dependencies)
*   [Installation](#installation)
*   [File Structure](#file-structure)
    *   [Decks Folder](#decks-folder)
    *   [CSV File Format](#csv-file-format)
*   [Usage](#usage)
    *   [Launching the Application](#launching-the-application)
    *   [Loading Decks](#loading-decks)
    *   [Reviewing Cards](#reviewing-cards)
    *   [Managing Cards](#managing-cards)
    *   [Viewing Statistics](#viewing-statistics)
    *   [Keyboard Shortcuts](#keyboard-shortcuts)
    *   [Saving Data](#saving-data)
*   [SRS Algorithm Details](#srs-algorithm-details)
*   [Math Rendering](#math-rendering)
*   [Configuration](#configuration)
*   [Contributing](#contributing)
*   [License](#license)
*   [Acknowledgements](#acknowledgements)

---

## Screenshots

*(Please add screenshots of your application here! Showing the main review window, the card browser, and the statistics window would be very helpful for users.)*

*Example:*
*   `(Image: Main review interface)`
*   `(Image: Card Management / Browser window)`
*   `(Image: Statistics window with plot)`

---

## Key Features

*   **CSV-Based:** Uses simple, human-readable `.csv` files to store flashcard decks. Easy to edit externally if needed.
*   **Modern GUI:** Clean and responsive user interface using the [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) library. Adapts to system light/dark modes.
*   **Spaced Repetition System (SRS):** Implements an SM-2 algorithm variant to schedule card reviews efficiently based on recall difficulty.
*   **Math Rendering:** Supports rendering LaTeX-style mathematical notation within card text using Matplotlib's `mathtext` (requires Matplotlib and Pillow). Use `$...$` for math expressions (e.g., `What is $E=mc^2$?`).
*   **Card Management:** Browse, search, add, edit, and delete cards across loaded decks via a dedicated management window.
*   **Deck Statistics:** View detailed statistics about your decks, including card counts (new, learning, mature), review forecasts, interval/ease distribution, and review history (requires Matplotlib for plotting).
*   **Multi-Deck Loading:** Load and review cards from multiple decks simultaneously.
*   **Cross-Platform:** Should run on Windows, macOS, and Linux where Python and the required libraries are installed.

---

## Why PyAnki CSV?

This project was created for users who:

*   Prefer the simplicity and portability of CSV files over database formats.
*   Want a standalone desktop SRS application without needing external services.
*   Need basic math rendering capabilities within their flashcards.
*   Appreciate a modern, theme-aware user interface.

It offers core SRS functionality with useful management tools in a self-contained Python script.

---

## Dependencies

*   **Python:** 3.7+
*   **CustomTkinter:** For the graphical user interface.
*   **Pillow (PIL Fork):** **Optional, but required for Math Rendering.** Used to process images generated by Matplotlib.
*   **Matplotlib:** **Optional, but required for Math Rendering and Statistics Plotting.** Used for rendering math equations and plotting forecast graphs.

---

## Installation

1.  **Clone or Download:** Get the project files:
    ```bash
    git clone https://github.com/FreddyCharles/PyAnki.git # Replace with your repo URL
    cd PyAnki
    ```
    Alternatively, download the `PyAnki.py` script directly.

2.  **Install Dependencies:**
    *   **Required:**
        ```bash
        pip install customtkinter
        ```
    *   **Optional (for Math Rendering & Stats Plotting):**
        ```bash
        pip install Pillow matplotlib
        ```
    *(Note: On some systems, you might need `pip3` instead of `pip`)*

3.  **Prepare Decks:** Create a folder named `decks` in the same directory as `PyAnki.py`. Place your `.csv` deck files inside this folder (see [CSV File Format](#csv-file-format)). If the `decks` folder doesn't exist, the application will create it with an `example_deck.csv` file on first run.

---

## File Structure

```
PyAnki-CSV/
│
├── PyAnki.py           # The main application script
│
├── decks/              # Folder containing your CSV deck files
│   ├── deck1.csv
│   ├── another_deck.csv
│   └── example_deck.csv # Created automatically if folder is missing
│
└── README.md           # This file
```

### Decks Folder

*   The application looks for `.csv` files exclusively within the `decks` subfolder, located in the same directory as `PyAnki.py`.
*   Each `.csv` file in this folder represents a single deck.
*   Create this folder manually or let the application create it on the first run (it will add an `example_deck.csv`).

### CSV File Format

Understanding the CSV format is key to creating decks compatible with PyAnki CSV, especially if you plan to edit them outside the application (e.g., in a spreadsheet program or text editor). Each `.csv` file represents one deck.

**1. File Encoding:**

*   **Save your CSV files using UTF-8 encoding.** This is crucial for handling special characters, accents, and non-English text correctly.
*   Most modern text editors and spreadsheet programs allow you to specify the encoding when saving. Choose "UTF-8".
*   *(Note: The application reads using `utf-8-sig` to handle potential Byte Order Marks (BOM) sometimes added by programs like Excel, but saves using standard `utf-8`)*.

**2. Header Row:**

*   The **very first line** of your CSV file **must** be a header row containing column names separated by commas.
*   **Headers are case-sensitive.** They must match the names listed below exactly.
*   **Required Columns (Must be present):**
    *   `front`: The text content displayed on the front of the flashcard.
    *   `back`: The text content displayed on the back of the flashcard.
    *   `next_review_date`: The date the card is next scheduled for review (Format: `YYYY-MM-DD`). Leave empty for new cards.
    *   `interval_days`: The number of days between the last review and the `next_review_date`. Use `0.0` or leave empty for new cards.
*   **Optional SRS Columns (Managed by the App):** These columns store the spaced repetition data.
    *   `ease_factor`: A number (usually starting around 2.5) representing how easy the card is. Lower means harder. Default: `2.5`.
    *   `lapses`: An integer counting how many times you've rated the card 'Again'. Default: `0`.
    *   `reviews`: An integer counting the total number of successful reviews (Hard, Good, Easy). Default: `0`.
    *   **Behavior:**
        *   If these columns **exist** in your header, the application will read their values.
        *   If they **do not exist**, the application will use default values internally (e.g., 2.5 ease, 0 lapses/reviews for new cards) and **will add these columns to the header** the next time the file is saved by the application.
*   **Extra Columns (Preserved):**
    *   You can include any other columns you like (e.g., `tags`, `notes`, `source`).
    *   The application will ignore these columns for its core logic but will **preserve them** when reading and saving the file. This is useful for adding your own metadata.

**3. Data Rows (One Row Per Card):**

*   Each row after the header represents a single flashcard.
*   The order of columns in the data rows must match the order defined in your header row.

**4. Column Data Formatting:**

*   **`front` / `back`:**
    *   Plain text content for the card faces.
    *   To include math notation, use LaTeX syntax enclosed in single dollar signs: `$E = mc^2$`. See [Math Rendering](#math-rendering) for details and limitations.
    *   If your text contains commas, newlines, or double quotes, it **must** be enclosed in double quotes (`"`). Spreadsheet programs usually handle this automatically.
        *   Example: `"This field contains a comma, and spans\ntwo lines."`
        *   To include a literal double quote inside a quoted field, double it up: `"He said, ""Hello""."`
*   **`next_review_date`:**
    *   Must be in **`YYYY-MM-DD`** format (e.g., `2024-03-15`).
    *   For **new cards**, leave this field **empty**. The application will treat it as due immediately (today).
    *   If the format is invalid, the application will also treat the card as due immediately.
*   **`interval_days`:**
    *   A number representing the current review interval in days (can be a decimal, e.g., `3.5`).
    *   For **new cards**, use `0`, `0.0`, or leave it **empty**.
*   **`ease_factor`:**
    *   A number (float, e.g., `2.5`, `1.95`).
    *   If omitted for a new card or invalid, the default (`2.5`) will be used internally and saved later.
*   **`lapses` / `reviews`:**
    *   Whole numbers (integers, e.g., `0`, `1`, `5`).
    *   If omitted for a new card or invalid, `0` will be used internally and saved later.
*   **Extra Columns:**
    *   Enter data as needed (e.g., `study_notes`, `lecture_1, concept_x`). Remember quoting rules if using commas within a tag list.

**5. Important Notes & Common Issues:**

*   **Encoding:** Always use **UTF-8**.
*   **Headers:** Required headers (`front`, `back`, `next_review_date`, `interval_days`) **must** be present and spelled correctly (case-sensitive).
*   **Empty Rows:** Blank lines in the CSV file might be skipped or cause issues. Ensure each card has its own row.
*   **Missing `front`/`back`:** Rows without content in the `front` or `back` columns will likely be skipped.
*   **Spreadsheet Software:** Programs like Excel, Google Sheets, or LibreOffice Calc are convenient for editing CSVs. Be sure to:
    *   Select "CSV (Comma delimited) (*.csv)" as the file type when saving.
    *   Verify UTF-8 encoding is selected in the save options.
    *   Be careful that the software doesn't automatically change date formats or number formats in ways incompatible with the application. Set date columns to `YYYY-MM-DD` format explicitly if possible.
*   **Text Editors:** When using a plain text editor, manually ensure commas separate fields and use double quotes (`"..."`) around fields containing commas, newlines, or double quotes themselves.
*   **Tips for making Flashcards:** Dont refer to any specific examples or pictures without giving the full relevent information in that specific card. If refering to an example question make sure to give the full question for each flashcard refering to it otherwise don't refer to it.
*   **Extra info:** Make sure not to use any extra/unnecessary syntax like breaklines

**Example `my_deck.csv`:**

```csv
front,back,next_review_date,interval_days,notes,tags,ease_factor,lapses,reviews
"What is the main objective of the MEC345 worked example?","To determine the specific thrust ($F_s$) and Specific Fuel Consumption (SFC) for a simple turbojet engine at cruise conditions ($M_a=0.8$, altitude = 10,000m).","","","Slide 2","turbojet_example,objective",2.5,0,0
"What are the main components of the turbojet engine analyzed in the MEC345 example?","Inlet, Compressor, Combustor (Combustion Chamber), Turbine, Nozzle.","","","Slide 3, 5","turbojet_example,components",2.5,0,0
"What are the specified cruise conditions for the MEC345 turbojet example?","Mach number $M_a = 0.8$ <br> Altitude = 10,000m","","","Slide 2, 4","turbojet_example,parameters,conditions",2.5,0,0
```

By following these guidelines, you can reliably create and manage your flashcard decks for use with PyAnki CSV.

---

## Usage

### Launching the Application

Run the script from your terminal:

```bash
python PyAnki.py
```

*(Or `python3 PyAnki.py` depending on your system setup)*

### Loading Decks

1.  The main window displays a list of `.csv` files found in the `decks` folder.
2.  Select one or more decks from the list (use `Ctrl+Click` or `Shift+Click` for multiple selections).
3.  Click the **"Load Selected Deck(s)"** button.
4.  The application will load the cards and present the first due card for review (if any).

### Reviewing Cards

1.  The **front** of the current due card is displayed.
2.  Click the **"Show Answer (Space/Enter)"** button or press `Spacebar` / `Enter` to reveal the back of the card.
3.  The **back** of the card is shown, along with four rating buttons:
    *   **Again (1):** You failed to recall the answer. The card will be shown again soon in the current session, and its ease factor decreases.
    *   **Hard (2):** You recalled the answer, but with significant difficulty. The interval increases slightly, and ease may decrease.
    *   **Good (3 / Space / Enter):** You recalled the answer correctly. The interval increases based on the current ease factor. (Default action for `Space`/`Enter` after showing answer).
    *   **Easy (4):** You recalled the answer very easily. The interval increases significantly, and the ease factor increases.
4.  Click the button or press the corresponding number key (`1`, `2`, `3`, `4`) that best reflects your recall difficulty.
5.  The application updates the card's schedule and shows the next due card.
6.  The process repeats until all due cards for the session are reviewed.

### Managing Cards

Click the **"Manage Cards"** button (enabled after loading a deck) to open the Card Browser window. Here you can:

*   **View All Cards:** See all cards from the currently loaded deck(s) in a sortable table.
*   **Search:** Filter cards by typing in the search box (searches Front and Back fields).
*   **Sort:** Click column headers to sort cards by Deck, Front, Back, Next Review, Interval, etc.
*   **Add Card (A):** Click "Add New Card" to open a window to add a new card to the *first* loaded deck.
*   **Edit Card:** Select a *single* card and click "Edit Selected" to modify its Front and Back content.
*   **Delete Card(s):** Select one or more cards and click "Delete Selected" (confirmation required).

### Viewing Statistics

Click the **"Stats"** button (enabled after loading a deck) to open the Statistics window. This shows:

*   **Deck Overview:** Total cards, breakdown by state (New, Learning, Young, Mature).
*   **Scheduling:** Cards due Today, Tomorrow, and in the next 7 days.
*   **Intervals:** Average and longest intervals.
*   **Ease:** Average ease factor and distribution.
*   **Review History:** Total reviews, lapses, averages per card.
*   **Forecast Plot:** A graph showing the number of cards due each day for the next 30 days (requires Matplotlib).

### Keyboard Shortcuts

*   **Review Screen:**
    *   `Space` or `Enter`: Show Answer / Rate as "Good" (3)
    *   `1`: Rate as "Again"
    *   `2`: Rate as "Hard"
    *   `3`: Rate as "Good"
    *   `4`: Rate as "Easy"
*   **Main Window:**
    *   `A`: Open Add Card window (if a deck is loaded).
*   **Pop-up Windows (Add, Edit, Stats, Manage):**
    *   `Escape`: Close the current pop-up window.
    *   `Enter`: Often confirms the default action (e.g., Add Card, Save Changes).

### Saving Data

*   Card review progress (updated `next_review_date`, `interval_days`, `ease_factor`, etc.) is marked internally as needing saving.
*   Changes are automatically saved to the corresponding CSV file(s) when:
    *   You load *different* deck(s).
    *   You close the application.
    *   You add, edit, or delete cards via the Manage Cards window.
*   If cards are deleted, the entire corresponding CSV file is rewritten to remove them. Otherwise, only modified cards trigger a save, usually updating the file in place.

**Recommendation:** While the app saves automatically, it's always wise to back up your `decks` folder periodically.

---

## SRS Algorithm Details

The scheduling algorithm is inspired by SM-2, using Ease Factors and Intervals:

*   **New Cards:** Start with an interval of 0 and the `DEFAULT_EASE_FACTOR` (2.5). First 'Good' rating gives `INITIAL_INTERVAL_DAYS` (1 day). 'Easy' gives 4 days.
*   **Ease Factor:** Represents card difficulty. Starts at 2.5.
    *   Decreases significantly for 'Again' (`EASE_MODIFIER_AGAIN`).
    *   Decreases slightly for 'Hard' (`EASE_MODIFIER_HARD`).
    *   Increases for 'Easy' (`EASE_MODIFIER_EASY`).
    *   Stays the same for 'Good'.
    *   Has a minimum value (`MINIMUM_EASE_FACTOR`, 1.3).
*   **Interval:** The time (in days) until the next review.
    *   Calculated roughly as `Previous Interval * Ease Factor`.
    *   'Hard' reviews use a smaller multiplier (`INTERVAL_MODIFIER_HARD`).
    *   'Easy' reviews get an additional bonus multiplier (`INTERVAL_MODIFIER_EASY_BONUS`).
    *   Intervals generally increase with each successful review (except potentially 'Hard').
    *   Has a minimum value after review (`MINIMUM_INTERVAL_DAYS`, 1 day).
*   **Lapses ('Again'):**
    *   Increases the lapse count.
    *   Reduces the ease factor.
    *   Resets the interval based on `LAPSE_INTERVAL_FACTOR` or `LAPSE_NEW_INTERVAL_DAYS` (defaults to 1 day).

The specific parameters controlling this behaviour can be found in the [Configuration](#configuration) section at the top of `PyAnki.py`.

---

## Math Rendering

*   Requires `Pillow` and `Matplotlib` to be installed.
*   Enclose LaTeX-style math expressions within single dollar signs (`$...$`).
    *   Example: `The formula is $E = mc^2$.`
*   The application uses Matplotlib's `mathtext` engine to render the expression as an image, which is then displayed in the card label.
*   Complex layouts or unsupported LaTeX commands might not render correctly. Basic mathematical symbols, fractions, superscripts, subscripts, Greek letters, etc., are generally supported.
*   If rendering fails, an error message might be printed to the console, and the original text (with `$`) will be shown on the card with a "[Math Render Error]" prefix.
*   The rendering resolution can be adjusted via the `MATH_RENDER_DPI` constant.

---

## Configuration

Several parameters controlling the application's behaviour are defined as constants near the top of the `PyAnki.py` script:

*   `DATE_FORMAT`: String format for dates in CSV ("%Y-%m-%d").
*   `DECKS_DIR`: Name of the subdirectory containing CSV decks ("decks").
*   `INITIAL_INTERVAL_DAYS`: Interval after the first 'Good' rating on a new card (1.0).
*   `MINIMUM_INTERVAL_DAYS`: Smallest interval allowed after a successful review (1.0).
*   `STATS_FORECAST_DAYS`: Number of days shown in the statistics forecast plot (30).
*   `MATH_RENDER_DPI`: Resolution for rendered math images (150).
*   **SRS Parameters:**
    *   `DEFAULT_EASE_FACTOR` (2.5)
    *   `MINIMUM_EASE_FACTOR` (1.3)
    *   `EASE_MODIFIER_AGAIN` (-0.20)
    *   `EASE_MODIFIER_HARD` (-0.15)
    *   `EASE_MODIFIER_EASY` (+0.15)
    *   `INTERVAL_MODIFIER_HARD` (1.2)
    *   `INTERVAL_MODIFIER_EASY_BONUS` (1.3)
    *   `LAPSE_INTERVAL_FACTOR` (0.0) - Multiplier for lapsed interval (0 uses `LAPSE_NEW_INTERVAL_DAYS`).
    *   `LAPSE_NEW_INTERVAL_DAYS` (1.0) - Fixed interval after lapse if factor is 0.

**Caution:** Modifying SRS parameters can significantly affect scheduling. Do so only if you understand the implications.

---

## Contributing

Contributions are welcome! If you'd like to contribute, please consider:

1.  **Reporting Bugs:** Open an issue detailing the problem, including steps to reproduce it.
2.  **Suggesting Features:** Open an issue to discuss new ideas.
3.  **Submitting Pull Requests:**
    *   Fork the repository.
    *   Create a new branch for your feature or bug fix (`git checkout -b feature/your-feature-name`).
    *   Make your changes.
    *   Ensure your code is clean and follows a similar style.
    *   Test your changes thoroughly.
    *   Commit your changes (`git commit -m 'Add some feature'`).
    *   Push to the branch (`git push origin feature/your-feature-name`).
    *   Open a Pull Request.

---

## License

This project is licensed under the [MIT License](LICENSE.txt) <!-- Create a LICENSE.txt file with the MIT license text -->. See the `LICENSE.txt` file for details.

---

## Acknowledgements

*   [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the excellent modern Tkinter widgets.
*   [Matplotlib](https://matplotlib.org/) for plotting and math text rendering.
*   [Pillow](https://python-pillow.org/) for image handling.
*   The developers of the original [Anki](https://apps.ankiweb.net/) SRS for the inspiration and the SM-2 algorithm concept.

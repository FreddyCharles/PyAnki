# PyAnki CSV - Simple Flashcard Review App

A graphical flashcard application built with Python and CustomTkinter. It uses CSV files to manage decks and implements a basic Spaced Repetition System (SRS) for scheduling reviews, inspired by Anki.

## Features

*   **GUI Interface:** Modern-looking interface using CustomTkinter.
*   **CSV-Based Decks:** Stores flashcard decks as simple `.csv` files.
*   **Deck Management:** Automatically finds `.csv` decks in a `decks` folder. Allows selecting and reloading decks.
*   **Spaced Repetition System (SRS):** Implements a basic SRS algorithm to schedule card reviews based on user feedback (Again, Hard, Good, Easy).
*   **Due Card Review:** Only shows cards that are scheduled for review today or are overdue.
*   **Card Adding:** Allows adding new cards to the currently selected deck via a simple dialog.
*   **Automatic Saving:** Saves review progress and new cards automatically to the CSV file.
*   **Error Handling:** Provides feedback for common issues like missing files, incorrect CSV formats, or directory errors.

## Screenshots

*(Consider adding screenshots of the main window and the 'Add Card' dialog here if possible)*

**Main Window:**
[Image Placeholder: Description of the main window showing deck selection, card display area, and control buttons]

**Add Card Dialog:**
[Image Placeholder: Description of the 'Add New Card' pop-up window]

## Requirements

*   **Python:** Version 3.7 or higher recommended (due to type hints and f-strings).
*   **CustomTkinter:** The library used for the GUI.
*   **Standard Libraries:** `csv`, `datetime`, `random`, `os`, `sys`, `tkinter` (Tkinter base is usually included with Python).

## Installation

1.  **Clone or Download:** Get the Python script (`your_script_name.py` - replace with the actual filename).
2.  **Install CustomTkinter:** Open your terminal or command prompt and run:
    ```bash
    pip install customtkinter
    ```
3.  **Create Decks Folder:** The script expects flashcard decks (as `.csv` files) to be inside a folder named `decks` located in the *same directory* as the script. If the `decks` folder doesn't exist when you first run the script, it will attempt to create it.

## CSV File Format

Your flashcard decks must be saved as `.csv` files inside the `decks` directory. Each CSV file represents one deck.

**Required Columns:**

The CSV file **must** have at least the following columns in the header row:

1.  `front`: The text to display on the front of the card.
2.  `back`: The text to display on the back of the card.
3.  `next_review_date`: The date the card is scheduled for review next.
    *   Format: **YYYY-MM-DD** (e.g., `2023-10-27`). This format is defined by `DATE_FORMAT` in the script.
    *   An empty value or an invalid date format means the card is due immediately.
4.  `interval_days`: A number (float) representing the current interval (in days) before the card should be shown again after a successful review ('Good' or 'Easy').
    *   An empty value or an invalid number will default to `INITIAL_INTERVAL_DAYS` (usually 1.0).

**Example `my_deck.csv`:**

```csv
front,back,next_review_date,interval_days,notes,tags
"Capital of France","Paris",2023-11-05,4.5,"Geography","Europe capitals"
"print() function","Outputs text to the console",2023-10-26,1.0,"Python Basics","programming python built-in"
"What is H2O?","Water","",1.0,"Chemistry","basic science"
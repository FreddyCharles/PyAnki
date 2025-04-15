# PyAnki.py
# --- START OF FILE PyAnki.py ---

import csv
import datetime
import random
import os
import sys
import tkinter as tk # Base tkinter for listbox & messagebox
from tkinter import messagebox # For showing errors/info
import customtkinter as ctk # Use CustomTkinter for modern widgets
from typing import List, Dict, Any, Optional, Tuple

# --- Configuration ---
DATE_FORMAT = "%Y-%m-%d"
DECKS_DIR = "decks"
APP_NAME = "PyAnki CSV - MultiDeck"
INITIAL_INTERVAL_DAYS = 1.0
MINIMUM_INTERVAL_DAYS = 1.0

# --- Core Logic Functions ---

def parse_date(date_str: str) -> Optional[datetime.date]:
    """Safely parses a date string into a date object."""
    if not date_str: return None
    try:
        return datetime.datetime.strptime(date_str.strip(), DATE_FORMAT).date()
    except ValueError:
        print(f"Warning: Invalid date format '{date_str}'. Treating as due.")
        return None

def parse_interval(interval_str: str) -> float:
    """Safely parses an interval string into a float."""
    if not interval_str: return INITIAL_INTERVAL_DAYS
    try:
        interval = float(interval_str.strip())
        return max(MINIMUM_INTERVAL_DAYS, interval)
    except ValueError:
        print(f"Warning: Invalid interval '{interval_str}'. Using default {INITIAL_INTERVAL_DAYS} days.")
        return INITIAL_INTERVAL_DAYS

def load_deck(filepath: str) -> List[Dict[str, Any]]:
    """Loads flashcards from a specific CSV file path.
       Returns a list of card dictionaries WITHOUT the filepath attribute.
    """
    deck: List[Dict[str, Any]] = []
    if not os.path.exists(filepath):
        # Error handled by caller now for context
        return []

    required_columns = {'front', 'back', 'next_review_date', 'interval_days'}
    line_num = 1

    try:
        with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames:
                 messagebox.showerror("Error", f"CSV file '{os.path.basename(filepath)}' appears to be empty or has no header.")
                 return [] # Indicate failure
            if not required_columns.issubset(reader.fieldnames):
                missing = required_columns - set(reader.fieldnames)
                messagebox.showerror("Error", f"CSV file '{os.path.basename(filepath)}' is missing required columns: {', '.join(missing)}")
                return [] # Indicate failure

            extra_fieldnames = list(reader.fieldnames) # Preserve for adding back

            for i, row in enumerate(reader):
                line_num = i + 2
                try:
                    front = row.get('front', '').strip()
                    back = row.get('back', '').strip()
                    if not front or not back:
                         print(f"Warning: Skipping row {line_num} in '{os.path.basename(filepath)}' due to missing front or back.")
                         continue

                    next_review_date = parse_date(row.get('next_review_date', ''))
                    interval_days = parse_interval(row.get('interval_days', ''))

                    card = {
                        'front': front, 'back': back,
                        'next_review_date': next_review_date, 'interval_days': interval_days,
                        'original_row_index': line_num, '_dirty': False
                        # Filepath added by caller
                    }
                    # Preserve any extra columns
                    for field in extra_fieldnames:
                        if field not in card and field in row:
                             card[field] = row[field]

                    deck.append(card)
                except Exception as e:
                    print(f"Warning: Error processing row {line_num} in '{os.path.basename(filepath)}': {e}")

    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred while reading '{os.path.basename(filepath)}': {e}")
        return [] # Indicate failure

    return deck

def save_deck(filepath: str, deck_to_save: List[Dict[str, Any]]):
    """Saves the provided list of cards back to the specified CSV file path."""
    # Check if any card in this specific subset needs saving
    if not any(card.get('_dirty', False) for card in deck_to_save):
         print(f"Info: No dirty cards found for '{os.path.basename(filepath)}'. Skipping save.")
         return # Nothing to save for this specific file

    # Determine fieldnames: Prioritize existing header if file exists
    fieldnames = ['front', 'back', 'next_review_date', 'interval_days'] # Core fields
    all_keys = set(fieldnames)
    for card in deck_to_save:
        all_keys.update(card.keys())
    # Define a sensible default order, putting core fields first
    potential_fieldnames = fieldnames + sorted([k for k in all_keys if k not in fieldnames and not k.startswith('_') and k != 'deck_filepath' and k != 'original_row_index']) # Exclude internal fields

    try:
        if os.path.exists(filepath):
            with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)
                if header: # Use existing header if valid
                     # Simple validation: check if core fields are present
                     if all(field in header for field in ['front', 'back', 'next_review_date', 'interval_days']):
                         fieldnames = header
                     else:
                          print(f"Warning: Existing header in '{filepath}' missing core fields. Using inferred fields.")
                          fieldnames = potential_fieldnames
                else: # Empty file or no header row
                     print(f"Warning: No header found in '{filepath}'. Using inferred fields.")
                     fieldnames = potential_fieldnames

        else: # File doesn't exist, create with inferred fields
             print(f"Info: File '{filepath}' doesn't exist yet. Will create with inferred header.")
             fieldnames = potential_fieldnames

    except Exception as e:
        print(f"Info: Could not read existing header from '{filepath}'. Using inferred fields for saving. Error: {e}")
        fieldnames = potential_fieldnames


    try:
        with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
            # Ensure fieldnames don't include our internal helper fields unless they were somehow in the original file
            fieldnames_for_write = [f for f in fieldnames if f not in ['_dirty', 'deck_filepath', 'original_row_index'] or f in potential_fieldnames]
            # Make sure core fields are definitely included if missing from potential_fieldnames somehow
            core_fields = ['front', 'back', 'next_review_date', 'interval_days']
            for cf in reversed(core_fields): # Insert at beginning if missing
                if cf not in fieldnames_for_write:
                    fieldnames_for_write.insert(0, cf)

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames_for_write, extrasaction='ignore')
            writer.writeheader()
            for card in deck_to_save:
                # Prepare row data for writing
                row_to_write = card.copy() # Start with all data from the card
                # Format specific fields
                row_to_write['next_review_date'] = row_to_write.get('next_review_date').strftime(DATE_FORMAT) if row_to_write.get('next_review_date') else ''
                row_to_write['interval_days'] = str(round(row_to_write.get('interval_days', INITIAL_INTERVAL_DAYS), 2))

                # DictWriter with extrasaction='ignore' handles extra fields in row_to_write
                writer.writerow(row_to_write)

                # Reset dirty flag after successful write attempt for this card
                # This modifies the card object that might also be in the main self.deck_data list
                if '_dirty' in card:
                    card['_dirty'] = False

    except IOError as e:
        messagebox.showerror("Save Error", f"Could not write to file '{os.path.basename(filepath)}': {e}")
    except Exception as e:
        messagebox.showerror("Save Error", f"An unexpected error occurred while saving '{os.path.basename(filepath)}': {e}")


def get_due_cards(deck: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters the deck (potentially combined) to find cards due for review today."""
    today = datetime.date.today()
    return [card for card in deck if card.get('next_review_date') is None or card.get('next_review_date') <= today]

def update_card_schedule(card: Dict[str, Any], quality: int):
    """Updates the card's interval and next review date based on recall quality."""
    AGAIN_INTERVAL_DAYS = 1.0; HARD_FACTOR = 1.2; GOOD_FACTOR = 2.5; EASY_FACTOR = 4.0

    today = datetime.date.today()
    current_interval = card.get('interval_days', INITIAL_INTERVAL_DAYS)
    new_interval = current_interval
    days_to_add = 0

    if quality == 1: # Again
        new_interval = INITIAL_INTERVAL_DAYS; days_to_add = 1
    elif quality == 2: # Hard
        new_interval = max(MINIMUM_INTERVAL_DAYS, current_interval * HARD_FACTOR); days_to_add = round(new_interval)
    elif quality == 3: # Good
        new_interval = max(MINIMUM_INTERVAL_DAYS, current_interval * GOOD_FACTOR); days_to_add = round(new_interval)
    elif quality == 4: # Easy
        good_days = round(max(MINIMUM_INTERVAL_DAYS, current_interval * GOOD_FACTOR))
        new_interval = max(MINIMUM_INTERVAL_DAYS, current_interval * EASY_FACTOR);
        days_to_add = max(good_days + 1, round(new_interval))
    else: return

    next_review_date = today + datetime.timedelta(days=days_to_add)

    # Check if update actually changed anything before marking dirty
    old_interval = card.get('interval_days')
    old_date = card.get('next_review_date')

    if old_interval != new_interval or old_date != next_review_date:
        card['interval_days'] = new_interval
        card['next_review_date'] = next_review_date
        card['_dirty'] = True # Mark dirty ONLY if something changed


def find_decks(decks_dir: str) -> List[str]:
    """Finds all .csv files in the specified directory, creates dir if needed."""
    if not os.path.isdir(decks_dir):
        try:
            os.makedirs(decks_dir)
            print(f"Created decks directory: '{decks_dir}'")
            return []
        except OSError as e:
            messagebox.showerror("Error", f"Could not create directory '{decks_dir}': {e}")
            return []
    try:
        csv_files = [f for f in os.listdir(decks_dir)
                     if os.path.isfile(os.path.join(decks_dir, f)) and f.lower().endswith('.csv')]
        return sorted(csv_files)
    except OSError as e:
        messagebox.showerror("Error", f"Error accessing decks directory '{decks_dir}': {e}")
        return []

# --- Statistics Calculation ---
def calculate_deck_statistics(deck_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates various statistics for the provided deck data."""
    stats = {
        "total_cards": 0,
        "due_today": 0,
        "due_tomorrow": 0,
        "due_next_7_days": 0,
        "new_cards": 0,
        "learning_review_cards": 0,
        "average_interval": 0.0,
    }
    if not deck_data:
        return stats

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    next_week = today + datetime.timedelta(days=7)
    total_interval = 0.0
    review_card_count = 0 # Count only cards with an interval for averaging

    stats["total_cards"] = len(deck_data)

    for card in deck_data:
        review_date = card.get('next_review_date')
        interval = card.get('interval_days', INITIAL_INTERVAL_DAYS)

        # New Cards
        if review_date is None or interval == INITIAL_INTERVAL_DAYS: # Consider cards with initial interval as new too
            stats["new_cards"] += 1
            stats["due_today"] += 1 # New cards are due today
        else:
            # Learning/Review Cards
            stats["learning_review_cards"] += 1
            total_interval += interval
            review_card_count += 1

            # Due Counts
            if review_date <= today:
                stats["due_today"] += 1
            if review_date == tomorrow:
                stats["due_tomorrow"] += 1
            if today < review_date <= next_week: # Due after today but within 7 days
                stats["due_next_7_days"] += 1

    # Calculate Average Interval
    if review_card_count > 0:
        stats["average_interval"] = round(total_interval / review_card_count, 2)
    else:
        stats["average_interval"] = 0.0 # Avoid division by zero

    return stats


# --- GUI Application Class ---

class FlashcardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("700x650") # Increased height slightly for stats button
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Data Attributes ---
        self.decks_dir = DECKS_DIR
        self.available_decks: List[str] = [] # List of filenames (e.g., "deck1.csv")
        self.current_deck_paths: List[str] = [] # List of full paths being studied
        self.deck_data: List[Dict[str, Any]] = [] # Combined data from loaded decks
        self.due_cards: List[Dict[str, Any]] = []
        self.current_card_index: int = -1
        self.showing_answer: bool = False
        self.add_card_window: Optional[ctk.CTkToplevel] = None
        self.settings_window: Optional[ctk.CTkToplevel] = None
        self.stats_window: Optional[ctk.CTkToplevel] = None # Added for stats
        self._is_review_active: bool = False

        # --- UI Elements ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Top Frame: Deck Selection
        self.top_frame = ctk.CTkFrame(self.main_frame)
        self.top_frame.pack(pady=(5,10), padx=10, fill="x")

        self.deck_label = ctk.CTkLabel(self.top_frame, text="Available Decks (Ctrl/Shift+Click):")
        self.deck_label.pack(side="top", padx=5, pady=(0,5), anchor="w")

        # Use standard Tkinter Listbox for multi-select
        self.deck_listbox = tk.Listbox(self.top_frame, selectmode=tk.EXTENDED,
                                       height=5, exportselection=False, # Crucial for multiple listboxes
                                       # Basic styling (can be customized further if needed)
                                       bg="#2B2B2B", fg="#DCE4EE", # Example dark theme colors
                                       selectbackground="#1F6AA5", selectforeground="white",
                                       borderwidth=0, highlightthickness=1,
                                       highlightbackground="#565B5E",
                                       highlightcolor="#1F6AA5")
        self.deck_listbox.pack(side="top", fill="x", expand=True, padx=5)

        # Frame for Load/Reload buttons
        self.deck_button_frame = ctk.CTkFrame(self.top_frame)
        self.deck_button_frame.pack(side="top", fill="x", pady=(5,0), padx=5)

        self.load_button = ctk.CTkButton(self.deck_button_frame, text="Load Selected Deck(s)", command=self.load_selected_decks)
        self.load_button.pack(side="left", padx=(0,5))

        self.reload_decks_button = ctk.CTkButton(self.deck_button_frame, text="Reload List", width=100, command=self.populate_deck_listbox)
        self.reload_decks_button.pack(side="left", padx=5)

        self.add_card_button = ctk.CTkButton(self.deck_button_frame, text="Add (A)", width=80, command=self.open_add_card_window, state="disabled")
        self.add_card_button.pack(side="left", padx=(10, 0))

        self.settings_button = ctk.CTkButton(self.deck_button_frame, text="Settings", width=80, command=self.open_settings_window, state="disabled")
        self.settings_button.pack(side="left", padx=(5, 0)) # Adjusted padding

        self.stats_button = ctk.CTkButton(self.deck_button_frame, text="Stats", width=80, command=self.open_stats_window, state="disabled") # Added Stats button
        self.stats_button.pack(side="left", padx=(5, 0))


        # Card Display Frame
        self.card_frame = ctk.CTkFrame(self.main_frame)
        self.card_frame.pack(pady=5, padx=10, fill="both", expand=True)

        self.front_label = ctk.CTkLabel(self.card_frame, text="Select deck(s) and click 'Load' to begin", font=ctk.CTkFont(size=20), wraplength=600)
        self.front_label.pack(pady=(15, 10), padx=10)

        self.back_label = ctk.CTkLabel(self.card_frame, text="", font=ctk.CTkFont(size=16), wraplength=600)
        # Pack later

        # Control Frame: Buttons
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.pack(pady=5, padx=10, fill="x")

        self.show_answer_button = ctk.CTkButton(self.control_frame, text="Show Answer (Space/Enter)", command=self.show_answer, state="disabled")
        self.show_answer_button.pack(side="top", pady=5)

        self.rating_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        # Rating buttons (packed later)
        self.again_button = ctk.CTkButton(self.rating_frame, text="Again (1)", command=lambda: self.rate_card(1), width=80)
        self.hard_button = ctk.CTkButton(self.rating_frame, text="Hard (2)", command=lambda: self.rate_card(2), width=80)
        self.good_button = ctk.CTkButton(self.rating_frame, text="Good (3/Space/Enter)", command=lambda: self.rate_card(3), width=120)
        self.easy_button = ctk.CTkButton(self.rating_frame, text="Easy (4)", command=lambda: self.rate_card(4), width=80)
        self.again_button.pack(side="left", padx=5, pady=5, expand=True)
        self.hard_button.pack(side="left", padx=5, pady=5, expand=True)
        self.good_button.pack(side="left", padx=5, pady=5, expand=True)
        self.easy_button.pack(side="left", padx=5, pady=5, expand=True)


        # Status Bar Frame
        self.status_frame = ctk.CTkFrame(self.main_frame, height=30)
        self.status_frame.pack(pady=(5,5), padx=10, fill="x")
        self.status_label = ctk.CTkLabel(self.status_frame, text="Welcome!")
        self.status_label.pack(side="left", padx=10)
        self.cards_due_label = ctk.CTkLabel(self.status_frame, text="")
        self.cards_due_label.pack(side="right", padx=10)


        # --- Initial Setup ---
        self.populate_deck_listbox() # Load decks into listbox
        self._setup_shortcuts()

    # --- UI Update Methods ---

    def update_status(self, message: str):
        """Updates the status bar text."""
        self.status_label.configure(text=message)
        print(f"Status: {message}")

    def update_due_count(self):
        """Updates the label showing the number of cards remaining in the current session."""
        if self._is_review_active and self.current_card_index < len(self.due_cards):
             remaining = len(self.due_cards) - self.current_card_index
             self.cards_due_label.configure(text=f"Due: {remaining}")
        elif self.current_deck_paths: # Decks loaded but maybe none due or session finished
            # Recalculate due cards from the full loaded deck data
            current_due_count = len(get_due_cards(self.deck_data))
            self.cards_due_label.configure(text=f"Due Today: {current_due_count}")
        else:
             self.cards_due_label.configure(text="") # Clear when no session active/no deck

    def populate_deck_listbox(self):
        """Finds decks and updates the listbox."""
        self.available_decks = find_decks(self.decks_dir)
        self.deck_listbox.delete(0, tk.END) # Clear existing items

        if not self.available_decks:
            self.deck_listbox.insert(tk.END, " No decks found in 'decks' folder ")
            self.deck_listbox.configure(state="disabled") # Disable listbox
            self.load_button.configure(state="disabled")
            self.update_status(f"No decks found in '{self.decks_dir}'. Add CSV files there.")
        else:
            self.deck_listbox.configure(state="normal") # Enable listbox
            self.load_button.configure(state="normal")
            for deck_file in self.available_decks:
                deck_name = os.path.splitext(deck_file)[0] # Show name without .csv
                self.deck_listbox.insert(tk.END, f" {deck_name}") # Add padding for looks
            self.update_status(f"Found {len(self.available_decks)} deck(s). Select and click Load.")

        # Reset current session if list is reloaded
        self.reset_session_state()
        self.front_label.configure(text="Select deck(s) and click 'Load' to begin")


    def display_card(self):
        """Updates the UI to show the current card's front."""
        if self.current_card_index < 0 or self.current_card_index >= len(self.due_cards):
            # Handle session complete state
            self._is_review_active = False
            loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
            deck_context = f"'{', '.join(loaded_deck_names)}'" if loaded_deck_names else "this session"

            self.front_label.configure(text=f"Session complete for {deck_context}!" if self.deck_data else "Select deck(s) and load to begin")
            self.back_label.pack_forget()
            self.show_answer_button.pack(side="top", pady=5)
            self.show_answer_button.configure(state="disabled", text="Show Answer (Space/Enter)")
            self.rating_frame.pack_forget()
            self.update_status(f"Review session finished for {deck_context}." if self.deck_data else "No decks loaded.")
            # Enable Add Card only if exactly one deck is loaded
            self.add_card_button.configure(state="normal" if len(self.current_deck_paths) == 1 else "disabled")
            # Enable Settings/Stats if any deck is loaded
            self.settings_button.configure(state="normal" if self.current_deck_paths else "disabled")
            self.stats_button.configure(state="normal" if self.current_deck_paths else "disabled")
            self.update_due_count() # Show total due today
            return

        # A card is being displayed
        self._is_review_active = True
        self.showing_answer = False
        card = self.due_cards[self.current_card_index]

        self.front_label.configure(text=f"Front:\n\n{card['front']}")
        self.back_label.configure(text="")
        self.back_label.pack_forget()

        self.show_answer_button.pack(side="top", pady=5)
        self.show_answer_button.configure(state="normal", text="Show Answer (Space/Enter)")
        self.rating_frame.pack_forget()

        # Indicate source deck (optional)
        source_deck_name = os.path.splitext(os.path.basename(card.get('deck_filepath', 'Unknown Deck')))[0]
        self.update_status(f"Card {self.current_card_index + 1} of {len(self.due_cards)} (From: {source_deck_name} | Row: {card.get('original_row_index', 'N/A')})")
        self.update_due_count() # Show remaining in session
        # Add/Settings/Stats button status managed by load/completion logic


    # --- Event Handlers ---

    def reset_session_state(self):
        """Clears current session data and resets UI elements."""
        self.current_deck_paths = []
        self.deck_data = []
        self.due_cards = []
        self.current_card_index = -1
        self._is_review_active = False
        self.showing_answer = False
        self.show_answer_button.configure(state="disabled")
        self.rating_frame.pack_forget()
        self.add_card_button.configure(state="disabled") # Disable add initially
        self.settings_button.configure(state="disabled") # Disable settings initially
        self.stats_button.configure(state="disabled") # Disable stats initially
        self.update_status("Session reset. Select decks to load.")
        self.update_due_count()


    def load_selected_decks(self):
        """Loads data from decks selected in the listbox."""
        selected_indices = self.deck_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select one or more decks from the list.")
            return

        selected_files = [self.available_decks[i] for i in selected_indices]
        selected_paths = [os.path.join(self.decks_dir, f) for f in selected_files]

        self.reset_session_state() # Clear previous session
        self.current_deck_paths = selected_paths # Store loaded paths
        combined_deck_data = []
        loaded_deck_names = []
        load_errors = False

        self.update_status(f"Loading {len(selected_files)} deck(s)...")
        self.update() # Force UI update for status message

        for i, filepath in enumerate(self.current_deck_paths):
            deck_name = os.path.splitext(selected_files[i])[0]
            print(f"Loading: {deck_name} ({filepath})")
            cards = load_deck(filepath)
            # Check if load_deck indicated error (returned []) or file not found
            if not cards and not os.path.exists(filepath):
                 print(f"Error loading {deck_name}.")
                 # load_deck should have shown a messagebox
                 load_errors = True
                 # Remove the problematic path from current_deck_paths
                 self.current_deck_paths.remove(filepath)
                 continue # Skip this deck
            elif not cards and os.path.exists(filepath):
                 print(f"Info: Deck '{deck_name}' is empty or has format issues.")
                 # Allow loading empty decks, load_deck would show error for format issues

            # Add filepath to each card for tracking
            for card in cards:
                card['deck_filepath'] = filepath
            combined_deck_data.extend(cards)
            loaded_deck_names.append(deck_name)

        self.deck_data = combined_deck_data

        # Update loaded deck names based on successful loads
        loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
        deck_context = f"'{', '.join(loaded_deck_names)}'" if loaded_deck_names else "selected decks"


        if not self.deck_data and load_errors:
             self.update_status("Failed to load any valid deck data.")
             self.front_label.configure(text="Loading failed. Check console/errors.")
             self.settings_button.configure(state="disabled")
             self.stats_button.configure(state="disabled")
             return
        elif not self.deck_data and not load_errors and self.current_deck_paths:
            # Selected files might exist but be empty
            self.update_status(f"Loaded {deck_context}. Decks are empty.")
            self.front_label.configure(text="Selected deck(s) are empty.")
            # Allow adding if only one deck selected, allow settings/stats if any deck loaded
            self.add_card_button.configure(state="normal" if len(self.current_deck_paths) == 1 else "disabled")
            self.settings_button.configure(state="normal" if self.current_deck_paths else "disabled")
            self.stats_button.configure(state="normal" if self.current_deck_paths else "disabled")
            self.update_due_count()
            return
        elif not self.current_deck_paths: # All selected decks failed to load
            self.update_status("Failed to load selected deck(s).")
            self.front_label.configure(text="Select valid deck(s) and load.")
            self.settings_button.configure(state="disabled")
            self.stats_button.configure(state="disabled")
            return


        # Decks loaded, process due cards
        self.due_cards = get_due_cards(self.deck_data)
        random.shuffle(self.due_cards)

        # Enable/disable Add Card based on how many decks were successfully loaded
        self.add_card_button.configure(state="normal" if len(self.current_deck_paths) == 1 else "disabled")
        # Enable Settings/Stats buttons as decks are loaded
        self.settings_button.configure(state="normal")
        self.stats_button.configure(state="normal")

        if not self.due_cards:
            self.current_card_index = -1
            self._is_review_active = False
            self.front_label.configure(text=f"No cards due in {deck_context} today!")
            self.show_answer_button.configure(state="disabled")
            self.update_status(f"Loaded {deck_context}. No cards due.")
        else:
            self.current_card_index = 0
            self.display_card() # Show the first due card
            self.update_status(f"Loaded {deck_context}. {len(self.due_cards)} cards due.")

        self.update_due_count()

    def show_answer(self):
        """Reveals the back of the card and shows rating buttons."""
        if not self._is_review_active:
            return

        self.showing_answer = True
        card = self.due_cards[self.current_card_index]
        self.back_label.configure(text=f"Back:\n\n{card['back']}")

        self.show_answer_button.pack_forget()
        self.back_label.pack(pady=(5, 10), padx=10)
        self.rating_frame.pack(side="top", pady=5, fill="x")

    def rate_card(self, quality: int):
        """Processes rating, saves the specific deck file, moves to next card."""
        if not self.showing_answer or not self._is_review_active:
            return

        card_to_update = self.due_cards[self.current_card_index]
        original_filepath = card_to_update.get('deck_filepath')

        if not original_filepath:
            messagebox.showerror("Error", "Cannot save card: Original deck filepath not found.", parent=self)
            # Maybe skip to next card without saving? Or stop?
            self.current_card_index += 1
            self.display_card()
            return

        update_card_schedule(card_to_update, quality)

        if card_to_update.get('_dirty'):
            # Filter the main deck data to get only cards belonging to the file we need to save
            cards_for_this_file = [card for card in self.deck_data if card.get('deck_filepath') == original_filepath]

            if not cards_for_this_file:
                 # This shouldn't happen if the card came from deck_data
                 print(f"Error: Could not find cards for file '{original_filepath}' in main data.")
                 self.update_status(f"Card rated ({quality}). Save failed (data mismatch).")
            else:
                 # Save only the relevant deck file
                 save_deck(original_filepath, cards_for_this_file)
                 # save_deck resets the _dirty flag on the card objects within cards_for_this_file,
                 # which are the same objects as in self.deck_data and self.due_cards.
                 self.update_status(f"Card rated ({quality}). Saved '{os.path.basename(original_filepath)}'.")
        else:
             self.update_status(f"Card rated ({quality}). No schedule change.")


        # Move to the next card
        self.current_card_index += 1
        self.display_card()

    # --- Add Card Functionality ---

    def open_add_card_window(self):
        """Opens add card window ONLY if exactly one deck is loaded."""
        if len(self.current_deck_paths) != 1:
             messagebox.showwarning("Add Card Disabled", "Please load exactly one deck to add new cards.", parent=self)
             return

        if self.add_card_window is not None and self.add_card_window.winfo_exists():
            self.add_card_window.focus()
            return

        # Now we know exactly one deck is loaded
        target_deck_path = self.current_deck_paths[0]
        target_deck_name = os.path.splitext(os.path.basename(target_deck_path))[0]

        self.add_card_window = ctk.CTkToplevel(self)
        self.add_card_window.title(f"Add Card to: {target_deck_name}")
        self.add_card_window.geometry("400x250")
        self.add_card_window.transient(self)
        self.add_card_window.grab_set()
        self.add_card_window.protocol("WM_DELETE_WINDOW", self._on_add_card_close)

        # --- Widgets (Same as before) ---
        front_frame = ctk.CTkFrame(self.add_card_window)
        front_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(front_frame, text="Front:").pack(side="left", padx=5)
        front_entry = ctk.CTkEntry(front_frame, width=300)
        front_entry.pack(side="left", fill="x", expand=True)

        back_frame = ctk.CTkFrame(self.add_card_window)
        back_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(back_frame, text="Back: ").pack(side="left", padx=5)
        back_entry = ctk.CTkEntry(back_frame, width=300)
        back_entry.pack(side="left", fill="x", expand=True)

        button_frame = ctk.CTkFrame(self.add_card_window)
        button_frame.pack(pady=20, padx=10, fill="x")

        self.add_card_window.front_entry = front_entry
        self.add_card_window.back_entry = back_entry

        save_button = ctk.CTkButton(button_frame, text="Save Card", command=self.save_new_card)
        save_button.pack(side="left", padx=10, expand=True)
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=self._on_add_card_close)
        cancel_button.pack(side="right", padx=10, expand=True)

        # --- Bindings & Focus ---
        front_entry.focus()
        front_entry.bind("<Return>", lambda event: back_entry.focus())
        back_entry.bind("<Return>", lambda event: self.save_new_card())
        self.add_card_window.bind("<Escape>", lambda event: self._on_add_card_close())

    def save_new_card(self):
        """Saves the new card to the currently loaded single deck."""
        if len(self.current_deck_paths) != 1: # Safety check
            messagebox.showerror("Error", "Cannot save: No single deck loaded.", parent=self.add_card_window)
            return

        target_deck_path = self.current_deck_paths[0]

        # Ensure window and entries exist
        if not (self.add_card_window and self.add_card_window.winfo_exists()): return
        front_entry = getattr(self.add_card_window, 'front_entry', None)
        back_entry = getattr(self.add_card_window, 'back_entry', None)
        if not front_entry or not back_entry: return

        front = front_entry.get().strip()
        back = back_entry.get().strip()

        if not front or not back:
            messagebox.showwarning("Input Required", "Both 'Front' and 'Back' fields must be filled.", parent=self.add_card_window)
            if not front: front_entry.focus()
            else: back_entry.focus()
            return

        # Check if deck data is still loaded (should be)
        if self.deck_data is None:
             messagebox.showerror("Error", "Deck data lost. Cannot save card.", parent=self.add_card_window)
             self._on_add_card_close()
             return

        try:
            new_card = {
                'front': front, 'back': back,
                'next_review_date': None, # New cards are due immediately
                'interval_days': INITIAL_INTERVAL_DAYS,
                'original_row_index': 'NEW',
                'deck_filepath': target_deck_path, # Assign the correct filepath
                '_dirty': True
            }

            # Append to the main in-memory deck list
            self.deck_data.append(new_card)

            # Filter data for saving just this deck
            cards_for_this_file = [card for card in self.deck_data if card.get('deck_filepath') == target_deck_path]

            # Save the target deck file
            save_deck(target_deck_path, cards_for_this_file)

            messagebox.showinfo("Success", "New card added and saved successfully!", parent=self.add_card_window)
            self._on_add_card_close()

            deck_name = os.path.splitext(os.path.basename(target_deck_path))[0]
            self.update_status(f"New card added to '{deck_name}'.")

            # Refresh due count as the new card is due
            self.update_due_count()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save new card:\n{e}", parent=self.add_card_window)

    def _on_add_card_close(self):
        """Handles closing the add card window gracefully."""
        if self.add_card_window and self.add_card_window.winfo_exists():
            self.add_card_window.grab_release()
            self.add_card_window.destroy()
        self.add_card_window = None

    # --- Settings Functionality ---

    def open_settings_window(self):
        """Opens the settings window."""
        if not self.current_deck_paths:
            messagebox.showwarning("Settings Disabled", "Please load at least one deck to access settings.", parent=self)
            return

        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("Deck Settings")
        self.settings_window.geometry("500x400")
        self.settings_window.transient(self)
        self.settings_window.grab_set()
        self.settings_window.protocol("WM_DELETE_WINDOW", self._on_settings_close)

        # --- Settings Widgets ---
        settings_frame = ctk.CTkFrame(self.settings_window)
        settings_frame.pack(pady=10, padx=10, fill="both", expand=True)

        ctk.CTkLabel(settings_frame, text="Loaded Decks:").pack(anchor="w", padx=5, pady=(0,5))

        # Listbox to show loaded decks
        deck_info_listbox = tk.Listbox(settings_frame, height=8, exportselection=False,
                                        bg="#2B2B2B", fg="#DCE4EE",
                                        selectbackground="#1F6AA5", selectforeground="white",
                                        borderwidth=0, highlightthickness=1,
                                        highlightbackground="#565B5E",
                                        highlightcolor="#1F6AA5")
        deck_info_listbox.pack(fill="x", expand=True, padx=5, pady=5)
        self.settings_window.deck_info_listbox = deck_info_listbox # Store reference

        # Populate the listbox
        self.populate_settings_deck_list()

        # --- Deck Actions Frame ---
        actions_frame = ctk.CTkFrame(settings_frame)
        actions_frame.pack(pady=10, padx=5, fill="x")

        ctk.CTkLabel(actions_frame, text="Actions for Selected Deck:").pack(anchor="w", pady=(0,5))

        reset_button = ctk.CTkButton(actions_frame, text="Reset Progress", command=self.reset_selected_deck_progress)
        reset_button.pack(side="left", padx=5)

        # Add more actions here later (e.g., rename, delete - require careful implementation)

        # --- Close Button ---
        close_button = ctk.CTkButton(settings_frame, text="Close", command=self._on_settings_close)
        close_button.pack(pady=(15, 5))

        # --- Bindings & Focus ---
        self.settings_window.bind("<Escape>", lambda event: self._on_settings_close())


    def populate_settings_deck_list(self):
        """Populates the listbox in the settings window with deck info."""
        if not (self.settings_window and self.settings_window.winfo_exists()):
            return
        listbox = getattr(self.settings_window, 'deck_info_listbox', None)
        if not listbox: return

        listbox.delete(0, tk.END) # Clear existing

        if not self.current_deck_paths:
            listbox.insert(tk.END, " No decks loaded.")
            listbox.configure(state="disabled")
            return

        listbox.configure(state="normal")
        for deck_path in self.current_deck_paths:
            deck_name = os.path.splitext(os.path.basename(deck_path))[0]
            cards_in_deck = [card for card in self.deck_data if card.get('deck_filepath') == deck_path]
            total_cards = len(cards_in_deck)
            # Add more stats if needed (e.g., due count for this specific deck)
            listbox.insert(tk.END, f" {deck_name} ({total_cards} cards)")


    def reset_selected_deck_progress(self):
        """Resets all cards in the selected deck to 'new' state."""
        if not (self.settings_window and self.settings_window.winfo_exists()):
            return
        listbox = getattr(self.settings_window, 'deck_info_listbox', None)
        if not listbox: return

        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select a deck from the list to reset.", parent=self.settings_window)
            return

        selected_deck_index = selected_indices[0] # Only handle one selection for now
        try:
            target_deck_path = self.current_deck_paths[selected_deck_index]
            target_deck_name = os.path.splitext(os.path.basename(target_deck_path))[0]
        except IndexError:
            messagebox.showerror("Error", "Could not find the selected deck.", parent=self.settings_window)
            self.populate_settings_deck_list() # Refresh list
            return

        confirm = messagebox.askyesno("Confirm Reset",
                                      f"Are you sure you want to reset all progress for the deck '{target_deck_name}'?\n"
                                      f"All cards will become 'new' (due today, initial interval). This cannot be undone easily.",
                                      parent=self.settings_window)

        if not confirm:
            return

        # Find cards belonging to the target deck
        cards_to_reset = [card for card in self.deck_data if card.get('deck_filepath') == target_deck_path]

        if not cards_to_reset:
            messagebox.showinfo("Info", f"No cards found in memory for deck '{target_deck_name}'. Nothing to reset.", parent=self.settings_window)
            return

        # Reset progress and mark dirty
        cards_modified = 0
        for card in cards_to_reset:
            # Check if modification is needed
            if card.get('next_review_date') is not None or card.get('interval_days') != INITIAL_INTERVAL_DAYS:
                card['next_review_date'] = None # Due immediately
                card['interval_days'] = INITIAL_INTERVAL_DAYS
                card['_dirty'] = True
                cards_modified += 1

        if cards_modified == 0:
             messagebox.showinfo("Info", f"All cards in '{target_deck_name}' were already in the initial state. No changes made.", parent=self.settings_window)
             return

        # Save the modified deck
        save_deck(target_deck_path, cards_to_reset)

        messagebox.showinfo("Success", f"Progress for deck '{target_deck_name}' ({cards_modified} cards) has been reset and saved.", parent=self.settings_window)

        # Refresh main UI state (due counts, potentially current review session)
        self.refresh_after_settings_change()


    def refresh_after_settings_change(self):
        """Refreshes the main UI after changes in settings (e.g., deck reset)."""
        # Recalculate due cards based on potentially modified deck_data
        self.due_cards = get_due_cards(self.deck_data)
        random.shuffle(self.due_cards)

        # If a review was active, restart it from the beginning of the new due list
        if self._is_review_active or self.current_card_index != -1:
            self.current_card_index = 0 if self.due_cards else -1
            self.display_card() # Display the first card or the "complete/no due" message
        else:
            # If no review was active, just update the due count display
            self.update_due_count()

        # Refresh the settings window list as well, in case stats changed
        self.populate_settings_deck_list()


    def _on_settings_close(self):
        """Handles closing the settings window gracefully."""
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.grab_release()
            self.settings_window.destroy()
        self.settings_window = None

    # --- Statistics Functionality ---

    def open_stats_window(self):
        """Opens the statistics window."""
        if not self.current_deck_paths:
            messagebox.showwarning("Stats Disabled", "Please load at least one deck to view statistics.", parent=self)
            return

        if self.stats_window is not None and self.stats_window.winfo_exists():
            self.stats_window.focus()
            return

        self.stats_window = ctk.CTkToplevel(self)
        self.stats_window.title("Deck Statistics")
        self.stats_window.geometry("450x400") # Adjusted size
        self.stats_window.transient(self)
        self.stats_window.grab_set()
        self.stats_window.protocol("WM_DELETE_WINDOW", self._on_stats_close)

        # --- Stats Widgets ---
        stats_frame = ctk.CTkFrame(self.stats_window)
        stats_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Title Label
        loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
        title_text = f"Statistics for: {', '.join(loaded_deck_names)}" if loaded_deck_names else "Statistics (No Decks Loaded)"
        ctk.CTkLabel(stats_frame, text=title_text, font=ctk.CTkFont(weight="bold")).pack(pady=(5, 10))

        # Frame for the stats grid
        grid_frame = ctk.CTkFrame(stats_frame)
        grid_frame.pack(pady=5, padx=5, fill="x")
        grid_frame.columnconfigure(1, weight=1) # Make value column expand

        # Create labels for stats (will be populated by _update_stats_display)
        self.stats_window.stat_labels = {} # Dictionary to hold the value labels
        stat_items = [
            ("Total Cards:", "total_cards"),
            ("Due Today:", "due_today"),
            ("Due Tomorrow:", "due_tomorrow"),
            ("Due Next 7 Days:", "due_next_7_days"),
            ("New Cards:", "new_cards"),
            ("Learning/Review Cards:", "learning_review_cards"),
            ("Average Interval (days):", "average_interval"),
        ]

        for i, (label_text, key) in enumerate(stat_items):
            label = ctk.CTkLabel(grid_frame, text=label_text, anchor="w")
            label.grid(row=i, column=0, padx=10, pady=3, sticky="w")
            value_label = ctk.CTkLabel(grid_frame, text="...", anchor="e") # Placeholder text
            value_label.grid(row=i, column=1, padx=10, pady=3, sticky="ew")
            self.stats_window.stat_labels[key] = value_label # Store reference to value label

        # --- Buttons Frame ---
        button_frame = ctk.CTkFrame(stats_frame)
        button_frame.pack(pady=(15, 5), fill="x")

        refresh_button = ctk.CTkButton(button_frame, text="Refresh", command=self._update_stats_display)
        refresh_button.pack(side="left", padx=10, expand=True)

        close_button = ctk.CTkButton(button_frame, text="Close", command=self._on_stats_close)
        close_button.pack(side="right", padx=10, expand=True)

        # --- Bindings & Initial Population ---
        self.stats_window.bind("<Escape>", lambda event: self._on_stats_close())
        self._update_stats_display() # Populate with initial stats


    def _update_stats_display(self):
        """Calculates stats and updates the labels in the stats window."""
        if not (self.stats_window and self.stats_window.winfo_exists()):
            return

        stats = calculate_deck_statistics(self.deck_data)

        for key, label_widget in self.stats_window.stat_labels.items():
            value = stats.get(key, "N/A") # Get value from calculated stats
            label_widget.configure(text=str(value))


    def _on_stats_close(self):
        """Handles closing the stats window gracefully."""
        if self.stats_window and self.stats_window.winfo_exists():
            self.stats_window.grab_release()
            self.stats_window.destroy()
        self.stats_window = None


    # --- Keyboard Shortcuts ---
    def _setup_shortcuts(self):
        """Binds common Anki keyboard shortcuts."""
        self.bind_all("<Key>", self._handle_key_press)
        self.bind_all("<space>", lambda e: self._handle_key_press(e, force_space=True))
        self.bind_all("<Return>", lambda e: self._handle_key_press(e, force_return=True))

    def _handle_key_press(self, event, force_space=False, force_return=False):
        """Handles key presses for shortcuts."""
        # Ignore if modal window is active (Add Card, Settings, or Stats)
        if self.grab_set_applied() or \
           (self.add_card_window and self.add_card_window.winfo_exists()) or \
           (self.settings_window and self.settings_window.winfo_exists()) or \
           (self.stats_window and self.stats_window.winfo_exists()): # Added check for stats window
            focused_widget = self.focus_get()
            # Allow typing in Entry widgets within the modal windows
            if isinstance(focused_widget, (ctk.CTkEntry, tk.Entry)):
                 top_level = focused_widget.winfo_toplevel()
                 if top_level in (self.add_card_window, self.settings_window, self.stats_window):
                      return
            # Block shortcuts otherwise when modal is up
            return

        key_sym = event.keysym

        # Add Card Shortcut (A) - only if exactly ONE deck loaded
        if key_sym.lower() == 'a':
            if len(self.current_deck_paths) == 1: # Check if exactly one deck loaded
                self.open_add_card_window()
            else:
                # Optionally provide feedback if user presses 'A' in multi-deck mode
                # print("Info: Add card shortcut disabled in multi-deck mode.")
                pass
            return # Consume event


        # Review Shortcuts - only if review is active
        if not self._is_review_active:
             return

        # Show Answer / Rate Good (Space or Enter)
        if force_space or force_return:
            if self.showing_answer:
                 self.rate_card(3)
            else:
                 self.show_answer()
            return

        # Rating keys (1, 2, 3, 4) - only when answer is shown
        if key_sym in ('1', '2', '3', '4'):
             if self.showing_answer:
                  quality = int(key_sym)
                  self.rate_card(quality)
             return

    def grab_set_applied(self) -> bool:
        """Checks if a grab is currently active on any window."""
        try:
            return self.grab_current() is not None
        except tk.TclError:
             return False


if __name__ == "__main__":
    if not os.path.exists(DECKS_DIR):
        try:
            os.makedirs(DECKS_DIR)
            print(f"Created missing decks directory: '{DECKS_DIR}'")
        except OSError as e:
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Startup Error", f"Could not create decks directory '{DECKS_DIR}': {e}\nPlease create it manually.")
            root.destroy(); sys.exit(1)

    app = FlashcardApp()
    app.mainloop()
# --- END OF FILE PyAnki.py ---

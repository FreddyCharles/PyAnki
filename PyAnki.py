# PyAnki.py
# --- START OF FILE PyAnki.py ---

import csv
import datetime
import random
import os
import sys
import io # For handling image data in memory
import math # For ceiling function in interval calculation
import tkinter as tk # Base tkinter for listbox & messagebox
from tkinter import ttk # For Treeview (card browser)
from tkinter import messagebox # For showing errors/info
import customtkinter as ctk # Use CustomTkinter for modern widgets
from customtkinter import CTkImage # To display rendered math images
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter, defaultdict

# --- Pillow Dependency ---
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow library not found. Math rendering will be disabled.")
    print("Install it using: pip install Pillow")


# --- Matplotlib Integration ---
try:
    import matplotlib
    matplotlib.use('Agg') # Use Agg backend for non-interactive image generation
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    MATPLOTLIB_AVAILABLE = True
    # Configure Matplotlib for mathtext
    matplotlib.rcParams['mathtext.fontset'] = 'stix' # Or 'cm', 'stixsans', etc.
    matplotlib.rcParams['font.family'] = 'STIXGeneral' # Match font set if possible
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not found. Statistics plotting and Math rendering will be disabled.")
    print("Install it using: pip install matplotlib")

# --- Configuration ---
DATE_FORMAT = "%Y-%m-%d"
DECKS_DIR = "decks"
APP_NAME = "PyAnki CSV - Enhanced SRS + Mgmt"
INITIAL_INTERVAL_DAYS = 1.0 # Default interval for first 'Good' rating
MINIMUM_INTERVAL_DAYS = 1.0 # Smallest interval allowed after review (except lapse)
STATS_FORECAST_DAYS = 30 # How many days into the future to show in stats plot
MATH_RENDER_DPI = 150 # Resolution for rendered math images

# --- SRS Algorithm Parameters ---
DEFAULT_EASE_FACTOR = 2.5 # Starting ease (Anki uses 250%)
MINIMUM_EASE_FACTOR = 1.3 # Minimum ease allowed (Anki uses 130%)
EASE_MODIFIER_AGAIN = -0.20 # Decrease ease by this much for 'Again'
EASE_MODIFIER_HARD = -0.15  # Decrease ease by this much for 'Hard'
EASE_MODIFIER_EASY = +0.15  # Increase ease by this much for 'Easy'
INTERVAL_MODIFIER_HARD = 1.2 # Multiply interval by this for 'Hard' (applied before ease)
INTERVAL_MODIFIER_EASY_BONUS = 1.3 # Extra multiplier for 'Easy' reviews
LAPSE_INTERVAL_FACTOR = 0.0 # New interval after lapse (fraction of old, 0 means reset based on lapse count or fixed)
LAPSE_NEW_INTERVAL_DAYS = 1.0 # Fixed interval (days) after first lapse if LAPSE_INTERVAL_FACTOR is 0

# --- Color Name to Hex Mapping (for Matplotlib compatibility) ---
GRAY_NAME_TO_HEX = {
    "gray10": "#1A1A1A", "gray17": "#2B2B2B", "gray20": "#333333",
    "gray28": "#474747", "gray65": "#A6A6A6", "gray81": "#CFCFCF",
    "gray86": "#DBDBDB",
}


# --- Core Logic Functions ---

def parse_date(date_str: str) -> Optional[datetime.date]:
    """Safely parses a date string into a date object."""
    if not date_str: return None
    try:
        return datetime.datetime.strptime(date_str.strip(), DATE_FORMAT).date()
    except ValueError:
        # Keep console warning, but don't show messagebox during bulk load
        # print(f"Warning: Invalid date format '{date_str}'. Treating as due.")
        return None # Treat invalid format as due today

def _safe_float_parse(value_str: Optional[str], default: float) -> float:
    if value_str is None: return default
    try: return float(value_str.strip())
    except (ValueError, TypeError): return default

def _safe_int_parse(value_str: Optional[str], default: int) -> int:
    if value_str is None: return default
    try: return int(float(value_str.strip()))
    except (ValueError, TypeError): return default


def load_deck(filepath: str) -> List[Dict[str, Any]]:
    """Loads flashcards from a specific CSV file path, including new SRS fields."""
    deck: List[Dict[str, Any]] = []
    if not os.path.exists(filepath): return []

    required_columns = {'front', 'back', 'next_review_date', 'interval_days'}
    optional_columns = {'ease_factor', 'lapses', 'reviews'}
    line_num = 1
    has_shown_date_warning = False # Show only one date format warning per file

    try:
        with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            # Handle potential empty lines before header
            first_line = csvfile.readline()
            while first_line and not first_line.strip():
                 first_line = csvfile.readline()
            if not first_line: # File is effectively empty
                 messagebox.showerror("Error", f"CSV file '{os.path.basename(filepath)}' appears to be empty or has no header.")
                 return []
            csvfile.seek(0) # Reset position after reading first line

            reader = csv.DictReader(csvfile)
            header = reader.fieldnames
            if not header:
                 messagebox.showerror("Error", f"CSV file '{os.path.basename(filepath)}' has no valid header.")
                 return []

            if not required_columns.issubset(header):
                missing = required_columns - set(header)
                messagebox.showerror("Error", f"CSV file '{os.path.basename(filepath)}' is missing required columns: {', '.join(missing)}")
                return []

            file_specific_fieldnames = list(header)

            for i, row in enumerate(reader):
                line_num = i + 2
                # Check for empty rows (DictReader might return rows with all None values)
                if not any(row.values()):
                     print(f"Warning: Skipping empty row {line_num} in '{os.path.basename(filepath)}'.")
                     continue

                try:
                    front = row.get('front', '').strip()
                    back = row.get('back', '').strip()
                    if not front or not back:
                         print(f"Warning: Skipping row {line_num} in '{os.path.basename(filepath)}' due to missing front or back.")
                         continue

                    next_review_date_str = row.get('next_review_date', '').strip()
                    interval_str = row.get('interval_days', '').strip()

                    # Parse date with single warning per file
                    next_review_date = None
                    if next_review_date_str:
                        try:
                            next_review_date = datetime.datetime.strptime(next_review_date_str, DATE_FORMAT).date()
                        except ValueError:
                            if not has_shown_date_warning:
                                print(f"Warning: Invalid date format '{next_review_date_str}' in '{os.path.basename(filepath)}' (row {line_num}). Subsequent invalid dates in this file will be treated as due today without further warning.")
                                has_shown_date_warning = True
                            next_review_date = None # Treat as due

                    is_new_or_invalid_date = not next_review_date

                    interval_days = 0.0
                    if not is_new_or_invalid_date:
                        try:
                             interval_days = max(MINIMUM_INTERVAL_DAYS, float(interval_str))
                        except (ValueError, TypeError):
                             interval_days = INITIAL_INTERVAL_DAYS
                    elif interval_str: # If date is invalid/new but interval exists, still parse it? No, new card = 0 interval.
                         pass # Keep interval_days = 0.0 for new/invalid date cards

                    if is_new_or_invalid_date:
                        next_review_date = datetime.date.today()

                    ease_factor = _safe_float_parse(row.get('ease_factor'), DEFAULT_EASE_FACTOR)
                    lapses = _safe_int_parse(row.get('lapses'), 0)
                    reviews = _safe_int_parse(row.get('reviews'), 0)
                    ease_factor = max(MINIMUM_EASE_FACTOR, ease_factor)

                    # Assign a unique ID to each card for easier management in Treeview
                    # Use original row index + filepath hash for reasonable uniqueness
                    card_id = f"{hash(filepath)}_{line_num}"

                    card = {
                        'id': card_id, # Unique identifier for this card session
                        'front': front, 'back': back,
                        'next_review_date': next_review_date,
                        'interval_days': round(interval_days, 2),
                        'ease_factor': round(ease_factor, 3),
                        'lapses': lapses,
                        'reviews': reviews,
                        'original_row_index': line_num, # Keep for potential reference
                        'deck_filepath': filepath, # Store filepath for saving/grouping
                        '_dirty': False
                    }

                    for field in file_specific_fieldnames:
                        if field not in card and field in row:
                             card[field] = row[field]

                    deck.append(card)
                except Exception as e:
                    print(f"Warning: Error processing row {line_num} in '{os.path.basename(filepath)}': {e}")

    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred while reading '{os.path.basename(filepath)}': {e}")
        return []

    return deck


def save_deck(filepath: str, deck_to_save: List[Dict[str, Any]]):
    """Saves the provided list of cards back to the specified CSV file path, including new SRS fields."""
    # No need to check dirty flag here, assume caller decided save is needed
    # (e.g., due to deletion or modification)

    core_fields = ['front', 'back', 'next_review_date', 'interval_days']
    srs_fields = ['ease_factor', 'lapses', 'reviews']
    base_fieldnames = core_fields + srs_fields
    all_keys_in_data = set()
    for card in deck_to_save: all_keys_in_data.update(card.keys())
    internal_fields = {'_dirty', 'deck_filepath', 'original_row_index', 'id'} # Exclude internal fields
    extra_fields = sorted([k for k in all_keys_in_data if k not in base_fieldnames and k not in internal_fields])
    potential_fieldnames = base_fieldnames + extra_fields
    final_fieldnames = potential_fieldnames

    try:
        if os.path.exists(filepath):
            with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)
                if header and all(field in header for field in core_fields):
                     newly_added_fields = [f for f in potential_fieldnames if f not in header]
                     final_fieldnames = header + newly_added_fields
                     # print(f"Info: Using existing header and adding new fields: {newly_added_fields}") # Debug
                # else: use potential_fieldnames (already set)
        # else: use potential_fieldnames (already set)
    except Exception as e:
        print(f"Info: Could not read existing header from '{filepath}'. Using inferred fields for saving. Error: {e}")
        final_fieldnames = potential_fieldnames

    for bf in reversed(base_fieldnames):
         if bf not in final_fieldnames: final_fieldnames.insert(0, bf)

    try:
        with open(filepath, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=final_fieldnames, extrasaction='ignore')
            writer.writeheader()
            for card in deck_to_save:
                row_to_write = card.copy()
                row_to_write['next_review_date'] = row_to_write.get('next_review_date').strftime(DATE_FORMAT) if row_to_write.get('next_review_date') else ''
                row_to_write['interval_days'] = str(round(row_to_write.get('interval_days', 0.0), 2))
                row_to_write['ease_factor'] = str(round(row_to_write.get('ease_factor', DEFAULT_EASE_FACTOR), 3))
                row_to_write['lapses'] = str(row_to_write.get('lapses', 0))
                row_to_write['reviews'] = str(row_to_write.get('reviews', 0))
                writer.writerow(row_to_write)
                if '_dirty' in card: card['_dirty'] = False # Reset dirty flag after successful write
    except IOError as e:
        messagebox.showerror("Save Error", f"Could not write to file '{os.path.basename(filepath)}': {e}")
    except Exception as e:
        messagebox.showerror("Save Error", f"An unexpected error occurred while saving '{os.path.basename(filepath)}': {e}")


def get_due_cards(deck: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters the deck (potentially combined) to find cards due for review today."""
    today = datetime.date.today()
    return [card for card in deck if card.get('next_review_date') is None or card.get('next_review_date') <= today]


def update_card_schedule(card: Dict[str, Any], quality: int):
    """Updates the card's interval, ease factor, and next review date using an SM-2 like algorithm."""
    today = datetime.date.today()
    old_interval = card.get('interval_days', 0.0)
    old_ease_factor = card.get('ease_factor', DEFAULT_EASE_FACTOR)
    old_lapses = card.get('lapses', 0)
    old_reviews = card.get('reviews', 0)
    old_next_review_date = card.get('next_review_date')

    current_ease = max(MINIMUM_EASE_FACTOR, old_ease_factor)
    new_reviews = old_reviews + 1
    new_lapses = old_lapses
    new_ease_factor = current_ease
    days_to_add = 0

    is_learning_phase = old_interval < MINIMUM_INTERVAL_DAYS

    if quality == 1: # Again (Lapse)
        new_lapses += 1
        new_ease_factor = max(MINIMUM_EASE_FACTOR, current_ease + EASE_MODIFIER_AGAIN)
        if LAPSE_INTERVAL_FACTOR > 0: days_to_add = math.ceil(old_interval * LAPSE_INTERVAL_FACTOR)
        else: days_to_add = LAPSE_NEW_INTERVAL_DAYS
        days_to_add = max(1, days_to_add)
        new_interval = float(days_to_add)
    else: # Hard, Good, Easy
        if is_learning_phase or old_reviews <= 0: # Treat as learning if never reviewed before
            if quality == 2: # Hard
                 days_to_add = 1
                 new_ease_factor = max(MINIMUM_EASE_FACTOR, current_ease + EASE_MODIFIER_HARD)
            elif quality == 3: # Good
                 days_to_add = INITIAL_INTERVAL_DAYS
            elif quality == 4: # Easy
                 days_to_add = 4
                 new_ease_factor = current_ease + EASE_MODIFIER_EASY
            new_interval = float(days_to_add)
        else: # Reviewing graduated card
            days_to_add = math.ceil(old_interval * current_ease)
            if quality == 2: # Hard
                 days_to_add = math.ceil(old_interval * INTERVAL_MODIFIER_HARD)
                 new_ease_factor = max(MINIMUM_EASE_FACTOR, current_ease + EASE_MODIFIER_HARD)
            elif quality == 3: # Good
                 pass # Ease doesn't change, days_to_add already calculated
            elif quality == 4: # Easy
                 days_to_add = math.ceil(days_to_add * INTERVAL_MODIFIER_EASY_BONUS)
                 new_ease_factor = current_ease + EASE_MODIFIER_EASY
            if quality != 2: days_to_add = max(days_to_add, old_interval + 1)
            new_interval = float(days_to_add)

    if quality > 1: # Hard, Good, Easy
        days_to_add = max(MINIMUM_INTERVAL_DAYS, days_to_add)
        new_interval = max(MINIMUM_INTERVAL_DAYS, new_interval)

    next_review_date = today + datetime.timedelta(days=int(days_to_add))
    new_interval_rounded = round(new_interval, 2)
    new_ease_factor_rounded = round(new_ease_factor, 3)

    changed = (old_interval != new_interval_rounded or
               old_ease_factor != new_ease_factor_rounded or
               old_lapses != new_lapses or
               old_reviews != new_reviews or
               old_next_review_date != next_review_date)

    if changed:
        card['interval_days'] = new_interval_rounded
        card['ease_factor'] = new_ease_factor_rounded
        card['lapses'] = new_lapses
        card['reviews'] = new_reviews
        card['next_review_date'] = next_review_date
        card['_dirty'] = True
    else:
         card['_dirty'] = card.get('_dirty', False)


def find_decks(decks_dir: str) -> List[str]:
    """Finds all .csv files in the specified directory, creates dir if needed."""
    if not os.path.isdir(decks_dir):
        try:
            os.makedirs(decks_dir)
            print(f"Created decks directory: '{decks_dir}'")
            dummy_path = os.path.join(decks_dir, "example_deck.csv")
            if not os.path.exists(dummy_path):
                 with open(dummy_path, 'w', newline='', encoding='utf-8') as f:
                      writer = csv.writer(f)
                      writer.writerow(['front', 'back', 'next_review_date', 'interval_days', 'ease_factor', 'lapses', 'reviews'])
                      writer.writerow(['Sample Question: What is $E=mc^2$?', 'Sample Answer: Energy equals mass times the speed of light squared.', '', '', str(DEFAULT_EASE_FACTOR), '0', '0'])
                      writer.writerow(['Regular Text', 'Another plain card.', '', '', str(DEFAULT_EASE_FACTOR), '0', '0'])
                 print(f"Created '{dummy_path}'. Please replace it with your actual decks.")
            return ["example_deck.csv"]
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

# --- Statistics Calculation (Enhanced) ---
def calculate_deck_statistics(deck_data: List[Dict[str, Any]], forecast_days: int = STATS_FORECAST_DAYS) -> Dict[str, Any]:
    """Calculates various statistics for the provided deck data, including SRS stats."""
    stats = {
        "total_cards": 0, "new_cards": 0, "learning_cards": 0, "young_cards": 0, "mature_cards": 0,
        "due_today": 0, "due_tomorrow": 0, "due_next_7_days": 0, "due_counts_forecast": defaultdict(int),
        "average_interval_all": 0.0, "average_interval_mature": 0.0, "longest_interval": 0.0,
        "cards_by_interval_range": defaultdict(int), "average_ease": 0.0, "ease_distribution": defaultdict(int),
        "total_reviews": 0, "total_lapses": 0, "average_reviews_per_card": 0.0,
        "average_lapses_per_card": 0.0, "lapsed_card_count": 0,
    }
    if not deck_data: return stats

    today = datetime.date.today(); tomorrow = today + datetime.timedelta(days=1)
    next_7_days_start = tomorrow; next_7_days_end = today + datetime.timedelta(days=7)
    forecast_end_date = today + datetime.timedelta(days=forecast_days)
    total_interval_all = 0.0; total_interval_mature = 0.0; mature_card_count = 0
    total_ease = 0.0; non_new_card_count = 0
    learning_interval_threshold = 21; young_interval_threshold = 90
    stats["total_cards"] = len(deck_data)
    interval_bins = [0, 1, 3, 7, 14, 30, 60, 90, 180, 365, float('inf')]
    interval_labels = ["New/Learning (0d)", "<=1d", "2-3d", "4-7d", "8-14d", "15-30d", "1-2m", "2-3m", "3-6m", "6-12m", ">1y"]
    ease_bins = [0, 1.3, 1.5, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, float('inf')]
    ease_labels = ["<1.3", "1.3-1.5", "1.5-1.8", "1.8-2.0", "2.0-2.2", "2.2-2.4", "2.4-2.6", "2.6-2.8", "2.8-3.0", ">3.0"]

    for card in deck_data:
        review_date = card.get('next_review_date'); interval = card.get('interval_days', 0.0)
        ease = card.get('ease_factor', DEFAULT_EASE_FACTOR); lapses = card.get('lapses', 0); reviews = card.get('reviews', 0)
        is_new = reviews == 0
        stats["total_reviews"] += reviews; stats["total_lapses"] += lapses
        if lapses > 0: stats["lapsed_card_count"] += 1
        if not is_new:
            total_interval_all += interval; total_ease += ease; non_new_card_count += 1
            stats["longest_interval"] = max(stats["longest_interval"], interval)
        if is_new: stats["new_cards"] += 1
        elif interval < learning_interval_threshold: stats["learning_cards"] += 1
        elif interval < young_interval_threshold: stats["young_cards"] += 1
        else: stats["mature_cards"] += 1; total_interval_mature += interval; mature_card_count += 1
        bin_found = False
        for i in range(len(interval_bins) - 1):
            if interval == 0 and interval_bins[i] == 0: stats["cards_by_interval_range"][interval_labels[0]] += 1; bin_found = True; break
            elif interval_bins[i] < interval <= interval_bins[i+1]: stats["cards_by_interval_range"][interval_labels[i+1]] += 1; bin_found = True; break
        if not bin_found and interval > interval_bins[-2]: stats["cards_by_interval_range"][interval_labels[-1]] += 1
        if not is_new:
             bin_found = False
             for i in range(len(ease_bins) - 1):
                  if ease_bins[i] <= ease < ease_bins[i+1]: stats["ease_distribution"][ease_labels[i]] += 1; bin_found = True; break
             if not bin_found and ease >= ease_bins[-2]: stats["ease_distribution"][ease_labels[-1]] += 1
        if review_date:
            if review_date <= forecast_end_date and review_date >= today: stats["due_counts_forecast"][review_date] += 1
            if review_date <= today: stats["due_today"] += 1
            if review_date == tomorrow: stats["due_tomorrow"] += 1
            if next_7_days_start <= review_date <= next_7_days_end: stats["due_next_7_days"] += 1
        elif is_new: stats["due_today"] += 1; stats["due_counts_forecast"][today] += 1

    if non_new_card_count > 0:
        stats["average_ease"] = round(total_ease / non_new_card_count, 2)
        stats["average_interval_all"] = round(total_interval_all / non_new_card_count, 1)
    if mature_card_count > 0: stats["average_interval_mature"] = round(total_interval_mature / mature_card_count, 1)
    if stats["total_cards"] > 0:
        stats["average_reviews_per_card"] = round(stats["total_reviews"] / stats["total_cards"], 1)
        stats["average_lapses_per_card"] = round(stats["total_lapses"] / stats["total_cards"], 1)
    full_forecast = {today + datetime.timedelta(days=i): stats["due_counts_forecast"].get(today + datetime.timedelta(days=i), 0) for i in range(forecast_days + 1)}
    stats["due_counts_forecast"] = dict(sorted(full_forecast.items()))
    stats["cards_by_interval_range"] = dict(sorted(stats["cards_by_interval_range"].items(), key=lambda item: interval_labels.index(item[0])))
    stats["ease_distribution"] = dict(sorted(stats["ease_distribution"].items(), key=lambda item: ease_labels.index(item[0])))
    return stats


# --- Math Rendering Function ---
def render_math_to_image(text: str, text_color: str, bg_color: str, dpi: int = MATH_RENDER_DPI) -> Optional[Image.Image]:
    """Renders text (potentially with Matplotlib mathtext) to a PIL Image."""
    if not MATPLOTLIB_AVAILABLE or not PIL_AVAILABLE: return None
    if '$' not in text: return None

    try:
        fig = plt.figure(figsize=(8, 1), dpi=dpi, facecolor=bg_color)
        text_obj = fig.text(0.5, 0.5, text, ha='center', va='center', fontsize=12, color=text_color, wrap=True)
        fig.canvas.draw()
        bbox = text_obj.get_window_extent(renderer=fig.canvas.get_renderer())
        padding_inches = 0.1
        req_width = max((bbox.width / dpi) + 2 * padding_inches, 0.3)
        req_height = max((bbox.height / dpi) + 2 * padding_inches, 0.3)
        fig.set_size_inches(req_width, req_height)
        text_obj.set_position((0.5, 0.5)); text_obj.set_text(text)

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, facecolor=bg_color, edgecolor='none', bbox_inches='tight', pad_inches=padding_inches)
        buf.seek(0)
        plt.close(fig)
        image = Image.open(buf)
        return image
    except Exception as e:
        print(f"Error rendering math text: {e}")
        try: plt.close(fig)
        except: pass
        return None


# --- GUI Application Class ---

class FlashcardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("700x650")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Data Attributes ---
        self.decks_dir = DECKS_DIR
        self.available_decks: List[str] = []
        self.current_deck_paths: List[str] = []
        self.deck_data: List[Dict[str, Any]] = [] # Combined data from loaded decks
        self.due_cards: List[Dict[str, Any]] = []
        self.current_card_index: int = -1
        self.showing_answer: bool = False
        self._is_review_active: bool = False
        self._update_theme_colors() # Initialize theme colors
        self._math_image_cache: Dict[str, CTkImage] = {}
        self.files_needing_full_save: Set[str] = set() # Track files needing rewrite due to deletion

        # --- Window References ---
        self.add_card_window: Optional[ctk.CTkToplevel] = None
        self.edit_card_window: Optional[ctk.CTkToplevel] = None
        self.manage_cards_window: Optional[ctk.CTkToplevel] = None
        self.settings_window: Optional[ctk.CTkToplevel] = None
        self.stats_window: Optional[ctk.CTkToplevel] = None
        self.stats_figure_canvas: Optional[FigureCanvasTkAgg] = None
        self.stats_toolbar: Optional[NavigationToolbar2Tk] = None

        # --- UI Elements ---
        self._setup_ui()
        self._setup_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._appearance_mode_tracker = ctk.StringVar(value=ctk.get_appearance_mode())
        self._appearance_mode_tracker.trace_add("write", self._handle_appearance_change)
        self.populate_deck_listbox() # Load initial deck list

    def _setup_ui(self):
        """Creates and packs all main UI elements."""
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # --- Top Frame: Deck Selection & Management ---
        self.top_frame = ctk.CTkFrame(self.main_frame)
        self.top_frame.pack(pady=(5,10), padx=10, fill="x")

        self.deck_label = ctk.CTkLabel(self.top_frame, text="Available Decks (Ctrl/Shift+Click):")
        self.deck_label.pack(side="top", padx=5, pady=(0,5), anchor="w")

        self.deck_listbox = tk.Listbox(self.top_frame, selectmode=tk.EXTENDED, height=5, exportselection=False,
                                       borderwidth=1, relief="solid", highlightthickness=0)
        self.deck_listbox.pack(side="top", fill="x", expand=True, padx=5)
        self._update_listbox_colors()

        self.deck_button_frame = ctk.CTkFrame(self.top_frame)
        self.deck_button_frame.pack(side="top", fill="x", pady=(5,0), padx=5)

        self.load_button = ctk.CTkButton(self.deck_button_frame, text="Load Selected Deck(s)", command=self.load_selected_decks)
        self.load_button.pack(side="left", padx=(0,5))
        self.reload_decks_button = ctk.CTkButton(self.deck_button_frame, text="Reload List", width=100, command=self.populate_deck_listbox)
        self.reload_decks_button.pack(side="left", padx=5)

        # --- Management Buttons ---
        self.manage_button_frame = ctk.CTkFrame(self.top_frame)
        self.manage_button_frame.pack(side="top", fill="x", pady=(5,0), padx=5)

        # Add Card button (now acts globally or via Manage window)
        self.add_card_button = ctk.CTkButton(self.manage_button_frame, text="Add Card (A)", width=100, command=self.open_add_card_window, state="disabled")
        self.add_card_button.pack(side="left", padx=(0, 5))

        # Manage Cards Button
        self.manage_cards_button = ctk.CTkButton(self.manage_button_frame, text="Manage Cards", width=110, command=self.open_manage_cards_window, state="disabled")
        self.manage_cards_button.pack(side="left", padx=5)

        # Stats Button
        self.stats_button = ctk.CTkButton(self.manage_button_frame, text="Stats", width=80, command=self.open_stats_window, state="disabled")
        self.stats_button.pack(side="left", padx=5)

        # Settings Button (Optional place)
        # self.settings_button = ctk.CTkButton(self.manage_button_frame, text="Settings", width=80, command=self.open_settings_window, state="disabled")
        # self.settings_button.pack(side="left", padx=5)


        # --- Card Display Frame ---
        self.card_frame = ctk.CTkFrame(self.main_frame)
        self.card_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.front_label = ctk.CTkLabel(self.card_frame, text="Select deck(s) and click 'Load' to begin",
                                        font=ctk.CTkFont(size=20), wraplength=600, compound="center", anchor="center")
        self.front_label.pack(pady=(15, 10), padx=10, fill="both", expand=True)
        self.back_label = ctk.CTkLabel(self.card_frame, text="", font=ctk.CTkFont(size=16), wraplength=600,
                                       compound="center", anchor="center")

        # --- Control Frame: Buttons ---
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.pack(pady=5, padx=10, fill="x")
        self.show_answer_button = ctk.CTkButton(self.control_frame, text="Show Answer (Space/Enter)", command=self.show_answer, state="disabled")
        self.show_answer_button.pack(side="top", pady=5)

        self.rating_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.again_button = ctk.CTkButton(self.rating_frame, text="Again (1)", command=lambda: self.rate_card(1), width=80, fg_color="#E53E3E", hover_color="#C53030")
        self.hard_button = ctk.CTkButton(self.rating_frame, text="Hard (2)", command=lambda: self.rate_card(2), width=80, fg_color="#DD6B20", hover_color="#C05621")
        self.good_button = ctk.CTkButton(self.rating_frame, text="Good (3/Space/Enter)", command=lambda: self.rate_card(3), width=140)
        self.easy_button = ctk.CTkButton(self.rating_frame, text="Easy (4)", command=lambda: self.rate_card(4), width=80, fg_color="#38A169", hover_color="#2F855A")
        self.again_button.pack(side="left", padx=5, pady=5, expand=True); self.hard_button.pack(side="left", padx=5, pady=5, expand=True)
        self.good_button.pack(side="left", padx=5, pady=5, expand=True); self.easy_button.pack(side="left", padx=5, pady=5, expand=True)

        # --- Status Bar Frame ---
        self.status_frame = ctk.CTkFrame(self.main_frame, height=30)
        self.status_frame.pack(pady=(5,5), padx=10, fill="x")
        self.status_label = ctk.CTkLabel(self.status_frame, text="Welcome!")
        self.status_label.pack(side="left", padx=10)
        self.cards_due_label = ctk.CTkLabel(self.status_frame, text="")
        self.cards_due_label.pack(side="right", padx=10)

    # --- Theme Handling ---
    def _handle_appearance_change(self, *args):
        """Update colors when system theme changes."""
        print("Appearance mode changed:", ctk.get_appearance_mode())
        self._update_theme_colors(); self._update_listbox_colors()
        if self._is_review_active and 0 <= self.current_card_index < len(self.due_cards):
             card = self.due_cards[self.current_card_index]
             self._display_label_content(self.front_label, card['front'])
             if self.showing_answer: self._display_label_content(self.back_label, card['back'])
        if self.manage_cards_window and self.manage_cards_window.winfo_exists():
             self.manage_cards_window._apply_treeview_style() # Update browser style
        if self.stats_window and self.stats_window.winfo_exists() and MATPLOTLIB_AVAILABLE:
             try:
                 current_stats = calculate_deck_statistics(self.deck_data, forecast_days=STATS_FORECAST_DAYS)
                 if hasattr(self, 'stats_plot_frame') and self.stats_plot_frame:
                     self._create_stats_chart(self.stats_plot_frame, current_stats)
             except Exception as e: print(f"Error updating stats plot theme: {e}")

    def _update_theme_colors(self):
        """Reads current theme colors from the already loaded theme data."""
        self._current_text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self._current_bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self._current_listbox_select_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        self._current_listbox_select_fg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["text_color"])
        self._math_image_cache = {}

    def _update_listbox_colors(self):
        """Sets the colors for the Tkinter Listbox based on CURRENTLY STORED theme colors."""
        if not hasattr(self, '_current_text_color'): self._update_theme_colors()
        self.deck_listbox.configure(bg=self._current_bg_color, fg=self._current_text_color,
                                    selectbackground=self._current_listbox_select_bg,
                                    selectforeground=self._current_listbox_select_fg)

    def _apply_appearance_mode(self, color: Any) -> str:
        """Gets the light/dark mode color string, converting known gray names to hex."""
        color_str = ""
        if isinstance(color, (list, tuple)) and len(color) >= 2:
            mode_index = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
            color_str = color[mode_index] if color[mode_index] is not None else "#000000"
        elif isinstance(color, str): color_str = color
        else: color_str = "#FFFFFF" if ctk.get_appearance_mode().lower() == "light" else "#000000"
        return GRAY_NAME_TO_HEX.get(color_str, color_str)

    # --- UI Update Methods ---
    def update_status(self, message: str): self.status_label.configure(text=message)
    def update_due_count(self):
        if self._is_review_active and self.due_cards and self.current_card_index < len(self.due_cards):
            remaining = len(self.due_cards) - self.current_card_index; self.cards_due_label.configure(text=f"Due: {remaining}")
        elif self.current_deck_paths:
            current_due_count = len(get_due_cards(self.deck_data)); self.cards_due_label.configure(text=f"Due Today: {current_due_count}")
            if current_due_count == 0 and not self._is_review_active and self.deck_data: self.update_status("No cards due today in selected deck(s).")
        else: self.cards_due_label.configure(text="")

    def populate_deck_listbox(self):
        selected_indices = self.deck_listbox.curselection()
        self.available_decks = find_decks(self.decks_dir)
        self.deck_listbox.delete(0, tk.END)
        if not self.available_decks:
            self.deck_listbox.insert(tk.END, " No decks found in 'decks' folder "); self.deck_listbox.configure(state="disabled")
            self.load_button.configure(state="disabled"); self.update_status(f"No decks found in '{self.decks_dir}'. Add CSV files there.")
            self.reset_session_state(); self._display_label_content(self.front_label, "Add decks (.csv) to the 'decks' folder")
        else:
            self.deck_listbox.configure(state="normal"); self.load_button.configure(state="normal")
            for deck_file in self.available_decks: self.deck_listbox.insert(tk.END, f" {os.path.splitext(deck_file)[0]}")
            for index in selected_indices:
                if index < self.deck_listbox.size(): self.deck_listbox.selection_set(index)
            if not self.current_deck_paths:
                self.update_status(f"Found {len(self.available_decks)} deck(s). Select and click Load.")
                self.reset_session_state(); self._display_label_content(self.front_label, "Select deck(s) and click 'Load' to begin")
            else:
                loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
                self.update_status(f"Loaded: {', '.join(loaded_deck_names)}")

    def _display_label_content(self, label: ctk.CTkLabel, content: str):
         """Sets label content, rendering math to image if needed."""
         cache_key = f"{content}|{self._current_text_color}|{self._current_bg_color}"
         if not isinstance(content, str): content = str(content)
         if MATPLOTLIB_AVAILABLE and PIL_AVAILABLE and '$' in content:
             if cache_key in self._math_image_cache: ctk_image = self._math_image_cache[cache_key]
             else:
                 pil_image = render_math_to_image(content, self._current_text_color, self._current_bg_color)
                 if pil_image:
                      ctk_image = CTkImage(light_image=pil_image, dark_image=pil_image, size=(pil_image.width, pil_image.height))
                      self._math_image_cache[cache_key] = ctk_image
                 else: ctk_image = None; content = f"[Math Render Error]\n{content}"
             if ctk_image: label.configure(image=ctk_image, text=""); return
         label.configure(text=content, image=None)

    def display_card(self):
        """Updates the UI to show the current card's front."""
        if self.current_card_index < 0 or self.current_card_index >= len(self.due_cards):
            self._is_review_active = False; message = ""; deck_context = ""
            if self.current_deck_paths: deck_context = f"'{', '.join(os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths)}'"
            else: deck_context = "this session"
            total_due_today = len(get_due_cards(self.deck_data)) if self.deck_data else 0
            if self.deck_data: message = f"No more cards due today in {deck_context}!" if total_due_today == 0 else f"Session complete for {deck_context}!\n({total_due_today} cards due today in total)"
            else: message = "Select deck(s) and click 'Load' to begin"
            self.update_status("Review finished." if self.deck_data else "No deck loaded.")
            self._display_label_content(self.front_label, message); self._display_label_content(self.back_label, "")
            self.back_label.pack_forget(); self.show_answer_button.pack(side="top", pady=5)
            self.show_answer_button.configure(state="disabled", text="Show Answer (Space/Enter)"); self.rating_frame.pack_forget()
            self.update_due_count(); self.focus_set(); self.deck_listbox.focus_set()
            return

        self._is_review_active = True; self.showing_answer = False
        card = self.due_cards[self.current_card_index]
        self._display_label_content(self.front_label, card['front']); self.front_label.pack(pady=(15, 10), padx=10, fill="both", expand=True)
        self._display_label_content(self.back_label, ""); self.back_label.pack_forget(); self.rating_frame.pack_forget()
        self.show_answer_button.pack(side="top", pady=5); self.show_answer_button.configure(state="normal", text="Show Answer (Space/Enter)")
        self.update_status(f"Reviewing card {self.current_card_index + 1} of {len(self.due_cards)}"); self.update_due_count()
        self.show_answer_button.focus_set()

    def show_answer(self):
        """Reveals the answer and shows rating buttons."""
        if not self._is_review_active or self.showing_answer: return
        if self.current_card_index < 0 or self.current_card_index >= len(self.due_cards): self.display_card(); return
        self.showing_answer = True; card = self.due_cards[self.current_card_index]
        self._display_label_content(self.back_label, card['back']); self.back_label.pack(pady=(5, 15), padx=10, fill="x")
        self.show_answer_button.pack_forget(); self.rating_frame.pack(side="top", pady=5, fill="x", padx=20)
        self.update_status("Rate your recall difficulty."); self.good_button.focus_set()

    def rate_card(self, quality: int):
        """Processes the user's rating, updates schedule, and moves to the next card."""
        if not self._is_review_active or not self.showing_answer: return
        if 0 <= self.current_card_index < len(self.due_cards):
            card = self.due_cards[self.current_card_index]; update_card_schedule(card, quality)
            if quality == 1:
                card_to_repeat = self.due_cards.pop(self.current_card_index)
                insert_pos = len(self.due_cards) - min(len(self.due_cards)//4, 2); self.due_cards.insert(max(0, insert_pos), card_to_repeat)
                self.update_status(f"Card marked 'Again'. Will see again soon.")
            else: self.current_card_index += 1
            self.display_card()
        else: print("Error: Tried to rate card with invalid index."); self.display_card()

    # --- Deck Management ---
    def load_selected_decks(self):
        selected_indices = self.deck_listbox.curselection()
        if not selected_indices: messagebox.showwarning("No Selection", "Please select one or more decks from the list."); return
        selected_paths = [os.path.join(self.decks_dir, self.available_decks[i]) for i in selected_indices]
        selected_names = [os.path.splitext(self.available_decks[i])[0] for i in selected_indices]
        self.save_all_dirty_cards() # Save previous deck changes
        self.update_status(f"Loading deck(s): {', '.join(selected_names)}...")
        self.current_deck_paths = []; self.deck_data = []; load_errors = False; self._math_image_cache = {}; self.files_needing_full_save.clear()

        for i, filepath in enumerate(selected_paths):
            deck_name = selected_names[i]; print(f"Loading: {filepath}")
            single_deck = load_deck(filepath)
            if single_deck is None: load_errors = True; self.update_status(f"Error loading '{deck_name}'. Check console/log.")
            elif not single_deck and os.path.exists(filepath): messagebox.showwarning("Empty Deck", f"Deck '{deck_name}' is empty or could not be read properly."); self.current_deck_paths.append(filepath)
            elif single_deck: self.deck_data.extend(single_deck); self.current_deck_paths.append(filepath)

        if not self.deck_data and not load_errors:
             messagebox.showwarning("No Cards", "Selected deck(s) contain no valid flashcards."); self.reset_session_state(); self._display_label_content(self.front_label, "Selected deck(s) are empty."); self.update_status("Load failed or deck(s) empty."); return
        if load_errors and not self.deck_data:
             messagebox.showerror("Load Failed", "Failed to load any cards. Check CSV format and file permissions."); self.reset_session_state(); self._display_label_content(self.front_label, "Failed to load deck(s)."); self.update_status("Load failed."); return

        self.due_cards = get_due_cards(self.deck_data); random.shuffle(self.due_cards); self.current_card_index = 0; self._is_review_active = True
        self.add_card_button.configure(state="normal"); self.manage_cards_button.configure(state="normal"); self.stats_button.configure(state="normal") # Enable buttons

        if not self.due_cards:
            self._is_review_active = False; self.update_status(f"Loaded {len(self.deck_data)} card(s) from {len(self.current_deck_paths)} deck(s). No cards due now.")
            self._display_label_content(self.front_label, f"No cards due right now in '{', '.join(selected_names)}'."); self.show_answer_button.configure(state="disabled")
        else:
            self.update_status(f"Loaded {len(self.deck_data)} card(s). Starting review with {len(self.due_cards)} due card(s)."); self.display_card()
        self.update_due_count()

    def save_all_dirty_cards(self):
        """Saves changes for modified cards and rewrites files with deletions."""
        files_to_process = set(self.files_needing_full_save) # Start with files needing full save
        dirty_cards_by_file = defaultdict(list)
        for card in self.deck_data:
            if card.get('_dirty', False):
                filepath = card.get('deck_filepath')
                if filepath:
                    dirty_cards_by_file[filepath].append(card)
                    files_to_process.add(filepath) # Also process files with dirty cards

        if not files_to_process: return # Nothing to save or rewrite

        print(f"Saving changes to {len(files_to_process)} file(s)...")
        saved_files = 0
        for filepath in files_to_process:
             # Get ALL current cards belonging to this file for saving/rewriting
             full_deck_for_file = [c for c in self.deck_data if c.get('deck_filepath') == filepath]

             # Check if save is needed (either full rewrite or dirty cards exist)
             needs_save = (filepath in self.files_needing_full_save) or any(c.get('_dirty', False) for c in full_deck_for_file)

             if needs_save:
                 print(f"Saving {len(full_deck_for_file)} card(s) to {os.path.basename(filepath)} (Rewrite: {filepath in self.files_needing_full_save})...")
                 save_deck(filepath, full_deck_for_file) # Pass the full subset
                 saved_files += 1
             # Dirty flags are reset within save_deck

        if saved_files > 0: self.update_status(f"Saved changes to {saved_files} deck file(s).")
        self.files_needing_full_save.clear() # Clear the rewrite set after processing


    def reset_session_state(self):
        """Resets the application state when no deck is loaded or list is reloaded."""
        self.save_all_dirty_cards() # Save any pending changes first
        self.current_deck_paths = []; self.deck_data = []; self.due_cards = []
        self.current_card_index = -1; self.showing_answer = False; self._is_review_active = False
        self._math_image_cache = {}; self.files_needing_full_save.clear()
        # Disable buttons that require a loaded deck
        self.add_card_button.configure(state="disabled"); self.manage_cards_button.configure(state="disabled")
        self.stats_button.configure(state="disabled"); self.show_answer_button.configure(state="disabled")
        self.rating_frame.pack_forget()
        self.update_due_count() # Clear due count


    # --- Window Management ---
    def open_add_card_window(self, manage_window_ref=None):
        """Opens a window to add a new flashcard."""
        if self.add_card_window is not None and self.add_card_window.winfo_exists():
            self.add_card_window.focus(); return

        if not self.current_deck_paths:
             messagebox.showerror("Error", "Please load at least one deck before adding a card."); return

        # Determine target deck (use first loaded if multiple)
        target_deck_path = self.current_deck_paths[0]
        target_deck_name = os.path.splitext(os.path.basename(target_deck_path))[0]
        window_title = f"Add New Card to '{target_deck_name}'"
        if len(self.current_deck_paths) > 1:
             messagebox.showwarning("Multiple Decks", f"Multiple decks loaded. Card will be added to the *first* loaded deck: '{target_deck_name}'", parent=self if manage_window_ref is None else manage_window_ref)

        self.add_card_window = ctk.CTkToplevel(self)
        self.add_card_window.title(window_title)
        self.add_card_window.geometry("450x300")
        self.add_card_window.transient(self)
        self.add_card_window.grab_set()
        self.center_toplevel(self.add_card_window)

        ctk.CTkLabel(self.add_card_window, text="Front:").pack(pady=(10,0), padx=10, anchor="w")
        front_entry = ctk.CTkTextbox(self.add_card_window, height=60, wrap="word")
        front_entry.pack(pady=5, padx=10, fill="x")
        ctk.CTkLabel(self.add_card_window, text="Back:").pack(pady=(5,0), padx=10, anchor="w")
        back_entry = ctk.CTkTextbox(self.add_card_window, height=80, wrap="word")
        back_entry.pack(pady=5, padx=10, fill="x")
        button_frame = ctk.CTkFrame(self.add_card_window); button_frame.pack(pady=(10, 10), padx=10, fill="x")

        def submit_card():
            front = front_entry.get("1.0", tk.END).strip(); back = back_entry.get("1.0", tk.END).strip()
            if not front or not back: messagebox.showerror("Error", "Both Front and Back fields are required.", parent=self.add_card_window); return

            # Create unique ID (less critical for add, but good practice)
            # A simple timestamp+random might suffice if not immediately shown in browser
            new_card_id = f"new_{int(datetime.datetime.now().timestamp())}_{random.randint(100,999)}"
            new_card = {
                'id': new_card_id, 'front': front, 'back': back, 'next_review_date': datetime.date.today(),
                'interval_days': 0.0, 'ease_factor': DEFAULT_EASE_FACTOR, 'lapses': 0, 'reviews': 0,
                'deck_filepath': target_deck_path, '_dirty': True
            }
            self.deck_data.append(new_card)
            self.files_needing_full_save.add(target_deck_path) # Mark for save
            self.update_status(f"Added new card to '{target_deck_name}'.")
            self.update_due_count() # Update main window due count
            self.save_all_dirty_cards() # Save immediately

            # Refresh manage window if it's open and called this function
            if manage_window_ref and manage_window_ref.winfo_exists():
                 manage_window_ref._populate_card_list()

            front_entry.delete("1.0", tk.END); back_entry.delete("1.0", tk.END); front_entry.focus_set()

        def cancel_add(): self.add_card_window.destroy()

        add_button = ctk.CTkButton(button_frame, text="Add Card", command=submit_card)
        add_button.pack(side="left", padx=(0, 10), expand=True)
        cancel_button = ctk.CTkButton(button_frame, text="Close", command=cancel_add, fg_color="gray")
        cancel_button.pack(side="right", padx=(10, 0), expand=True)
        front_entry.bind("<Return>", lambda event: submit_card()); back_entry.bind("<Return>", lambda event: submit_card())
        self.add_card_window.bind("<Escape>", lambda event: cancel_add()); front_entry.focus_set()

    def open_edit_card_window(self, card_to_edit: Dict[str, Any], manage_window_ref):
        """Opens a window to edit an existing flashcard (Front/Back only)."""
        if self.edit_card_window is not None and self.edit_card_window.winfo_exists():
            self.edit_card_window.focus(); return
        if not card_to_edit: return # Should not happen if called correctly

        self.edit_card_window = ctk.CTkToplevel(self)
        self.edit_card_window.title("Edit Card")
        self.edit_card_window.geometry("450x300")
        self.edit_card_window.transient(manage_window_ref) # Transient to manage window
        self.edit_card_window.grab_set()
        self.center_toplevel(self.edit_card_window)

        ctk.CTkLabel(self.edit_card_window, text="Front:").pack(pady=(10,0), padx=10, anchor="w")
        front_entry = ctk.CTkTextbox(self.edit_card_window, height=60, wrap="word")
        front_entry.pack(pady=5, padx=10, fill="x")
        front_entry.insert("1.0", card_to_edit.get('front', ''))

        ctk.CTkLabel(self.edit_card_window, text="Back:").pack(pady=(5,0), padx=10, anchor="w")
        back_entry = ctk.CTkTextbox(self.edit_card_window, height=80, wrap="word")
        back_entry.pack(pady=5, padx=10, fill="x")
        back_entry.insert("1.0", card_to_edit.get('back', ''))

        # Display SRS info read-only for context
        srs_info_frame = ctk.CTkFrame(self.edit_card_window, fg_color="transparent")
        srs_info_frame.pack(pady=5, padx=10, fill="x")
        srs_text = (f"Interval: {card_to_edit.get('interval_days', 0)}d | "
                    f"Ease: {card_to_edit.get('ease_factor', 0):.2f} | "
                    f"Reviews: {card_to_edit.get('reviews', 0)} | "
                    f"Lapses: {card_to_edit.get('lapses', 0)}")
        ctk.CTkLabel(srs_info_frame, text=srs_text, font=ctk.CTkFont(size=10)).pack(anchor="w")


        button_frame = ctk.CTkFrame(self.edit_card_window); button_frame.pack(pady=(10, 10), padx=10, fill="x")

        def submit_changes():
            new_front = front_entry.get("1.0", tk.END).strip()
            new_back = back_entry.get("1.0", tk.END).strip()
            if not new_front or not new_back: messagebox.showerror("Error", "Front and Back cannot be empty.", parent=self.edit_card_window); return

            # Find the original card in self.deck_data using its unique ID
            original_card = next((c for c in self.deck_data if c.get('id') == card_to_edit.get('id')), None)

            if original_card:
                 if original_card['front'] != new_front or original_card['back'] != new_back:
                      original_card['front'] = new_front
                      original_card['back'] = new_back
                      original_card['_dirty'] = True
                      self.update_status(f"Updated card.")
                      self.save_all_dirty_cards() # Save change
                      # Refresh manage window
                      if manage_window_ref and manage_window_ref.winfo_exists():
                           manage_window_ref._populate_card_list() # Refresh the list
                 self.edit_card_window.destroy() # Close edit window
            else:
                 messagebox.showerror("Error", "Could not find the original card to update.", parent=self.edit_card_window)


        def cancel_edit(): self.edit_card_window.destroy()

        save_button = ctk.CTkButton(button_frame, text="Save Changes", command=submit_changes)
        save_button.pack(side="left", padx=(0, 10), expand=True)
        cancel_button = ctk.CTkButton(button_frame, text="Cancel", command=cancel_edit, fg_color="gray")
        cancel_button.pack(side="right", padx=(10, 0), expand=True)
        self.edit_card_window.bind("<Return>", lambda e: submit_changes()) # Allow Enter to save
        self.edit_card_window.bind("<Escape>", lambda event: cancel_edit()); front_entry.focus_set()


    def open_manage_cards_window(self):
        """Opens the card browser/management window."""
        if not self.deck_data: messagebox.showinfo("Manage Cards", "No deck loaded."); return
        if self.manage_cards_window is not None and self.manage_cards_window.winfo_exists():
            self.manage_cards_window.focus(); return

        self.manage_cards_window = ManageCardsWindow(master=self, app_instance=self)
        self.manage_cards_window.grab_set() # Make modal


    def open_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists(): self.settings_window.focus(); return
        self.settings_window = ctk.CTkToplevel(self); self.settings_window.title("Settings"); self.settings_window.geometry("300x200")
        self.settings_window.transient(self); self.settings_window.grab_set(); self.center_toplevel(self.settings_window)
        ctk.CTkLabel(self.settings_window, text="Settings (Placeholder)").pack(pady=20)
        ctk.CTkButton(self.settings_window, text="Close", command=self.settings_window.destroy).pack(pady=10)
        self.settings_window.bind("<Escape>", lambda event: self.settings_window.destroy())

    def open_stats_window(self):
        """Opens the statistics window displaying deck and SRS stats."""
        if not self.deck_data: messagebox.showinfo("Statistics", "No deck data loaded."); return
        if self.stats_window is not None and self.stats_window.winfo_exists(): self.stats_window.focus(); return

        self.stats_window = ctk.CTkToplevel(self); self.stats_window.title("Deck Statistics"); self.stats_window.geometry("800x700")
        self.stats_window.transient(self); self.center_toplevel(self.stats_window); self.stats_window.protocol("WM_DELETE_WINDOW", self._on_stats_close)
        stats_main_frame = ctk.CTkFrame(self.stats_window); stats_main_frame.pack(pady=10, padx=10, fill="both", expand=True)
        text_stats_frame = ctk.CTkFrame(stats_main_frame); text_stats_frame.pack(pady=5, padx=5, fill="x")
        plot_frame = ctk.CTkFrame(stats_main_frame); plot_frame.pack(pady=5, padx=5, fill="both", expand=True)
        self.stats_plot_frame = plot_frame
        stats = calculate_deck_statistics(self.deck_data, forecast_days=STATS_FORECAST_DAYS)

        stats_text_widget = ctk.CTkTextbox(text_stats_frame, wrap="none", height=280, activate_scrollbars=True)
        stats_text_widget.pack(pady=5, padx=5, fill="x"); stats_text_widget.configure(state="normal"); stats_text_widget.delete("1.0", tk.END)
        loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
        stats_text_widget.insert(tk.END, f"--- Deck Overview {'-'*20}\nDeck(s):\t\t{', '.join(loaded_deck_names)}\nTotal Cards:\t\t{stats['total_cards']}\n")
        stats_text_widget.insert(tk.END, f"  - New:\t\t{stats['new_cards']}\n  - Learning (<{21}d):\t{stats['learning_cards']}\n  - Young (<{90}d):\t{stats['young_cards']}\n  - Mature (>= {90}d):\t{stats['mature_cards']}\n\n")
        stats_text_widget.insert(tk.END, f"--- Scheduling {'-'*23}\nDue Today:\t\t{stats['due_today']}\nDue Tomorrow:\t\t{stats['due_tomorrow']}\nDue in Next 7 Days:\t{stats['due_next_7_days']} (excluding today)\n\n")
        stats_text_widget.insert(tk.END, f"--- Intervals {'-'*26}\nAvg. Interval (Seen):\t{stats['average_interval_all']} days\nAvg. Interval (Mature):\t{stats['average_interval_mature']} days\nLongest Interval:\t{stats['longest_interval']} days\n\n")
        stats_text_widget.insert(tk.END, f"--- Ease {'-'*31}\nAvg. Ease (Seen):\t{stats['average_ease']:.2f}\n\nEase Distribution (Seen Cards):\n")
        if stats['ease_distribution']:
             max_label_len = max(len(label) for label in stats['ease_distribution']); [stats_text_widget.insert(tk.END, f"  {label:<{max_label_len}}\t: {count}\n") for label, count in stats['ease_distribution'].items()]
        else: stats_text_widget.insert(tk.END, "  (No cards with ease factor calculated yet)\n"); stats_text_widget.insert(tk.END, "\n")
        stats_text_widget.insert(tk.END, f"--- Reviews & Lapses {'-'*18}\nTotal Reviews:\t{stats['total_reviews']} (Avg: {stats['average_reviews_per_card']}/card)\n")
        stats_text_widget.insert(tk.END, f"Total Lapses:\t\t{stats['total_lapses']} (Avg: {stats['average_lapses_per_card']}/card)\n")
        stats_text_widget.insert(tk.END, f"Cards Lapsed:\t\t{stats['lapsed_card_count']} ({stats['lapsed_card_count']/stats['total_cards']:.1%} of total)\n" if stats['total_cards'] > 0 else "Cards Lapsed:\t\t0\n")
        stats_text_widget.configure(state="disabled")

        if MATPLOTLIB_AVAILABLE:
            try: self._create_stats_chart(plot_frame, stats)
            except Exception as e: ctk.CTkLabel(plot_frame, text=f"Error creating plot: {e}", text_color="red").pack(pady=10); print(f"Matplotlib Error: {e}")
        else: ctk.CTkLabel(plot_frame, text="Matplotlib not installed. Plotting disabled.\n(Run: pip install matplotlib)", text_color="orange").pack(pady=20)
        ctk.CTkButton(stats_main_frame, text="Close", command=self._on_stats_close).pack(pady=(5, 10))
        self.stats_window.bind("<Escape>", lambda event: self._on_stats_close())

    def _create_stats_chart(self, parent_frame: ctk.CTkFrame, stats: Dict[str, Any]):
        """Creates and embeds the Matplotlib forecast chart."""
        for widget in parent_frame.winfo_children(): widget.destroy()
        self.stats_figure_canvas = None; self.stats_toolbar = None
        forecast_data = stats.get("due_counts_forecast", {})
        if not forecast_data: ctk.CTkLabel(parent_frame, text="No forecast data available.").pack(pady=10); return
        dates = list(forecast_data.keys()); counts = list(forecast_data.values()); cumulative_counts = [sum(counts[:i+1]) for i in range(len(counts))]
        plot_bg_color = self._current_bg_color; plot_text_color = self._current_text_color; bar_color = "#1f77b4"; line_color = "#ff7f0e"
        fig = Figure(figsize=(7, 4), dpi=100, facecolor=plot_bg_color); ax1 = fig.add_subplot(111); ax1.set_facecolor(plot_bg_color)
        ax1.bar(dates, counts, label='Cards Due Daily', color=bar_color, width=0.7); ax1.set_xlabel("Date", color=plot_text_color); ax1.set_ylabel("Cards Due", color=bar_color)
        ax1.tick_params(axis='y', labelcolor=bar_color, colors=plot_text_color); ax1.tick_params(axis='x', rotation=45, colors=plot_text_color); ax1.grid(True, axis='y', linestyle='--', alpha=0.6, color=plot_text_color)
        ax2 = ax1.twinx(); ax2.plot(dates, cumulative_counts, label='Cumulative Due', color=line_color, marker='.', linestyle='-'); ax2.set_ylabel("Total Cumulative Cards", color=line_color); ax2.tick_params(axis='y', labelcolor=line_color, colors=plot_text_color)
        fig.suptitle("Review Forecast", color=plot_text_color); ax1.set_title(f"Next {STATS_FORECAST_DAYS} Days", fontsize=10, color=plot_text_color)
        for spine in ax1.spines.values(): spine.set_edgecolor(plot_text_color);
        for spine in ax2.spines.values(): spine.set_edgecolor(plot_text_color)
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        self.stats_figure_canvas = FigureCanvasTkAgg(fig, master=parent_frame); canvas_widget = self.stats_figure_canvas.get_tk_widget(); canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.stats_toolbar = NavigationToolbar2Tk(self.stats_figure_canvas, parent_frame, pack_toolbar=False)
        try:
             toolbar_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"]); toolbar_fg = plot_text_color
             self.stats_toolbar.configure(background=toolbar_bg)
             for item in self.stats_toolbar.winfo_children():
                 try: item.configure(bg=toolbar_bg, fg=toolbar_fg)
                 except tk.TclError: pass
        except Exception as e: print(f"Minor error styling toolbar: {e}")
        self.stats_toolbar.update(); self.stats_toolbar.pack(side=tk.BOTTOM, fill=tk.X); self.stats_figure_canvas.draw()

    def _on_stats_close(self):
        if self.stats_figure_canvas:
            try: self.stats_figure_canvas.get_tk_widget().destroy(); plt.close(self.stats_figure_canvas.figure)
            except Exception as e: print(f"Error closing stats canvas: {e}")
        if self.stats_toolbar:
            try: self.stats_toolbar.destroy()
            except Exception as e: print(f"Error closing stats toolbar: {e}")
        self.stats_figure_canvas = None; self.stats_toolbar = None; self.stats_plot_frame = None
        if self.stats_window:
            try: self.stats_window.destroy()
            except Exception as e: print(f"Error closing stats window: {e}")
        self.stats_window = None

    def center_toplevel(self, window: ctk.CTkToplevel):
         window.update_idletasks(); main_x, main_y = self.winfo_x(), self.winfo_y(); main_w, main_h = self.winfo_width(), self.winfo_height()
         win_w, win_h = window.winfo_width(), window.winfo_height(); x = main_x + (main_w // 2) - (win_w // 2); y = main_y + (main_h // 2) - (win_h // 2)
         window.geometry(f"+{x}+{y}")

    # --- Event Handling & Shortcuts ---
    def _setup_shortcuts(self): self.bind("<KeyPress>", self._handle_keypress)
    def _handle_keypress(self, event):
        active_grab = self.grab_current()
        if active_grab and active_grab != self and event.widget.winfo_toplevel() == active_grab: return # Let modal handle keys
        if active_grab and active_grab != self: return # Ignore keys if grab is elsewhere
        key_sym = event.keysym; is_space = key_sym == "space"; is_return = key_sym == "Return"; is_a = key_sym.lower() == "a"
        if is_a and self.add_card_button.cget("state") == "normal": self.open_add_card_window(); return
        if not self._is_review_active: return
        if is_space or is_return:
            if self.showing_answer: self.rate_card(3)
            else: self.show_answer()
            return
        if key_sym in ('1', '2', '3', '4') and self.showing_answer: self.rate_card(int(key_sym)); return

    def on_close(self):
        """Handles the main window closing event."""
        self.save_all_dirty_cards() # Ensure data is saved
        # Clean up any open Toplevel windows
        if self.stats_window is not None and self.stats_window.winfo_exists(): self._on_stats_close()
        if self.manage_cards_window is not None and self.manage_cards_window.winfo_exists(): self.manage_cards_window.destroy()
        if self.add_card_window is not None and self.add_card_window.winfo_exists(): self.add_card_window.destroy()
        if self.edit_card_window is not None and self.edit_card_window.winfo_exists(): self.edit_card_window.destroy()
        if self.settings_window is not None and self.settings_window.winfo_exists(): self.settings_window.destroy()
        self.destroy() # Close the application


# --- Manage Cards Window Class ---

class ManageCardsWindow(ctk.CTkToplevel):
    def __init__(self, master, app_instance: FlashcardApp):
        super().__init__(master)
        self.app = app_instance # Reference to the main FlashcardApp instance

        self.title("Manage Cards")
        self.geometry("950x600")
        self.transient(master)
        # Don't grab_set initially, allow interaction with main window if needed,
        # but grab might be needed if edits/adds open further windows. Let's see.
        # self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.app.center_toplevel(self)

        # --- UI Elements ---
        # Top frame for search and buttons
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(top_frame, text="Search:").pack(side="left", padx=(5, 2))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(top_frame, textvariable=self.search_var, width=200)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<Return>", self._filter_cards)
        self.search_entry.bind("<KeyRelease>", self._filter_cards) # Filter as user types

        self.add_button = ctk.CTkButton(top_frame, text="Add New Card", width=120, command=self._add_card)
        self.add_button.pack(side="right", padx=(5, 5))
        self.edit_button = ctk.CTkButton(top_frame, text="Edit Selected", width=100, state="disabled", command=self._edit_card)
        self.edit_button.pack(side="right", padx=5)
        self.delete_button = ctk.CTkButton(top_frame, text="Delete Selected", width=120, state="disabled", command=self._delete_cards, fg_color="#D32F2F", hover_color="#B71C1C")
        self.delete_button.pack(side="right", padx=5)


        # Frame for Treeview
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(pady=5, padx=10, fill="both", expand=True)

        # --- Treeview Setup ---
        # Define columns (use IDs and display names)
        self.columns = {
            "deck": "Deck", "front": "Front", "back": "Back",
            "next_review": "Next Review", "interval": "Interval (d)", "ease": "Ease",
            "reviews": "Reviews", "lapses": "Lapses"
        }
        self.tree = ttk.Treeview(tree_frame, columns=list(self.columns.keys()), show="headings", selectmode="extended")

        # Configure Headings
        for col_id, col_name in self.columns.items():
            self.tree.heading(col_id, text=col_name, command=lambda _col=col_id: self._sort_column(_col, False))

        # Configure Column Widths (adjust as needed)
        self.tree.column("deck", width=100, anchor="w")
        self.tree.column("front", width=250, anchor="w")
        self.tree.column("back", width=250, anchor="w")
        self.tree.column("next_review", width=100, anchor="center")
        self.tree.column("interval", width=80, anchor="e")
        self.tree.column("ease", width=60, anchor="e")
        self.tree.column("reviews", width=60, anchor="e")
        self.tree.column("lapses", width=60, anchor="e")

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

        # Apply styling
        self._apply_treeview_style()

        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)

        # Populate the list
        self._populate_card_list()

        # Bottom frame (optional, for status or close button)
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.pack(pady=(5, 10), padx=10, fill="x")
        close_button = ctk.CTkButton(bottom_frame, text="Close", command=self.on_close)
        close_button.pack()

    def _apply_treeview_style(self):
        """Applies theme colors to the ttk.Treeview."""
        style = ttk.Style()
        bg_col = self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        fg_col = self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        select_bg_col = self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        select_fg_col = self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["text_color"])

        style.theme_use("default") # Start from a known base
        # Configure Treeview overall style
        style.configure("Treeview", background=bg_col, foreground=fg_col, fieldbackground=bg_col, rowheight=25)
        # Configure selected item style
        style.map("Treeview", background=[('selected', select_bg_col)], foreground=[('selected', select_fg_col)])
        # Configure heading style
        style.configure("Treeview.Heading", background=self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"]),
                        foreground=self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["text_color"]),
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', self.app._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["hover_color"]))])
        self.update_idletasks() # Force update

    def _populate_card_list(self, sort_column=None, reverse=False):
        """Clears and refills the Treeview with card data."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get current data, potentially filtered
        search_term = self.search_var.get().lower()
        display_data = []
        if search_term:
            for card in self.app.deck_data:
                 # Simple search in front and back
                 if search_term in card.get('front', '').lower() or search_term in card.get('back', '').lower():
                      display_data.append(card)
        else:
             display_data = self.app.deck_data[:] # Work with a copy

        # --- Sorting ---
        if sort_column:
            key_func = None
            if sort_column == "deck": key_func = lambda card: os.path.basename(card.get('deck_filepath', ''))
            elif sort_column == "front": key_func = lambda card: card.get('front', '').lower()
            elif sort_column == "back": key_func = lambda card: card.get('back', '').lower()
            elif sort_column == "next_review": key_func = lambda card: card.get('next_review_date', datetime.date.min)
            elif sort_column == "interval": key_func = lambda card: card.get('interval_days', 0.0)
            elif sort_column == "ease": key_func = lambda card: card.get('ease_factor', 0.0)
            elif sort_column == "reviews": key_func = lambda card: card.get('reviews', 0)
            elif sort_column == "lapses": key_func = lambda card: card.get('lapses', 0)

            if key_func:
                 try:
                      display_data.sort(key=key_func, reverse=reverse)
                 except Exception as e:
                      print(f"Error sorting column {sort_column}: {e}") # Handle potential type errors during sort

        # --- Insert Data ---
        for card in display_data:
            deck_name = os.path.splitext(os.path.basename(card.get('deck_filepath', '')))[0]
            next_review_str = card.get('next_review_date').strftime(DATE_FORMAT) if card.get('next_review_date') else "N/A"
            values = (
                deck_name,
                card.get('front', ''),
                card.get('back', ''),
                next_review_str,
                f"{card.get('interval_days', 0.0):.1f}", # Format interval
                f"{card.get('ease_factor', 0.0):.2f}", # Format ease
                card.get('reviews', 0),
                card.get('lapses', 0)
            )
            # Use card's unique 'id' as the Treeview item ID (iid)
            self.tree.insert("", "end", iid=card.get('id'), values=values)

    def _sort_column(self, col, reverse):
        """Sorts the treeview by the clicked column."""
        self._populate_card_list(sort_column=col, reverse=reverse)
        # Update heading command to sort in reverse next time
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))

    def _filter_cards(self, event=None):
        """Filters the card list based on the search entry."""
        self._populate_card_list() # Repopulate applies the filter

    def _on_selection_change(self, event=None):
        """Enables/disables Edit/Delete buttons based on selection."""
        selected_items = self.tree.selection()
        if selected_items:
            self.edit_button.configure(state="normal" if len(selected_items) == 1 else "disabled")
            self.delete_button.configure(state="normal")
        else:
            self.edit_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")

    def _get_selected_card_dicts(self) -> List[Dict[str, Any]]:
        """Gets the full card dictionaries for selected Treeview items."""
        selected_iids = self.tree.selection()
        selected_cards = []
        for iid in selected_iids:
            # Find the card in the main app data using the iid
            card = next((c for c in self.app.deck_data if c.get('id') == iid), None)
            if card:
                selected_cards.append(card)
        return selected_cards

    def _add_card(self):
        """Opens the add card window."""
        # Pass self as reference so add window can call back to refresh
        self.app.open_add_card_window(manage_window_ref=self)

    def _edit_card(self):
        """Opens the edit window for the selected card."""
        selected_cards = self._get_selected_card_dicts()
        if len(selected_cards) == 1:
            # Pass self as reference so edit window can call back to refresh
            self.app.open_edit_card_window(selected_cards[0], manage_window_ref=self)
        elif len(selected_cards) > 1:
             messagebox.showwarning("Select One", "Please select only one card to edit.", parent=self)
        else:
             messagebox.showerror("No Selection", "Please select a card to edit.", parent=self)


    def _delete_cards(self):
        """Deletes selected cards after confirmation."""
        selected_cards = self._get_selected_card_dicts()
        if not selected_cards:
            messagebox.showerror("No Selection", "Please select card(s) to delete.", parent=self)
            return

        count = len(selected_cards)
        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete {count} selected card(s)?\nThis action cannot be undone.", parent=self)

        if confirm:
            deleted_count = 0
            files_affected = set()
            ids_to_delete = {card.get('id') for card in selected_cards}

            # Filter out the cards to be deleted from the main list
            original_count = len(self.app.deck_data)
            self.app.deck_data = [card for card in self.app.deck_data if card.get('id') not in ids_to_delete]
            deleted_count = original_count - len(self.app.deck_data)

            # Mark the files from which cards were deleted as needing a full save
            for card in selected_cards:
                filepath = card.get('deck_filepath')
                if filepath:
                     files_affected.add(filepath)

            self.app.files_needing_full_save.update(files_affected)

            print(f"Deleted {deleted_count} card(s). Marked files for rewrite: {files_affected}")
            self.app.update_status(f"Deleted {deleted_count} card(s).")
            self.app.save_all_dirty_cards() # Save immediately to persist deletion
            self._populate_card_list() # Refresh the view
            self._on_selection_change() # Update button states

    def on_close(self):
        """Closes the manage cards window."""
        self.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    if not PIL_AVAILABLE:
        try: root = ctk.CTk(); root.withdraw(); messagebox.showwarning("Missing Dependency", "Pillow library not found..."); root.destroy()
        except Exception as e: print(f"Error showing Pillow warning: {e}")
    if not MATPLOTLIB_AVAILABLE:
         try: root = ctk.CTk(); root.withdraw(); messagebox.showwarning("Missing Dependency", "Matplotlib library not found..."); root.destroy()
         except Exception as e: print(f"Error showing Matplotlib warning: {e}")

    find_decks(DECKS_DIR)
    app = FlashcardApp()
    app.mainloop()

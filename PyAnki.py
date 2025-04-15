# PyAnki.py
# --- START OF FILE PyAnki.py ---

import csv
import datetime
import random
import os
import sys
import io # For handling image data in memory
import tkinter as tk # Base tkinter for listbox & messagebox
from tkinter import messagebox # For showing errors/info
import customtkinter as ctk # Use CustomTkinter for modern widgets
from customtkinter import CTkImage # To display rendered math images
from typing import List, Dict, Any, Optional, Tuple
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
APP_NAME = "PyAnki CSV - MultiDeck (with Stats & Math)"
INITIAL_INTERVAL_DAYS = 1.0
MINIMUM_INTERVAL_DAYS = 1.0
STATS_FORECAST_DAYS = 30 # How many days into the future to show in stats plot
MATH_RENDER_DPI = 150 # Resolution for rendered math images

# --- Core Logic Functions ---

def parse_date(date_str: str) -> Optional[datetime.date]:
    """Safely parses a date string into a date object."""
    if not date_str: return None
    try:
        return datetime.datetime.strptime(date_str.strip(), DATE_FORMAT).date()
    except ValueError:
        print(f"Warning: Invalid date format '{date_str}'. Treating as due.")
        return None # Treat invalid format as due today

def parse_interval(interval_str: str) -> float:
    """Safely parses an interval string into a float."""
    if not interval_str: return INITIAL_INTERVAL_DAYS
    try:
        interval = float(interval_str.strip())
        # Allow zero interval for new cards, but enforce minimum for reviews
        return max(0.0, interval) if interval == 0 else max(MINIMUM_INTERVAL_DAYS, interval)
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

                    # Handle potentially empty date/interval more robustly
                    next_review_date_str = row.get('next_review_date', '').strip()
                    interval_str = row.get('interval_days', '').strip()

                    next_review_date = parse_date(next_review_date_str)
                    # If date is empty or invalid, treat as new (due now)
                    is_new = not next_review_date_str or next_review_date is None

                    # If interval is empty or invalid, use default. If card is new, use 0.
                    interval_days = INITIAL_INTERVAL_DAYS # Default
                    if is_new:
                        interval_days = 0.0 # New cards have 0 interval until first review
                        next_review_date = datetime.date.today() # New cards are due today
                    elif interval_str: # Only parse if interval exists and card isn't new
                         interval_days = parse_interval(interval_str)


                    card = {
                        'front': front, 'back': back,
                        'next_review_date': next_review_date,
                        'interval_days': interval_days,
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
         # print(f"Info: No dirty cards found for '{os.path.basename(filepath)}'. Skipping save.")
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
                reader = csv.reader(csvfile) # Keep it simple for now
                header = next(reader, None)
                if header: # Use existing header if valid
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
            # Ensure core fields are present and at the beginning, maintaining relative order of others
            final_fieldnames = []
            present_core = {f for f in core_fields if f in fieldnames_for_write}
            final_fieldnames.extend([f for f in core_fields if f in present_core]) # Add present core fields first
            final_fieldnames.extend([f for f in fieldnames_for_write if f not in present_core]) # Add the rest


            writer = csv.DictWriter(csvfile, fieldnames=final_fieldnames, extrasaction='ignore')
            writer.writeheader()
            for card in deck_to_save:
                # Prepare row data for writing
                row_to_write = card.copy() # Start with all data from the card
                # Format specific fields
                row_to_write['next_review_date'] = row_to_write.get('next_review_date').strftime(DATE_FORMAT) if row_to_write.get('next_review_date') else ''
                # Ensure interval is formatted correctly (handle potential 0.0 for new)
                interval_val = row_to_write.get('interval_days', INITIAL_INTERVAL_DAYS)
                row_to_write['interval_days'] = str(round(interval_val, 2)) if interval_val is not None else ''


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
    # Card is due if date is missing (treated as new) or date is today or earlier
    return [card for card in deck if card.get('next_review_date') is None or card.get('next_review_date') <= today]

def update_card_schedule(card: Dict[str, Any], quality: int):
    """Updates the card's interval and next review date based on recall quality."""
    # --- SM-2 Algorithm Parameters (Simplified) ---
    AGAIN_INTERVAL_DAYS = 0.0 # Reset interval completely for 'Again'
    HARD_FACTOR = 1.2       # Multiplier for 'Hard'
    GOOD_FACTOR = 2.5       # Multiplier for 'Good' (standard recall)
    EASY_FACTOR = 4.0       # Multiplier for 'Easy'
    FIRST_GOOD_INTERVAL = 1.0 # Interval after getting 'Good' on a new card
    FIRST_EASY_INTERVAL = 4.0 # Interval after getting 'Easy' on a new card

    today = datetime.date.today()
    current_interval = card.get('interval_days', 0.0) # Default to 0 for potentially new cards
    is_new_card = current_interval <= 0 # Check if it's the first review

    new_interval = current_interval
    days_to_add = 0

    if quality == 1: # Again
        new_interval = AGAIN_INTERVAL_DAYS # Reset interval
        days_to_add = 1 # See it again tomorrow (or configured minimum lapse)
    elif quality == 2: # Hard
        if is_new_card:
             new_interval = AGAIN_INTERVAL_DAYS # Treat Hard on new card like Again
             days_to_add = 1
        else:
            new_interval = max(MINIMUM_INTERVAL_DAYS, current_interval * HARD_FACTOR)
            days_to_add = round(new_interval)
    elif quality == 3: # Good
        if is_new_card:
            new_interval = FIRST_GOOD_INTERVAL
        else:
            new_interval = max(MINIMUM_INTERVAL_DAYS, current_interval * GOOD_FACTOR)
        days_to_add = round(new_interval)
    elif quality == 4: # Easy
        if is_new_card:
            new_interval = FIRST_EASY_INTERVAL
        else:
            good_interval_calc = max(MINIMUM_INTERVAL_DAYS, current_interval * GOOD_FACTOR)
            easy_interval_calc = max(MINIMUM_INTERVAL_DAYS, current_interval * EASY_FACTOR)
            new_interval = max(good_interval_calc + 1, easy_interval_calc) # At least one day more than good
        days_to_add = round(new_interval)
    else:
        print(f"Warning: Invalid quality rating {quality} received.")
        return # No change if quality is invalid

    if quality != 1 and days_to_add < MINIMUM_INTERVAL_DAYS:
         days_to_add = int(MINIMUM_INTERVAL_DAYS) # Schedule at least minimum days away

    next_review_date = today + datetime.timedelta(days=days_to_add)

    old_interval = card.get('interval_days')
    old_date = card.get('next_review_date')
    new_interval_rounded = round(new_interval, 2)

    if old_interval != new_interval_rounded or old_date != next_review_date:
        card['interval_days'] = new_interval_rounded
        card['next_review_date'] = next_review_date
        card['_dirty'] = True


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
                      writer.writerow(['front', 'back', 'next_review_date', 'interval_days'])
                      writer.writerow(['Sample Question: What is $E=mc^2$?', 'Sample Answer: Energy equals mass times the speed of light squared.', '', ''])
                      writer.writerow(['Regular Text', 'Another plain card.', '', ''])
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

# --- Statistics Calculation ---
def calculate_deck_statistics(deck_data: List[Dict[str, Any]], forecast_days: int = STATS_FORECAST_DAYS) -> Dict[str, Any]:
    """Calculates various statistics for the provided deck data, including future due counts."""
    stats = {
        "total_cards": 0, "new_cards": 0, "learning_cards": 0, "young_cards": 0,
        "mature_cards": 0, "suspended_cards": 0, "average_interval_mature": 0.0,
        "due_counts_forecast": defaultdict(int), "due_today": 0, "due_tomorrow": 0,
        "due_next_7_days": 0, "cards_by_interval_range": defaultdict(int),
    }
    if not deck_data: return stats

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    next_7_days_start = tomorrow
    next_7_days_end = today + datetime.timedelta(days=7)
    forecast_end_date = today + datetime.timedelta(days=forecast_days)

    total_mature_interval = 0.0
    mature_card_count = 0
    learning_interval_threshold = 21
    young_interval_threshold = 90

    stats["total_cards"] = len(deck_data)

    interval_bins = [0, 1, 3, 7, 14, 30, 60, 90, 180, 365, float('inf')]
    interval_labels = [
        "New/Learning (0d)", "<=1d", "2-3d", "4-7d", "8-14d",
        "15-30d", "1-2m", "2-3m", "3-6m", "6-12m", ">1y"
    ]

    for card in deck_data:
        review_date = card.get('next_review_date')
        interval = card.get('interval_days', 0.0)

        if interval <= 0: stats["new_cards"] += 1
        elif interval < learning_interval_threshold: stats["learning_cards"] += 1
        elif interval < young_interval_threshold: stats["young_cards"] += 1
        else:
            stats["mature_cards"] += 1
            total_mature_interval += interval
            mature_card_count += 1

        for i in range(len(interval_bins) - 1):
            if interval_bins[i] <= interval < interval_bins[i+1]:
                 label_index = i + 1 if interval > 0 else 0
                 stats["cards_by_interval_range"][interval_labels[label_index]] += 1
                 break

        if review_date:
            if review_date <= forecast_end_date and review_date >= today:
                 stats["due_counts_forecast"][review_date] += 1
            if review_date <= today: stats["due_today"] += 1
            if review_date == tomorrow: stats["due_tomorrow"] += 1
            if next_7_days_start <= review_date <= next_7_days_end: stats["due_next_7_days"] += 1
        elif interval <= 0:
             stats["due_today"] += 1
             stats["due_counts_forecast"][today] += 1

    if mature_card_count > 0:
        stats["average_interval_mature"] = round(total_mature_interval / mature_card_count, 1)
    else:
        stats["average_interval_mature"] = 0.0

    full_forecast = {}
    for i in range(forecast_days + 1):
        current_date = today + datetime.timedelta(days=i)
        full_forecast[current_date] = stats["due_counts_forecast"].get(current_date, 0)
    stats["due_counts_forecast"] = dict(sorted(full_forecast.items()))

    stats["cards_by_interval_range"] = dict(sorted(
        stats["cards_by_interval_range"].items(),
        key=lambda item: interval_labels.index(item[0])
    ))

    return stats

# --- Math Rendering Function ---
def render_math_to_image(text: str, text_color: str, bg_color: str, dpi: int = MATH_RENDER_DPI) -> Optional[Image.Image]:
    """Renders text (potentially with Matplotlib mathtext) to a PIL Image."""
    if not MATPLOTLIB_AVAILABLE or not PIL_AVAILABLE:
        return None
    if '$' not in text: # Basic check for math markup
         return None # Don't render if no math detected

    try:
        fig = plt.figure(figsize=(8, 1), dpi=dpi, facecolor=bg_color) # Start with a reasonable size

        # Render text centered in the figure
        # Use fig.text for positioning relative to the figure
        # We need to estimate the required figure size based on text extent
        # This is tricky; let's render first, then adjust.
        text_obj = fig.text(0.5, 0.5, text, ha='center', va='center',
                            fontsize=12, # Adjust font size as needed
                            color=text_color,
                            wrap=True) # Enable wrapping

        # --- Auto-adjust figure size to fit text tightly ---
        # Force draw to calculate text bounding box
        fig.canvas.draw()

        # Get bounding box in display coordinates
        bbox = text_obj.get_window_extent(renderer=fig.canvas.get_renderer())

        # Calculate required width and height in inches
        # Add some padding
        padding_inches = 0.1
        req_width = (bbox.width / dpi) + 2 * padding_inches
        req_height = (bbox.height / dpi) + 2 * padding_inches

        # Minimum size to avoid tiny images
        min_size_inches = 0.3
        req_width = max(req_width, min_size_inches)
        req_height = max(req_height, min_size_inches)


        # Resize figure
        fig.set_size_inches(req_width, req_height)

        # Re-center text in the *resized* figure
        text_obj.set_position((0.5, 0.5))
        text_obj.set_text(text) # Re-set text in case properties were lost


        # Save to an in-memory buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, facecolor=bg_color, edgecolor='none', bbox_inches='tight', pad_inches=padding_inches)
        buf.seek(0)

        # Close the figure to free memory
        plt.close(fig)

        # Load the image data using Pillow
        image = Image.open(buf)
        return image

    except Exception as e:
        print(f"Error rendering math text: {e}")
        # Ensure figure is closed even on error
        try:
             plt.close(fig)
        except:
             pass
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
        self.deck_data: List[Dict[str, Any]] = []
        self.due_cards: List[Dict[str, Any]] = []
        self.current_card_index: int = -1
        self.showing_answer: bool = False
        self.add_card_window: Optional[ctk.CTkToplevel] = None
        self.settings_window: Optional[ctk.CTkToplevel] = None
        self.stats_window: Optional[ctk.CTkToplevel] = None
        self.stats_figure_canvas: Optional[FigureCanvasTkAgg] = None
        self.stats_toolbar: Optional[NavigationToolbar2Tk] = None
        self._is_review_active: bool = False
        # Store theme colors for math rendering and UI elements
        self._update_theme_colors() # Initialize theme colors

        # Cache for rendered math images (optional, for performance)
        self._math_image_cache: Dict[str, CTkImage] = {}

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
                                       height=5, exportselection=False,
                                       borderwidth=1, relief="solid",
                                       highlightthickness=0)
        self.deck_listbox.pack(side="top", fill="x", expand=True, padx=5)
        self._update_listbox_colors() # Set initial colors

        # Frame for Load/Reload buttons
        self.deck_button_frame = ctk.CTkFrame(self.top_frame)
        self.deck_button_frame.pack(side="top", fill="x", pady=(5,0), padx=5)

        self.load_button = ctk.CTkButton(self.deck_button_frame, text="Load Selected Deck(s)", command=self.load_selected_decks)
        self.load_button.pack(side="left", padx=(0,5))

        self.reload_decks_button = ctk.CTkButton(self.deck_button_frame, text="Reload List", width=100, command=self.populate_deck_listbox)
        self.reload_decks_button.pack(side="left", padx=5)

        # Add/Settings/Stats buttons
        self.add_card_button = ctk.CTkButton(self.deck_button_frame, text="Add (A)", width=80, command=self.open_add_card_window, state="disabled")
        self.add_card_button.pack(side="left", padx=(15, 0))

        self.settings_button = ctk.CTkButton(self.deck_button_frame, text="Settings", width=80, command=self.open_settings_window, state="disabled")
        self.settings_button.pack(side="left", padx=(5, 0))

        self.stats_button = ctk.CTkButton(self.deck_button_frame, text="Stats", width=80, command=self.open_stats_window, state="disabled")
        self.stats_button.pack(side="left", padx=(5, 0))


        # Card Display Frame
        self.card_frame = ctk.CTkFrame(self.main_frame)
        self.card_frame.pack(pady=5, padx=10, fill="both", expand=True)

        # Labels will now display EITHER text OR a rendered math image
        self.front_label = ctk.CTkLabel(self.card_frame, text="Select deck(s) and click 'Load' to begin",
                                        font=ctk.CTkFont(size=20), wraplength=600,
                                        compound="center", # Allow image and text (though we'll clear text when image is shown)
                                        anchor="center") # Center content
        self.front_label.pack(pady=(15, 10), padx=10, fill="both", expand=True)

        self.back_label = ctk.CTkLabel(self.card_frame, text="",
                                       font=ctk.CTkFont(size=16), wraplength=600,
                                       compound="center", anchor="center")
        # Pack later when showing answer

        # Control Frame: Buttons
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.pack(pady=5, padx=10, fill="x")

        self.show_answer_button = ctk.CTkButton(self.control_frame, text="Show Answer (Space/Enter)", command=self.show_answer, state="disabled")
        self.show_answer_button.pack(side="top", pady=5)

        self.rating_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.again_button = ctk.CTkButton(self.rating_frame, text="Again (1)", command=lambda: self.rate_card(1), width=80, fg_color="#E53E3E", hover_color="#C53030")
        self.hard_button = ctk.CTkButton(self.rating_frame, text="Hard (2)", command=lambda: self.rate_card(2), width=80, fg_color="#DD6B20", hover_color="#C05621")
        self.good_button = ctk.CTkButton(self.rating_frame, text="Good (3/Space/Enter)", command=lambda: self.rate_card(3), width=140)
        self.easy_button = ctk.CTkButton(self.rating_frame, text="Easy (4)", command=lambda: self.rate_card(4), width=80, fg_color="#38A169", hover_color="#2F855A")

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
        self.populate_deck_listbox()
        self._setup_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # Track theme changes
        self._appearance_mode_tracker = ctk.StringVar(value=ctk.get_appearance_mode())
        self._appearance_mode_tracker.trace_add("write", self._handle_appearance_change)


    # --- Theme Handling ---
    def _handle_appearance_change(self, *args):
        """Update colors when system theme changes."""
        print("Appearance mode changed:", ctk.get_appearance_mode())
        self._update_theme_colors() # Update stored colors first
        self._update_listbox_colors() # Then update listbox using new colors
        # Re-render the current card if it's showing math
        if self._is_review_active and 0 <= self.current_card_index < len(self.due_cards):
             card = self.due_cards[self.current_card_index]
             self._display_label_content(self.front_label, card['front'])
             if self.showing_answer:
                 self._display_label_content(self.back_label, card['back'])
        # Update stats plot colors if window is open
        if self.stats_window and self.stats_window.winfo_exists() and MATPLOTLIB_AVAILABLE:
             # Re-create the chart with new theme colors
             try:
                 # Need the parent frame and current stats data
                 # Assuming self.stats_plot_frame and self.current_stats are stored or accessible
                 # For simplicity, let's just recalculate stats if needed.
                 current_stats = calculate_deck_statistics(self.deck_data, forecast_days=STATS_FORECAST_DAYS)
                 if hasattr(self, 'stats_plot_frame') and self.stats_plot_frame:
                     self._create_stats_chart(self.stats_plot_frame, current_stats)
                 else:
                     print("Warning: Cannot update stats plot theme - plot frame reference missing.")
             except Exception as e:
                 print(f"Error updating stats plot theme: {e}")


    def _update_theme_colors(self):
        """Reads current theme colors from the already loaded theme data."""
        # REMOVED: ctk.ThemeManager.load_theme() - Unnecessary and caused the error
        self._current_text_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        self._current_bg_color = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self._current_listbox_select_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["fg_color"])
        self._current_listbox_select_fg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["text_color"])
        # Clear math image cache as colors changed
        self._math_image_cache = {}


    def _update_listbox_colors(self):
        """Sets the colors for the Tkinter Listbox based on CURRENTLY STORED theme colors."""
        # Use the colors stored by _update_theme_colors
        # Ensure _update_theme_colors has been called at least once
        if not hasattr(self, '_current_text_color'):
             self._update_theme_colors()

        self.deck_listbox.configure(
            bg=self._current_bg_color, # Use stored frame background
            fg=self._current_text_color, # Use stored label text color
            selectbackground=self._current_listbox_select_bg, # Use stored button background
            selectforeground=self._current_listbox_select_fg # Use stored button text color
        )

    # Helper to get the correct color tuple element based on appearance mode
    def _apply_appearance_mode(self, color: Any) -> str:
        """Gets the light or dark mode color string from a CTk color tuple or returns string directly."""
        if isinstance(color, (list, tuple)) and len(color) >= 2:
            # 0 is light mode, 1 is dark mode
            mode_index = 1 if ctk.get_appearance_mode().lower() == "dark" else 0
            # Handle cases where one mode might be None (though unlikely in default themes)
            return color[mode_index] if color[mode_index] is not None else "#000000" # Fallback
        elif isinstance(color, str):
             return color # Already a single color string
        else:
             # Fallback if color format is unexpected (e.g., None)
             print(f"Warning: Unexpected color format '{color}'. Using fallback.")
             return "#FFFFFF" if ctk.get_appearance_mode().lower() == "light" else "#000000"


    # --- UI Update Methods ---
    def update_status(self, message: str):
        self.status_label.configure(text=message)

    def update_due_count(self):
        if self._is_review_active and self.due_cards and self.current_card_index < len(self.due_cards):
            remaining = len(self.due_cards) - self.current_card_index
            self.cards_due_label.configure(text=f"Due: {remaining}")
        elif self.current_deck_paths:
            current_due_count = len(get_due_cards(self.deck_data))
            self.cards_due_label.configure(text=f"Due Today: {current_due_count}")
            if current_due_count == 0 and not self._is_review_active and self.deck_data:
                 self.update_status("No cards due today in selected deck(s).")
        else:
            self.cards_due_label.configure(text="")

    def populate_deck_listbox(self):
        selected_indices = self.deck_listbox.curselection()
        self.available_decks = find_decks(self.decks_dir)
        self.deck_listbox.delete(0, tk.END)

        if not self.available_decks:
            self.deck_listbox.insert(tk.END, " No decks found in 'decks' folder ")
            self.deck_listbox.configure(state="disabled")
            self.load_button.configure(state="disabled")
            self.update_status(f"No decks found in '{self.decks_dir}'. Add CSV files there.")
            self.reset_session_state()
            self._display_label_content(self.front_label, "Add decks (.csv) to the 'decks' folder")
        else:
            self.deck_listbox.configure(state="normal")
            self.load_button.configure(state="normal")
            for deck_file in self.available_decks:
                deck_name = os.path.splitext(deck_file)[0]
                self.deck_listbox.insert(tk.END, f" {deck_name}")

            for index in selected_indices:
                if index < self.deck_listbox.size():
                     self.deck_listbox.selection_set(index)

            if not self.current_deck_paths:
                self.update_status(f"Found {len(self.available_decks)} deck(s). Select and click Load.")
                self.reset_session_state()
                self._display_label_content(self.front_label, "Select deck(s) and click 'Load' to begin")
            else:
                loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
                self.update_status(f"Loaded: {', '.join(loaded_deck_names)}")


    def _display_label_content(self, label: ctk.CTkLabel, content: str):
         """Sets label content, rendering math to image if needed."""
         # Cache key combines content and current theme colors
         cache_key = f"{content}|{self._current_text_color}|{self._current_bg_color}"

         # Ensure content is a string
         if not isinstance(content, str):
             content = str(content) # Convert just in case

         if MATPLOTLIB_AVAILABLE and PIL_AVAILABLE and '$' in content:
             # Check cache first
             if cache_key in self._math_image_cache:
                 ctk_image = self._math_image_cache[cache_key]
                 # print(f"Using cached math image for: {content[:30]}...") # Debug cache
             else:
                 # print(f"Rendering math image for: {content[:30]}...") # Debug render
                 pil_image = render_math_to_image(content, self._current_text_color, self._current_bg_color)
                 if pil_image:
                      ctk_image = CTkImage(light_image=pil_image, dark_image=pil_image, size=(pil_image.width, pil_image.height))
                      self._math_image_cache[cache_key] = ctk_image # Store in cache
                 else:
                      # Render failed, show error text instead
                      ctk_image = None
                      content = f"[Math Render Error]\n{content}" # Show error indication

             if ctk_image:
                 label.configure(image=ctk_image, text="") # Show image, clear text
                 return # Done

         # Fallback or no math detected: show plain text
         label.configure(text=content, image=None) # Clear image


    def display_card(self):
        """Updates the UI to show the current card's front."""
        if self.current_card_index < 0 or self.current_card_index >= len(self.due_cards):
            self._is_review_active = False
            loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
            deck_context = f"'{', '.join(loaded_deck_names)}'" if loaded_deck_names else "this session"
            total_due_today = len(get_due_cards(self.deck_data))

            message = ""
            if self.deck_data:
                 if total_due_today > 0:
                      message = f"Session complete for {deck_context}!\n({total_due_today} cards due today in total)"
                      self.update_status(f"Review session finished. Check back later or load other decks.")
                 else:
                      message = f"No more cards due today in {deck_context}!"
                      self.update_status(f"All cards reviewed for today!")
            else:
                 message = "Select deck(s) and click 'Load' to begin"
                 self.update_status("No deck loaded.")

            self._display_label_content(self.front_label, message)
            self._display_label_content(self.back_label, "") # Clear back label
            self.back_label.pack_forget()
            self.show_answer_button.pack(side="top", pady=5)
            self.show_answer_button.configure(state="disabled", text="Show Answer (Space/Enter)")
            self.rating_frame.pack_forget()
            self.update_due_count()
            self.focus_set()
            self.deck_listbox.focus_set()
            return

        # --- Display Current Card ---
        self._is_review_active = True
        self.showing_answer = False
        card = self.due_cards[self.current_card_index]

        # Display Front using the helper function
        self._display_label_content(self.front_label, card['front'])
        self.front_label.pack(pady=(15, 10), padx=10, fill="both", expand=True)

        # Hide Back and Rating Buttons, Show "Show Answer"
        self._display_label_content(self.back_label, "") # Clear back label
        self.back_label.pack_forget()
        self.rating_frame.pack_forget()
        self.show_answer_button.pack(side="top", pady=5)
        self.show_answer_button.configure(state="normal", text="Show Answer (Space/Enter)")

        self.update_status(f"Reviewing card {self.current_card_index + 1} of {len(self.due_cards)}")
        self.update_due_count()
        self.show_answer_button.focus_set()

    def show_answer(self):
        """Reveals the answer and shows rating buttons."""
        if not self._is_review_active or self.showing_answer: return
        if self.current_card_index < 0 or self.current_card_index >= len(self.due_cards):
            self.display_card(); return

        self.showing_answer = True
        card = self.due_cards[self.current_card_index]

        # Display Back Label using the helper function
        self._display_label_content(self.back_label, card['back'])
        self.back_label.pack(pady=(5, 15), padx=10, fill="x") # Pack below front

        # Hide "Show Answer", Show Rating Buttons
        self.show_answer_button.pack_forget()
        self.rating_frame.pack(side="top", pady=5, fill="x", padx=20)

        self.update_status("Rate your recall difficulty.")
        self.good_button.focus_set()

    def rate_card(self, quality: int):
        """Processes the user's rating, updates schedule, and moves to the next card."""
        if not self._is_review_active or not self.showing_answer: return

        if 0 <= self.current_card_index < len(self.due_cards):
            card = self.due_cards[self.current_card_index]
            update_card_schedule(card, quality)

            if quality == 1: # Again
                card_to_repeat = self.due_cards.pop(self.current_card_index)
                insert_pos = min(self.current_card_index + 5, len(self.due_cards))
                self.due_cards.insert(insert_pos, card_to_repeat)
                self.update_status(f"Card marked 'Again'. Will see again shortly.")
            else: # Hard, Good, Easy
                self.current_card_index += 1

            self.display_card()
        else:
            print("Error: Tried to rate card with invalid index.")
            self.display_card()


    # --- Deck Management ---
    def load_selected_decks(self):
        selected_indices = self.deck_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select one or more decks from the list.")
            return

        selected_paths = [os.path.join(self.decks_dir, self.available_decks[i]) for i in selected_indices]
        selected_names = [os.path.splitext(self.available_decks[i])[0] for i in selected_indices]

        self.save_all_dirty_cards()

        self.update_status(f"Loading deck(s): {', '.join(selected_names)}...")
        self.current_deck_paths = []
        self.deck_data = []
        load_errors = False
        self._math_image_cache = {} # Clear cache when loading new deck

        for i, filepath in enumerate(selected_paths):
            deck_name = selected_names[i]
            print(f"Loading: {filepath}")
            single_deck = load_deck(filepath)
            if single_deck is None:
                load_errors = True
                self.update_status(f"Error loading '{deck_name}'. Check console/log.")
            elif not single_deck and os.path.exists(filepath):
                 messagebox.showwarning("Empty Deck", f"Deck '{deck_name}' ({os.path.basename(filepath)}) is empty or could not be read properly.")
                 self.current_deck_paths.append(filepath)
            elif single_deck:
                for card in single_deck: card['deck_filepath'] = filepath
                self.deck_data.extend(single_deck)
                self.current_deck_paths.append(filepath)

        if not self.deck_data and not load_errors:
             messagebox.showwarning("No Cards", "Selected deck(s) contain no valid flashcards.")
             self.reset_session_state()
             self._display_label_content(self.front_label, "Selected deck(s) are empty.")
             self.update_status("Load failed or deck(s) empty.")
             return

        if load_errors and not self.deck_data:
             messagebox.showerror("Load Failed", "Failed to load any cards. Check CSV format and file permissions.")
             self.reset_session_state()
             self._display_label_content(self.front_label, "Failed to load deck(s).")
             self.update_status("Load failed.")
             return

        self.due_cards = get_due_cards(self.deck_data)
        random.shuffle(self.due_cards)
        self.current_card_index = 0
        self._is_review_active = True

        self.add_card_button.configure(state="normal")
        self.settings_button.configure(state="normal")
        self.stats_button.configure(state="normal")

        if not self.due_cards:
            self._is_review_active = False
            self.update_status(f"Loaded {len(self.deck_data)} card(s) from {len(self.current_deck_paths)} deck(s). No cards due now.")
            self._display_label_content(self.front_label, f"No cards due right now in '{', '.join(selected_names)}'.")
            self.show_answer_button.configure(state="disabled")
        else:
            self.update_status(f"Loaded {len(self.deck_data)} card(s). Starting review with {len(self.due_cards)} due card(s).")
            self.display_card()

        self.update_due_count()


    def save_all_dirty_cards(self):
        dirty_cards_by_file = defaultdict(list)
        for card in self.deck_data:
            if card.get('_dirty', False):
                filepath = card.get('deck_filepath')
                if filepath:
                    dirty_cards_by_file[filepath].append(card)
                else:
                    print(f"Warning: Dirty card missing 'deck_filepath'. Cannot save: {card.get('front', 'N/A')}")

        if not dirty_cards_by_file: return

        print(f"Saving changes to {len(dirty_cards_by_file)} file(s)...")
        saved_files = 0
        for filepath, cards_to_save in dirty_cards_by_file.items():
             full_deck_for_file = [c for c in self.deck_data if c.get('deck_filepath') == filepath]
             if not full_deck_for_file:
                  print(f"Warning: Could not find full deck data for saving '{os.path.basename(filepath)}'. Skipping.")
                  continue
             print(f"Saving {len(cards_to_save)} modified card(s) to {os.path.basename(filepath)} (out of {len(full_deck_for_file)} total in file)...")
             save_deck(filepath, full_deck_for_file)
             saved_files += 1

        if saved_files > 0:
             self.update_status(f"Saved changes to {saved_files} deck file(s).")


    def reset_session_state(self):
        self.save_all_dirty_cards()
        self.current_deck_paths = []
        self.deck_data = []
        self.due_cards = []
        self.current_card_index = -1
        self.showing_answer = False
        self._is_review_active = False
        self._math_image_cache = {} # Clear cache
        self.add_card_button.configure(state="disabled")
        self.settings_button.configure(state="disabled")
        self.stats_button.configure(state="disabled")
        self.show_answer_button.configure(state="disabled")
        self.rating_frame.pack_forget()
        self.update_due_count()


    # --- Window Management ---
    def open_add_card_window(self):
        if self.add_card_window is not None and self.add_card_window.winfo_exists():
            self.add_card_window.focus(); return

        if not self.current_deck_paths:
             messagebox.showerror("Error", "Please load at least one deck before adding a card."); return
        elif len(self.current_deck_paths) > 1:
             messagebox.showwarning("Multiple Decks", "Multiple decks loaded. Card will be added to the *first* loaded deck:\n" + os.path.basename(self.current_deck_paths[0]))

        target_deck_path = self.current_deck_paths[0]

        self.add_card_window = ctk.CTkToplevel(self)
        self.add_card_window.title("Add New Card")
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

        button_frame = ctk.CTkFrame(self.add_card_window)
        button_frame.pack(pady=(10, 10), padx=10, fill="x")

        def submit_card():
            front = front_entry.get("1.0", tk.END).strip()
            back = back_entry.get("1.0", tk.END).strip()
            if not front or not back:
                messagebox.showerror("Error", "Both Front and Back fields are required.", parent=self.add_card_window); return

            new_card = {
                'front': front, 'back': back, 'next_review_date': None,
                'interval_days': 0.0, 'deck_filepath': target_deck_path, '_dirty': True
            }
            self.deck_data.append(new_card)
            self.update_status(f"Added new card to '{os.path.basename(target_deck_path)}'.")
            self.update_due_count()
            self.save_all_dirty_cards() # Save immediately

            front_entry.delete("1.0", tk.END)
            back_entry.delete("1.0", tk.END)
            front_entry.focus_set()

        def cancel_add(): self.add_card_window.destroy()

        add_button = ctk.CTkButton(button_frame, text="Add Card", command=submit_card)
        add_button.pack(side="left", padx=(0, 10), expand=True)
        cancel_button = ctk.CTkButton(button_frame, text="Close", command=cancel_add, fg_color="gray")
        cancel_button.pack(side="right", padx=(10, 0), expand=True)

        front_entry.bind("<Return>", lambda event: submit_card())
        back_entry.bind("<Return>", lambda event: submit_card())
        self.add_card_window.bind("<Escape>", lambda event: cancel_add())
        front_entry.focus_set()


    def open_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus(); return

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("Settings")
        self.settings_window.geometry("300x200")
        self.settings_window.transient(self)
        self.settings_window.grab_set()
        self.center_toplevel(self.settings_window)

        ctk.CTkLabel(self.settings_window, text="Settings (Placeholder)").pack(pady=20)
        close_button = ctk.CTkButton(self.settings_window, text="Close", command=self.settings_window.destroy)
        close_button.pack(pady=10)
        self.settings_window.bind("<Escape>", lambda event: self.settings_window.destroy())


    def open_stats_window(self):
        if not self.deck_data:
            messagebox.showinfo("Statistics", "No deck data loaded to calculate statistics."); return
        if self.stats_window is not None and self.stats_window.winfo_exists():
            self.stats_window.focus(); return

        self.stats_window = ctk.CTkToplevel(self)
        self.stats_window.title("Deck Statistics")
        self.stats_window.geometry("800x650")
        self.stats_window.transient(self)
        self.center_toplevel(self.stats_window)
        self.stats_window.protocol("WM_DELETE_WINDOW", self._on_stats_close)

        stats_main_frame = ctk.CTkFrame(self.stats_window)
        stats_main_frame.pack(pady=10, padx=10, fill="both", expand=True)
        text_stats_frame = ctk.CTkFrame(stats_main_frame)
        text_stats_frame.pack(pady=5, padx=5, fill="x")
        plot_frame = ctk.CTkFrame(stats_main_frame)
        plot_frame.pack(pady=5, padx=5, fill="both", expand=True)
        self.stats_plot_frame = plot_frame # Store reference for theme updates

        stats = calculate_deck_statistics(self.deck_data, forecast_days=STATS_FORECAST_DAYS)
        # self.current_stats = stats # Store stats if needed for theme update redraw

        stats_text_widget = ctk.CTkTextbox(text_stats_frame, wrap="word", height=200, activate_scrollbars=True)
        stats_text_widget.pack(pady=5, padx=5, fill="x")
        stats_text_widget.configure(state="normal")
        stats_text_widget.delete("1.0", tk.END)

        loaded_deck_names = [os.path.splitext(os.path.basename(p))[0] for p in self.current_deck_paths]
        stats_text_widget.insert(tk.END, f"Statistics for Deck(s): {', '.join(loaded_deck_names)}\n")
        stats_text_widget.insert(tk.END, f"----------------------------------------\n")
        stats_text_widget.insert(tk.END, f"Total Cards:\t\t{stats['total_cards']}\n")
        stats_text_widget.insert(tk.END, f"  - New Cards:\t\t{stats['new_cards']}\n")
        stats_text_widget.insert(tk.END, f"  - Learning Cards (<{21}d):\t{stats['learning_cards']}\n")
        stats_text_widget.insert(tk.END, f"  - Young Cards (<{90}d):\t{stats['young_cards']}\n")
        stats_text_widget.insert(tk.END, f"  - Mature Cards (>= {90}d):\t{stats['mature_cards']}\n")
        stats_text_widget.insert(tk.END, f"Average Interval (Mature):\t{stats['average_interval_mature']} days\n\n")
        stats_text_widget.insert(tk.END, f"Due Today:\t\t{stats['due_today']}\n")
        stats_text_widget.insert(tk.END, f"Due Tomorrow:\t\t{stats['due_tomorrow']}\n")
        stats_text_widget.insert(tk.END, f"Due in Next 7 Days:\t{stats['due_next_7_days']} (excluding today)\n")
        stats_text_widget.insert(tk.END, f"----------------------------------------\n")
        stats_text_widget.configure(state="disabled")

        if MATPLOTLIB_AVAILABLE:
            try:
                self._create_stats_chart(plot_frame, stats)
            except Exception as e:
                 error_label = ctk.CTkLabel(plot_frame, text=f"Error creating plot: {e}", text_color="red")
                 error_label.pack(pady=10)
                 print(f"Matplotlib Error: {e}")
        else:
            no_mpl_label = ctk.CTkLabel(plot_frame, text="Matplotlib not installed. Plotting disabled.\n(Run: pip install matplotlib)", text_color="orange")
            no_mpl_label.pack(pady=20)

        close_button = ctk.CTkButton(stats_main_frame, text="Close", command=self._on_stats_close)
        close_button.pack(pady=(5, 10))
        self.stats_window.bind("<Escape>", lambda event: self._on_stats_close())


    def _create_stats_chart(self, parent_frame: ctk.CTkFrame, stats: Dict[str, Any]):
        """Creates and embeds the Matplotlib forecast chart."""
        # Clear previous widgets in the parent frame before drawing new ones
        for widget in parent_frame.winfo_children():
            widget.destroy()
        self.stats_figure_canvas = None # Reset references
        self.stats_toolbar = None

        forecast_data = stats.get("due_counts_forecast", {})
        if not forecast_data:
            ctk.CTkLabel(parent_frame, text="No forecast data available.").pack(pady=10); return

        dates = list(forecast_data.keys())
        counts = list(forecast_data.values())
        cumulative_counts = [sum(counts[:i+1]) for i in range(len(counts))]

        # Get current theme colors for the plot using the stored values
        plot_bg_color = self._current_bg_color
        plot_text_color = self._current_text_color
        bar_color = "#1f77b4" # Example blue
        line_color = "#ff7f0e" # Example orange

        fig = Figure(figsize=(7, 4), dpi=100, facecolor=plot_bg_color)
        ax1 = fig.add_subplot(111)
        ax1.set_facecolor(plot_bg_color) # Set axes background too

        ax1.bar(dates, counts, label='Cards Due Daily', color=bar_color, width=0.7)
        ax1.set_xlabel("Date", color=plot_text_color)
        ax1.set_ylabel("Cards Due", color=bar_color)
        ax1.tick_params(axis='y', labelcolor=bar_color, colors=plot_text_color) # Label color vs tick text color
        ax1.tick_params(axis='x', rotation=45, colors=plot_text_color)
        ax1.grid(True, axis='y', linestyle='--', alpha=0.6, color=plot_text_color)

        ax2 = ax1.twinx()
        ax2.plot(dates, cumulative_counts, label='Cumulative Due', color=line_color, marker='.', linestyle='-')
        ax2.set_ylabel("Total Cumulative Cards", color=line_color)
        ax2.tick_params(axis='y', labelcolor=line_color, colors=plot_text_color)

        fig.suptitle("Review Forecast", color=plot_text_color)
        ax1.set_title(f"Next {STATS_FORECAST_DAYS} Days", fontsize=10, color=plot_text_color)

        # Set spine colors
        for spine in ax1.spines.values(): spine.set_edgecolor(plot_text_color)
        for spine in ax2.spines.values(): spine.set_edgecolor(plot_text_color)

        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        self.stats_figure_canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas_widget = self.stats_figure_canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.stats_toolbar = NavigationToolbar2Tk(self.stats_figure_canvas, parent_frame, pack_toolbar=False)
        # --- Try to style toolbar (basic) ---
        try:
             # Use a background color that contrasts well in both light/dark
             toolbar_bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["bg_color"]) # e.g., window background
             toolbar_fg = plot_text_color
             self.stats_toolbar.configure(background=toolbar_bg)
             # Style toolbar buttons if possible (might depend on Tk version/theme)
             for item in self.stats_toolbar.winfo_children():
                 try:
                     item.configure(bg=toolbar_bg, fg=toolbar_fg)
                     # For ttk buttons, styling might differ
                     if hasattr(item, 'style'):
                          pass # More complex ttk styling could go here
                 except tk.TclError:
                     pass # Ignore widgets that don't support bg/fg config
        except Exception as e:
             print(f"Minor error styling toolbar: {e}") # Non-critical
        # --- End toolbar styling ---
        self.stats_toolbar.update()
        self.stats_toolbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.stats_figure_canvas.draw()


    def _on_stats_close(self):
        if self.stats_figure_canvas:
            try:
                # Destroy Tkinter widgets first
                self.stats_figure_canvas.get_tk_widget().destroy()
                if self.stats_toolbar: self.stats_toolbar.destroy()
                # Then clean up Matplotlib figure
                plt.close(self.stats_figure_canvas.figure)
            except Exception as e: print(f"Error closing stats canvas/toolbar: {e}")

        self.stats_figure_canvas = None
        self.stats_toolbar = None
        self.stats_plot_frame = None # Clear reference
        if self.stats_window:
            try: self.stats_window.destroy()
            except Exception as e: print(f"Error closing stats window: {e}")
        self.stats_window = None


    def center_toplevel(self, window: ctk.CTkToplevel):
         window.update_idletasks()
         main_x, main_y = self.winfo_x(), self.winfo_y()
         main_w, main_h = self.winfo_width(), self.winfo_height()
         win_w, win_h = window.winfo_width(), window.winfo_height()
         x = main_x + (main_w // 2) - (win_w // 2)
         y = main_y + (main_h // 2) - (win_h // 2)
         window.geometry(f"+{x}+{y}")


    # --- Event Handling & Shortcuts ---
    def _setup_shortcuts(self):
        self.bind("<KeyPress>", self._handle_keypress)

    def _handle_keypress(self, event):
        active_grab = self.grab_current()
        if active_grab and active_grab != self:
             if event.widget.winfo_toplevel() == active_grab: return
             else: return

        key_sym = event.keysym
        is_space = key_sym == "space"
        is_return = key_sym == "Return"
        is_a = key_sym.lower() == "a"

        # Global: Add Card
        if is_a and self.add_card_button.cget("state") == "normal":
            self.open_add_card_window(); return

        # Review Shortcuts
        if not self._is_review_active: return

        if is_space or is_return:
            if self.showing_answer: self.rate_card(3) # Rate Good
            else: self.show_answer()
            return

        if key_sym in ('1', '2', '3', '4') and self.showing_answer:
             self.rate_card(int(key_sym)); return


    def on_close(self):
        self.save_all_dirty_cards()
        if self.stats_window is not None and self.stats_window.winfo_exists():
             self._on_stats_close()
        self.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    # Basic checks for dependencies needed for math rendering
    if not PIL_AVAILABLE:
        try:
            root = ctk.CTk(); root.withdraw() # Need a root for messagebox
            messagebox.showwarning("Missing Dependency", "Pillow library not found. Math rendering disabled.\nInstall using: pip install Pillow")
            root.destroy()
        except Exception as e: print(f"Error showing Pillow warning: {e}")
        # Continue without math rendering
    if not MATPLOTLIB_AVAILABLE:
         try:
             root = ctk.CTk(); root.withdraw()
             messagebox.showwarning("Missing Dependency", "Matplotlib library not found. Stats and Math rendering disabled.\nInstall using: pip install matplotlib")
             root.destroy()
         except Exception as e: print(f"Error showing Matplotlib warning: {e}")
         # Continue without stats/math

    find_decks(DECKS_DIR) # Ensure decks directory exists

    app = FlashcardApp()
    app.mainloop()

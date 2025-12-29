#!/usr/bin/env python3
"""KeyRGB Per-Key Editor.

GUI for setting individual key colors with proper keyboard layout.
"""

import logging
import os
import sys
from pathlib import Path


logger = logging.getLogger(__name__)

# Prefer the installed dependency. If running from a repo checkout without
# installing dependencies, fall back to the vendored copy.
try:
    from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS
except Exception:
    repo_root = Path(__file__).resolve().parent.parent
    vendored_candidates = [
        repo_root / "vendor" / "ite8291r3-ctl",
        repo_root / "ite8291r3-ctl",  # legacy layout
    ]
    for vendored in vendored_candidates:
        if vendored.exists():
            sys.path.insert(0, str(vendored))
            break
    from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS

import tkinter as tk
from tkinter import ttk, colorchooser



class PerKeyEditor:
    """Per-key color editor with 6x21 grid layout"""
    
    def __init__(self):
        self.kb = get()
        self.current_color = (255, 0, 0)  # Default red
        self.colors = {}  # Store colors for each (row, col)
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("KeyRGB Per-Key Editor")
        self.root.geometry("1100x500")
        
        self._create_ui()
        
        # Draw grid after window is shown
        self.root.after(100, self._draw_keyboard_grid)
    
    def _create_ui(self):
        """Create user interface"""
        # Top toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Color picker button
        self.color_button = tk.Button(
            toolbar,
            text="Choose Color",
            command=self._choose_color,
            bg='#ff0000',
            fg='white',
            width=15,
            font=('Arial', 10, 'bold')
        )
        self.color_button.pack(side=tk.LEFT, padx=5)
        
        # Current color label
        self.color_label = ttk.Label(toolbar, text="Color: RGB(255, 0, 0)", font=('Arial', 10))
        self.color_label.pack(side=tk.LEFT, padx=10)
        
        # Quick colors
        ttk.Label(toolbar, text="Quick:", font=('Arial', 10)).pack(side=tk.LEFT, padx=(20, 5))
        for name, color in [
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("Yellow", (255, 255, 0)),
            ("Purple", (255, 0, 255)),
            ("Cyan", (0, 255, 255)),
            ("White", (255, 255, 255)),
            ("Off", (0, 0, 0))
        ]:
            btn = tk.Button(
                toolbar,
                text=name,
                command=lambda c=color: self._set_quick_color(c),
                width=7
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # Main canvas for keyboard layout
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add scrollbar
        scrollbar_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollbar_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#2a2a2a',
            highlightthickness=0,
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        scrollbar_y.config(command=self.canvas.yview)
        scrollbar_x.config(command=self.canvas.xview)
        
        # Info label
        info_frame = ttk.Frame(self.root)
        info_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        ttk.Label(info_frame, 
                 text=f"Click any key to apply current color. Layout: {NUM_ROWS} rows x {NUM_COLS} cols = {NUM_ROWS * NUM_COLS} keys", 
                 font=('Arial', 9)).pack(side=tk.LEFT)
        
        # Bottom buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Fill All", command=self._fill_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All", command=self._clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Apply Colors", command=self._apply_colors).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.root.quit).pack(side=tk.RIGHT, padx=5)
    
    def _draw_keyboard_grid(self):
        """Draw keyboard grid (6 rows x 21 cols)"""
        print(f"Drawing keyboard grid ({NUM_ROWS} rows x {NUM_COLS} cols)...")
        
        self.key_boxes = {}
        
        # Fixed box size for better visibility
        box_width = 40
        box_height = 40
        gap = 3
        
        start_x = 10
        start_y = 10
        
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                x1 = start_x + col * (box_width + gap)
                y1 = start_y + row * (box_height + gap)
                x2 = x1 + box_width
                y2 = y1 + box_height
                
                # Create rectangle with visible default color
                box = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill='#444444',
                    outline='#777777',
                    width=2,
                    tags=f'key_{row}_{col}'
                )
                
                # Add position label
                text = self.canvas.create_text(
                    x1 + box_width // 2,
                    y1 + box_height // 2,
                    text=f'{row},{col}',
                    fill='#aaaaaa',
                    font=('Arial', 8),
                    tags=f'key_{row}_{col}'
                )
                
                self.key_boxes[(row, col)] = box
                
                # Bind click event
                self.canvas.tag_bind(f'key_{row}_{col}', '<Button-1>', 
                                   lambda e, r=row, c=col: self._on_key_click(r, c))
                
                # Hover effect
                self.canvas.tag_bind(f'key_{row}_{col}', '<Enter>',
                                   lambda e, r=row, c=col: self.canvas.itemconfig(self.key_boxes[(r, c)], width=3))
                self.canvas.tag_bind(f'key_{row}_{col}', '<Leave>',
                                   lambda e, r=row, c=col: self.canvas.itemconfig(self.key_boxes[(r, c)], width=2))
        
        # Set canvas scroll region
        self.canvas.config(scrollregion=self.canvas.bbox('all'))
        
        print(f"Drew {len(self.key_boxes)} key boxes")
    
    def _choose_color(self):
        """Open color picker dialog"""
        color = colorchooser.askcolor(
            title="Choose key color",
            initialcolor=self.current_color
        )
        if color[0]:  # If user didn't cancel
            self.current_color = tuple(int(c) for c in color[0])
            self._update_color_display()
    
    def _set_quick_color(self, color):
        """Set quick color"""
        self.current_color = color
        self._update_color_display()
    
    def _update_color_display(self):
        """Update color button and label"""
        r, g, b = self.current_color
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        
        # Choose button text color for visibility
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = 'black' if brightness > 128 else 'white'
        
        self.color_button.config(bg=hex_color, fg=text_color)
        self.color_label.config(text=f"Color: RGB({r}, {g}, {b})")
    
    def _on_key_click(self, row, col):
        """Handle key click"""
        print(f"Key ({row}, {col}) clicked")
        
        # Store color
        self.colors[(row, col)] = self.current_color
        
        # Update canvas display
        r, g, b = self.current_color
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        self.canvas.itemconfig(self.key_boxes[(row, col)], fill=hex_color)
        
        # Update text color for visibility
        text_items = self.canvas.find_withtag(f'key_{row}_{col}')
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = '#000000' if brightness > 128 else '#ffffff'
        for item in text_items:
            if self.canvas.type(item) == 'text':
                self.canvas.itemconfig(item, fill=text_color)
    
    def _fill_all(self):
        """Fill all keys with current color"""
        print("Filling all keys")
        r, g, b = self.current_color
        
        # Store color for all keys
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.colors[(row, col)] = self.current_color
        
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        
        # Update all boxes
        for (row, col), box in self.key_boxes.items():
            self.canvas.itemconfig(box, fill=hex_color)
            
            # Update text colors
            text_items = self.canvas.find_withtag(f'key_{row}_{col}')
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            text_color = '#000000' if brightness > 128 else '#ffffff'
            for item in text_items:
                if self.canvas.type(item) == 'text':
                    self.canvas.itemconfig(item, fill=text_color)
        
        # Apply to hardware
        self._apply_colors()
    
    def _clear_all(self):
        """Clear all keys (turn off)"""
        print("Clearing all keys")
        self.kb.turn_off()
        self.colors.clear()
        
        for (row, col), box in self.key_boxes.items():
            self.canvas.itemconfig(box, fill='#444444')
            
            # Reset text colors
            text_items = self.canvas.find_withtag(f'key_{row}_{col}')
            for item in text_items:
                if self.canvas.type(item) == 'text':
                    self.canvas.itemconfig(item, fill='#aaaaaa')
    
    def _apply_colors(self):
        """Apply stored colors to keyboard"""
        if not self.colors:
            print("No colors to apply")
            return
        
        print(f"Applying {len(self.colors)} key colors...")
        
        try:
            # Enable user mode and apply all colors at once
            self.kb.set_key_colors(self.colors, brightness=25, save=False)
            print("Colors applied successfully")
        except Exception as e:
            if os.environ.get("KEYRGB_DEBUG"):
                logger.exception("Error applying colors")
            else:
                logger.error("Error applying colors: %s", e)
    
    def run(self):
        """Run the editor"""
        self.root.mainloop()


def main():
    """Main entry point"""
    level = logging.DEBUG if os.environ.get("KEYRGB_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    try:
        editor = PerKeyEditor()
        editor.run()
    except Exception as e:
        if os.environ.get("KEYRGB_DEBUG"):
            logger.exception("Unhandled error")
        else:
            logger.error("Unhandled error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()

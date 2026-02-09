"""
Floating overlay window for displaying live transcription text.
Frameless, borderless, dynamic height. Shows on demand and auto-hides.
"""

import tkinter as tk
import tkinter.font as tkfont


class FloatingOverlay:
    """
    Manages a floating, always-on-top, frameless overlay window
    for displaying live transcription text.
    Shows automatically when new text arrives, hides after 3 seconds.
    """

    def __init__(self, parent):
        self.parent = parent
        self.overlay = None
        self.text_widget = None
        self.is_visible = False
        self.max_lines = 10
        self.opacity = 0.90
        self.width = 400
        self.position = 'bottom-right'
        self.font_size = 11
        self._hide_timer = None
        self._font = None
        # Cached bottom-right anchor point (set once during positioning)
        self._anchor_x = 0
        self._anchor_y = 0

    def create_overlay(self, settings):
        """Create and configure the overlay window."""
        if self.overlay is not None:
            return

        # Load settings
        self.opacity = settings.get('overlay_opacity', 0.90)
        self.width = settings.get('overlay_width', 400)
        self.position = settings.get('overlay_position', 'bottom-right')
        self.max_lines = settings.get('overlay_max_lines', 10)
        self.font_size = settings.get('overlay_font_size', 11)

        # Create toplevel window
        self.overlay = tk.Toplevel(self.parent.root)

        # Frameless, borderless
        self.overlay.overrideredirect(True)

        # Configure window attributes
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-alpha', self.opacity)

        # Prevent overlay from stealing focus (WS_EX_NOACTIVATE)
        self.overlay.update_idletasks()
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOPMOST = 0x00000008
            hwnd = ctypes.windll.user32.GetParent(self.overlay.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        except Exception:
            pass

        # Configure dark theme
        self.overlay.configure(bg='#1e1e1e')

        # Create font for measurement
        self._font = tkfont.Font(family='Consolas', size=self.font_size)

        # Create text widget (no scrollbar — compact popup)
        self.text_widget = tk.Text(
            self.overlay,
            wrap=tk.WORD,
            bg='#1e1e1e',
            fg='white',
            font=self._font,
            insertbackground='white',
            relief=tk.FLAT,
            padx=10,
            pady=8,
            borderwidth=0,
            highlightthickness=0,
            cursor='arrow',
            state=tk.DISABLED
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Make window draggable
        self._make_draggable()

        # Calculate anchor position
        self._calculate_anchor()

        # Start hidden with minimal size
        initial_height = self._font.metrics('linespace') + 16
        self.overlay.geometry(f'{self.width}x{initial_height}+{self._anchor_x}+{self._anchor_y}')
        self.overlay.withdraw()
        self.is_visible = False

    def _calculate_anchor(self):
        """Calculate the anchor point based on position setting."""
        padding = 20

        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            work_left = rect.left
            work_top = rect.top
            work_right = rect.right
            work_bottom = rect.bottom
        except Exception:
            work_left = 0
            work_top = 0
            work_right = self.parent.root.winfo_screenwidth()
            work_bottom = self.parent.root.winfo_screenheight() - 48

        # Anchor = bottom-right corner of overlay area
        if 'right' in self.position:
            self._anchor_x = work_right - self.width - padding
        else:
            self._anchor_x = work_left + padding

        if 'top' in self.position:
            self._anchor_y = work_top + padding
        else:
            # Bottom positions: anchor_y is the bottom edge
            self._anchor_y = work_bottom - padding

    def _make_draggable(self):
        """Make the overlay window draggable."""
        self._drag_data = {'x': 0, 'y': 0}
        self._custom_position = False

        def on_press(event):
            self._drag_data['x'] = event.x
            self._drag_data['y'] = event.y

        def on_drag(event):
            x = self.overlay.winfo_x() + event.x - self._drag_data['x']
            y = self.overlay.winfo_y() + event.y - self._drag_data['y']
            self.overlay.geometry(f'+{x}+{y}')
            self._custom_position = True

        self.overlay.bind('<Button-1>', on_press)
        self.overlay.bind('<B1-Motion>', on_drag)
        self.text_widget.bind('<Button-1>', on_press)
        self.text_widget.bind('<B1-Motion>', on_drag)

    def update_text(self, text):
        """Update overlay text (thread-safe). Shows overlay and resets auto-hide timer."""
        if self.overlay is None:
            return
        self.parent.root.after(0, self._update_text_impl, text)

    def _update_text_impl(self, text):
        """Internal: update text, resize, show, and schedule auto-hide."""
        if self.text_widget is None:
            return

        # Insert text
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, text)

        # Trim to max_lines
        line_count = int(self.text_widget.index('end-1c').split('.')[0])
        if line_count > self.max_lines:
            lines_to_delete = line_count - self.max_lines
            self.text_widget.delete('1.0', f'{lines_to_delete + 1}.0')

        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)

        # Calculate dynamic height
        line_count = int(self.text_widget.index('end-1c').split('.')[0])
        line_height = self._font.metrics('linespace')
        padding = 16  # top + bottom pady
        new_height = line_count * line_height + padding
        max_height = 300
        new_height = max(line_height + padding, min(new_height, max_height))

        # Position: grow upward from bottom anchor (or keep custom drag position)
        if not self._custom_position:
            if 'bottom' in self.position:
                y = self._anchor_y - new_height
            else:
                y = self._anchor_y
            self.overlay.geometry(f'{self.width}x{new_height}+{self._anchor_x}+{y}')
        else:
            # Keep x,y but update height
            x = self.overlay.winfo_x()
            y = self.overlay.winfo_y()
            self.overlay.geometry(f'{self.width}x{new_height}+{x}+{y}')

        # Show overlay
        if not self.is_visible:
            self.overlay.deiconify()
            self.is_visible = True

        # Reset auto-hide timer (3 seconds)
        if self._hide_timer:
            self.parent.root.after_cancel(self._hide_timer)
        self._hide_timer = self.parent.root.after(3000, self._auto_hide)

    def _auto_hide(self):
        """Auto-hide overlay after timeout."""
        if self.overlay and self.is_visible:
            self.overlay.withdraw()
            self.is_visible = False
        self._hide_timer = None

    def clear_text(self):
        """Clear all text from overlay."""
        if self.text_widget is not None:
            self.parent.root.after(0, self._clear_text_impl)

    def _clear_text_impl(self):
        """Internal: clear text (runs in main thread)."""
        if self.text_widget is not None:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.config(state=tk.DISABLED)

    def toggle_visibility(self):
        """Toggle overlay window visibility."""
        if self.overlay is None:
            return

        if self.is_visible:
            self.overlay.withdraw()
            self.is_visible = False
            # Cancel auto-hide timer
            if self._hide_timer:
                self.parent.root.after_cancel(self._hide_timer)
                self._hide_timer = None
        else:
            self.overlay.deiconify()
            self.is_visible = True

    def destroy(self):
        """Cleanup and destroy overlay window."""
        if self._hide_timer:
            try:
                self.parent.root.after_cancel(self._hide_timer)
            except Exception:
                pass
            self._hide_timer = None
        if self.overlay is not None:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
            self.text_widget = None
            self.is_visible = False

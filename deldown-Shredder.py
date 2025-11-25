#!/usr/bin/env python3
"""
deldown shredder
Ein sicherer Dateischredder mit moderner blauer Benutzeroberfläche.
Funktioniert auf Windows und Linux (Debian/GNOME).
"""

import os
import sys
import random
import threading
import platform
from pathlib import Path
from typing import List, Callable
import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ShredderEngine:
    """Core shredding engine with multiple overwrite methods"""
    
    # Shredding patterns
    PATTERNS = {
        "quick": 1,      # 1 pass random
        "secure": 3,     # 3 pass (DoD short)
        "dod": 7,        # DoD 5220.22-M (7 passes)
        "gutmann": 35,   # Gutmann method (35 passes)
    }
    
    @staticmethod
    def get_file_size(filepath: str) -> int:
        """Get file size in bytes"""
        return os.path.getsize(filepath)
    
    @staticmethod
    def generate_pattern(size: int, pass_num: int) -> bytes:
        """Generate overwrite pattern based on pass number"""
        if pass_num % 3 == 0:
            return bytes([0x00] * size)  # All zeros
        elif pass_num % 3 == 1:
            return bytes([0xFF] * size)  # All ones
        else:
            return bytes([random.randint(0, 255) for _ in range(size)])  # Random
    
    @classmethod
    def shred_file(
        cls,
        filepath: str,
        method: str = "secure",
        progress_callback: Callable[[float, str], None] = None,
        chunk_size: int = 1024 * 1024  # 1MB chunks
    ) -> bool:
        """
        Securely shred a file by overwriting with patterns
        
        Args:
            filepath: Path to file to shred
            method: Shredding method (quick, secure, dod, gutmann)
            progress_callback: Callback for progress updates (0-100, status_text)
            chunk_size: Size of chunks to write at a time
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.isfile(filepath):
                return False
            
            file_size = cls.get_file_size(filepath)
            passes = cls.PATTERNS.get(method, 3)
            
            # Open file for binary write
            for pass_num in range(passes):
                with open(filepath, "r+b") as f:
                    bytes_written = 0
                    
                    while bytes_written < file_size:
                        remaining = file_size - bytes_written
                        current_chunk = min(chunk_size, remaining)
                        
                        # Generate and write pattern
                        pattern = cls.generate_pattern(current_chunk, pass_num)
                        f.write(pattern)
                        f.flush()
                        os.fsync(f.fileno())
                        
                        bytes_written += current_chunk
                        
                        # Update progress
                        if progress_callback:
                            total_progress = ((pass_num * file_size + bytes_written) / 
                                            (passes * file_size)) * 100
                            status = f"Durchgang {pass_num + 1}/{passes}"
                            progress_callback(total_progress, status)
            
            # Rename file multiple times to obscure original name
            directory = os.path.dirname(filepath)
            current_path = filepath
            
            for i in range(3):
                new_name = ''.join(random.choices('0123456789abcdef', k=32))
                new_path = os.path.join(directory, new_name)
                os.rename(current_path, new_path)
                current_path = new_path
            
            # Finally delete
            os.remove(current_path)
            
            if progress_callback:
                progress_callback(100, "Fertig!")
            
            return True
            
        except Exception as e:
            print(f"Error shredding {filepath}: {e}")
            return False


class FileItem(ctk.CTkFrame):
    """Individual file item in the list"""
    
    def __init__(self, master, filepath: str, on_remove: Callable, **kwargs):
        super().__init__(master, **kwargs)
        
        self.filepath = filepath
        self.on_remove = on_remove
        
        self.configure(
            fg_color="#0a1628",
            corner_radius=10,
            border_width=1,
            border_color="#1e3a5f",
            height=55
        )
        
        # Dateisymbol – Emoji entfernt für deutschsprachige Version
        self.icon_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=22),
            width=45
        )
        self.icon_label.pack(side="left", padx=(12, 5))
        
        # File info frame
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        # Filename
        filename = os.path.basename(filepath)
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=filename if len(filename) < 40 else filename[:37] + "...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e8f4fc",
            anchor="w"
        )
        self.name_label.pack(anchor="w")
        
        # File size
        try:
            size = os.path.getsize(filepath)
            size_str = self._format_size(size)
        except:
            size_str = "Unknown"
            
        self.size_label = ctk.CTkLabel(
            info_frame,
            text=size_str,
            font=ctk.CTkFont(size=11),
            text_color="#6b8cae",
            anchor="w"
        )
        self.size_label.pack(anchor="w")
        
        # Progress bar (hidden initially)
        self.progress = ctk.CTkProgressBar(
            self,
            width=100,
            height=10,
            progress_color="#00a8ff",
            fg_color="#1e3a5f",
            corner_radius=5
        )
        self.progress.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=10),
            text_color="#00a8ff",
            width=80
        )
        
        # Entfernen‑Schaltfläche (ohne Emoji)
        self.remove_btn = ctk.CTkButton(
            self,
            text="X",
            width=32,
            height=32,
            corner_radius=16,
            fg_color="#1e3a5f",
            hover_color="#00a8ff",
            text_color="#6b8cae",
            hover=True,
            command=self._remove
        )
        self.remove_btn.pack(side="right", padx=12)
        
    def _format_size(self, size: int) -> str:
        """Format file size to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    def _remove(self):
        """Remove this item from list"""
        self.on_remove(self)
        
    def start_shredding(self):
        """Show progress UI"""
        self.remove_btn.pack_forget()
        self.status_label.pack(side="right", padx=5)
        self.progress.pack(side="right", padx=5)
        
    def update_progress(self, value: float, status: str):
        """Update progress bar and status"""
        self.progress.set(value / 100)
        self.status_label.configure(text=status)
        
    def mark_complete(self, success: bool):
        """Mark as complete"""
        self.progress.pack_forget()
        if success:
            # Anzeige nach erfolgreichem Vernichten
            self.icon_label.configure(text="✔")
            self.status_label.configure(text="Vernichtet!", text_color="#00e676")
            self.configure(border_color="#00e676")
        else:
            # Anzeige bei Fehlschlag
            self.icon_label.configure(text="✘")
            self.status_label.configure(text="Fehlgeschlagen!", text_color="#ff5252")
            self.configure(border_color="#ff5252")


class DeldownShredder(ctk.CTk):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.title("deldown shredder")
        self.geometry("720x620")
        self.minsize(620, 520)
        self.configure(fg_color="#040d1a")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        # Files list
        self.files: List[FileItem] = []
        self.is_shredding = False
        
        self._create_header()
        self._create_dropzone()
        self._create_file_list()
        self._create_controls()
        self._create_footer()
        
    def _create_header(self):
        """Create header with title and branding"""
        header = ctk.CTkFrame(self, fg_color="#061224", corner_radius=0, height=90)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_propagate(False)
        
        # Gradient effect frame
        accent_line = ctk.CTkFrame(header, fg_color="#00a8ff", height=3, corner_radius=0)
        accent_line.pack(side="bottom", fill="x")
        
        # Title container
        title_container = ctk.CTkFrame(header, fg_color="transparent")
        title_container.pack(expand=True)
        
        # Titel ohne Diamant‑Emoji
        title = ctk.CTkLabel(
            title_container,
            text="deldown shredder",
            font=ctk.CTkFont(family="Segoe UI" if platform.system() == "Windows" else "Ubuntu", 
                            size=30, weight="bold"),
            text_color="#00a8ff"
        )
        title.pack(pady=(20, 5))
        
        # Untertitel auf Deutsch
        subtitle = ctk.CTkLabel(
            title_container,
            text="Sichere Datei‑Vernichtung • Keine Wiederherstellung möglich",
            font=ctk.CTkFont(size=12),
            text_color="#4a6fa5"
        )
        subtitle.pack()
        
    def _create_dropzone(self):
        """Create drag and drop zone"""
        self.dropzone = ctk.CTkFrame(
            self,
            fg_color="#0a1628",
            corner_radius=15,
            border_width=2,
            border_color="#1e3a5f"
        )
        self.dropzone.grid(row=1, column=0, sticky="ew", padx=25, pady=20)
        
        # Inner content
        inner = ctk.CTkFrame(self.dropzone, fg_color="transparent")
        inner.pack(pady=30, fill="x")
        
        # Icon with glow effect simulation
        icon_frame = ctk.CTkFrame(inner, fg_color="transparent")
        icon_frame.pack()
        
        icon = ctk.CTkLabel(
            icon_frame,
            text="",
            font=ctk.CTkFont(size=45)
        )
        icon.pack()
        
        # Text
        text = ctk.CTkLabel(
            inner,
            text="Dateien hierher ziehen oder zum Durchsuchen klicken",
            font=ctk.CTkFont(size=15),
            text_color="#6b8cae"
        )
        text.pack(pady=8)
        
        # Button container
        btn_container = ctk.CTkFrame(inner, fg_color="transparent")
        btn_container.pack(pady=12)
        
        # Browse button
        browse_btn = ctk.CTkButton(
            btn_container,
            text="Dateien durchsuchen",
            width=150,
            height=40,
            corner_radius=20,
            fg_color="#00a8ff",
            hover_color="#0090e0",
            text_color="#ffffff",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._browse_files
        )
        browse_btn.pack(side="left", padx=8)
        
        # Add folder button
        folder_btn = ctk.CTkButton(
            btn_container,
            text="Ordner hinzufügen",
            width=150,
            height=40,
            corner_radius=20,
            fg_color="transparent",
            border_width=2,
            border_color="#00a8ff",
            text_color="#00a8ff",
            hover_color="#0a1e36",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._browse_folder
        )
        folder_btn.pack(side="left", padx=8)
        
    def _create_file_list(self):
        """Create scrollable file list"""
        # Container
        list_container = ctk.CTkFrame(self, fg_color="transparent")
        list_container.grid(row=2, column=0, sticky="nsew", padx=25, pady=5)
        list_container.grid_columnconfigure(0, weight=1)
        list_container.grid_rowconfigure(0, weight=1)
        
        # Scrollable frame
        self.file_list = ctk.CTkScrollableFrame(
            list_container,
            fg_color="#061224",
            corner_radius=15,
            border_width=1,
            border_color="#1e3a5f",
            scrollbar_button_color="#1e3a5f",
            scrollbar_button_hover_color="#00a8ff"
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")
        self.file_list.grid_columnconfigure(0, weight=1)
        
        # Leerzustand
        self.empty_label = ctk.CTkLabel(
            self.file_list,
            text="Keine Dateien hinzugefügt\nFüge Dateien hinzu, um sie sicher zu vernichten",
            font=ctk.CTkFont(size=14),
            text_color="#3d5a80"
        )
        self.empty_label.grid(row=0, column=0, pady=60)
        
    def _create_controls(self):
        """Create control panel with options and shred button"""
        controls = ctk.CTkFrame(
            self, 
            fg_color="#0a1628", 
            corner_radius=15,
            border_width=1,
            border_color="#1e3a5f"
        )
        controls.grid(row=3, column=0, sticky="ew", padx=25, pady=15)
        
        # Left side - Options
        options_frame = ctk.CTkFrame(controls, fg_color="transparent")
        options_frame.pack(side="left", padx=20, pady=18)
        
        # Methodenbezeichner
        method_label = ctk.CTkLabel(
            options_frame,
            text="Vernichtungsmethode:",
            font=ctk.CTkFont(size=13),
            text_color="#6b8cae"
        )
        method_label.pack(side="left", padx=(0, 12))
        
        self.method_var = ctk.StringVar(value="secure")
        self.method_menu = ctk.CTkOptionMenu(
            options_frame,
            values=["quick (1 Durchgang)", "secure (3 Durchgänge)", "dod (7 Durchgänge)", "gutmann (35 Durchgänge)"],
            variable=self.method_var,
            width=180,
            height=35,
            corner_radius=10,
            fg_color="#1e3a5f",
            button_color="#2a5080",
            button_hover_color="#00a8ff",
            dropdown_fg_color="#0a1628",
            dropdown_hover_color="#1e3a5f",
            dropdown_text_color="#e8f4fc",
            text_color="#e8f4fc",
            font=ctk.CTkFont(size=12),
            command=self._on_method_change
        )
        self.method_menu.pack(side="left")
        
        # Right side - Buttons
        button_frame = ctk.CTkFrame(controls, fg_color="transparent")
        button_frame.pack(side="right", padx=20, pady=18)
        
        # Alle entfernen‑Schaltfläche
        self.clear_btn = ctk.CTkButton(
            button_frame,
            text="Alle entfernen",
            width=110,
            height=42,
            corner_radius=21,
            fg_color="transparent",
            border_width=1,
            border_color="#3d5a80",
            text_color="#6b8cae",
            hover_color="#1e3a5f",
            font=ctk.CTkFont(size=12),
            command=self._clear_all
        )
        self.clear_btn.pack(side="left", padx=8)
        
        # Vernichtungs‑Schaltfläche
        self.shred_btn = ctk.CTkButton(
            button_frame,
            text="Dateien vernichten",
            width=170,
            height=48,
            corner_radius=24,
            fg_color="#0066cc",
            hover_color="#0052a3",
            text_color="#ffffff",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_shredding
        )
        self.shred_btn.pack(side="left", padx=8)
        
    def _create_footer(self):
        """Create footer with info"""
        footer = ctk.CTkFrame(self, fg_color="transparent", height=35)
        footer.grid(row=4, column=0, sticky="ew", padx=25, pady=(0, 12))
        
        # Dateianzahl
        self.count_label = ctk.CTkLabel(
            footer,
            text="0 Dateien ausgewählt",
            font=ctk.CTkFont(size=12),
            text_color="#3d5a80"
        )
        self.count_label.pack(side="left")
        
        # Warnhinweis
        warning = ctk.CTkLabel(
            footer,
            text="Dateien können nach dem Vernichten nicht wiederhergestellt werden!",
            font=ctk.CTkFont(size=12),
            text_color="#00a8ff"
        )
        warning.pack(side="right")
        
    def _on_method_change(self, value: str):
        """Handle method selection change"""
        method = value.split()[0]  # Extract method name
        self.method_var.set(method)
        
    def _browse_files(self):
        """Open file browser dialog"""
        if self.is_shredding:
            return
            
        filetypes = [("All files", "*.*")]
        files = filedialog.askopenfilenames(
            title="Select files to shred",
            filetypes=filetypes
        )
        
        for filepath in files:
            self._add_file(filepath)
            
    def _browse_folder(self):
        """Open folder browser dialog"""
        if self.is_shredding:
            return
            
        folder = filedialog.askdirectory(title="Select folder to shred")
        
        if folder:
            # Add all files in folder
            for root, dirs, files in os.walk(folder):
                for file in files:
                    filepath = os.path.join(root, file)
                    self._add_file(filepath)
                    
    def _add_file(self, filepath: str):
        """Add a file to the list"""
        # Check if already added
        for item in self.files:
            if item.filepath == filepath:
                return
                
        # Hide empty state
        self.empty_label.grid_forget()
        
        # Create file item
        item = FileItem(
            self.file_list,
            filepath,
            self._remove_file
        )
        item.pack(fill="x", padx=8, pady=4)
        self.files.append(item)
        
        self._update_count()
        
    def _remove_file(self, item: FileItem):
        """Remove a file from the list"""
        if self.is_shredding:
            return
            
        item.pack_forget()
        item.destroy()
        self.files.remove(item)
        
        self._update_count()
        
        # Show empty state if no files
        if not self.files:
            self.empty_label.grid(row=0, column=0, pady=60)
            
    def _clear_all(self):
        """Clear all files from list"""
        if self.is_shredding:
            return
            
        for item in self.files[:]:
            item.pack_forget()
            item.destroy()
        self.files.clear()
        
        self.empty_label.grid(row=0, column=0, pady=60)
        self._update_count()
        
    def _update_count(self):
        """Update file count label"""
        count = len(self.files)
        text = f"{count} Datei{'en' if count != 1 else ''} ausgewählt"
        
        # Calculate total size
        total_size = 0
        for item in self.files:
            try:
                total_size += os.path.getsize(item.filepath)
            except:
                pass
                
        if total_size > 0:
            text += f" ({self._format_size(total_size)})"
            
        self.count_label.configure(text=text)
        
    def _format_size(self, size: int) -> str:
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
        
    def _start_shredding(self):
        """Start the shredding process"""
        if not self.files:
            messagebox.showinfo("Keine Dateien", "Bitte füge zuerst Dateien zum Vernichten hinzu.")
            return
            
        if self.is_shredding:
            return
            
        # Bestätigung vom Benutzer einholen
        count = len(self.files)
        result = messagebox.askyesno(
            "Vernichtung bestätigen",
            f"Du bist dabei, {count} Datei{'en' if count != 1 else ''} dauerhaft zu zerstören.\n\n"
            "Diese Aktion KANN NICHT rückgängig gemacht werden!\n\n"
            "Bist du sicher, dass du fortfahren möchtest?",
            icon="warning"
        )
        
        if not result:
            return
            
        self.is_shredding = True
        self.shred_btn.configure(state="disabled", text="Vernichtung...")
        self.clear_btn.configure(state="disabled")
        self.method_menu.configure(state="disabled")
        
        # Start shredding in background thread
        thread = threading.Thread(target=self._shred_files, daemon=True)
        thread.start()
        
    def _shred_files(self):
        """Shred all files (runs in background thread)"""
        method = self.method_var.get().split()[0]
        
        for item in self.files:
            # Update UI in main thread
            self.after(0, item.start_shredding)
            
            def progress_callback(value, status, item=item):
                self.after(0, lambda: item.update_progress(value, status))
                
            success = ShredderEngine.shred_file(
                item.filepath,
                method=method,
                progress_callback=progress_callback
            )
            
            self.after(0, lambda s=success, i=item: i.mark_complete(s))
            
        # Re-enable UI
        self.after(0, self._shredding_complete)
        
    def _shredding_complete(self):
        """Called when shredding is complete"""
        self.is_shredding = False
        self.shred_btn.configure(state="normal", text="Dateien vernichten")
        self.clear_btn.configure(state="normal")
        self.method_menu.configure(state="normal")

        messagebox.showinfo(
            "Vernichtung abgeschlossen",
            "Alle Dateien wurden sicher vernichtet!"
        )


def main():
    """Main entry point"""
    app = DeldownShredder()
    app.mainloop()


if __name__ == "__main__":
    main()

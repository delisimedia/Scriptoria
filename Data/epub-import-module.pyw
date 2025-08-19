import sys
import os
import tempfile
import zipfile
import shutil
import traceback
import logging
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QFileDialog, QTextBrowser, 
                            QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit,
                            QLabel, QProgressBar, QToolButton, QMessageBox,
                            QCheckBox, QFrame, QHeaderView)
from PyQt6.QtCore import Qt, QUrl, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QTextCursor, QFont, QColor

import xml.etree.ElementTree as ET
import re
import html
from bs4 import BeautifulSoup
import urllib.parse

# Set up logging
logger = logging.getLogger('epub_import')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class EPubImportDialog(QDialog):
    # Signal to emit when content is processed and ready
    content_ready = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set window properties
        self.setWindowTitle("EPUB Import")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        # Initialize variables
        self.temp_dir = None
        self.content_files = []      # List of full paths to content files
        self.content_ids = {}        # Map of content file IDs to paths
        self.toc_items = []          # Table of contents items
        self.current_chapter_index = 0
        self.selected_chapters = set()  # Set to track selected chapters
        self.toc_path_map = {}       # Map TOC paths to content file paths
        self.epub_version = 2        # Default to EPUB2 version
        
        # Set up the UI
        self.init_ui()
        
    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Content splitter - Dominates the UI
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Table of Contents
        toc_container = QWidget()
        toc_layout = QVBoxLayout(toc_container)
        toc_layout.setContentsMargins(0, 0, 0, 0)

        toc_header = QLabel("Table of Contents")
        toc_header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #203740;
            padding-bottom: 5px;
        """)

        # Create the tree widget first so it exists
        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderLabel("Chapters")
        self.toc_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.toc_tree.itemClicked.connect(self.on_toc_item_clicked)
        self.toc_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.toc_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 4px 0;
                color: black;
                border: none;
            }
            QTreeWidget::item:selected {
                background-color: rgba(70, 130, 180, 80);
                color: black;
                border: none;
            }
            QTreeWidget:focus, QTreeWidget::item:focus {
                outline: none;
                border: none;
            }
        """)
        self.toc_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Now add view mode toggle
        view_mode_layout = QHBoxLayout()
    
        self.view_mode_label = QLabel("View Mode:")
    
        self.toc_mode_btn = QPushButton("TOC Structure")
        self.toc_mode_btn.setCheckable(True)
        self.toc_mode_btn.setChecked(True)
        self.toc_mode_btn.clicked.connect(lambda: self.switch_view_mode("toc"))
        self.toc_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #203740;
                color: white;
                border: none;
                border-radius: 4px 0 0 4px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #2C4952;
            }
            QPushButton:!checked {
                background-color: transparent;
                color: #203740;
                border: 1px solid #203740;
            }
        """)
    
        self.files_mode_btn = QPushButton("Content Files")
        self.files_mode_btn.setCheckable(True)
        self.files_mode_btn.clicked.connect(lambda: self.switch_view_mode("files"))
        self.files_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #203740;
                border-radius: 0 4px 4px 0;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #2C4952;
                color: white;
                border: none;
            }
            QPushButton:!checked {
                background-color: transparent;
            }
        """)
   
        view_mode_layout.addWidget(self.view_mode_label)
        view_mode_layout.addWidget(self.toc_mode_btn)
        view_mode_layout.addWidget(self.files_mode_btn)
        view_mode_layout.addStretch()
   
        # Selection actions
        select_buttons_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #203740;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.select_all_btn.clicked.connect(self.select_all_chapters)

        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #203740;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.clear_selection_btn.clicked.connect(self.clear_chapter_selection)

        select_buttons_layout.addWidget(self.select_all_btn)
        select_buttons_layout.addWidget(self.clear_selection_btn)
        select_buttons_layout.addStretch()

        # Add everything to the toc layout in the correct order
        toc_layout.addWidget(toc_header)
        toc_layout.addLayout(view_mode_layout)  # Add the toggle buttons
        toc_layout.addWidget(self.toc_tree)
        toc_layout.addLayout(select_buttons_layout)

        # Add an instance variable to track current view mode
        self.current_view_mode = "toc"
   
        # Right side - Preview
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        preview_header = QLabel("Chapter Preview")
        preview_header.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #203740;
            padding-bottom: 5px;
        """)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenLinks(False)
        self.text_browser.setReadOnly(True)
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Georgia', serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)

        # Format options dropdown section
        format_options_section = self.create_format_options_section()

        # Navigation buttons
        nav_layout = QHBoxLayout()

        self.prev_button = QPushButton("Previous")
        self.prev_button.setIcon(self.create_white_icon("go-previous"))
        self.prev_button.clicked.connect(self.previous_chapter)
        self.prev_button.setEnabled(False)
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #e0e0e0;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover:enabled {
                background-color: #f5f5f5;
                border-color: #203740;
            }
            QPushButton:disabled {
                color: #aaaaaa;
                border-color: #e0e0e0;
            }
        """)

        self.chapter_label = QLabel("Chapter: --/--")
        self.chapter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.next_button = QPushButton("Next")
        self.next_button.setIcon(self.create_white_icon("go-next"))
        self.next_button.clicked.connect(self.next_chapter)
        self.next_button.setEnabled(False)
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #e0e0e0;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover:enabled {
                background-color: #f5f5f5;
                border-color: #203740;
            }
            QPushButton:disabled {
                color: #aaaaaa;
                border-color: #e0e0e0;
            }
        """)

        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.chapter_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_button)

        preview_layout.addWidget(preview_header)
        preview_layout.addWidget(self.text_browser)
        preview_layout.addWidget(format_options_section)
        preview_layout.addLayout(nav_layout)

        # Add widgets to splitter
        splitter.addWidget(toc_container)
        splitter.addWidget(preview_container)

        # Set splitter sizes (30% TOC, 70% preview)
        splitter.setSizes([300, 700])

        main_layout.addWidget(splitter)

        # Bottom section with buttons
        bottom_layout = QHBoxLayout()

        # Open EPUB button
        open_button = QPushButton("Open EPUB")
        open_button.setIcon(self.create_white_icon("document-open"))
        open_button.setStyleSheet("""
            QPushButton {
                background-color: #203740;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2C4952;
            }
            QPushButton:pressed {
                background-color: #1A5E5C;
            }
        """)
        open_button.clicked.connect(self.open_file_dialog)

        # Selection count label
        self.selection_label = QLabel("No chapters selected")

        # Copy button
        self.copy_button = QPushButton("Copy Selected")
        self.copy_button.setIcon(self.create_white_icon("edit-copy"))
        self.copy_button.setEnabled(False)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #203740;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover:enabled {
                background-color: #2C4952;
            }
            QPushButton:pressed {
                background-color: #1A5E5C;
            }
            QPushButton:disabled {
                background-color: #aaaaaa;
            }
        """)
        self.copy_button.clicked.connect(self.copy_selected_to_clipboard)

        # Done button
        self.done_button = QPushButton("Done")
        self.done_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #203740;
                border: 1px solid #203740;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
            }
        """)
        self.done_button.clicked.connect(self.accept)

        bottom_layout.addWidget(open_button)
        bottom_layout.addWidget(self.selection_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.copy_button)
        bottom_layout.addWidget(self.done_button)

        main_layout.addLayout(bottom_layout)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 1px;
                text-align: center;
                background-color: rgba(245, 245, 245, 0.7);
                height: 20px;
                color: #203740;  /* Dark text color for when bar is empty */
            }
            QProgressBar::chunk {
                background-color: #203740;
                border-radius: 3px;
            }
            /* This ensures text is readable on both the bar and background */
            QProgressBar {
                color: white;  /* White text color that will appear over the chunk */
            }
        """)

        main_layout.addWidget(self.progress_bar)

    def create_white_icon(self, theme_name):
        """Create white icon from system theme icon"""
        from PyQt6.QtGui import QPainter, QPixmap
    
        theme_icon = QIcon.fromTheme(theme_name)
        if theme_icon.isNull():
            return QIcon()  # Return empty icon if theme icon isn't found
        
        # Create pixmap from the theme icon
        pixmap = theme_icon.pixmap(QSize(22, 22))
    
        # Create a new pixmap with same size
        white_pixmap = QPixmap(pixmap.size())
        white_pixmap.fill(Qt.GlobalColor.transparent)
    
        # Paint the icon in white
        painter = QPainter(white_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(white_pixmap.rect(), QColor(255, 255, 255))
        painter.end()
    
        return QIcon(white_pixmap)

    def create_format_options_section(self):
        """Create a collapsible format options section"""
        # Main container
        format_section = QWidget()
        format_layout = QVBoxLayout(format_section)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(0)

        # Header with dropdown button
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Dropdown button with arrow
        self.format_toggle_btn = QToolButton()
        self.format_toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.format_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.format_toggle_btn.setText("Format Options")
        self.format_toggle_btn.setStyleSheet("""
            QToolButton {
                font-weight: bold;
                color: #203740;
                background: transparent;
                border: none;
                padding: 3px;
            }
            QToolButton:hover {
                color: #1A5E5C;
            }
        """)
        self.format_toggle_btn.setCheckable(True)
        self.format_toggle_btn.setChecked(False)
        self.format_toggle_btn.toggled.connect(self.toggle_format_options)

        header_layout.addWidget(self.format_toggle_btn)
        header_layout.addStretch()

        # Options container (hidden initially)
        self.format_options_container = QFrame()
        self.format_options_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.format_options_container.setStyleSheet("""
            QFrame {
                background-color: #f5f8fa;
                border: 1px solid #dde4e9;
                border-radius: 4px;
                margin-top: 3px;
            }
        """)
        self.format_options_container.setVisible(False)

        options_layout = QVBoxLayout(self.format_options_container)
        options_layout.setContentsMargins(10, 10, 10, 10)
        options_layout.setSpacing(10)

        # Create format options
        # Text formatting group
        text_group = QWidget()
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.add_headers_checkbox = QCheckBox("Add chapter titles as headers")
        self.add_headers_checkbox.setChecked(True)
        self.add_headers_checkbox.setToolTip("Add chapter titles as headers wrapped in ** (bold)")

        self.remove_duplicate_titles_checkbox = QCheckBox("Remove duplicate chapter titles")
        self.remove_duplicate_titles_checkbox.setChecked(True)
        self.remove_duplicate_titles_checkbox.setToolTip("Remove headers that are also links, which often appear as duplicate chapter titles")
    
        # Header selection sub-options
        self.header_options_container = QWidget()
        header_options_layout = QHBoxLayout(self.header_options_container)
        header_options_layout.setContentsMargins(20, 0, 0, 0)  # Indent to show nesting
    
        # Create checkboxes for h1, h2, h3, h4
        self.h1_checkbox = QCheckBox("H1")
        self.h1_checkbox.setChecked(True)  # H1 checked by default
        self.h1_checkbox.setToolTip("Remove H1 headers with links")
    
        self.h2_checkbox = QCheckBox("H2")
        self.h2_checkbox.setChecked(True)
        self.h2_checkbox.setToolTip("Remove H2 headers with links")
    
        self.h3_checkbox = QCheckBox("H3")
        self.h3_checkbox.setChecked(True)
        self.h3_checkbox.setToolTip("Remove H3 headers with links")
    
        self.h4_checkbox = QCheckBox("H4")
        self.h4_checkbox.setChecked(True)
        self.h4_checkbox.setToolTip("Remove H4 headers with links")
    
        header_options_layout.addWidget(self.h1_checkbox)
        header_options_layout.addWidget(self.h2_checkbox)
        header_options_layout.addWidget(self.h3_checkbox)
        header_options_layout.addWidget(self.h4_checkbox)
        header_options_layout.addStretch()
    
        self.remove_duplicate_titles_checkbox.toggled.connect(self.on_remove_duplicate_titles_toggled)

        self.fix_paragraphs_checkbox = QCheckBox("Fix paragraph spacing")
        self.fix_paragraphs_checkbox.setChecked(True)
        self.fix_paragraphs_checkbox.setToolTip("Standardize paragraph spacing for Scriptoria format")
        
        # NEW: Checkbox to enable nested chapter formatting.
        self.handle_subchapters_checkbox = QCheckBox("Handle Nested Chapters")
        self.handle_subchapters_checkbox.setChecked(False)
        self.handle_subchapters_checkbox.setToolTip("Main chapters containing sub-chapters will have titles formatted as [[TITLE]] while subchapters use **TITLE**")

        text_layout.addWidget(self.add_headers_checkbox)
        text_layout.addWidget(self.remove_duplicate_titles_checkbox)
        text_layout.addWidget(self.header_options_container)
        text_layout.addWidget(self.fix_paragraphs_checkbox)
        text_layout.addWidget(self.handle_subchapters_checkbox)  # <-- Added here

        # Verse numbers group (with mutually exclusive options)
        verse_group = QWidget()
        verse_layout = QVBoxLayout(verse_group)
        verse_layout.setContentsMargins(0, 0, 0, 0)

        verse_label = QLabel("Superscript Numbers:")
        verse_label.setStyleSheet("font-weight: bold;")

        # Indent the verse options
        verse_options = QWidget()
        verse_options_layout = QVBoxLayout(verse_options)
        verse_options_layout.setContentsMargins(15, 0, 0, 0)

        # Changed default: format_verses_checkbox is now unchecked by default
        self.format_verses_checkbox = QCheckBox("Format superscript numbers as [1], [2], etc.")
        self.format_verses_checkbox.setChecked(False)
        self.format_verses_checkbox.setToolTip("Like verse numbers or numbered footnotes")

        # Changed default: remove_verses_checkbox is now checked by default
        self.remove_verses_checkbox = QCheckBox("Remove superscript numbers")
        self.remove_verses_checkbox.setChecked(True)
        self.remove_verses_checkbox.setToolTip("Like verse numbers or numbered footnotes")

        # Connect signals for mutual exclusion
        self.format_verses_checkbox.toggled.connect(self.on_format_verses_toggled)
        self.remove_verses_checkbox.toggled.connect(self.on_remove_verses_toggled)

        verse_options_layout.addWidget(self.format_verses_checkbox)
        verse_options_layout.addWidget(self.remove_verses_checkbox)

        verse_layout.addWidget(verse_label)
        verse_layout.addWidget(verse_options)

        # Footnotes options
        footnotes_group = QWidget()
        footnotes_layout = QVBoxLayout(footnotes_group)
        footnotes_layout.setContentsMargins(0, 0, 0, 0)

        self.remove_footnotes_checkbox = QCheckBox("Remove footnote markers and references")
        self.remove_footnotes_checkbox.setChecked(True)
        self.remove_footnotes_checkbox.setToolTip("Remove footnote markers, letters, and references")

        footnotes_layout.addWidget(self.remove_footnotes_checkbox)

        # Add all option groups
        options_layout.addWidget(text_group)
        options_layout.addWidget(verse_group)
        options_layout.addWidget(footnotes_group)

        # Arrange the main layout
        format_layout.addWidget(header_widget)
        format_layout.addWidget(self.format_options_container)
    
        # Initial state of header options based on main checkbox
        self.on_remove_duplicate_titles_toggled(self.remove_duplicate_titles_checkbox.isChecked())

        return format_section

    def on_remove_duplicate_titles_toggled(self, checked):
        """Handle the state of header type checkboxes based on main checkbox"""
        self.header_options_container.setEnabled(checked)

    def toggle_format_options(self, checked):
        """Toggle the visibility of format options"""
        self.format_options_container.setVisible(checked)
        # Change the arrow direction
        self.format_toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def on_format_verses_toggled(self, checked):
        """Handle format verses checkbox toggle"""
        if checked and self.remove_verses_checkbox.isChecked():
            # Prevent signal recursion
            self.remove_verses_checkbox.blockSignals(True)
            self.remove_verses_checkbox.setChecked(False)
            self.remove_verses_checkbox.blockSignals(False)

    def on_remove_verses_toggled(self, checked):
        """Handle remove verses checkbox toggle"""
        if checked and self.format_verses_checkbox.isChecked():
            # Prevent signal recursion
            self.format_verses_checkbox.blockSignals(True)
            self.format_verses_checkbox.setChecked(False)
            self.format_verses_checkbox.blockSignals(False)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open EPUB File", "", "EPUB Files (*.epub);;All Files (*)"
        )
        
        if file_path:
            self.open_epub(file_path)

    def open_epub(self, file_path):
        # Clean up previous temp directory if exists
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()
        
        try:
            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(10)
            self.progress_bar.setFormat("Extracting EPUB file...")
            QApplication.processEvents()
            
            # Extract EPUB (which is a ZIP file)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
            
            self.progress_bar.setValue(30)
            self.progress_bar.setFormat("Analyzing content...")
            QApplication.processEvents()
            
            # Find the content files
            self.content_files = []
            self.content_ids = {}
            self.toc_items = []
            self.toc_path_map = {}
            
            # Parse container.xml to find the content.opf file
            container_path = os.path.join(self.temp_dir, "META-INF", "container.xml")
            if os.path.exists(container_path):
                tree = ET.parse(container_path)
                root = tree.getroot()
                
                # Find the content.opf path
                ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                rootfile_element = root.find(".//ns:rootfile", ns)
                
                if rootfile_element is not None:
                    content_path = rootfile_element.get("full-path")
                    content_dir = os.path.dirname(content_path)
                    
                    # Parse content.opf to find the spine and manifest
                    content_opf_path = os.path.join(self.temp_dir, content_path)
                    
                    if os.path.exists(content_opf_path):
                        self.progress_bar.setValue(50)
                        self.progress_bar.setFormat("Parsing content structure...")
                        QApplication.processEvents()
                        
                        self.parse_content_opf(content_opf_path, content_dir)
                        
                        self.progress_bar.setValue(70)
                        self.progress_bar.setFormat("Loading table of contents...")
                        QApplication.processEvents()
                        
                        # Parse NCX file to get table of contents
                        self.parse_toc(content_dir)
                        
                        # Log what we found
                        logger.debug(f"Found {len(self.content_files)} content files")
                        logger.debug(f"TOC path map has {len(self.toc_path_map)} entries")
                        
                        self.progress_bar.setValue(90)
                        self.progress_bar.setFormat("Loading first chapter...")
                        QApplication.processEvents()
                        
                        # Load the first chapter
                        if self.content_files:
                            self.load_chapter(0)
                            self.setWindowTitle(f"EPUB Import - {os.path.basename(file_path)}")
                            
                            # Update UI state
                            self.copy_button.setEnabled(False)
                            self.selection_label.setText("No chapters selected")
                            
                            self.progress_bar.setValue(100)
                            self.progress_bar.setFormat("Ready")
                            
                            # Hide progress bar after a delay
                            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Failed to open EPUB file:\n{str(e)}")
            logger.error(f"Error opening EPUB: {str(e)}")
            traceback.print_exc()



    def process_epub3_nav_items(self, ol_element, parent_item, content_dir):
        """Process EPUB3 navigation items recursively"""
        for li in ol_element.find_all('li', recursive=False):
            anchor = li.find('a')
            if not anchor:
                continue
                
            label = anchor.get_text().strip()
            href = anchor.get('href', '')
            
            # Handle fragment identifiers
            path, fragment = href.split('#', 1) if '#' in href else (href, None)
            
            # Find matching content file with improved path handling
            file_path = None
            
            # Try multiple path formats to improve matching
            if path:
                # URL decode the path
                try:
                    path = urllib.parse.unquote(path)
                except:
                    pass
                
                # Try direct path
                full_path = os.path.join(content_dir, path)
                full_path = os.path.normpath(os.path.join(self.temp_dir, full_path))
                
                # Try by basename
                basename = os.path.basename(path)
                
                # Check toc_path_map
                for p in [path.lower(), basename.lower(), full_path.lower()]:
                    if p in self.toc_path_map:
                        file_path = self.toc_path_map[p]
                        break
                
                # If still not found, try content file matching
                if not file_path:
                    file_path = self.find_content_file(path)
            
            # Create the TOC item
            if parent_item is None:
                item = QTreeWidgetItem(self.toc_tree, [label])
            else:
                item = QTreeWidgetItem(parent_item, [label])
            
            # Store path information
            item.setData(0, Qt.ItemDataRole.UserRole, {
                "original_path": path,
                "path": file_path,
                "fragment": fragment
            })
            
            # Process nested lists
            nested_ol = li.find('ol')
            if nested_ol:
                self.process_epub3_nav_items(nested_ol, item, content_dir)

    def process_nav_points(self, nav_points, ns, content_dir, parent_item):
        for nav_point in nav_points:
            # Get label
            nav_label = nav_point.find(".//ncx:navLabel/ncx:text", ns)
            label = nav_label.text if nav_label is not None and nav_label.text else "Untitled"
            
            # Get content
            content = nav_point.find("ncx:content", ns)
            if content is not None:
                src = content.get("src")
                
                # Handle fragment identifiers
                path = src.split('#')[0]
                fragment = src.split('#')[1] if '#' in src else None
                
                # URL decode the path
                try:
                    path = urllib.parse.unquote(path)
                except:
                    pass
                
                # Find the corresponding content file using improved matching
                file_path = self.find_content_file(path)
                
                # Create item with metadata
                if parent_item is None:
                    item = QTreeWidgetItem(self.toc_tree, [label])
                else:
                    item = QTreeWidgetItem(parent_item, [label])
                
                # Store both the original path and our best matched path
                item.setData(0, Qt.ItemDataRole.UserRole, {
                    "original_path": path,
                    "path": file_path,
                    "fragment": fragment
                })
                
                # Add to our path map if we found a match
                if file_path:
                    self.toc_path_map[path.lower()] = file_path
                
                # Process child nav points
                child_nav_points = nav_point.findall("ncx:navPoint", ns)
                self.process_nav_points(child_nav_points, ns, content_dir, item)

    def load_chapter(self, index, fragment=None):
        """Load and display a chapter"""
        if 0 <= index < len(self.content_files):
            try:
                # Update current chapter index
                self.current_chapter_index = index
                
                # Read the file
                with open(self.content_files[index], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Process the HTML content
                processed_content = self.process_html_content(content)
                
                # Set content in text browser
                self.text_browser.setHtml(processed_content)
                
                # Scroll to fragment if specified
                if fragment:
                    self.text_browser.scrollToAnchor(fragment)
                else:
                    # Scroll to top
                    cursor = self.text_browser.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    self.text_browser.setTextCursor(cursor)
                
                # Update UI
                self.update_navigation_buttons()
                self.chapter_label.setText(f"Chapter: {index + 1}/{len(self.content_files)}")
                
                # Update the TOC selection
                self.update_toc_selection()
                
            except Exception as e:
                logger.error(f"Error loading chapter: {str(e)}")
                traceback.print_exc()

    def process_html_content(self, html_content):
        """Process HTML content for display"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Clean up the HTML
            for tag in soup(['script', 'style']):
                tag.decompose()
            
            # Add custom CSS
            css = """
            <style>
                body {
                    font-family: 'Georgia', serif;
                    font-size: 13px;
                    line-height: 1.6;
                    margin: 0;
                    padding: 10px;
                    color: #333;
                }
                h1, h2, h3, h4, h5, h6 {
                    color: #203740;
                    margin-top: 1.2em;
                    margin-bottom: 0.5em;
                }
                p { margin: 0.8em 0; }
                img { max-width: 100%; height: auto; }
            </style>
            """
            
            # Create or update head section
            head = soup.head
            if not head:
                head = soup.new_tag('head')
                if soup.html:
                    soup.html.insert(0, head)
                else:
                    html_tag = soup.new_tag('html')
                    html_tag.append(head)
                    if soup.body:
                        html_tag.append(soup.body)
                    soup = html_tag
            
            # Add CSS to head
            style_tag = soup.new_tag('style')
            style_tag.string = css
            head.append(style_tag)
            
            return str(soup)
        except Exception as e:
            logger.error(f"Error in process_html_content: {e}")
            # Fallback if BeautifulSoup fails
            return html_content

    def update_navigation_buttons(self):
        """Update the state of navigation buttons"""
        self.prev_button.setEnabled(self.current_chapter_index > 0)
        self.next_button.setEnabled(self.current_chapter_index < len(self.content_files) - 1)

    def update_toc_selection(self):
        """Update the selection in the TOC tree to match the current chapter"""
        current_path = self.content_files[self.current_chapter_index]
        
        # Helper function to recursively search the tree for an item with matching path
        def find_matching_item(item):
            if item is None:
                return None
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                path = data.get("path")
                if path == current_path:
                    return item
                
                # Also check if the original path matches when normalized
                original_path = data.get("original_path")
                if original_path:
                    matched_path = self.find_content_file(original_path)
                    if matched_path == current_path:
                        return item
            
            # Check children
            for i in range(item.childCount()):
                result = find_matching_item(item.child(i))
                if result:
                    return result
                    
            return None
            
        # Search all top-level items
        for i in range(self.toc_tree.topLevelItemCount()):
            item = find_matching_item(self.toc_tree.topLevelItem(i))
            if item:
                self.toc_tree.setCurrentItem(item)
                return
                
        # If we didn't find a match, try by basename
        basename = os.path.basename(current_path).lower()
        
        def find_by_basename(item):
            if item is None:
                return None
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                path = data.get("path")
                if path and os.path.basename(path).lower() == basename:
                    return item
                    
                original_path = data.get("original_path")
                if original_path and os.path.basename(original_path).lower() == basename:
                    return item
                    
            # Check children
            for i in range(item.childCount()):
                result = find_by_basename(item.child(i))
                if result:
                    return result
                    
            return None
            
        # Search by basename
        for i in range(self.toc_tree.topLevelItemCount()):
            item = find_by_basename(self.toc_tree.topLevelItem(i))
            if item:
                self.toc_tree.setCurrentItem(item)
                return

    def previous_chapter(self):
        """Navigate to the previous chapter"""
        if self.current_chapter_index > 0:
            self.load_chapter(self.current_chapter_index - 1)

    def next_chapter(self):
        """Navigate to the next chapter"""
        if self.current_chapter_index < len(self.content_files) - 1:
            self.load_chapter(self.current_chapter_index + 1)

    def select_all_chapters(self):
        """Select all chapters in the TOC"""
        # Set selection mode to MultiSelection
        previous_selection_mode = self.toc_tree.selectionMode()
        self.toc_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        
        # Helper function to select all items recursively
        def select_all_items(item=None):
            if item is None:
                # Process all top-level items
                for i in range(self.toc_tree.topLevelItemCount()):
                    select_all_items(self.toc_tree.topLevelItem(i))
                return
                
            # Select this item
            item.setSelected(True)
            
            # Get item data
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                path = data.get("path")
                if not path:
                    # Try to find a matching content file
                    original_path = data.get("original_path")
                    path = self.find_content_file(original_path)
                
                if path and os.path.exists(path):
                    self.selected_chapters.add(path)
                    # Set background for visual feedback
                    item.setBackground(0, QColor(70, 130, 180, 80))
            
            # Process all children
            for i in range(item.childCount()):
                select_all_items(item.child(i))
        
        # Clear existing selection first
        self.toc_tree.clearSelection()
        self.selected_chapters.clear()
        
        # Select all items
        select_all_items()
        
        # Restore previous selection mode
        self.toc_tree.setSelectionMode(previous_selection_mode)
        
        # Update UI
        if self.selected_chapters:
            self.selection_label.setText(f"{len(self.selected_chapters)} chapters selected")
            self.copy_button.setEnabled(True)
        else:
            self.selection_label.setText("No chapters selected")
            self.copy_button.setEnabled(False)

    def clear_chapter_selection(self):
        """Clear all chapter selections"""
        # Clear Qt's selection
        self.toc_tree.clearSelection()
    
        # Clear our internal tracking
        self.selected_chapters.clear()
    
        # Helper function to clear item backgrounds recursively
        def clear_item_backgrounds(item=None):
            if item is None:
                # Process all top-level items
                for i in range(self.toc_tree.topLevelItemCount()):
                    clear_item_backgrounds(self.toc_tree.topLevelItem(i))
                return
                
            # Clear this item's background
            item.setBackground(0, QColor(0, 0, 0, 0))
            
            # Process all children
            for i in range(item.childCount()):
                clear_item_backgrounds(item.child(i))
        
        # Clear all item backgrounds
        clear_item_backgrounds()
    
        # Update UI
        self.selection_label.setText("No chapters selected")
        self.copy_button.setEnabled(False)
        
    def find_parent_text_edit(self):
        """Find the parent CreateTranscriptTextEdit widget"""
        parent = self.parent()
        while parent:
            # Look for the CreateTranscriptTextEdit in children
            for child in parent.findChildren(QTextEdit):
                # Check for characteristic methods/attributes
                if hasattr(child, 'header_highlighter') and hasattr(child, '_notify_changes_pending'):
                    return child
                
            # Try the next parent in hierarchy
            parent = parent.parent()
        
        return None        

    def copy_selected_to_clipboard(self):
        """Copy the text content from all selected chapters directly to the parent text editor"""
        if not self.selected_chapters:
            QMessageBox.warning(self, "No Selection", "Please select at least one chapter to copy.")
            return

        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Preparing to copy selected chapters...")
        QApplication.processEvents()

        try:
            # Get formatting options
            add_headers = self.add_headers_checkbox.isChecked()
            format_verses = self.format_verses_checkbox.isChecked()
            remove_verses = self.remove_verses_checkbox.isChecked()
            remove_footnotes = self.remove_footnotes_checkbox.isChecked()
            fix_paragraphs = self.fix_paragraphs_checkbox.isChecked()
            remove_duplicate_titles = self.remove_duplicate_titles_checkbox.isChecked()
        
            # Check if we're in content files mode
            is_content_files_mode = self.current_view_mode == "files"
        
            # If in content files mode, ensure we handle headers appropriately
            if is_content_files_mode:
                # Visual feedback to user that headers are handled differently in content files mode
                self.progress_bar.setFormat("Content Files Mode: Processing HTML headers...")
                QApplication.processEvents()

            # Get a list of all selected chapter paths
            selected_paths = list(self.selected_chapters)
        
            # Order chapters based on their positions in content_files to maintain book order
            def get_chapter_order(path):
                if path in self.content_files:
                    return self.content_files.index(path)
                # Try to find a matching content file
                matched_path = self.find_content_file(path)
                if matched_path in self.content_files:
                    return self.content_files.index(matched_path)
                # If still not found, put at the end
                return float('inf')
            
            # Sort chapters by their position in the book
            selected_paths.sort(key=get_chapter_order)
        
            # Log selection info
            logger.debug(f"Selected {len(selected_paths)} chapters for copying")
        
            # Ensure all paths exist
            selected_paths = [path for path in selected_paths if os.path.exists(path)]
            logger.debug(f"Found {len(selected_paths)} existing chapter files")

            combined_text = []
            total_chapters = len(selected_paths)

            for i, path in enumerate(selected_paths):
                try:
                    # Update progress
                    progress = int((i / total_chapters) * 90)
                    self.progress_bar.setValue(progress)
                    self.progress_bar.setFormat(f"Processing chapter {i+1}/{total_chapters}...")
                    QApplication.processEvents()

                    # Read the file
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Different processing based on view mode
                    if is_content_files_mode:
                        # Special handling for content files mode
                        processed_text = self.process_content_file_for_copy(
                            content, 
                            path,
                            format_verses,
                            remove_verses,
                            remove_footnotes,
                            fix_paragraphs
                        )
                    else:
                        # Standard TOC mode processing
                        # Get the chapter title
                        chapter_title = self.get_chapter_title_for_path(path)
                        if not chapter_title:
                            # Try to extract a title from the HTML content
                            try:
                                soup = BeautifulSoup(content, 'html.parser')
                                title_tag = soup.find(['h1', 'h2', 'title'])
                                if title_tag:
                                    chapter_title = title_tag.get_text().strip()
                                else:
                                    chapter_title = os.path.splitext(os.path.basename(path))[0]
                            except:
                                chapter_title = os.path.splitext(os.path.basename(path))[0]
                            
                        processed_text = self.extract_formatted_text(
                            content, 
                            chapter_title, 
                            path,
                            add_headers,
                            format_verses,
                            remove_verses,
                            remove_footnotes,
                            fix_paragraphs,
                            remove_duplicate_titles
                        )

                    if processed_text:
                        combined_text.append(processed_text)

                except Exception as e:
                    logger.error(f"Error processing chapter: {e}")
                    traceback.print_exc()

            if combined_text:
                self.progress_bar.setValue(95)
                self.progress_bar.setFormat("Inserting content...")
                QApplication.processEvents()

                all_text = "\n\n".join(combined_text)

                # Final cleanup passes
                if format_verses:
                    # Make sure all verse numbers have proper spacing after them
                    all_text = re.sub(r'\[(\d+)\]([A-Za-z])', r'[\1] \2', all_text)
                elif remove_verses:
                    # Final sweep for any remaining verse numbers
                    all_text = re.sub(r'(\n\n)(\d{1,3})(?=[A-Za-z])', r'\1', all_text)
                    all_text = re.sub(r'\[\d{1,3}\](\s*)', '', all_text)

                # Try to find parent CreateTranscriptTextEdit
                text_edit = self.find_parent_text_edit()
    
                if text_edit:
                    # Insert the text at the current cursor position
                    text_edit.insertPlainText(all_text)
        
                    # Get parent main window
                    main_window = self.parent()
            
                    # Update progress message
                    self.progress_bar.setValue(98)
                    self.progress_bar.setFormat("Processing headers...")
                    QApplication.processEvents()
            
                    # Sequence of operations to properly update everything
                    # 1. First notify that changes are pending
                    if hasattr(text_edit, '_notify_changes_pending'):
                        logger.debug("EPUB Import: Notifying changes pending")
                        text_edit._notify_changes_pending()
                
                    # 2. Ensure header highlighting
                    if hasattr(text_edit, 'header_highlighter'):
                        highlighter = text_edit.header_highlighter
                
                        # Mark headers refresh in progress to prevent interference
                        if hasattr(highlighter, '_header_refresh_in_progress'):
                            highlighter._header_refresh_in_progress = False
                    
                        # First analyze document to locate headers
                        if hasattr(highlighter, 'analyze_document'):
                            logger.debug("EPUB Import: Analyzing document")
                            highlighter.analyze_document()
                    
                        # Enable orphaned checking
                        if hasattr(highlighter, 'check_orphaned'):
                            highlighter.check_orphaned = True
                    
                        # Force header highlighting
                        if hasattr(highlighter, 'force_rehighlight_all_headers'):
                            logger.debug("EPUB Import: Force rehighlighting headers")
                            highlighter.force_rehighlight_all_headers()
                    
                        # Resume highlighting
                        if hasattr(highlighter, 'resume_highlighting'):
                            logger.debug("EPUB Import: Resuming highlighting")
                            highlighter.resume_highlighting()
            
                    # 3. Explicitly refresh headers list
                    if main_window and hasattr(main_window, 'refresh_headers_list'):
                        logger.debug("EPUB Import: Refreshing headers list")
                        main_window.refresh_headers_list()
                
                    # 4. Trigger orphaned text check in the editor
                    if hasattr(text_edit, '_perform_orphaned_check'):
                        logger.debug("EPUB Import: Performing orphaned check")
                        text_edit._perform_orphaned_check()
                
                    # 5. Trigger schedule highlight 
                    if hasattr(text_edit, 'schedule_highlight'):
                        logger.debug("EPUB Import: Scheduling highlight")
                        text_edit.schedule_highlight()
            
                    self.progress_bar.setValue(100)
                    self.progress_bar.setFormat("Successfully inserted content!")
            
                    # Give time for UI to update before closing
                    QTimer.singleShot(250, self.accept)
                else:
                    # Fallback to clipboard
                    clipboard = QApplication.clipboard()
                    clipboard.setText(all_text)
        
                    self.progress_bar.setValue(100)
                    self.progress_bar.setFormat("Successfully copied to clipboard!")
        
                    # Show success message
                    QMessageBox.information(
                        self,
                        "Copy Complete",
                        f"Successfully copied {len(combined_text)} chapters to clipboard.\n\n"
                        "You can now paste them into the Create Transcript tab."
                    )
            else:
                self.progress_bar.setVisible(False)
                QMessageBox.warning(self, "Error", "No content was copied.")

        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Failed to copy content:\n{str(e)}")
            logger.error(f"ERROR in copy_selected_to_clipboard: {e}")
            traceback.print_exc()

        # Hide progress bar after a delay
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

    def is_main_chapter(self, chapter_path):
        """Return True if the TOC item for chapter_path has child items (i.e. it is a main chapter with nested sub-chapters)"""
        # Helper function to search the tree recursively
        def find_item_for_path(item, path):
            if item is None:
                return None
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                item_path = data.get("path")
                if item_path == path:
                    return item
                    
                original_path = data.get("original_path")
                if original_path:
                    matched_path = self.find_content_file(original_path)
                    if matched_path == path:
                        return item
            
            # Check children
            for i in range(item.childCount()):
                result = find_item_for_path(item.child(i), path)
                if result:
                    return result
                    
            return None
            
        # Search all top-level items
        for i in range(self.toc_tree.topLevelItemCount()):
            item = find_item_for_path(self.toc_tree.topLevelItem(i), chapter_path)
            if item:
                return item.childCount() > 0
                
        return False
    
    def get_chapter_title_for_path(self, path):
        """Find chapter title for a given path from the TOC"""
        # Normalize path for comparison
        path = os.path.normpath(path)
        
        # Helper function to recursively search for an item with matching path
        def find_title_for_path(item):
            if item is None:
                return None
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                item_path = data.get("path")
                if item_path == path:
                    return item.text(0)
                    
                # Also check if this could be the mapped path
                original_path = data.get("original_path")
                if original_path:
                    matched_path = self.find_content_file(original_path)
                    if matched_path == path:
                        return item.text(0)
            
            # Check children
            for i in range(item.childCount()):
                result = find_title_for_path(item.child(i))
                if result:
                    return result
                    
            return None
            
        # Search all top-level items
        for i in range(self.toc_tree.topLevelItemCount()):
            title = find_title_for_path(self.toc_tree.topLevelItem(i))
            if title:
                return title
                
        # If we didn't find a match, try by basename
        basename = os.path.basename(path).lower()
        
        def find_title_by_basename(item):
            if item is None:
                return None
                
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                item_path = data.get("path")
                if item_path and os.path.basename(item_path).lower() == basename:
                    return item.text(0)
                    
                original_path = data.get("original_path")
                if original_path and os.path.basename(original_path).lower() == basename:
                    return item.text(0)
                    
            # Check children
            for i in range(item.childCount()):
                result = find_title_by_basename(item.child(i))
                if result:
                    return result
                    
            return None
            
        # Search by basename
        for i in range(self.toc_tree.topLevelItemCount()):
            title = find_title_by_basename(self.toc_tree.topLevelItem(i))
            if title:
                return title
                
        # If still not found, try to extract from the HTML content or use the filename
        return None
    
    def closeEvent(self, event):
        """Clean up on close"""
        if self.temp_dir:
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        event.accept()

    def parse_content_opf(self, opf_path, content_dir):
        try:
            tree = ET.parse(opf_path)
            root = tree.getroot()
        
            # Detect EPUB version
            version = root.get('version')
            self.epub_version = 3 if version == '3.0' else 2
            print(f"[EPUB VERSION] Detected version attribute in OPF: {version}")
            print(f"[EPUB VERSION] Setting EPUB version to: {self.epub_version}")
            logger.debug(f"Detected EPUB version: {self.epub_version}")
        
            # Find namespace
            ns = {'ns': 'http://www.idpf.org/2007/opf'}
        
            # Get manifest items
            manifest_items = {}
            for item in root.findall(".//ns:manifest/ns:item", ns):
                item_id = item.get("id")
                href = item.get("href")
                media_type = item.get("media-type")
            
                if media_type == "application/xhtml+xml" or media_type == "text/html":
                    manifest_items[item_id] = href
                    # Store normalized path as key for the ID
                    file_path = os.path.join(content_dir, href)
                    if file_path.startswith('./'):
                        file_path = file_path[2:]
                    file_path = os.path.normpath(os.path.join(self.temp_dir, file_path))
                    self.content_ids[item_id] = file_path
                
                    # Add more variants to the path map
                    norm_href = os.path.normpath(href.replace('\\', '/')).lower()
                    self.toc_path_map[norm_href] = file_path
                
                    # Also add URL-decoded path
                    try:
                        decoded_href = urllib.parse.unquote(href)
                        if decoded_href != href:
                            norm_decoded = os.path.normpath(decoded_href.replace('\\', '/')).lower()
                            self.toc_path_map[norm_decoded] = file_path
                    except:
                        pass
        
            # Get spine items
            spine = root.find(".//ns:spine", ns)
            if spine is not None:
                for itemref in spine.findall(".//ns:itemref", ns):
                    idref = itemref.get("idref")
                    if idref in manifest_items:
                        # Normalize paths to handle different directory structures
                        file_path = os.path.join(content_dir, manifest_items[idref])
                        if file_path.startswith('./'):
                            file_path = file_path[2:]
                        file_path = os.path.normpath(os.path.join(self.temp_dir, file_path))
                    
                        if os.path.exists(file_path):
                            self.content_files.append(file_path)
                        
                            # Store both with and without temp_dir prefix for better matching
                            rel_path = os.path.join(content_dir, manifest_items[idref])
                            if rel_path.startswith('./'):
                                rel_path = rel_path[2:]
                            rel_path = os.path.normpath(rel_path)
                        
                            # Map all possible path variations to the full path
                            self.toc_path_map[file_path.lower()] = file_path
                            self.toc_path_map[os.path.basename(file_path).lower()] = file_path
                            self.toc_path_map[rel_path.lower()] = file_path
                            self.toc_path_map[manifest_items[idref].lower()] = file_path
                        
                            # Add the ID itself to the map for EPUB3 format
                            self.toc_path_map[idref.lower()] = file_path
        
            # Find TOC reference
            self.toc_path = None
            self.epub3_nav_path = None
        
            for item in root.findall(".//ns:manifest/ns:item", ns):
                # EPUB2 NCX file
                if item.get("media-type") == "application/x-dtbncx+xml":
                    self.toc_path = os.path.join(content_dir, item.get("href"))
                    print(f"[EPUB VERSION] Found EPUB2 NCX file: {self.toc_path}")
            
                # EPUB3 navigation document
                properties = item.get("properties")
                if properties and "nav" in properties.split():
                    self.epub3_nav_path = os.path.join(content_dir, item.get("href"))
                    print(f"[EPUB VERSION] Found EPUB3 nav document: {self.epub3_nav_path}")
        
            # For EPUB3, prefer the navigation document
            if self.epub_version == 3 and self.epub3_nav_path:
                print(f"[EPUB VERSION] Using EPUB3 navigation document over NCX: {self.epub3_nav_path}")
                logger.debug(f"Using EPUB3 navigation document: {self.epub3_nav_path}")
                self.toc_path = self.epub3_nav_path
        
            # Log content files
            logger.debug(f"Parsed content.opf with {len(self.content_files)} content files")
        except Exception as e:
            logger.error(f"Error parsing content.opf: {str(e)}")
            traceback.print_exc()

    def parse_toc(self, content_dir):
        if not hasattr(self, 'toc_path') or not self.toc_path:
            return
    
        toc_full_path = os.path.join(self.temp_dir, self.toc_path)
    
        if not os.path.exists(toc_full_path):
            return
    
        try:
            # Clear existing TOC
            self.toc_tree.clear()
        
            # Check if using EPUB3 navigation document
            is_epub3_nav = hasattr(self, 'epub3_nav_path') and self.toc_path == self.epub3_nav_path
        
            if is_epub3_nav:
                # Parse EPUB3 navigation document
                logger.debug("Parsing EPUB3 navigation document")
                with open(toc_full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
                soup = BeautifulSoup(content, 'html.parser')
            
                # Find the nav element
                nav_element = soup.find('nav', attrs={'epub:type': 'toc'})
                if not nav_element:
                    nav_element = soup.find('nav')  # Fallback if epub:type not specified
            
                if nav_element:
                    # Process the navigation list
                    ol_element = nav_element.find('ol')
                    if ol_element:
                        self.process_epub3_nav_items(ol_element, None, content_dir)
            else:
                # Parse EPUB2 NCX file
                logger.debug("Parsing EPUB2 NCX file")
                tree = ET.parse(toc_full_path)
                root = tree.getroot()
            
                # Define NCX namespace
                ns = {'ncx': 'http://www.daisy.org/z3986/2005/ncx/'}
            
                # Process navMap
                nav_points = root.findall(".//ncx:navMap/ncx:navPoint", ns)
                self.process_nav_points(nav_points, ns, content_dir, None)
        
            # Expand all items
            self.toc_tree.expandAll()
        
            logger.debug(f"Parsed TOC with {len(self.toc_path_map)} entries in path map")
        
            # Check for TOC vs Content Files mismatch and auto-switch if needed
            toc_count = self.count_toc_entries()
            content_file_count = len(self.content_files)
        
            # If there are significantly more TOC entries than content files (e.g., more than 3x)
            # then switch to content files view automatically
            if toc_count > content_file_count * 3:
                logger.debug(f"Detected TOC/Content mismatch: {toc_count} TOC entries vs {content_file_count} content files")
                QTimer.singleShot(100, lambda: self.switch_view_mode("files"))
            
        except Exception as e:
            logger.error(f"Error parsing table of contents: {str(e)}")
            traceback.print_exc()

    def find_content_file(self, path):
        """Improved content file matching for both EPUB2 and EPUB3"""
        if not path:
            return None
    
        print(f"[PATH MATCHING] Trying to find content file for path: {path}")
    
        # Try direct lookup first
        if path in self.content_files:
            print(f"[PATH MATCHING] Direct match found in content_files")
            return path
    
        # Normalize path for better matching
        norm_path = os.path.normpath(path).lower()
        if norm_path in self.toc_path_map:
            print(f"[PATH MATCHING] Normalized path found in toc_path_map: {norm_path}")
            return self.toc_path_map[norm_path]
    
        # Try just the filename
        basename = os.path.basename(path).lower()
        if basename in self.toc_path_map:
            print(f"[PATH MATCHING] Basename found in toc_path_map: {basename}")
            return self.toc_path_map[basename]
    
        # Try with URL decoding
        try:
            decoded_path = urllib.parse.unquote(path)
            if decoded_path != path:
                print(f"[PATH MATCHING] URL decoded path: {decoded_path}")
                norm_decoded = os.path.normpath(decoded_path).lower()
                if norm_decoded in self.toc_path_map:
                    print(f"[PATH MATCHING] URL decoded normalized path found in toc_path_map")
                    return self.toc_path_map[norm_decoded]
            
                decoded_basename = os.path.basename(decoded_path).lower()
                if decoded_basename in self.toc_path_map:
                    print(f"[PATH MATCHING] URL decoded basename found in toc_path_map")
                    return self.toc_path_map[decoded_basename]
        except:
            pass
    
        # Try any matching basename in content files
        for content_file in self.content_files:
            if os.path.basename(content_file).lower() == basename:
                print(f"[PATH MATCHING] Basename match found in content_files: {os.path.basename(content_file)}")
                return content_file
    
        # Try partial filename match (for those long prefixed filenames)
        for content_file in self.content_files:
            if basename in os.path.basename(content_file).lower():
                print(f"[PATH MATCHING] Partial basename match found: {os.path.basename(content_file)}")
                return content_file
    
        # Try ID-based matching (for EPUB3)
        if self.epub_version == 3 and path.startswith("id"):
            print(f"[PATH MATCHING] Trying ID-based matching for EPUB3: {path}")
            for content_id, content_path in self.content_ids.items():
                if content_id in path:
                    print(f"[PATH MATCHING] ID match found: {content_id}")
                    return content_path
    
        print(f"[PATH MATCHING] Could not find content file for path: {path}")
        logger.warning(f"Could not find content file for path: {path}")
        return None

    def build_content_files_view(self):
        """Build a tree view showing actual content files"""
        if not self.content_files:
            return
    
        # Group content files by directory
        file_groups = {}
    
        for file_path in self.content_files:
            # Get relative path from temp_dir
            rel_path = os.path.relpath(file_path, self.temp_dir)
            directory = os.path.dirname(rel_path)
        
            if directory not in file_groups:
                file_groups[directory] = []
        
            file_groups[directory].append(file_path)
    
        # Create tree items for each directory and file
        for directory, files in file_groups.items():
            if directory == '.':
                # Files in root directory
                for file_path in files:
                    basename = os.path.basename(file_path)
                    item = QTreeWidgetItem(self.toc_tree, [basename])
                    item.setData(0, Qt.ItemDataRole.UserRole, {
                        "path": file_path,
                        "fragment": None,
                        "is_content_file": True
                    })
            else:
                # Create directory item
                dir_item = QTreeWidgetItem(self.toc_tree, [directory])
            
                # Add file items as children
                for file_path in files:
                    basename = os.path.basename(file_path)
                    item = QTreeWidgetItem(dir_item, [basename])
                    item.setData(0, Qt.ItemDataRole.UserRole, {
                        "path": file_path,
                        "fragment": None,
                        "is_content_file": True
                    })
    
        # Expand all items
        self.toc_tree.expandAll()

    def on_toc_item_clicked(self, item, column):
        """Handle clicks on TOC items or content files"""
        # Get the data for this item
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
    
        # Check if we're in content files mode
        is_content_file = data.get("is_content_file", False)
    
        # Try to find the matching content file
        path = data.get("path")
        if not path and not is_content_file:
            # Try to find it from the original path
            original_path = data.get("original_path")
            path = self.find_content_file(original_path)
            if not path:
                logger.warning(f"Could not find content file for {original_path}")
                return
    
        # Check if modifier keys are pressed
        modifiers = QApplication.keyboardModifiers()
        fragment = data.get("fragment")
    
        # If no modifier keys are pressed, clear the current selection and navigate
        if not (modifiers & Qt.KeyboardModifier.ControlModifier or 
                modifiers & Qt.KeyboardModifier.ShiftModifier):
            # This ensures we only have one item selected
            self.toc_tree.clearSelection()
            item.setSelected(True)
        
            # Try to find the chapter index
            if path in self.content_files:
                index = self.content_files.index(path)
                self.load_chapter(index, fragment)
            else:
                # Log that we couldn't find the content file
                logger.warning(f"Path not in content_files: {path}")
    
        # Update selection tracking immediately instead of delayed
        self.update_selection_tracking()

    def update_selection_tracking(self):
        """Update our internal selection tracking based on Qt's selection state"""
        # Clear our selection set
        self.selected_chapters.clear()
    
        # Helper function to recursively process items and their children
        def process_item_selection(item):
            # Get item data
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                # If item is selected, add its path to our set
                if item.isSelected():
                    is_content_file = data.get("is_content_file", False)
                
                    if is_content_file:
                        # In files mode, use the path directly
                        path = data.get("path")
                    else:
                        # In TOC mode, try to resolve the path
                        path = data.get("path")
                        if not path:
                            # Try to find a matching content file
                            original_path = data.get("original_path")
                            path = self.find_content_file(original_path)
                
                    if path and os.path.exists(path):
                        self.selected_chapters.add(path)
                        # Set background for visual feedback
                        item.setBackground(0, QColor(70, 130, 180, 80))
                else:
                    # Clear background if not selected
                    item.setBackground(0, QColor(0, 0, 0, 0))
        
            # Process all children
            for i in range(item.childCount()):
                process_item_selection(item.child(i))
    
        # Process all top-level items
        for i in range(self.toc_tree.topLevelItemCount()):
            process_item_selection(self.toc_tree.topLevelItem(i))
    
        # Update UI
        if self.selected_chapters:
            self.selection_label.setText(f"{len(self.selected_chapters)} chapters selected")
            self.copy_button.setEnabled(True)
        else:
            self.selection_label.setText("No chapters selected")
            self.copy_button.setEnabled(False)

    def count_toc_entries(self):
        """Count the total number of TOC entries in the tree"""
        count = 0
    
        def count_items(item):
            nonlocal count
            if item is None:
                return
        
            # Count this item
            count += 1
        
            # Count all children
            for i in range(item.childCount()):
                count_items(item.child(i))
    
        # Count all top-level items and their children
        for i in range(self.toc_tree.topLevelItemCount()):
            count_items(self.toc_tree.topLevelItem(i))
    
        return count

    def switch_view_mode(self, mode):
        """Switch between TOC structure view and content files view"""
        if mode == self.current_view_mode:
            return
    
        # Update button states
        if mode == "toc":
            self.toc_mode_btn.setChecked(True)
            self.files_mode_btn.setChecked(False)
        else:
            self.toc_mode_btn.setChecked(False)
            self.files_mode_btn.setChecked(True)
    
        # Save current view mode
        self.current_view_mode = mode
    
        # Clear selection
        self.selected_chapters.clear()
    
        # Update tree widget
        self.toc_tree.clear()
    
        if mode == "toc":
            # Rebuild TOC structure
            content_dir = os.path.dirname(self.toc_path) if hasattr(self, 'toc_path') and self.toc_path else ""
            self.parse_toc(content_dir)
        else:
            # Build content files view
            self.build_content_files_view()
    
        # Update UI
        self.selection_label.setText("No chapters selected")
        self.copy_button.setEnabled(False)
        self.chapter_label.setText(f"Chapter: --/--")
        self.text_browser.setHtml("")

    def extract_formatted_text(self, html_content, chapter_title, chapter_path, add_headers=True, 
                               format_verses=True, remove_verses=False, remove_footnotes=True, 
                               fix_paragraphs=True, remove_duplicate_titles=True):
        """Extract and format text content from HTML with proper verse formatting."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for tag in soup(['script', 'style']):
                tag.decompose()
        
            # Determine if we're in content files mode
            is_content_files_mode = self.current_view_mode == "files"
        
            # Special handling for content files mode
            if is_content_files_mode:
                # For content files mode, don't remove headers but convert them to markdown
                headers_processed = set()  # Track processed headers to avoid duplicates
            
                # Find all headers h1-h4 and convert them to markdown format
                for header_tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                    header_text = header_tag.get_text().strip()
                    if not header_text or header_text in headers_processed:
                        continue
                
                    # Add to processed set to avoid duplicates
                    headers_processed.add(header_text)
                
                    # Convert header to markdown bold syntax
                    new_tag = soup.new_tag('p')
                    new_tag.string = f"**{header_text}**"
                    header_tag.replace_with(new_tag)
            
            # Regular TOC mode - handle duplicate removal as before    
            elif remove_duplicate_titles:
                header_types = []
                if self.h1_checkbox.isChecked():
                    header_types.append('h1')
                if self.h2_checkbox.isChecked():
                    header_types.append('h2')
                if self.h3_checkbox.isChecked():
                    header_types.append('h3')
                if self.h4_checkbox.isChecked():
                    header_types.append('h4')
        
                if header_types:
                    for header in soup.find_all(header_types):
                        links = header.find_all('a')
                        if links:
                            header.decompose()

            # Process superscript elements according to options
            superscript_numbers = []

            # If removing footnotes, handle superscript elements first at the HTML level
            if remove_footnotes:
                # First, identify and remove superscript elements that appear to be footnotes
                for sup in soup.find_all('sup'):
                    sup_text = sup.get_text().strip()
                    # If it's a single letter, a short alphanumeric sequence, or common footnote pattern
                    if (len(sup_text) == 1 and sup_text.isalpha()) or \
                       re.match(r'^[a-z0-9]{1,3}$', sup_text) and not sup_text.isdigit() or \
                       re.match(r'^[\*\†\‡\§\|\¶\#][a-z0-9]*$', sup_text):
                        sup.decompose()

            # Handle verse numbers in superscript format
            for sup in soup.find_all('sup'):
                sup_text = sup.get_text().strip()

                # Check if it's a numeric superscript (likely a verse number)
                if sup_text.isdigit():
                    # Store the verse number and its parent for possible processing
                    verse_num = sup_text
    
                    if format_verses:
                        # Replace with formatted verse number
                        new_text = f"[{verse_num}] "
                        sup.replace_with(new_text)
                    elif remove_verses:
                        # Remove verse numbers entirely
                        sup.decompose()
                    else:
                        # Leave as is
                        pass

            # Extract HTML content in a way that avoids duplication
            paragraphs = []
        
            # FIX: Use a more selective approach to avoid nested duplication
            if soup.body:
                # First attempt: Get all <p> tags that don't have nested <p> tags inside them
                p_tags = []
            
                # Check if there are direct paragraph children to avoid duplication
                direct_paragraphs = soup.body.find_all('p', recursive=False)
            
                if direct_paragraphs:
                    # If we have direct paragraphs, use those
                    p_tags = direct_paragraphs
                else:
                    # Otherwise use all paragraphs (we'll deduplicate later)
                    p_tags = soup.body.find_all('p')
                
                    # If no paragraphs found, fall back to divs and other containers
                    if not p_tags:
                        # Try to find direct div children
                        p_tags = soup.body.find_all(['div', 'section', 'article'], recursive=False)
                    
                        # If still nothing, get all text containers
                        if not p_tags:
                            p_tags = soup.body.find_all(['div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            
                # Process the tags, tracking content to avoid duplication
                processed_content = set()
            
                for p in p_tags:
                    text = p.get_text().strip()
                    if not text:
                        continue
                    
                    # Create a content signature to detect duplicates
                    # Only use first 50 chars to catch near-duplicates
                    content_sig = text[:50].lower() if len(text) > 50 else text.lower()
                
                    if content_sig not in processed_content:
                        processed_content.add(content_sig)
                    
                        # Apply verse formatting if needed
                        if format_verses:
                            text = re.sub(r'^(\d{1,3})([A-Za-z])', r'[\1] \2', text)
                            text = re.sub(r'(\s)(\d{1,3})([A-Za-z])', r'\1[\2] \3', text)
                            text = re.sub(r'\[(\[\d+\])\]', r'\1', text)
                        elif remove_verses:
                            text = re.sub(r'^(\d{1,3})([A-Za-z\[])', r'\2', text)
                            text = re.sub(r'([.,:;!?—–\-])(\d{1,3})([A-Za-z\[])', r'\1\3', text)
                            text = re.sub(r'(\s)(\d{1,3})([A-Za-z\[])', r'\1\3', text)
                            text = re.sub(r'\[\d{1,3}\](\s*)', '', text)

                        if remove_footnotes:
                            text = re.sub(r'[\*\†\‡\§\|\¶\#]', '', text)
                            text = re.sub(r'[\[\(]([a-z])[\]\)]', '', text)
                            text = re.sub(r'<sup>([a-z0-9]{1,3})</sup>', '', text)
                            text = re.sub(r'(\s)([a-z])(\s|[.,;:])', r'\1\3', text)
                            text = re.sub(r'([,.;:])([a-z])(\s)', r'\1\3', text)
                            text = re.sub(r'([a-z],)([a-z])(\s|[.,;:])', r'\1\3', text)
                            text = re.sub(r'([a-z]\d+)(\s|[.,;:])', r'\2', text)

                        # Clean up HTML tags and whitespace
                        text = re.sub(r'<[^>]*>', '', text)
                        text = re.sub(r'\s+', ' ', text)
                        text = text.strip()

                        if text:
                            paragraphs.append(text)
            else:
                # Fallback if no body tag - extract all text
                text = soup.get_text().strip()
            
                # Apply the same formatting options
                if format_verses:
                    text = re.sub(r'^(\d{1,3})([A-Za-z])', r'[\1] \2', text)
                    text = re.sub(r'(\s)(\d{1,3})([A-Za-z])', r'\1[\2] \3', text)
                elif remove_verses:
                    text = re.sub(r'^(\d{1,3})([A-Za-z\[])', r'\2', text)
                    text = re.sub(r'(\s)(\d{1,3})([A-Za-z\[])', r'\1\3', text)
                    text = re.sub(r'\[\d{1,3}\](\s*)', '', text)
                
                if remove_footnotes:
                    text = re.sub(r'[\*\†\‡\§\|\¶\#]', '', text)
                    text = re.sub(r'[\[\(]([a-z])[\]\)]', '', text)
                
                # Clean up and split into paragraphs
                lines = text.split('\n')
                for line in lines:
                    clean_line = line.strip()
                    if clean_line:
                        paragraphs.append(clean_line)

            # Build chapter text with proper formatting
            chapter_text = []
        
            is_content_files_mode = self.current_view_mode == "files"
        
            if is_content_files_mode:
                # In content files mode, we already processed headers, so only add chapter title 
                # if it's not going to be redundant with the first header
                if add_headers and chapter_title and not any(chapter_title in p for p in paragraphs[:3]):
                    if self.handle_subchapters_checkbox.isChecked() and self.is_main_chapter(chapter_path):
                        chapter_text.append(f"[[{chapter_title}]]\n\n")
                    else:
                        chapter_text.append(f"**{chapter_title}**\n\n")
            else:
                # Standard TOC mode behavior
                if add_headers and chapter_title:
                    if self.handle_subchapters_checkbox.isChecked() and self.is_main_chapter(chapter_path):
                        chapter_text.append(f"[[{chapter_title}]]\n\n")
                    else:
                        chapter_text.append(f"**{chapter_title}**\n\n")

            if paragraphs:
                chapter_text.append("\n\n".join(paragraphs))

            result = "\n\n".join(chapter_text)

            if remove_verses:
                result = re.sub(r'\[\d{1,3}\](\s*)', '', result)
            elif format_verses:
                result = re.sub(r'\[(\d+)\]([A-Za-z\[])', r'[\1] \2', result)

            if fix_paragraphs:
                result = re.sub(r'\n{3,}', '\n\n', result)

            return result
        except Exception as e:
            logger.error(f"Error extracting formatted text: {str(e)}")
            traceback.print_exc()
            return f"**{chapter_title}**\n\n[Error processing chapter content]"

    def process_content_file_for_copy(self, html_content, path, format_verses=True, 
                                      remove_verses=False, remove_footnotes=True, fix_paragraphs=True):
        """Process HTML content file for copying, with special handling for headers."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for tag in soup(['script', 'style']):
                tag.decompose()
        
            # Process footnotes and verses first
            if remove_footnotes:
                for sup in soup.find_all('sup'):
                    sup_text = sup.get_text().strip()
                    if (len(sup_text) == 1 and sup_text.isalpha()) or \
                       re.match(r'^[a-z0-9]{1,3}$', sup_text) and not sup_text.isdigit() or \
                       re.match(r'^[\*\†\‡\§\|\¶\#][a-z0-9]*$', sup_text):
                        sup.decompose()

            for sup in soup.find_all('sup'):
                sup_text = sup.get_text().strip()
                if sup_text.isdigit():
                    verse_num = sup_text
                    if format_verses:
                        sup.replace_with(f"[{verse_num}] ")
                    elif remove_verses:
                        sup.decompose()
        
            # Find all headers and store their text for later identification
            header_texts = {}
            for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                text = header.get_text().strip()
                if text:
                    header_texts[text] = True
        
            logger.debug(f"Found {len(header_texts)} headers in {os.path.basename(path)}")
        
            # Extract HTML content into a structured format maintaining header info
            paragraphs = []
        
            # Process the content elements
            if soup.body:
                for element in soup.body.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    text = element.get_text().strip()
                    if not text:
                        continue
                
                    # Check if this is a header
                    is_header = element.name.lower() in ['h1', 'h2', 'h3', 'h4']
                
                    # Format text based on element type
                    if is_header:
                        # Format as markdown style header
                        paragraphs.append(f"**{text}**")
                        logger.debug(f"Formatted header: {text}")
                    else:
                        # Apply verse formatting if needed
                        if format_verses:
                            text = re.sub(r'^(\d{1,3})([A-Za-z])', r'[\1] \2', text)
                            text = re.sub(r'(\s)(\d{1,3})([A-Za-z])', r'\1[\2] \3', text)
                            text = re.sub(r'\[(\[\d+\])\]', r'\1', text)
                        elif remove_verses:
                            text = re.sub(r'^(\d{1,3})([A-Za-z\[])', r'\2', text)
                            text = re.sub(r'([.,:;!?—–\-])(\d{1,3})([A-Za-z\[])', r'\1\3', text)
                            text = re.sub(r'(\s)(\d{1,3})([A-Za-z\[])', r'\1\3', text)
                            text = re.sub(r'\[\d{1,3}\](\s*)', '', text)
                    
                        if remove_footnotes:
                            text = re.sub(r'[\*\†\‡\§\|\¶\#]', '', text)
                            text = re.sub(r'[\[\(]([a-z])[\]\)]', '', text)
                            text = re.sub(r'<sup>([a-z0-9]{1,3})</sup>', '', text)
                            text = re.sub(r'(\s)([a-z])(\s|[.,;:])', r'\1\3', text)
                            text = re.sub(r'([,.;:])([a-z])(\s)', r'\1\3', text)
                            text = re.sub(r'([a-z],)([a-z])(\s|[.,;:])', r'\1\3', text)
                            text = re.sub(r'([a-z]\d+)(\s|[.,;:])', r'\2', text)
                    
                        # Clean up HTML tags and whitespace
                        text = re.sub(r'<[^>]*>', '', text)
                        text = re.sub(r'\s+', ' ', text)
                        text = text.strip()
                    
                        if text:
                            paragraphs.append(text)
            else:
                # Fallback if no body tag
                all_text = soup.get_text()
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            
                # Check each line to see if it might be a header
                for line in lines:
                    if line in header_texts:
                        paragraphs.append(f"**{line}**")
                    else:
                        paragraphs.append(line)
        
            # Join paragraphs with proper spacing
            result = "\n\n".join(paragraphs)
        
            # Final cleanup passes
            if fix_paragraphs:
                result = re.sub(r'\n{3,}', '\n\n', result)
        
            return result
        except Exception as e:
            logger.error(f"Error processing content file for copy: {str(e)}")
            traceback.print_exc()
            return f"[Error processing file {os.path.basename(path)}]"
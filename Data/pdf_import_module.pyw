import sys, os, re, traceback
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton,
    QFileDialog, QTextBrowser, QTreeWidget, QTreeWidgetItem, QLabel,QTextEdit,
    QProgressBar, QToolButton, QMessageBox, QCheckBox, QFrame, QHeaderView, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QColor

# Use pdfminer.six for advanced layout extraction.
from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTTextContainer

def superscript_to_int(s):
    """Convert a string of superscript digits into a normal number string."""
    mapping = {
        '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
        '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9'
    }
    return "".join(mapping.get(ch, ch) for ch in s)

def is_all_caps(s):
    """Return True if s (after removing non-letter characters) is non-empty and in all uppercase."""
    letters = re.sub(r'[^A-Za-z]', '', s)
    return bool(letters) and letters == letters.upper()

def is_title_case_line(s):
    """
    Return True if the line 's' follows title capitalization guidelines.
    
    For a line to be considered title case:
    1. If it ends with a period, comma, or other sentence-ending punctuation,
       evaluate the entire sentence, not just the line
    2. Each significant word should be capitalized (first letter uppercase, rest lowercase)
    3. Minor words can be in lowercase
    4. Single words are only considered title case if they are in the allowed exceptions list
    5. If any part of the sentence doesn't follow title case, the whole line is rejected
    """
    allowed_exceptions = {"Introduction", "Abstract", "Conclusion", "Results", "Conclusions",
                         "Result", "References", "Review", "Reviews", "Prologue", "Epilogue", "Forward"}
    minor_words = {"and", "or", "the", "a", "an", "but", "nor", "at", "by", 
                  "for", "in", "of", "on", "to", "up", "with", "as", "that", "which"}
    
    # Check if this looks like it might be part of a longer sentence
    if not s.strip():
        return False
        
    # If it doesn't end with sentence-ending punctuation, it might be a fragment
    ends_with_punctuation = bool(re.search(r'[.!?]$', s.strip()))
    
    # Split the line into words, stripping punctuation but preserving it for analysis
    words_with_punct = re.findall(r'\b[\w\']+\b|[.,!?;:]', s)
    words = [w for w in words_with_punct if re.match(r'\w', w)]  # Only keep actual words
    
    if not words:
        return False
        
    # Single word check
    if len(words) == 1:
        return words[0] in allowed_exceptions
    
    # Check if the line continues a sentence
    # If it doesn't start with a capital letter and not at beginning of text, likely mid-sentence
    if words and words[0] and not words[0][0].isupper() and not s.strip() == s:
        return False
    
    # Check for proper title case format - all significant words must be properly capitalized
    for word in words:
        # Skip punctuation
        if not word or not word[0].isalpha():
            continue
            
        # If the word is a minor word, it's acceptable in lowercase
        if word.lower() in minor_words:
            continue
            
        # For other words: first letter should be uppercase, rest lowercase
        # This is the key check - if ANY word breaks the pattern, it's not title case
        if not (word[0].isupper() and word[1:].islower()):
            return False
    
    # Verify this is a complete thought - if it doesn't end with punctuation
    # and appears to be a fragment of a longer sentence, be more cautious
    if not ends_with_punctuation and len(s) > 40:  # Longer lines without ending punctuation
        # Check for sentence continuation clues
        continuation_clues = ["and ", "or ", "but ", "because ", "however ", "therefore "]
        if any(clue in s.lower() for clue in continuation_clues):
            return False
    
    # If we passed all checks, consider it title case
    return True

def is_statistical_table(text):
    """
    Identify if a paragraph is likely a statistical table by checking for number density
    and table-like patterns.
    Returns True if the line contains predominantly numbers and appears to be tabular data.
    """
    # Remove spaces to calculate character ratios
    text_no_spaces = re.sub(r'\s', '', text)
    if not text_no_spaces:
        return False
        
    # Count digits and total characters
    digit_count = sum(1 for c in text_no_spaces if c.isdigit())
    
    # If more than 30% of characters are digits and the text is longer than 30 characters,
    # it's likely tabular data (reduced threshold from 40% to 30%)
    if len(text_no_spaces) > 30 and digit_count / len(text_no_spaces) > 0.3:
        return True
    
    # If very number-dense (>50%) and at least 15 characters, it's likely tabular data
    if len(text_no_spaces) > 15 and digit_count / len(text_no_spaces) > 0.5:
        return True
        
    # Check for tabular patterns like '1.2 (45.6%)' that commonly appear in tables
    tabular_pattern = re.search(r'\d+\s*\(\s*\d+\.?\d*\s*%\s*\)', text)
    if tabular_pattern and len(text) > 20:
        return True
    
    # Look for consecutive years pattern (common in tables)
    year_pattern = re.search(r'(19|20)\d{2}\s+(?:19|20)\d{2}', text)
    if year_pattern:
        return True
    
    # Check for year series common in tables (e.g., "2004 2005 2006 2007 2008")
    if re.search(r'(?:19|20)\d{2}(?:\s+(?:19|20)\d{2}){3,}', text):
        return True
        
    # Check for rows of numbers (common in tables)
    # This looks for multiple groups of digits separated by whitespace
    row_of_numbers = re.findall(r'\b\d+\b', text)
    if len(row_of_numbers) >= 5:  # If we have 5 or more separate numbers, likely a table
        return True

    # Check for "Table" keyword followed by number
    if re.search(r'Table\s+\d+', text, re.IGNORECASE) and digit_count > 5:
        return True
        
    return False

def is_copyright_line(text):
    """Check if a line contains copyright information."""
    copyright_keywords = ['copyright', '©', 'all rights reserved', 'www.', '.org', '.com']
    text_lower = text.lower()
    
    # Check if the text contains any copyright keywords
    if any(keyword in text_lower for keyword in copyright_keywords):
        # Additional check for common copyright patterns
        if re.search(r'(copyright|©|rights reserved)', text_lower) or \
           ('www.' in text_lower and any(domain in text_lower for domain in ['.org', '.com', '.net'])):
            return True
    return False

def reform_paragraphs(text):
    """
    Reform paragraphs by removing single line breaks within paragraph blocks.
    Preserves formatting of headers (wrapped in ** markers).
    """
    # Split the text by double line breaks to get paragraphs
    paragraphs = re.split(r'\n\n+', text)
    
    # Process each paragraph to remove single line breaks
    for i in range(len(paragraphs)):
        # Skip headers and section dividers - don't modify their formatting
        if re.match(r'^\s*\*\*.*?\*\*\s*$', paragraphs[i]) or re.match(r'^\s*\[\[.*?\]\]\s*$', paragraphs[i]):
            continue
        
        # Replace single line breaks with spaces in this paragraph
        paragraphs[i] = re.sub(r'\n', ' ', paragraphs[i])
        
        # Remove any multiple spaces that might have been created
        paragraphs[i] = re.sub(r' {2,}', ' ', paragraphs[i])
        
        # Trim leading/trailing whitespace
        paragraphs[i] = paragraphs[i].strip()
    
    # Join the paragraphs back together with double line breaks
    return '\n\n'.join(paragraphs)

class PDFImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Import")
        self.setMinimumSize(900, 600)
        self.pages = []             # List to hold raw text for each PDF page
        self.current_page_index = 0
        self.selected_pages = set() # Track selected page indices
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Pages List
        pages_container = QWidget()
        pages_layout = QVBoxLayout(pages_container)
        pages_layout.setContentsMargins(0, 0, 0, 0)
        pages_header = QLabel("Pages")
        pages_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #203740; padding-bottom: 5px;")
        self.pages_tree = QTreeWidget()
        self.pages_tree.setHeaderLabel("Page List")
        self.pages_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.pages_tree.itemClicked.connect(self.on_page_item_clicked)
        self.pages_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        pages_layout.addWidget(pages_header)
        pages_layout.addWidget(self.pages_tree)

        # Selection buttons
        select_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_pages)
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_page_selection)
        select_buttons_layout.addWidget(self.select_all_btn)
        select_buttons_layout.addWidget(self.clear_selection_btn)
        select_buttons_layout.addStretch()
        pages_layout.addLayout(select_buttons_layout)

        # Right: Preview and Format Options
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_header = QLabel("Page Preview")
        preview_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #203740; padding-bottom: 5px;")
        self.text_browser = QTextBrowser()
        self.text_browser.setReadOnly(True)
        preview_layout.addWidget(preview_header)
        preview_layout.addWidget(self.text_browser)

        # Format Options section (collapsible)
        format_options_section = self.create_format_options_section()
        preview_layout.addWidget(format_options_section)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_page)
        self.prev_button.setEnabled(False)
        self.page_label = QLabel("Page: --/--")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_page)
        self.next_button.setEnabled(False)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.page_label)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_button)
        preview_layout.addLayout(nav_layout)

        splitter.addWidget(pages_container)
        splitter.addWidget(preview_container)
        splitter.setSizes([300, 700])
        main_layout.addWidget(splitter)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        open_button = QPushButton("Open PDF")
        open_button.clicked.connect(self.open_file_dialog)
        self.copy_button = QPushButton("Copy Selected")
        self.copy_button.clicked.connect(self.copy_selected_to_clipboard)
        self.copy_button.setEnabled(False)
        done_button = QPushButton("Done")
        done_button.clicked.connect(self.accept)
        bottom_layout.addWidget(open_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.copy_button)
        bottom_layout.addWidget(done_button)
        main_layout.addLayout(bottom_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

    def create_format_options_section(self):
        """Create a collapsible section for formatting options applied on copy."""
        format_section = QWidget()
        layout = QVBoxLayout(format_section)
        layout.setContentsMargins(0, 0, 0, 0)

        header_layout = QHBoxLayout()
        self.format_toggle_btn = QToolButton()
        self.format_toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.format_toggle_btn.setText("Format Options")
        self.format_toggle_btn.setCheckable(True)
        self.format_toggle_btn.setChecked(False)
        self.format_toggle_btn.toggled.connect(self.toggle_format_options)
        header_layout.addWidget(self.format_toggle_btn)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.format_options_container = QFrame()
        self.format_options_container.setFrameShape(QFrame.Shape.StyledPanel)
        self.format_options_container.setStyleSheet(
            "background-color: #f5f8fa; border: 1px solid #dde4e9; border-radius: 4px; margin-top: 3px;"
        )
        self.format_options_container.setVisible(False)
        options_layout = QVBoxLayout(self.format_options_container)
        options_layout.setContentsMargins(10, 10, 10, 10)
        options_layout.setSpacing(10)

        self.fix_paragraphs_checkbox = QCheckBox("Fix paragraph spacing (no indentation)")
        self.fix_paragraphs_checkbox.setChecked(True)
        self.fix_paragraphs_checkbox.setToolTip("Collapse extra blank lines; no extra indentation is applied")
        options_layout.addWidget(self.fix_paragraphs_checkbox)

        # Separate header detection options.
        self.detect_all_caps_checkbox = QCheckBox("Detect ALL CAPS lines as headers")
        self.detect_all_caps_checkbox.setChecked(True)
        self.detect_all_caps_checkbox.setToolTip("Wrap lines that are entirely uppercase in ** markers with extra spacing")
        options_layout.addWidget(self.detect_all_caps_checkbox)
        
        self.detect_title_case_checkbox = QCheckBox("Detect Title Case lines as headers")
        self.detect_title_case_checkbox.setChecked(True)
        self.detect_title_case_checkbox.setToolTip(
            "Wrap lines that follow title capitalization guidelines in ** markers with extra spacing. "
            "A line counts as title case only if it has more than one word, unless that word is one of the allowed exceptions."
        )
        options_layout.addWidget(self.detect_title_case_checkbox)

        # Superscript formatting options.
        self.format_verses_checkbox = QCheckBox("Format superscript numbers as [1], [2], etc.")
        self.format_verses_checkbox.setChecked(False)
        self.format_verses_checkbox.setToolTip("Reformat detected superscript numbers into bracketed numbers")
        options_layout.addWidget(self.format_verses_checkbox)
        self.remove_verses_checkbox = QCheckBox("Remove superscript numbers")
        self.remove_verses_checkbox.setChecked(True)
        self.remove_verses_checkbox.setToolTip("Remove any detected superscript numbers")
        options_layout.addWidget(self.remove_verses_checkbox)

        # Footnote formatting options.
        self.remove_footnotes_checkbox = QCheckBox("Remove footnote markers and references")
        self.remove_footnotes_checkbox.setChecked(True)
        self.remove_footnotes_checkbox.setToolTip("Remove common footnote markers such as *, †, ‡, etc.")
        options_layout.addWidget(self.remove_footnotes_checkbox)

        # New options for statistical tables and copyright
        self.remove_tables_checkbox = QCheckBox("Remove statistical tables (replace with '[Table removed]')")
        self.remove_tables_checkbox.setChecked(True)
        self.remove_tables_checkbox.setToolTip("Remove text that appears to be statistical tables (text with high density of numbers)")
        options_layout.addWidget(self.remove_tables_checkbox)

        self.remove_copyright_checkbox = QCheckBox("Remove copyright lines")
        self.remove_copyright_checkbox.setChecked(True)
        self.remove_copyright_checkbox.setToolTip("Remove lines that contain copyright information")
        options_layout.addWidget(self.remove_copyright_checkbox)

        self.reform_paragraphs_checkbox = QCheckBox("Reform paragraphs (join lines within paragraphs)")
        self.reform_paragraphs_checkbox.setChecked(True)
        self.reform_paragraphs_checkbox.setToolTip("Combine lines within paragraphs to form continuous text")
        options_layout.addWidget(self.reform_paragraphs_checkbox)

        layout.addWidget(self.format_options_container)
        return format_section

    def toggle_format_options(self, checked):
        self.format_options_container.setVisible(checked)
        self.format_toggle_btn.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.adjustSize()

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF File", "", "PDF Files (*.pdf);;All Files (*)"
        )
        if file_path:
            self.open_pdf(file_path)

    def open_pdf(self, file_path):
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(5)
            self.progress_bar.setFormat("Opening PDF file...")
            QApplication.processEvents()

            # Open the PDF with PyMuPDF
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            total_pages = len(doc)
        
            self.progress_bar.setValue(10)
            self.progress_bar.setFormat(f"Extracting text from {total_pages} pages...")
            QApplication.processEvents()
        
            # Extract text using PyMuPDF
            pages = []
            for page_idx, page in enumerate(doc):
                # Extract text with 'text' mode - this gives plain text with proper spacing
                page_text = page.get_text("text")
            
                # Do some basic cleanup
                # 1. Normalize line endings
                page_text = page_text.replace('\r\n', '\n').replace('\r', '\n')
            
                # 2. Remove excessive blank lines (more than 2 in a row)
                page_text = re.sub(r'\n{3,}', '\n\n', page_text)
            
                pages.append(page_text)
            
                # Update progress
                progress = 10 + int(80 * (page_idx + 1) / total_pages)
                self.progress_bar.setValue(progress)
                self.progress_bar.setFormat(f"Processing page {page_idx + 1}/{total_pages}...")
                QApplication.processEvents()
        
            doc.close()
            self.pages = pages

            # Populate UI with extracted pages
            self.progress_bar.setValue(90)
            self.progress_bar.setFormat("Updating interface...")
            QApplication.processEvents()
    
            self.update_pages_tree()
            if self.pages:
                self.load_page(0)  # Show raw text in preview
                self.page_label.setText(f"Page: 1/{len(self.pages)}")
                self.prev_button.setEnabled(False)
                self.next_button.setEnabled(len(self.pages) > 1)
    
            self.setWindowTitle(f"PDF Import - {os.path.basename(file_path)}")
    
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Complete")
            QApplication.processEvents()
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Failed to open PDF file:\n{str(e)}")
            traceback.print_exc()

    def update_pages_tree(self):
        self.pages_tree.clear()
        for i in range(len(self.pages)):
            item = QTreeWidgetItem(self.pages_tree, [f"Page {i+1}"])
            item.setData(0, Qt.ItemDataRole.UserRole, i)
        self.pages_tree.expandAll()
        self.update_selection_tracking()

    def on_page_item_clicked(self, item, column):
        index = item.data(0, Qt.ItemDataRole.UserRole)
        if index is not None:
            self.load_page(index)
        QTimer.singleShot(10, self.update_selection_tracking)

    def load_page(self, index):
        if 0 <= index < len(self.pages):
            self.current_page_index = index
            self.text_browser.setPlainText(self.pages[index])
            self.page_label.setText(f"Page: {index+1}/{len(self.pages)}")
            self.update_navigation_buttons()
            self.update_pages_tree_selection(index)

    def process_text_content(self, text):
        """
        Process text (when copying) with improved context awareness for header detection.
        """
        lines = text.splitlines()
        processed_lines = []
    
        # First pass: identify potential sections and paragraphs
        text_blocks = []
        current_block = []
    
        for i, line in enumerate(lines):
            stripped = line.strip()
        
            # Skip empty lines but use them as section breaks
            if not stripped:
                if current_block:
                    text_blocks.append(current_block)
                    current_block = []
                continue
            
            # Skip copyright lines if option is checked
            if self.remove_copyright_checkbox.isChecked() and is_copyright_line(stripped):
                continue
            
            # Handle statistical tables if option is checked
            if self.remove_tables_checkbox.isChecked() and (
                re.search(r'Table\s+\d+\.?\s+', stripped, re.IGNORECASE) or 
                is_statistical_table(stripped)
            ):
                if current_block:
                    text_blocks.append(current_block)
                    current_block = []
                text_blocks.append(["[Table removed]"])
                continue
        
            # Apply inline formatting
            processed_line = stripped
            if self.format_verses_checkbox.isChecked():
                processed_line = re.sub(r'([⁰¹²³⁴⁵⁶⁷⁸⁹]+)', 
                                       lambda m: f"[{superscript_to_int(m.group(1))}] ", 
                                       processed_line)
            elif self.remove_verses_checkbox.isChecked():
                processed_line = re.sub(r'[⁰¹²³⁴⁵⁶⁷⁸⁹]+', '', processed_line)

            if self.remove_footnotes_checkbox.isChecked():
                processed_line = re.sub(r'[\*\†\‡\§\¶]', '', processed_line)

            processed_line = re.sub(r'[■]', '', processed_line)
        
            # Add to current block
            current_block.append(processed_line)
    
        # Don't forget the last block
        if current_block:
            text_blocks.append(current_block)
    
        # Second pass: analyze blocks for header characteristics
        for block in text_blocks:
            # Single line blocks are candidates for headers
            if len(block) == 1:
                line = block[0]
            
                # Definite header indicators
                is_header = False
            
                # 1. ALL CAPS is almost always a header
                if self.detect_all_caps_checkbox.isChecked() and is_all_caps(line):
                    processed_lines.append(f"\n**{line}**\n")
                    is_header = True
            
                # 2. Title case needs more careful handling
                elif self.detect_title_case_checkbox.isChecked():
                    # Additional checks to reduce false positives:
                    # - Short phrases (less than 60 chars) are more likely to be headers
                    # - No sentence-ending punctuation in the middle
                    # - No connecting words that suggest it's part of a paragraph
                    if (is_title_case_line(line) and 
                        len(line) < 60 and
                        not re.search(r'[.!?]\s+[A-Z]', line) and
                        not any(connector in line.lower() for connector in 
                               ["therefore", "however", "moreover", "because"])):
                        processed_lines.append(f"\n**{line}**\n")
                        is_header = True
            
                if not is_header:
                    processed_lines.append(line)
        
            # Multi-line blocks are regular paragraphs
            else:
                # Join with newlines first (we'll reform later if needed)
                for line in block:
                    processed_lines.append(line)
    
        # Join all processed lines
        processed_text = "\n".join(processed_lines)
    
        # Apply paragraph reformatting as a final step if enabled
        if self.reform_paragraphs_checkbox.isChecked():
            processed_text = reform_paragraphs(processed_text)
        
        return processed_text

    def update_navigation_buttons(self):
        self.prev_button.setEnabled(self.current_page_index > 0)
        self.next_button.setEnabled(self.current_page_index < len(self.pages) - 1)

    def previous_page(self):
        if self.current_page_index > 0:
            self.load_page(self.current_page_index - 1)

    def next_page(self):
        if self.current_page_index < len(self.pages) - 1:
            self.load_page(self.current_page_index + 1)

    def update_pages_tree_selection(self, current_index):
        def search_tree(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == current_index:
                self.pages_tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if search_tree(item.child(i)):
                    return True
            return False

        for i in range(self.pages_tree.topLevelItemCount()):
            if search_tree(self.pages_tree.topLevelItem(i)):
                break

    def update_selection_tracking(self):
        self.selected_pages.clear()
        for i in range(self.pages_tree.topLevelItemCount()):
            item = self.pages_tree.topLevelItem(i)
            self._update_item_selection(item)
        self.copy_button.setEnabled(bool(self.selected_pages))

    def _update_item_selection(self, item):
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if item.isSelected() and idx is not None:
            self.selected_pages.add(idx)
            item.setBackground(0, QColor(70, 130, 180, 80))
        else:
            item.setBackground(0, QColor(0, 0, 0, 0))
        for i in range(item.childCount()):
            self._update_item_selection(item.child(i))

    def select_all_pages(self):
        current_mode = self.pages_tree.selectionMode()
        self.pages_tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        self.pages_tree.selectAll()
        self.update_selection_tracking()
        self.pages_tree.setSelectionMode(current_mode)

    def clear_page_selection(self):
        self.pages_tree.clearSelection()
        self.selected_pages.clear()
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
        """Copy the text content from all selected pages and insert directly into the parent text editor"""
        if not self.selected_pages:
            QMessageBox.warning(self, "No Selection", "Please select at least one page to copy.")
            return
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(10)
        self.progress_bar.setFormat("Processing selected pages...")
        QApplication.processEvents()
    
        try:
            combined_text = []
            total_pages = len(self.selected_pages)
        
            for i, idx in enumerate(sorted(self.selected_pages)):
                if 0 <= idx < len(self.pages):
                    # Update progress
                    progress = int(10 + (i / total_pages) * 80)
                    self.progress_bar.setValue(progress)
                    self.progress_bar.setFormat(f"Processing page {i+1}/{total_pages}...")
                    QApplication.processEvents()
                
                    combined_text.append(self.process_text_content(self.pages[idx]))
        
            all_text = "\n\n".join(combined_text)
        
            # Try to find parent CreateTranscriptTextEdit
            self.progress_bar.setValue(95)
            self.progress_bar.setFormat("Inserting content...")
            QApplication.processEvents()
        
            text_edit = self.find_parent_text_edit()
        
            if text_edit:
                # Insert the text at the current cursor position
                text_edit.insertPlainText(all_text)
            
                # Trigger highlights and updates
                if hasattr(text_edit, 'schedule_highlight'):
                    text_edit.schedule_highlight()
            
                # Notify that changes are pending
                if hasattr(text_edit, '_notify_changes_pending'):
                    text_edit._notify_changes_pending()
            
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Successfully inserted content!")
            
                # Close the dialog after a short delay
                QTimer.singleShot(500, self.accept)
            else:
                # Fallback to clipboard
                clipboard = QApplication.clipboard()
                clipboard.setText(all_text)
            
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Successfully copied to clipboard!")
            
                QMessageBox.information(
                    self,
                    "Copy Complete",
                    f"Successfully copied {len(self.selected_pages)} pages to clipboard."
                )
        except Exception as e:
            self.progress_bar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Failed to process content:\n{str(e)}")
            traceback.print_exc()
        
        # Hide progress bar after a delay
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = PDFImportDialog()
    dialog.show()
    sys.exit(app.exec())
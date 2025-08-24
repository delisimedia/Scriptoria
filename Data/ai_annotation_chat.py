"""
AI Annotation Chat Module for Scriptoria

Provides an AI-powered chat interface for querying and analyzing annotations.
Users can ask questions about their annotations and receive intelligent responses
with clickable annotation references.
"""

import json
import os
import re
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
                             QGroupBox, QComboBox, QPushButton, QProgressBar,
                             QMessageBox, QFormLayout, QApplication, QCheckBox,
                             QSplitter, QFrame, QTextBrowser, QLineEdit)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor, QDesktopServices

try:
    from google import genai
    import google.genai.types as genai_types
    NEW_API = True
except ImportError:
    import google.generativeai as genai
    NEW_API = False


class QueryTextEdit(QTextEdit):
    """Custom QTextEdit that handles Enter/Shift+Enter for submission"""
    
    def __init__(self, submit_callback=None):
        super().__init__()
        self.submit_callback = submit_callback
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter: Insert new line
                super().keyPressEvent(event)
            else:
                # Enter: Submit query
                if self.submit_callback:
                    self.submit_callback()
                return
        else:
            # All other keys: normal behavior
            super().keyPressEvent(event)


class AIChatWorkerThread(QThread):
    """Worker thread for AI chat processing"""
    
    response_received = pyqtSignal(str)
    chunk_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    retry_suggested = pyqtSignal(str)
    
    def __init__(self, prompt, api_key, model="gemini-2.5-pro", max_retries=2):
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self._stop_requested = False
        
    def stop_generation(self):
        """Request to stop the generation"""
        self._stop_requested = True
        
    def run(self):
        """Execute AI request with retry logic"""
        for attempt in range(self.max_retries + 1):
            if self._stop_requested:
                return
                
            try:
                if attempt > 0:
                    print(f"AI chat attempt {attempt + 1}/{self.max_retries + 1}")
                    import time
                    time.sleep(2 ** attempt)
                
                if NEW_API:
                    client = genai.Client(api_key=self.api_key)
                    config = genai_types.GenerateContentConfig(
                        temperature=0.7,
                        top_p=0.9,
                    )
                    
                    response = client.models.generate_content(
                        model=self.model,
                        contents=self.prompt,
                        config=config
                    )
                    
                    full_response = response.text if hasattr(response, 'text') else str(response)
                    if full_response:
                        self.chunk_received.emit(full_response)
                        self.response_received.emit(full_response)
                        return
                    else:
                        self.error_occurred.emit("No response generated from AI")
                        return
                        
                else:
                    genai.configure(api_key=self.api_key)
                    model = genai.GenerativeModel(self.model)
                    
                    response = model.generate_content(
                        self.prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,
                            top_p=0.9,
                        ),
                        stream=True
                    )
                    
                    full_response = ""
                    for chunk in response:
                        if self._stop_requested:
                            return
                        if chunk.text:
                            full_response += chunk.text
                            self.chunk_received.emit(chunk.text)
                            
                    if full_response:
                        self.response_received.emit(full_response)
                        return
                    else:
                        self.error_occurred.emit("No response generated from AI")
                        return
                        
            except Exception as e:
                error_str = str(e).lower()
                retryable_errors = [
                    '500 internal', 'internal server error', 'service unavailable',
                    'timeout', 'connection error', 'network error', 'temporarily unavailable'
                ]
                
                is_retryable = any(err in error_str for err in retryable_errors)
                
                if is_retryable and attempt < self.max_retries:
                    print(f"Retryable error on attempt {attempt + 1}: {str(e)}")
                    continue
                else:
                    if is_retryable:
                        error_message = (
                            f"AI service temporarily unavailable after {self.max_retries + 1} attempts.\n\n"
                            f"Please try again in a few moments.\n\n"
                            f"Original error: {str(e)}"
                        )
                        self.retry_suggested.emit(error_message)
                    else:
                        self.error_occurred.emit(f"AI chat failed: {str(e)}")
                    return


class AIAnnotationChatDialog(QDialog):
    """
    Dialog for AI-powered annotation querying and analysis.
    """
    
    def __init__(self, parent, web_view, main_window):
        super().__init__(parent)
        self.web_view = web_view
        self.main_window = main_window
        self.annotations_data = []
        self.full_transcript = ""
        self.api_key = ""
        self.worker_thread = None
        
        self.setWindowTitle("Ask Gemini (Annotations)")
        self.setModal(False)  # Non-modal dialog
        
        # Set minimum width and let height adjust
        self.setMinimumWidth(600)
        self.resize(650, 750)  # Increased by 100px width and height
        
        self.setup_ui()
        self.load_transcript()
        self.load_api_key()
        self.load_transcript_data()
        self.load_annotations_data()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("<h2>Ask Gemini about your Annotations</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Info note
        info_note = QLabel(
            "<b>Ask questions about your annotations:</b> Ask Gemini to find, analyze, or recommend "
            "specific annotations based on content, themes, or context. Responses will include clickable annotation references."
        )
        info_note.setWordWrap(True)
        info_note.setStyleSheet("padding: 10px; background-color: #f0f8ff; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(info_note)
        
        # Collapsible transcript information section
        transcript_container = QFrame()
        transcript_container_layout = QVBoxLayout(transcript_container)
        transcript_container_layout.setContentsMargins(0, 0, 0, 0)
        transcript_container_layout.setSpacing(0)
        
        # Clickable header
        self.transcript_header = QPushButton("📄 Transcript Information ▶")
        self.transcript_header.setStyleSheet("""
            QPushButton {
                text-align: left;
                border: none;
                padding: 6px 10px;
                background-color: transparent;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.transcript_header.clicked.connect(self.toggle_transcript_section)
        transcript_container_layout.addWidget(self.transcript_header)
        
        # Collapsible content
        self.transcript_content = QFrame()
        self.transcript_content.hide()  # Start collapsed
        self.transcript_content.setStyleSheet("""
            QFrame {
                border: none;
                background-color: transparent;
                padding: 5px;
            }
        """)
        transcript_layout = QFormLayout(self.transcript_content)
        
        self.transcript_title = QLineEdit()
        self.transcript_title.setPlaceholderText("e.g., Interview with John Smith, Chapter 5: The Journey")
        
        title_label = QLabel("Title:")
        title_label.setStyleSheet("border: none; background: transparent;")
        transcript_layout.addRow(title_label, self.transcript_title)
        
        self.transcript_description = QTextEdit()
        self.transcript_description.setMaximumHeight(50)
        self.transcript_description.setPlaceholderText("Brief description of what this transcript contains...")
        self.transcript_description.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
                background-color: white;
            }
            QTextEdit:focus {
                border: 1px solid #4a90e2;
            }
        """)
        
        desc_label = QLabel("Description:")
        desc_label.setStyleSheet("border: none; background: transparent;")
        transcript_layout.addRow(desc_label, self.transcript_description)
        
        # Compact save button
        save_button_layout = QHBoxLayout()
        self.save_transcript_button = QPushButton("💾 Save")
        self.save_transcript_button.setMaximumWidth(80)
        self.save_transcript_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        self.save_transcript_button.clicked.connect(self.save_transcript_data)
        save_button_layout.addWidget(self.save_transcript_button)
        save_button_layout.addStretch()
        transcript_layout.addRow("", save_button_layout)
        
        transcript_container_layout.addWidget(self.transcript_content)
        layout.addWidget(transcript_container)
        
        # Configuration section
        config_layout = QHBoxLayout()
        
        # AI Model selector
        model_group = QGroupBox("AI Model")
        model_layout = QFormLayout(model_group)
        
        self.model_selector = QComboBox()
        self.model_selector.addItems(["gemini-2.5-flash", "gemini-2.5-pro"])  # Flash as default
        model_layout.addRow("Model:", self.model_selector)
        
        # Include transcript context checkbox
        self.include_transcript = QCheckBox("Include full transcript context")
        self.include_transcript.setChecked(False)  # Unchecked by default
        self.include_transcript.setToolTip("When checked, AI gets full transcript for better context")
        model_layout.addRow(self.include_transcript)
        
        config_layout.addWidget(model_group)
        
        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 8px;")
        config_layout.addWidget(self.stats_label)
        
        config_layout.addStretch()
        layout.addLayout(config_layout)
        
        # Main chat interface
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Query input section
        query_widget = QGroupBox("Your Question")
        query_layout = QVBoxLayout(query_widget)
        
        self.query_input = QueryTextEdit(submit_callback=self.ask_gemini)
        self.query_input.setPlaceholderText(
            "Ask questions about your annotations... (Press Enter to send, Shift+Enter for new line)\n\n"
            "Examples:\n"
            "- Can you find annotations about John's motorcycle hobby?\n"
            "- Which annotations show emotional turning points?\n"
            "- What annotations would work best for an opening sequence?\n"
            "- Show me annotations tagged with #key-moment"
        )
        self.query_input.setMaximumHeight(80)
        query_layout.addWidget(self.query_input)
        
        splitter.addWidget(query_widget)
        
        # Response section
        response_widget = QGroupBox("Gemini Response")
        response_layout = QVBoxLayout(response_widget)
        
        self.response_display = QTextBrowser()  # Use QTextBrowser for clickable links
        self.response_display.setReadOnly(True)
        self.response_display.setPlaceholderText("Ask a question above and Gemini will respond with annotation analysis and recommendations...")
        self.response_display.setOpenExternalLinks(False)  # We'll handle clicks manually
        self.response_display.setStyleSheet("""
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.4;
            }
        """)
        response_layout.addWidget(self.response_display)
        
        splitter.addWidget(response_widget)
        
        # Set splitter proportions - smaller query section, larger response
        splitter.setSizes([120, 500])
        layout.addWidget(splitter)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                color: #495057;
                background-color: #f8f9fa;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #28a745, stop:0.5 #20c997, stop:1 #28a745);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_response)
        self.clear_button.setToolTip("Clear the response area")
        
        self.ask_button = QPushButton("Ask Gemini")
        self.ask_button.clicked.connect(self.ask_gemini)
        self.ask_button.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.ask_button.setDefault(True)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setStyleSheet("font-weight: bold; padding: 8px 16px; background-color: #dc3545; color: white;")
        self.stop_button.hide()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.hide)  # Hide instead of close
        
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.ask_button)
        
        layout.addLayout(button_layout)
        
        # Connect Enter key to ask button
        self.query_input.setAcceptRichText(False)
        
        # Connect click handler for annotation links
        self.response_display.anchorClicked.connect(self.handle_annotation_click)
        
    def load_transcript(self):
        """Load the full transcript from the web view"""
        if not self.web_view:
            return
        
        def handle_transcript(html):
            if html:
                from bs4 import BeautifulSoup
                
                soup = BeautifulSoup(html, 'html.parser')
                
                for element in soup(["style", "script", "head"]):
                    element.decompose()
                
                transcript_parts = []
                speech_headers = soup.find_all('div', class_='speech-header')
                
                if speech_headers:
                    for header in speech_headers:
                        title_elem = header.find(class_='speech-title')
                        
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            
                            content_elem = None
                            next_sibling = header.find_next_sibling()
                            while next_sibling:
                                if next_sibling.name == 'div' and 'speech-content' in next_sibling.get('class', []):
                                    content_elem = next_sibling
                                    break
                                next_sibling = next_sibling.find_next_sibling()
                            
                            if not content_elem:
                                parent = header.find_parent()
                                if parent:
                                    content_elem = parent.find(class_='speech-content')
                            
                            if content_elem:
                                content_text = content_elem.get_text(separator=' ', strip=True)
                                if title_text and content_text:
                                    formatted_entry = f"{title_text}: {content_text}"
                                    transcript_parts.append(formatted_entry)
                            elif title_text:
                                transcript_parts.append(title_text)
                else:
                    text = soup.get_text(separator=' ', strip=True)
                    import re
                    text = re.sub(r'\s+', ' ', text).strip()
                    transcript_parts.append(text)
                
                self.full_transcript = '\n\n'.join(transcript_parts)
                print(f"DEBUG: Loaded transcript with {len(self.full_transcript)} characters for annotation chat")
                
        self.web_view.page().toHtml(handle_transcript)
        
    def load_api_key(self):
        """Load API key from file"""
        import os
        
        try:
            possible_paths = [
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "api_key.txt"),
                os.path.join(os.path.dirname(__file__), "api_key.txt"),
                "data/api_key.txt",
                "api_key.txt"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        self.api_key = f.read().strip()
                        return
                        
            QMessageBox.information(self, "API Key Setup", 
                "Please ensure your Gemini API key is configured in data/api_key.txt")
                
        except Exception as e:
            print(f"Error loading API key: {e}")
    
    def load_transcript_data(self):
        """Load persistent transcript data from session file (shared with Generate Notes)"""
        try:
            if not hasattr(self.main_window, 'current_session_file') or not self.main_window.current_session_file:
                print("DEBUG: No session file available to load transcript data")
                return
            
            session_file = self.main_window.current_session_file
            if not os.path.exists(session_file):
                print("DEBUG: Session file does not exist")
                return
            
            # Load session data from file
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Load saved values from session data (same keys as Generate Notes)
            title = session_data.get('ai_notes_title', '')
            description = session_data.get('ai_notes_description', '')
            
            # Set UI values
            self.transcript_title.setText(title)
            self.transcript_description.setPlainText(description)
            
            print(f"DEBUG: Loaded transcript data from session - title: '{title}'")
        except Exception as e:
            print(f"Error loading transcript data: {e}")
    
    def save_transcript_data(self):
        """Save transcript data directly to session file (shared with Generate Notes)"""
        try:
            if not hasattr(self.main_window, 'current_session_file') or not self.main_window.current_session_file:
                print("DEBUG: No session file available to save transcript data")
                return
            
            session_file = self.main_window.current_session_file
            if not os.path.exists(session_file):
                print("DEBUG: Session file does not exist")
                return
            
            # Load current session data
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # Update AI notes configuration fields (same keys as Generate Notes)
            session_data['ai_notes_title'] = self.transcript_title.text().strip()
            session_data['ai_notes_description'] = self.transcript_description.toPlainText().strip()
            
            # Atomic write using temporary file for safety
            import tempfile
            import shutil
            
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, 
                                               dir=os.path.dirname(session_file)) as tf:
                    temp_file = tf.name
                    json.dump(session_data, tf, indent=2, ensure_ascii=False)
                
                # Atomic replacement
                if os.path.exists(session_file):
                    os.remove(session_file)
                shutil.move(temp_file, session_file)
                temp_file = None
                
                print(f"DEBUG: Saved transcript data to session file - title: '{session_data['ai_notes_title']}'")
                
            finally:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                
        except Exception as e:
            print(f"Error saving transcript data: {e}")
    
    def toggle_transcript_section(self):
        """Toggle the visibility of the transcript information section"""
        is_visible = self.transcript_content.isVisible()
        
        if is_visible:
            # Collapse
            self.transcript_content.hide()
            self.transcript_header.setText("📄 Transcript Information ▶")
        else:
            # Expand
            self.transcript_content.show()
            self.transcript_header.setText("📄 Transcript Information ▼")
            
    def _get_active_theme_search(self):
        """Get the active ThemeViewSearch instance from the main window"""
        try:
            # Navigate up to find main window with script_search
            current_parent = self.main_window
            while current_parent:
                if hasattr(current_parent, 'script_search'):
                    theme_search = current_parent.script_search
                    # Verify it's the right type and has the filtering method
                    if hasattr(theme_search, '_annotation_matches_current_filters'):
                        return theme_search
                current_parent = getattr(current_parent, 'parent', lambda: None)()
            
            print("DEBUG: Could not find ThemeViewSearch instance")
            return None
        except Exception as e:
            print(f"DEBUG: Error getting ThemeViewSearch: {e}")
            return None
    
    def _has_active_filters(self, theme_search):
        """Check if ThemeViewSearch has any active filters"""
        if not theme_search:
            return False
        
        return (
            bool(getattr(theme_search, 'current_search_text', '').strip()) and 
            getattr(theme_search, 'search_confirmed', False)
        ) or (
            bool(getattr(theme_search, 'selected_tags', set()))
        ) or (
            bool(getattr(theme_search, 'selected_headers', set()))
        ) or (
            bool(getattr(theme_search, 'selected_themes', set()))
        ) or (
            getattr(theme_search, 'favorites_only', False)
        ) or (
            getattr(theme_search, 'hide_used', 0) != 0  # 0 = show all, 1 = hide used, 2 = show only used
        ) or (
            getattr(theme_search, 'global_search_enabled', False)
        )

    def load_annotations_data(self):
        """Load and prepare annotations data for AI context, respecting active filters"""
        if not self.web_view or not hasattr(self.web_view, 'annotations'):
            self.stats_label.setText("❌ No annotations found")
            return
        
        # Get active theme view search filters
        theme_search = self._get_active_theme_search()
        
        self.annotations_data = []
        total_annotations = 0
        divider_count = 0
        
        for annotation in self.web_view.annotations:
            # Skip dividers
            if annotation.get('divider'):
                divider_count += 1
                continue
            
            total_annotations += 1
            
            # Apply current filters if theme search is available
            if theme_search and hasattr(theme_search, '_annotation_matches_current_filters'):
                if not theme_search._annotation_matches_current_filters(annotation):
                    continue  # Skip filtered out annotations
            
            # Include in AI context
            annotation_info = {
                'id': annotation.get('id', ''),
                'text': annotation.get('text', ''),
                'scene': annotation.get('scene', ''),
                'secondary_scenes': annotation.get('secondary_scenes', []),
                'notes': annotation.get('notes', ''),
                'notes_html': annotation.get('notes_html', ''),
                'tags': annotation.get('tags', [])
            }
            self.annotations_data.append(annotation_info)
        
        filtered_count = len(self.annotations_data)
        
        # Update stats display to show filtering status
        if theme_search and self._has_active_filters(theme_search):
            active_filters = []
            if getattr(theme_search, 'current_search_text', '').strip() and getattr(theme_search, 'search_confirmed', False):
                active_filters.append(f"search: '{theme_search.current_search_text[:20]}'")
            if getattr(theme_search, 'selected_tags', set()):
                active_filters.append(f"{len(theme_search.selected_tags)} tags")
            if getattr(theme_search, 'selected_headers', set()):
                active_filters.append(f"{len(theme_search.selected_headers)} headers")
            if getattr(theme_search, 'selected_themes', set()):
                active_filters.append(f"{len(theme_search.selected_themes)} themes")
            if getattr(theme_search, 'favorites_only', False):
                active_filters.append("favorites only")
            if getattr(theme_search, 'hide_used', 0) == 1:
                active_filters.append("hide used")
            elif getattr(theme_search, 'hide_used', 0) == 2:
                active_filters.append("used only")
            
            filter_desc = ", ".join(active_filters[:3])  # Show first 3 filters
            if len(active_filters) > 3:
                filter_desc += f" + {len(active_filters) - 3} more"
            
            self.stats_label.setText(f"{filtered_count}/{total_annotations} annotations available (filtered: {filter_desc})")
        else:
            self.stats_label.setText(f"{filtered_count} annotations available for AI analysis")
        
        print(f"DEBUG: Loaded {filtered_count}/{total_annotations} annotations for AI chat (filtering: {self._has_active_filters(theme_search)})")
        
    def create_ai_prompt(self, user_query):
        """Create the AI prompt with annotations context"""
        annotations_context = self.build_annotations_context()
        include_transcript = self.include_transcript.isChecked()
        
        # Get transcript information (always included)
        transcript_title = self.transcript_title.text().strip()
        transcript_description = self.transcript_description.toPlainText().strip()
        
        # Build transcript info section
        transcript_info = "TRANSCRIPT INFORMATION:\n"
        transcript_info += f"Title: {transcript_title if transcript_title else 'Not specified'}\n"
        transcript_info += f"Description: {transcript_description if transcript_description else 'Not specified'}\n"
        
        prompt = f"""You are an AI assistant helping users analyze and find specific annotations from their text analysis work in Scriptoria.

{transcript_info}

ABOUT SCRIPTORIA:
Scriptoria is a text analysis and annotation tool. Users read through text documents and create "annotations" by highlighting important segments. Each annotation contains:
- Text: The highlighted text segment
- Theme/Scene: A categorization (like "Emotional Moment", "Key Insight", "Challenge")  
- Secondary Themes: Additional categorizations
- Tags: Searchable hashtags
- Notes: Brief summary (3-6 words)
- Notes HTML: Detailed explanation (1-2 sentences)

ANNOTATIONS AVAILABLE ({len(self.annotations_data)} total):
{annotations_context}

{'FULL TRANSCRIPT CONTEXT:' + self.full_transcript if include_transcript else 'Note: Full transcript context not included (user can enable this option).'}

USER QUESTION: {user_query}

RESPONSE INSTRUCTIONS:
1. Analyze the user's question and find relevant annotations
2. When referencing specific annotations, use the format [[ANNOTATION_ID]] where ANNOTATION_ID is the EXACT ID from the annotation list above
3. Be helpful and specific in your analysis
4. If you can't find exact matches, suggest the closest alternatives
5. For each annotation reference, provide brief reasoning (1 sentence) explaining why it matches
6. Do not include the full annotation text in your response - users can click the links to see the content

CRITICAL ANNOTATION ID RULES:
- ONLY use annotation IDs that appear EXACTLY in the "ANNOTATIONS AVAILABLE" list above
- IDs are long UUID strings like "e5ef45de-a6dd-47e7-9a85-ed10fe13a187"
- Do NOT make up IDs, use short IDs, or modify existing IDs
- Do NOT use numbers like "14" or "12" - these are not valid IDs
- If you reference an annotation, copy its FULL ID exactly from the list
- Invalid IDs will show as "annotation not found" and break the user experience

DOUBLE-CHECK: Before using any [[ANNOTATION_ID]], verify it exists in the list above.

Respond naturally and helpfully to the user's question."""

        return prompt
        
    def build_annotations_context(self):
        """Build context string from annotations data"""
        if not self.annotations_data:
            return "No annotations available."
        
        context_parts = []
        for i, annotation in enumerate(self.annotations_data, 1):
            context_part = f"Annotation {i}:\n"
            context_part += f"ID: {annotation['id']}\n"
            context_part += f"Theme: {annotation['scene']}\n"
            
            if annotation['secondary_scenes']:
                context_part += f"Secondary Themes: {', '.join(annotation['secondary_scenes'])}\n"
                
            if annotation['tags']:
                context_part += f"Tags: {', '.join([f'#{tag}' for tag in annotation['tags']])}\n"
                
            if annotation['notes']:
                context_part += f"Brief Notes: {annotation['notes']}\n"
                
            if annotation['notes_html']:
                # Strip HTML tags for context
                from bs4 import BeautifulSoup
                clean_notes = BeautifulSoup(annotation['notes_html'], 'html.parser').get_text()
                context_part += f"Detailed Notes: {clean_notes}\n"
                
            context_part += f"Text: {annotation['text']}\n"
            context_parts.append(context_part)
        
        return '\n'.join(context_parts)
        
    def ask_gemini(self):
        """Send query to Gemini AI"""
        query = self.query_input.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "No Question", "Please enter a question about your annotations.")
            return
            
        # Clear previous response for fresh output
        self.clear_response()
            
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            QMessageBox.warning(self, "API Key Required", "Please configure your Gemini API key first.")
            return
            
        if not self.annotations_data:
            QMessageBox.warning(self, "No Annotations", "No annotations found to analyze.")
            return
            
        # Check if full transcript context is enabled and transcript is large
        if self.include_transcript.isChecked() and len(self.full_transcript) > 500000:
            msg = QMessageBox(self)
            msg.setWindowTitle("Large Transcript Warning")
            msg.setText("The transcript is very large (over 500,000 characters).")
            msg.setInformativeText("Including full transcript context will use a significant number of tokens. Do you want to continue?")
            msg.setDetailedText(f"Transcript size: {len(self.full_transcript):,} characters\n\n"
                               f"This will consume substantial API tokens and may be expensive. "
                               f"Consider unchecking 'Include full transcript context' for a more economical approach.")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setIcon(QMessageBox.Icon.Warning)
            
            if msg.exec() == QMessageBox.StandardButton.No:
                return
            
        prompt = self.create_ai_prompt(query)
        
        print("=" * 80)
        print("DEBUG: ANNOTATION CHAT PROMPT:")
        print("=" * 80)
        print(prompt[:1000] + "..." if len(prompt) > 1000 else prompt)
        print("=" * 80)
        
        # Reset streaming accumulation
        self._accumulating_text = ""
        
        # Update UI for processing state
        self.ask_button.hide()
        self.stop_button.show()
        self.progress_bar.show()
        self.progress_bar.setFormat("Gemini is analyzing your annotations...")
        
        # Start AI worker thread
        model = self.model_selector.currentText()
        self.worker_thread = AIChatWorkerThread(prompt, self.api_key, model)
        self.worker_thread.response_received.connect(self.handle_ai_response)
        self.worker_thread.chunk_received.connect(self.handle_ai_chunk)
        self.worker_thread.error_occurred.connect(self.handle_ai_error)
        self.worker_thread.retry_suggested.connect(self.handle_retry_suggestion)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()
        
    def handle_ai_response(self, response_text):
        """Handle complete AI response"""
        print(f"DEBUG: Received complete AI response: {len(response_text)} characters")
        
        # Process the response to convert [[ANNOTATION_ID]] to clickable links
        processed_response = self.process_annotation_references(response_text)
        
        # Set the processed response
        self.response_display.setHtml(processed_response)
        
    def handle_ai_chunk(self, chunk_text):
        """Handle streaming AI response chunks"""
        self.progress_bar.setFormat("Gemini is responding...")
        
        # For QTextBrowser, we'll accumulate text and show it
        current_text = getattr(self, '_accumulating_text', '') + chunk_text
        self._accumulating_text = current_text
        
        # Show the raw text while streaming (will be processed when complete)
        self.response_display.setPlainText(current_text)
        
        # Auto-scroll to bottom
        scrollbar = self.response_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def handle_ai_error(self, error_message):
        """Handle AI processing errors"""
        QMessageBox.critical(self, "AI Error", f"AI chat failed:\n{error_message}")
        
    def handle_retry_suggestion(self, error_message):
        """Handle retryable errors with user-friendly message and retry option"""
        msg = QMessageBox(self)
        msg.setWindowTitle("AI Service Temporarily Unavailable")
        msg.setText("The AI service is currently experiencing issues.")
        msg.setInformativeText("Would you like to try again?")
        msg.setDetailedText(error_message)
        msg.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Retry)
        msg.setIcon(QMessageBox.Icon.Warning)
        
        if msg.exec() == QMessageBox.StandardButton.Retry:
            self.ask_gemini()
        else:
            self.cleanup_worker()
            
    def stop_processing(self):
        """Stop the AI processing"""
        if self.worker_thread:
            self.worker_thread.stop_generation()
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
        
        self.cleanup_worker()
        self.response_display.append("\n<i>Generation stopped by user.</i>")
        
    def cleanup_worker(self):
        """Clean up worker thread and reset UI"""
        self.ask_button.show()
        self.stop_button.hide()
        self.progress_bar.hide()
        
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None
            
    def clear_response(self):
        """Clear the response display"""
        self.response_display.clear()
        
    def process_annotation_references(self, text):
        """Process [[ANNOTATION_ID]] references and convert to clickable links, plus basic markdown to HTML"""
        if not self.annotations_data:
            return self.markdown_to_html(text)
        
        # Create a mapping of annotation IDs to their text
        id_to_annotation = {ann['id']: ann for ann in self.annotations_data}
        
        def replace_annotation_ref(match):
            annotation_id = match.group(1).strip()
            
            if annotation_id in id_to_annotation:
                annotation = id_to_annotation[annotation_id]
                annotation_text = annotation['text']
                
                # Truncate text if too long for display
                display_text = annotation_text
                if len(display_text) > 100:
                    display_text = display_text[:97] + "..."
                
                # Escape HTML in the annotation text
                display_text = display_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                
                # Create clickable link
                return f'<a href="annotation://{annotation_id}" style="color: #007bff; text-decoration: underline; font-weight: bold; background-color: #f8f9fa; padding: 2px 4px; border-radius: 3px;">[{display_text}]</a>'
            else:
                # Annotation not found - try to find closest match
                print(f"DEBUG: Annotation ID not found: '{annotation_id}'")
                
                # Only try matching if ID is more than 6 characters
                if len(annotation_id) > 6:
                    closest_id = self.find_closest_annotation_id(annotation_id)
                    if closest_id:
                        print(f"DEBUG: Found closest match: '{closest_id}' for '{annotation_id}'")
                        annotation = id_to_annotation[closest_id]
                        annotation_text = annotation['text']
                        
                        # Truncate text if too long for display
                        display_text = annotation_text
                        if len(display_text) > 100:
                            display_text = display_text[:97] + "..."
                        
                        # Escape HTML in the annotation text
                        display_text = display_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        
                        # Create clickable link with note about auto-correction
                        return f'<a href="annotation://{closest_id}" style="color: #007bff; text-decoration: underline; font-weight: bold; background-color: #fff3cd; padding: 2px 4px; border-radius: 3px;" title="Auto-corrected ID">[{display_text}] <small>(auto-corrected)</small></a>'
                    else:
                        return f'<span style="color: #dc3545; font-style: italic;">[annotation not found: {annotation_id[:20]}...]</span>'
                else:
                    return f'<span style="color: #dc3545; font-style: italic;">[not found]</span>'
        
        # Find and replace all [[ANNOTATION_ID]] patterns first
        pattern = r'\[\[([^\]]+)\]\]'
        processed_text = re.sub(pattern, replace_annotation_ref, text)
        
        # Convert basic markdown to HTML
        processed_text = self.markdown_to_html(processed_text)
        
        return processed_text
        
    def markdown_to_html(self, text):
        """Convert basic markdown to HTML"""
        # Convert newlines to spaces for processing
        text = re.sub(r'\n+', '\n', text)
        
        # Convert headers
        text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Convert bold and italic
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        
        # Convert bullet points (handle both * and - bullets)
        text = re.sub(r'^\* (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^- (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        
        # Group consecutive <li> elements into <ul> blocks
        lines = text.split('\n')
        result_lines = []
        in_list = False
        
        for line in lines:
            if '<li>' in line and '</li>' in line:
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                result_lines.append(line)
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                result_lines.append(line)
        
        # Close any open list
        if in_list:
            result_lines.append('</ul>')
            
        text = '\n'.join(result_lines)
        
        # Convert numbered lists
        text = re.sub(r'^\d+\. (.*?)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        
        # Convert paragraphs (double newlines)
        paragraphs = text.split('\n\n')
        html_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if para:
                # Don't wrap already HTML elements in <p> tags
                if not (para.startswith('<') and para.endswith('>')):
                    # Convert single newlines to breaks within paragraphs
                    para = para.replace('\n', '<br>')
                    para = f'<p>{para}</p>'
                html_paragraphs.append(para)
        
        return '\n'.join(html_paragraphs)
    
    def find_closest_annotation_id(self, target_id):
        """Find the closest matching annotation ID using string similarity"""
        if not self.annotations_data:
            return None
        
        # Get all available IDs
        available_ids = [ann['id'] for ann in self.annotations_data]
        
        best_match = None
        best_score = 0
        
        # Use a simple character-based similarity metric
        for candidate_id in available_ids:
            score = self.calculate_similarity(target_id, candidate_id)
            if score > best_score and score > 0.3:  # Minimum 30% similarity threshold
                best_score = score
                best_match = candidate_id
        
        return best_match
    
    def calculate_similarity(self, str1, str2):
        """Calculate similarity between two strings (0.0 to 1.0)"""
        # Convert to lowercase for comparison
        str1, str2 = str1.lower(), str2.lower()
        
        # If one string is contained in the other, high similarity
        if str1 in str2 or str2 in str1:
            return 0.8
        
        # Calculate character overlap
        set1, set2 = set(str1), set(str2)
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        if union == 0:
            return 0.0
        
        # Basic Jaccard similarity with length penalty
        jaccard = intersection / union
        
        # Penalize large length differences
        len_diff = abs(len(str1) - len(str2))
        max_len = max(len(str1), len(str2))
        if max_len > 0:
            length_penalty = 1 - (len_diff / max_len)
        else:
            length_penalty = 1
        
        return jaccard * length_penalty
        
    def handle_annotation_click(self, url):
        """Handle clicks on annotation links"""
        url_string = url.toString()
        
        print(f"DEBUG: Link clicked: {url_string}")
        
        if url_string.startswith("annotation://"):
            annotation_id = url_string.replace("annotation://", "")
            print(f"DEBUG: Annotation link clicked: {annotation_id}")
            
            # Store current response content and scroll position
            current_html = self.response_display.toHtml()
            scrollbar = self.response_display.verticalScrollBar()
            current_scroll_position = scrollbar.value()
            
            # Navigate to annotation in theme view
            try:
                if hasattr(self.main_window, 'handle_navigate_to_annotation'):
                    # Find the scene for this annotation
                    annotation_scene = None
                    for annotation in self.annotations_data:
                        if annotation['id'] == annotation_id:
                            annotation_scene = annotation['scene']
                            break
                    
                    if annotation_scene:
                        print(f"DEBUG: Navigating to annotation {annotation_id} in scene {annotation_scene}")
                        self.main_window.handle_navigate_to_annotation(annotation_id, annotation_scene)
                        print(f"DEBUG: Navigation completed successfully")
                    else:
                        print(f"DEBUG: Could not find scene for annotation {annotation_id}")
                        
                else:
                    print("DEBUG: Navigation method not available")
                    
            except Exception as e:
                print(f"DEBUG: Error during navigation: {str(e)}")
            
            # Use a timer to restore content and scroll position after navigation
            def restore_content_and_scroll():
                if hasattr(self, 'response_display') and self.response_display:
                    self.response_display.setHtml(current_html)
                    # Restore scroll position
                    scrollbar = self.response_display.verticalScrollBar()
                    scrollbar.setValue(current_scroll_position)
                    print(f"DEBUG: Content and scroll position restored (position: {current_scroll_position})")
            
            # Restore immediately and also after a short delay
            self.response_display.setHtml(current_html)
            scrollbar.setValue(current_scroll_position)
            QTimer.singleShot(100, restore_content_and_scroll)  # Restore after 100ms
                
        else:
            # Handle other URLs normally (but don't clear our content)
            print(f"DEBUG: Opening external URL: {url_string}")
            QDesktopServices.openUrl(url)
            
    def hideEvent(self, event):
        """Override hide event to stop any running workers"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.stop_processing()
        super().hideEvent(event)
        
    def closeEvent(self, event):
        """Override close event to hide instead of close"""
        self.hide()
        event.ignore()  # Prevent actual closing
"""
AI Annotation Generator for Scriptoria

This module provides AI-powered annotation creation that analyzes full transcript content
and automatically creates targeted highlights with themes and notes.
"""

import json
import os
import re
import uuid
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
                             QGroupBox, QComboBox, QSlider, QPushButton, QProgressDialog,
                             QMessageBox, QFormLayout, QApplication, QProgressBar, QWidget,
                             QTabWidget, QLineEdit, QCheckBox, QSpinBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
try:
    from google import genai
    import google.genai.types as genai_types
    NEW_API = True
except ImportError:
    import google.generativeai as genai
    NEW_API = False


class AIWorkerThread(QThread):
    """Worker thread for AI processing to prevent UI blocking"""
    
    response_received = pyqtSignal(str)
    chunk_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    retry_suggested = pyqtSignal(str)  # For suggesting retry on recoverable errors
    
    def __init__(self, prompt, api_key, model="gemini-2.5-pro", thinking_budget=None, max_retries=2):
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.model = model
        self.thinking_budget = thinking_budget
        self.max_retries = max_retries
        
    def run(self):
        """Execute AI request in background thread with streaming and retry logic"""
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    print(f"AI request attempt {attempt + 1}/{self.max_retries + 1}")
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff: 2s, 4s, 8s...
                
                if NEW_API:
                    # Use new google.genai API with thinking budget support
                    print(f"DEBUG: Using NEW API (google.genai) - attempt {attempt + 1}")
                    print(f"DEBUG: API key length: {len(self.api_key) if self.api_key else 0}")
                    print(f"DEBUG: API key starts with: {self.api_key[:10]}..." if self.api_key and len(self.api_key) > 10 else "DEBUG: API key too short or missing")
                    print(f"DEBUG: Prompt length: {len(self.prompt)} characters")
                    print(f"DEBUG: Thinking budget: {self.thinking_budget}")
                    
                    client = genai.Client(api_key=self.api_key)
                    
                    # Configure generation with thinking budget
                    config = genai_types.GenerateContentConfig(
                        temperature=0.3,
                        top_p=0.8,
                    )
                    
                    # Add thinking budget if specified
                    if self.thinking_budget is not None:
                        config.thinking_config = genai_types.ThinkingConfig(
                            thinking_budget=self.thinking_budget
                        )
                    
                    print(f"DEBUG: Making API call to {self.model}...")
                    # Generate response with streaming
                    response = client.models.generate_content(
                        model=self.model,
                        contents=self.prompt,
                        config=config
                    )
                    print(f"DEBUG: API call completed, processing response...")
                else:
                    # Fallback to old google.generativeai API
                    print(f"DEBUG: Using OLD API (google.generativeai) - attempt {attempt + 1}")
                    print(f"DEBUG: API key length: {len(self.api_key) if self.api_key else 0}")
                    print(f"DEBUG: API key starts with: {self.api_key[:10]}..." if self.api_key and len(self.api_key) > 10 else "DEBUG: API key too short or missing")
                    print(f"DEBUG: Prompt length: {len(self.prompt)} characters")
                    
                    genai.configure(api_key=self.api_key)
                    model = genai.GenerativeModel(self.model)
                    
                    print(f"DEBUG: Making streaming API call to {self.model}...")
                    # Generate response with streaming (no thinking budget support)
                    response = model.generate_content(
                        self.prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.3,
                            top_p=0.8,
                        ),
                        stream=True
                    )
                    print(f"DEBUG: Streaming API call initiated, processing chunks...")
                
                if NEW_API:
                    # New API returns text directly
                    print(f"DEBUG: Processing NEW API response...")
                    print(f"DEBUG: Response object type: {type(response)}")
                    print(f"DEBUG: Response has 'text' attribute: {hasattr(response, 'text')}")
                    
                    if hasattr(response, 'text'):
                        full_response = response.text
                        print(f"DEBUG: Response.text length: {len(full_response) if full_response else 0}")
                        if full_response:
                            print(f"DEBUG: Response starts with: '{full_response[:100]}...'")
                        else:
                            print(f"DEBUG: Response.text is empty or None: {repr(full_response)}")
                    else:
                        full_response = str(response)
                        print(f"DEBUG: No 'text' attribute, using str(response): '{full_response[:100]}...'")
                    
                    if full_response:
                        print(f"DEBUG: Emitting successful response ({len(full_response)} chars)")
                        self.chunk_received.emit(full_response)
                        self.response_received.emit(full_response)
                        return  # Success - exit retry loop
                    else:
                        # Analyze the empty response to provide better error information
                        print(f"DEBUG: Empty response from API - analyzing response object...")
                        
                        # Check for candidates and finish reasons
                        candidates_info = ""
                        if hasattr(response, 'candidates') and response.candidates:
                            candidate = response.candidates[0]
                            finish_reason = getattr(candidate, 'finish_reason', 'UNKNOWN')
                            safety_ratings = getattr(candidate, 'safety_ratings', None)
                            
                            candidates_info = f"Finish reason: {finish_reason}"
                            if safety_ratings:
                                candidates_info += f", Safety ratings: {safety_ratings}"
                            
                            print(f"DEBUG: Candidate analysis: {candidates_info}")
                            
                            # Check if content filtering might be the issue
                            if finish_reason == 'SAFETY':
                                error_msg = (
                                    "AI response blocked by safety filters. This may be due to:\n"
                                    "• Content in your transcript triggering safety systems\n"
                                    "• Try simplifying your prompt or filtering sensitive content\n"
                                    f"• Technical details: {candidates_info}"
                                )
                            elif finish_reason == 'MAX_TOKENS':
                                error_msg = (
                                    "AI response truncated due to token limits. Try:\n"
                                    "• Reducing transcript length\n"
                                    "• Processing fewer annotations at once\n"
                                    "• Using a lower thinking budget\n"
                                    f"• Technical details: {candidates_info}"
                                )
                            elif finish_reason == 'STOP':
                                # Check usage metadata for more clues
                                usage_info = ""
                                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                                    usage = response.usage_metadata
                                    prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                                    total_tokens = getattr(usage, 'total_token_count', 0)
                                    thoughts_tokens = getattr(usage, 'thoughts_token_count', 0)
                                    usage_info = f" (Prompt: {prompt_tokens}, Total: {total_tokens}, Thoughts: {thoughts_tokens} tokens)"
                                
                                error_msg = (
                                    "AI completed processing but returned no content. This may be due to:\n\n"
                                    "LIKELY CAUSES:\n"
                                    "• Content filtering or safety restrictions\n"
                                    "• Prompt too complex or confusing for the AI\n"
                                    "• Annotation format issues (missing IDs, malformed text)\n\n"
                                    "TRY THESE SOLUTIONS:\n"
                                    "• Use fewer annotations per request (try 5-10 instead of 17)\n"
                                    "• Disable 'Use Full Transcript Context' to reduce complexity\n"
                                    "• Lower the thinking budget (try 1000 instead of 2000)\n"
                                    "• Check for unusual characters or content in annotations\n\n"
                                    f"Technical details: {candidates_info}{usage_info}"
                                )
                            else:
                                error_msg = f"AI processing stopped unexpectedly: {finish_reason}\n{candidates_info}"
                        else:
                            error_msg = "No response candidates received from AI API"
                        
                        print(f"DEBUG: Detailed error analysis: {error_msg}")
                        self.error_occurred.emit(error_msg)
                        return
                else:
                    # Old API streaming handling
                    print(f"DEBUG: Processing OLD API streaming response...")
                    full_response = ""
                    chunk_count = 0
                    
                    for chunk in response:
                        chunk_count += 1
                        print(f"DEBUG: Processing chunk {chunk_count}: has text={hasattr(chunk, 'text')}")
                        
                        if hasattr(chunk, 'text') and chunk.text:
                            chunk_text = chunk.text
                            print(f"DEBUG: Chunk {chunk_count} text length: {len(chunk_text)}")
                            full_response += chunk_text
                            self.chunk_received.emit(chunk_text)
                        else:
                            print(f"DEBUG: Chunk {chunk_count} has no text or empty text: {repr(getattr(chunk, 'text', 'NO_TEXT_ATTR'))}")
                            
                    print(f"DEBUG: Processed {chunk_count} chunks, total response length: {len(full_response)}")
                            
                    if full_response:
                        print(f"DEBUG: Emitting successful streaming response ({len(full_response)} chars)")
                        self.response_received.emit(full_response)
                        return  # Success - exit retry loop
                    else:
                        print(f"DEBUG: No content received from {chunk_count} streaming chunks")
                        self.error_occurred.emit(f"No response generated from AI - processed {chunk_count} chunks but no text content")
                        return
                        
            except Exception as e:
                print(f"DEBUG: Exception occurred on attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                
                # Import traceback for detailed error info
                import traceback
                error_traceback = traceback.format_exc()
                print(f"DEBUG: Full traceback:\n{error_traceback}")
                
                error_str = str(e).lower()
                
                # Check if this is a retryable error
                retryable_errors = [
                    '500 internal', 'internal server error', 'service unavailable',
                    'timeout', 'connection error', 'network error', 'temporarily unavailable'
                ]
                
                is_retryable = any(err in error_str for err in retryable_errors)
                print(f"DEBUG: Error classified as retryable: {is_retryable}")
                print(f"DEBUG: Attempt {attempt + 1}/{self.max_retries + 1}, can retry: {attempt < self.max_retries}")
                
                if is_retryable and attempt < self.max_retries:
                    print(f"DEBUG: Retrying after retryable error on attempt {attempt + 1}: {str(e)}")
                    continue  # Try again
                else:
                    # Final attempt failed or non-retryable error
                    if is_retryable:
                        error_message = (
                            f"AI service temporarily unavailable after {self.max_retries + 1} attempts.\n\n"
                            f"This appears to be a temporary issue with the Gemini API service. "
                            f"Please try again in a few moments.\n\n"
                            f"Original error: {str(e)}\n\n"
                            f"Full traceback:\n{error_traceback}"
                        )
                        print(f"DEBUG: Emitting retry suggestion after exhausted retries")
                        self.retry_suggested.emit(error_message)
                    else:
                        detailed_error = (
                            f"AI request failed: {str(e)}\n\n"
                            f"Error type: {type(e).__name__}\n"
                            f"API: {'NEW (google.genai)' if NEW_API else 'OLD (google.generativeai)'}\n"
                            f"Attempt: {attempt + 1}/{self.max_retries + 1}\n\n"
                            f"Full traceback:\n{error_traceback}"
                        )
                        print(f"DEBUG: Emitting non-retryable error")
                        self.error_occurred.emit(detailed_error)
                    return


class AIAnnotationGenerator(QDialog):
    """
    Dialog for AI-powered annotation creation from transcript text.
    Analyzes full transcript and creates targeted highlights with themes and notes.
    """
    
    def __init__(self, parent, web_view, main_window):
        super().__init__(parent)
        self.web_view = web_view
        self.main_window = main_window
        self.scene_styles = web_view.scene_styles if web_view else {}
        self.full_transcript = ""
        self.parsed_annotations = []
        self.api_key = ""
        
        self.setWindowTitle("AI Generate Annotations")
        self.setModal(True)
        self.resize(1000, 850)
        
        self.setup_ui()
        self.load_transcript()
        self.load_api_key()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("<h2>AI Generate Annotations</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Info note
        info_note = QLabel(
            "<b>Note:</b> AI will analyze the full transcript and create targeted highlights "
            "for the most compelling soundbites that can be arranged into a narrative."
        )
        info_note.setWordWrap(True)
        info_note.setStyleSheet("padding: 10px; background-color: #f0f8ff; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(info_note)
        
        # Main content in horizontal layout
        content_layout = QHBoxLayout()
        
        # Left side: Video purpose and guidance
        left_widget = QGroupBox("Video Purpose & Guidance")
        left_layout = QVBoxLayout(left_widget)
        
        self.purpose_input = QTextEdit()
        self.purpose_input.setPlaceholderText(
            "Describe the purpose of your video, main themes, target audience, and what kind of "
            "story you want to tell. This will guide the AI in selecting the most relevant segments.\n\n"
            "Examples:\n"
            "• 'Create a compelling personal story about overcoming challenges'\n"
            "• 'Focus on technical insights and practical advice for developers'\n"
            "• 'Highlight emotional moments and human connection for documentary'"
        )
        self.purpose_input.setMaximumHeight(200)
        left_layout.addWidget(self.purpose_input)
        
        content_layout.addWidget(left_widget, 2)
        
        # Right side: AI settings and scene list
        right_widget = QGroupBox("Configuration")
        right_layout = QVBoxLayout(right_widget)
        
        # Available scenes display
        scenes_group = QGroupBox("Available Themes/Scenes")
        scenes_layout = QVBoxLayout(scenes_group)
        
        self.scenes_display = QTextEdit()
        self.scenes_display.setReadOnly(True)
        self.scenes_display.setMaximumHeight(120)
        self.update_scenes_display()
        scenes_layout.addWidget(self.scenes_display)
        right_layout.addWidget(scenes_group)
        
        # AI configuration
        ai_group = QGroupBox("AI Configuration")
        ai_layout = QFormLayout(ai_group)
        
        self.model_selector = QComboBox()
        self.model_selector.addItems(["gemini-2.5-pro", "gemini-2.5-flash"])
        ai_layout.addRow("Model:", self.model_selector)
        
        # Thinking budget
        from PyQt6.QtWidgets import QSpinBox
        self.thinking_budget = QSpinBox()
        self.thinking_budget.setMinimum(1000)
        self.thinking_budget.setMaximum(20000)
        self.thinking_budget.setValue(5000)
        self.thinking_budget.setSuffix(" tokens")
        self.thinking_budget.setToolTip("Higher values allow more complex reasoning but take longer")
        ai_layout.addRow("Thinking Budget:", self.thinking_budget)
        
        # Selectivity slider
        selectivity_layout = QVBoxLayout()
        self.selectivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.selectivity_slider.setRange(1, 3)
        self.selectivity_slider.setValue(2)  # Default to balanced
        self.selectivity_label = QLabel("Balanced\nStrong narrative beats with key supporting details")
        self.selectivity_label.setWordWrap(True)
        self.selectivity_label.setStyleSheet("font-size: 11px; color: #495057;")
        self.selectivity_slider.valueChanged.connect(self.update_selectivity_label)
        
        selectivity_layout.addWidget(self.selectivity_slider)
        selectivity_layout.addWidget(self.selectivity_label)
        ai_layout.addRow("Selectivity:", selectivity_layout)
        
        # Help text for selectivity
        help_text = QLabel("Higher values = more focused story (fewer annotations, essential narrative beats only)")
        help_text.setStyleSheet("font-size: 10px; color: #666; font-style: italic;")
        ai_layout.addRow("", help_text)
        
        right_layout.addWidget(ai_group)
        content_layout.addWidget(right_widget, 1)
        
        layout.addLayout(content_layout)
        
        # AI Response display area
        response_group = QGroupBox("AI Response")
        response_layout = QVBoxLayout(response_group)
        
        self.response_display = QTextEdit()
        self.response_display.setReadOnly(True)
        self.response_display.setMaximumHeight(200)
        self.response_display.setPlaceholderText("AI response will appear here during processing...")
        self.response_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        response_layout.addWidget(self.response_display)
        
        layout.addWidget(response_group)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
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
                    stop:0 #007bff, stop:0.5 #0056b3, stop:1 #007bff);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("Generate Annotations")
        self.process_button.clicked.connect(self.process_with_ai)
        self.process_button.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.process_button.setDefault(True)  # Make this the default button (Enter key)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setStyleSheet("font-weight: bold; padding: 8px 16px; background-color: #dc3545; color: white;")
        self.stop_button.hide()  # Initially hidden
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.process_button)
        
        layout.addLayout(button_layout)
        
    def update_selectivity_label(self, value):
        """Update selectivity label based on slider value"""
        levels = {
            1: "Very Selective\nOnly the most compelling and essential story moments",
            2: "Balanced\nStrong narrative beats with key supporting details", 
            3: "Complete Story\nAs many annotations as necessary to tell the full story with setup, context, and highlights"
        }
        self.selectivity_label.setText(levels.get(value, f"Level {value}"))
        
    def update_scenes_display(self):
        """Update the scenes display with available themes"""
        if not self.scene_styles:
            self.scenes_display.setHtml("<i>No themes/scenes configured</i>")
            return
            
        html = "<b>Available Themes:</b><br>"
        for i, (scene_name, style) in enumerate(self.scene_styles.items(), 1):
            # Extract background color from style
            color = "#fff4c9"  # default yellow
            if "background-color:" in style:
                color = style.split("background-color:")[1].split(";")[0].strip()
            
            html += f'<span style="background-color: {color}; padding: 2px 6px; border-radius: 3px; margin-right: 5px;">{scene_name}</span>'
            if i % 3 == 0:  # Line break every 3 items
                html += "<br>"
        
        self.scenes_display.setHtml(html)
        
    def load_transcript(self):
        """Load the full transcript from the web view - extract clean text with speech titles"""
        if not self.web_view:
            return
        
        # Use the same method as AI Generate Script to get clean transcript text with speaker info
        def handle_transcript(html):
            if html:
                from bs4 import BeautifulSoup
                
                # Parse HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove CSS and script elements
                for element in soup(["style", "script", "head"]):
                    element.decompose()
                
                # DEBUG: Check overall HTML structure
                print(f"DEBUG: HTML body contains {len(soup.find_all())} total elements")
                speech_related = soup.find_all(class_=lambda x: x and 'speech' in x)
                print(f"DEBUG: Found {len(speech_related)} elements with 'speech' in class name:")
                for elem in speech_related[:5]:  # Show first 5
                    print(f"  - {elem.name}.{' '.join(elem.get('class', []))}")
                
                # Extract text with speech titles included
                transcript_parts = []
                
                # Look for speech headers and content sections
                speech_headers = soup.find_all('div', class_='speech-header')
                print(f"DEBUG: Found {len(speech_headers)} speech-header divs")
                
                if speech_headers:
                    # Process each speech header to get title and find corresponding content
                    for i, header in enumerate(speech_headers):
                        print(f"DEBUG: Processing speech-header {i+1}/{len(speech_headers)}")
                        title_elem = header.find(class_='speech-title')
                        
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            print(f"DEBUG: Found speech-title: '{title_text}'")
                            
                            # Find the corresponding speech content (usually follows the header)
                            content_elem = None
                            next_sibling = header.find_next_sibling()
                            while next_sibling:
                                if next_sibling.name == 'div' and 'speech-content' in next_sibling.get('class', []):
                                    content_elem = next_sibling
                                    break
                                next_sibling = next_sibling.find_next_sibling()
                            
                            # If no sibling found, look for speech-content within the same parent
                            if not content_elem:
                                parent = header.find_parent()
                                if parent:
                                    content_elem = parent.find(class_='speech-content')
                            
                            if content_elem:
                                content_text = content_elem.get_text(separator=' ', strip=True)
                                print(f"DEBUG: Found speech-content with {len(content_text)} characters")
                                if title_text and content_text:
                                    # Format as "Speaker: content"
                                    formatted_entry = f"{title_text}: {content_text}"
                                    transcript_parts.append(formatted_entry)
                                    print(f"DEBUG: Added transcript part: '{title_text}: {content_text[:50]}...'")
                            elif title_text:
                                # Just title without content
                                transcript_parts.append(title_text)
                                print(f"DEBUG: Added title-only transcript part: '{title_text}'")
                
                # Fallback: Look for speech sections (original logic)
                elif soup.find_all('div', class_='speech-section'):
                    speech_sections = soup.find_all('div', class_='speech-section')
                    for section in speech_sections:
                        # Get speech title if available
                        title_elem = section.find(class_='speech-title')
                        content_elem = section.find(class_='speech-content')
                        
                        if title_elem and content_elem:
                            title_text = title_elem.get_text(strip=True)
                            content_text = content_elem.get_text(separator=' ', strip=True)
                            
                            if title_text and content_text:
                                # Format as "Speaker: content"
                                transcript_parts.append(f"{title_text}: {content_text}")
                        elif content_elem:
                            # Just content without title
                            content_text = content_elem.get_text(separator=' ', strip=True)
                            if content_text:
                                transcript_parts.append(content_text)
                else:
                    # Fallback: look for speech content areas only
                    speech_contents = soup.find_all(class_="speech-content")
                    if speech_contents:
                        for content in speech_contents:
                            text = content.get_text(separator=' ', strip=True)
                            if text:
                                transcript_parts.append(text)
                    else:
                        # Final fallback: get all text but clean it up
                        text = soup.get_text(separator=' ', strip=True)
                        # Remove extra whitespace
                        import re
                        text = re.sub(r'\s+', ' ', text).strip()
                        transcript_parts.append(text)
                
                self.full_transcript = '\n\n'.join(transcript_parts)
                print(f"DEBUG: Loaded transcript with {len(self.full_transcript)} characters including speech titles")
                print(f"DEBUG: Total transcript parts: {len(transcript_parts)}")
                print(f"DEBUG: First 500 characters of transcript:")
                print(self.full_transcript[:500] + "..." if len(self.full_transcript) > 500 else self.full_transcript)
                
        # Get the HTML content
        self.web_view.page().toHtml(handle_transcript)
        
    def load_api_key(self):
        """Load API key from file"""
        import os
        
        try:
            # Try different possible locations
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
                        
            # If no key found, create the file
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
            os.makedirs(data_dir, exist_ok=True)
            key_path = os.path.join(data_dir, "api_key.txt")
            
            with open(key_path, 'w', encoding='utf-8') as f:
                f.write("YOUR_GEMINI_API_KEY_HERE")
                
            QMessageBox.information(self, "API Key Setup", 
                f"Please add your Gemini API key to:\n{key_path}")
                
        except Exception as e:
            print(f"Error loading API key: {e}")
            
    def create_annotation_prompt(self):
        """Create the AI prompt for annotation generation"""
        purpose_text = self.purpose_input.toPlainText().strip()
        selectivity_level = self.selectivity_slider.value()
        thinking_budget = self.thinking_budget.value()
        
        # Get available scenes
        available_scenes = list(self.scene_styles.keys())
        if not available_scenes:
            QMessageBox.warning(self, "No Themes", "No themes/scenes are configured. Please set up themes first.")
            return None
            
        scenes_text = "\n".join([f"- {scene}" for scene in available_scenes])
        
        selectivity_guidance = {
            1: "Very Selective - Only the most compelling and essential story moments",
            2: "Balanced - Strong narrative beats with key supporting details", 
            3: "Complete Story - As many annotations as necessary to tell the full story with setup, context, and highlights"
        }
        
        prompt = f"""<thinking>
You are creating a compelling VIDEO STORY, not just selecting individual clips. Take time to deeply analyze the content and understand the narrative journey.

Budget: {thinking_budget} tokens for reasoning about story construction.

Think about STORY ARCHITECTURE:
1. What's the complete journey from beginning to end?
2. How does the person change, grow, or transform?
3. What specific details bring this story to life and make it memorable?
4. What obstacles, challenges, or turning points create emotional investment?
5. What setup moments help the audience understand and connect?
6. How do different segments work together to build one coherent narrative?
7. What before/after contrasts are strongest and most concisely available to be told?
8. What personality quirks or authentic moments reveal character?

Think about STORY ARC BEATS:
1. HOOK — surprising claim or vivid detail that grabs attention
2. SETUP — who/where + what they want or need
3. STAKES — why it matters (consequences of failure/success)
4. OBSTACLE — conflict, setback, tension, or challenge
5. TURN — decision, insight, or pivot moment
6. RESULT — concrete outcome showing before→after transformation
7. REFLECTION/CTA — meaning, lesson, or call to action

Character and Flow Guidelines:
- Include quirks that reveal character—sparingly
- Add bridge lines only if essential
- Context tax: If it requires multiple bridges or on-screen text to land, replace it
- Tangents: If it needs >1–2 sentences of setup to make sense, cut it

SELECT FOR NARRATIVE FLOW, NOT JUST INDIVIDUAL SEGMENT QUALITY:
- Include setup moments that establish context (even if not individually "perfect")
- Choose specific details that reveal personality and authenticity
- Prioritize transformation stories that show clear change
- Look for connecting tissue that bridges different story phases
- Focus on moments that build emotional investment in the character's journey

Remember: Great video stories need setup, context, and connecting details - not just highlight reels.
</thinking>

You are creating a compelling video story from this transcript. Your job is to select segments that work together to build audience engagement, emotional connection, and a complete narrative journey.

SELECTIVITY REQUIREMENT: {selectivity_guidance[selectivity_level]}

CRITICAL: The selectivity level determines the FOCUS and COMPLETENESS of your story selection. Very Selective means only the most essential moments. Balanced means key narrative beats with supporting details. Complete Story means include whatever is needed for a full narrative.

STORY-BUILDING APPROACH: Prioritize narrative coherence over individual segment perfection, but respect the selectivity requirement above.

NARRATIVE FLOW REQUIREMENTS:
- Include setup moments that establish emotional stakes and anticipation
- Show the HOW between major story beats, not just the WHAT
- Select concrete examples that demonstrate change rather than just describe it
- Provide context that helps viewers understand the practical significance
- Develop important story elements as real characters with meaningful traits

PROMOTIONAL CONTENT STRATEGY: When creating fundraising/promotional videos, remember the dual narrative:
- Surface story: Personal transformation journey
- Underlying story: This organization has the expertise, quality, and strategic thinking to create these outcomes
Select segments that advance both narratives simultaneously - showing personal impact while demonstrating organizational competence.

VIDEO PURPOSE & GUIDANCE:
{purpose_text if purpose_text else "Focus on creating an engaging story that connects with viewers emotionally and shows personal transformation."}

AVAILABLE THEMES/SCENES:
{scenes_text}

TRANSCRIPT TO ANALYZE:
{self.full_transcript}

STORY ARC CONSTRUCTION:
1. HOOK: Lead with surprising claims, vivid details, or compelling contradictions
2. SETUP: Establish who they are, where they are, what they want/need
3. STAKES: Show why this matters - consequences of success or failure
4. OBSTACLE: Include conflicts, setbacks, challenges, or tension points
5. TURN: Capture decision moments, insights, breakthroughs, or pivot points
6. RESULT: Show concrete before→after outcomes and transformations
7. REFLECTION/CTA: Include meaning-making, lessons learned, or calls to action
8. ORGANIZATIONAL CREDIBILITY: Demonstrate expertise, quality, and strategic thinking through outcomes
9. CHARACTER QUIRKS: Include personality-revealing moments—sparingly and only if they serve the story
10. BRIDGE EFFICIENCY: Avoid segments requiring multiple explanations or extensive setup
11. CONTEXT ECONOMY: Replace segments that need on-screen text or complex bridging
12. TANGENT ELIMINATION: Cut content requiring >1–2 sentences of setup to make sense
   
2. Choose appropriate themes from the available list based on content
3. Be extremely precise with text matching - copy text EXACTLY as it appears
4. Provide brief, helpful notes explaining why each segment is valuable for the video

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
[[ANNOTATION :: PRIMARY_SCENE :: SECONDARY_SCENES :: EXACT_TEXT_SEGMENT :: BRIEF_NOTE :: DETAILED_FOOTNOTE]]

FIELD EXPLANATIONS:
- PRIMARY_SCENE: Main theme from available list
- SECONDARY_SCENES: Optional comma-separated additional themes (or "none" if not applicable)
- EXACT_TEXT_SEGMENT: Text copied exactly as it appears
- BRIEF_NOTE: 3-6 words describing content (e.g., "Strong opening line", "Explains condition")
- DETAILED_FOOTNOTE: 1-2 sentences explaining narrative value and context

CRITICAL TEXT MATCHING REQUIREMENTS:
The system uses automated text matching to find and highlight your selected segments in the transcript. This means:

- Text segments MUST be copied EXACTLY as they appear in the transcript
- NO truncation, ellipsis (...), or "shortening" allowed ANYWHERE - not at the beginning, middle, or end
- NO paraphrasing or rewording
- Include ALL punctuation, capitalization, and spacing exactly
- Do NOT add "..." ANYWHERE in the text - not even at the end
- Do NOT cut off sentences mid-way or at the end
- The entire text segment must be present in the transcript word-for-word
- Copy complete sentences from start to finish - no partial sentences

If text matching fails, the annotation will be skipped. Every character must match perfectly.

OTHER REQUIREMENTS:
- Primary scene must be from the available themes list  
- Secondary scenes (if any) must also be from the available themes list
- Brief notes should be very concise (3-6 words max)
- Detailed footnotes should explain why this segment is valuable for the video

DONOR CONFIDENCE BUILDING: Your selections should make potential supporters think:
- "This organization really knows what they're doing"
- "They provide exceptional quality and support"  
- "My donation would be well-used by competent professionals"
- "They create life-changing results through expertise, not luck"

CORRECT Example:
[[ANNOTATION :: Journey to First Guide Dog :: Personal Background :: I was probably 15, 14 or 15, I almost as a joke, decided to apply. I knew I was pretty young, but loved dogs and hated using a cane. So I thought, let me give it a shot and see what they think. :: Character motivation revealed :: This setup moment shows the speaker's authentic personality and establishes the key motivation driving their entire journey - a relatable teenage attitude that transforms into life-changing commitment]]

WRONG Examples (DO NOT DO THIS):
WRONG - Text with ellipsis in middle: "My instructor, Mike, brought her to my room... and then she promptly fell asleep"
WRONG - Text with ellipsis at end: "One moment that stands out for me in particular was going to the met and navigating both inside and ..."
WRONG - Truncated text: "I was born with a rare genetic condition called Leber's congenital amaurosis..."
WRONG - Paraphrased text: "She explained her condition and visual impairment"
WRONG - Incomplete sentences: "One moment that stands out for me in particular was going to"

CORRECT: Copy the complete sentence exactly as written in the transcript

Only provide annotations in the specified format. No additional text or explanations."""

        return prompt
        
    def process_with_ai(self):
        """Process the transcript with AI to generate annotations"""
        if not self.full_transcript:
            QMessageBox.warning(self, "No Transcript", "No transcript content found to analyze.")
            return
            
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            QMessageBox.warning(self, "API Key Required", "Please configure your Gemini API key first.")
            return
            
        # Check if transcript is large and warn user
        if len(self.full_transcript) > 500000:
            msg = QMessageBox(self)
            msg.setWindowTitle("Large Transcript Warning")
            msg.setText("The transcript is very large (over 500,000 characters).")
            msg.setInformativeText("Processing this transcript will use a significant number of tokens. Do you want to continue?")
            msg.setDetailedText(f"Transcript size: {len(self.full_transcript):,} characters\n\n"
                               f"This will consume substantial API tokens and may be expensive. "
                               f"Consider using a shorter transcript or splitting the content.")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setIcon(QMessageBox.Icon.Warning)
            
            if msg.exec() == QMessageBox.StandardButton.No:
                return
            
        prompt = self.create_annotation_prompt()
        if not prompt:
            return
            
        # DEBUG: Output the full prompt being sent to AI
        print("=" * 80)
        print("DEBUG: FULL PROMPT BEING SENT TO AI:")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
        print("END OF PROMPT")
        print("=" * 80)
            
        # Update UI for processing state
        self.process_button.hide()
        self.stop_button.show()
        
        # Show progress bar
        self.progress_bar.show()
        self.progress_bar.setFormat("AI is analyzing transcript...")
        
        # Clear response display
        self.response_display.clear()
        
        # Start AI worker thread with thinking budget
        thinking_budget = self.thinking_budget.value()
        selected_model = self.model_selector.currentText()
        self.worker_thread = AIWorkerThread(prompt, self.api_key, selected_model, thinking_budget)
        self.worker_thread.response_received.connect(self.handle_ai_response)
        self.worker_thread.chunk_received.connect(self.handle_ai_chunk)
        self.worker_thread.error_occurred.connect(self.handle_ai_error)
        self.worker_thread.retry_suggested.connect(self.handle_retry_suggestion)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()
        
    def handle_ai_response(self, response_text):
        """Handle AI response and create annotations"""
        try:
            # Parse AI response
            annotation_count = self.parse_ai_response(response_text)
            
            if annotation_count == 0:
                QMessageBox.warning(self, "No Annotations", "AI did not generate any valid annotations.")
                return
                
            # Show confirmation dialog
            msg = QMessageBox(self)  # Properly parent to this dialog
            msg.setWindowTitle("Create Annotations?")
            msg.setText(f"AI found {annotation_count} potential annotations.")
            msg.setInformativeText("Would you like to create these highlights?")
            
            # Add preview of first few annotations
            preview_text = "Preview (first 5):\n\n"
            for i, anno in enumerate(self.parsed_annotations[:5]):
                secondary_info = f" (+{len(anno['secondary_scenes'])} secondary)" if anno['secondary_scenes'] else ""
                preview_text += f"• {anno['scene']}{secondary_info}: \"{anno['brief_note']}\"\n"
                preview_text += f"  Text: {anno['text'][:60]}{'...' if len(anno['text']) > 60 else ''}\n\n"
            
            msg.setDetailedText(preview_text)
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self.create_annotations_sequentially()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process AI response: {str(e)}")
    
    def handle_ai_chunk(self, chunk_text):
        """Handle streaming AI response chunks"""
        # Update progress bar to show streaming
        self.progress_bar.setFormat("AI is generating annotations...")
        
        # Append chunk to response display
        cursor = self.response_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk_text)
        self.response_display.setTextCursor(cursor)
        
        # Auto-scroll to bottom
        scrollbar = self.response_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
            
    def handle_ai_error(self, error_message):
        """Handle AI processing errors with detailed feedback"""
        # Also display error in the response area for user visibility
        self.response_display.clear()
        error_text = f"❌ AI Processing Error:\n\n{error_message}\n\nPlease check:\n• Your API key is valid\n• You have internet connection\n• The Gemini service is available"
        self.response_display.setPlainText(error_text)
        
        # Show critical error dialog
        QMessageBox.critical(self, "AI Error", f"AI processing failed:\n\n{error_message}")
        
    def handle_retry_suggestion(self, error_message):
        """Handle retryable errors with user-friendly message and retry option"""
        # Display error info in response area
        self.response_display.clear()
        retry_text = f"⚠️ Temporary AI Service Issue:\n\n{error_message}\n\nThis appears to be a temporary problem with the AI service. You can retry the operation."
        self.response_display.setPlainText(retry_text)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("AI Service Temporarily Unavailable")
        msg.setText("The AI service is currently experiencing issues.")
        msg.setInformativeText("Would you like to try again?")
        msg.setDetailedText(error_message)
        msg.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Retry)
        msg.setIcon(QMessageBox.Icon.Warning)
        
        if msg.exec() == QMessageBox.StandardButton.Retry:
            # User wants to retry - restart the process
            self.process_with_ai()
        else:
            # User cancelled - clean up
            self.cleanup_worker()
        
    def stop_processing(self):
        """Stop the AI processing"""
        if hasattr(self, 'worker_thread'):
            self.worker_thread.terminate()
            self.worker_thread.wait()  # Wait for thread to finish
            self.worker_thread.deleteLater()
        
        # Reset UI
        self.cleanup_worker()
        
        # Show cancelled message
        self.response_display.setText("Processing cancelled by user.")
        
    def cleanup_worker(self):
        """Clean up worker thread and reset UI"""
        self.process_button.show()
        self.stop_button.hide()
        
        # Hide progress bar
        self.progress_bar.hide()
        
        if hasattr(self, 'worker_thread'):
            self.worker_thread.deleteLater()
            
    def parse_ai_response(self, response_text):
        """Parse AI response and extract annotation data"""
        self.parsed_annotations = []
        
        # Find all annotation blocks with new format - handle line breaks and spacing
        # First normalize the response text to remove problematic line breaks within annotations
        normalized_text = re.sub(r'\[\[ANNOTATION([^\]]*?)\]\]', 
                                lambda m: m.group(0).replace('\n', ' ').replace('  ', ' '), 
                                response_text, flags=re.DOTALL)
        
        pattern = r'\[\[ANNOTATION\s*::\s*([^:]+?)\s*::\s*([^:]+?)\s*::\s*(.+?)\s*::\s*([^:]+?)\s*::\s*([^\]]+?)\]\]'
        matches = re.findall(pattern, normalized_text, re.DOTALL)
        
        print(f"DEBUG: Original response length: {len(response_text)} chars")
        print(f"DEBUG: Normalized response length: {len(normalized_text)} chars") 
        print(f"DEBUG: Regex found {len(matches)} annotation matches")
        
        for i, match in enumerate(matches):
            print(f"DEBUG: Processing annotation {i+1}/{len(matches)}")
            primary_scene, secondary_scenes_str, text_segment, brief_note, detailed_footnote = match
            primary_scene = primary_scene.strip()
            secondary_scenes_str = secondary_scenes_str.strip()
            text_segment = text_segment.strip()
            brief_note = brief_note.strip()
            detailed_footnote = detailed_footnote.strip()
            
            print(f"DEBUG: Scene: '{primary_scene}', Text: '{text_segment[:50]}...'")
            
            # Validate primary scene exists - try fuzzy matching if exact match fails
            if primary_scene not in self.scene_styles:
                # Try fuzzy matching
                best_match = self.find_best_scene_match(primary_scene, list(self.scene_styles.keys()))
                if best_match:
                    print(f"Warning: Primary scene '{primary_scene}' not found, using best match: '{best_match}'")
                    primary_scene = best_match
                else:
                    print(f"Warning: Primary scene '{primary_scene}' not found in available scenes: {list(self.scene_styles.keys())}")
                    continue
            
            # Parse secondary scenes
            secondary_scenes = []
            if secondary_scenes_str.lower() != "none":
                for sec_scene in secondary_scenes_str.split(','):
                    sec_scene = sec_scene.strip()
                    if sec_scene and sec_scene in self.scene_styles and sec_scene != primary_scene:
                        secondary_scenes.append(sec_scene)
                    elif sec_scene and sec_scene not in self.scene_styles:
                        # Try fuzzy matching for secondary scenes too
                        best_match = self.find_best_scene_match(sec_scene, list(self.scene_styles.keys()))
                        if best_match and best_match != primary_scene:
                            print(f"Warning: Secondary scene '{sec_scene}' not found, using best match: '{best_match}'")
                            secondary_scenes.append(best_match)
                        else:
                            print(f"Warning: Secondary scene '{sec_scene}' not found in available scenes, ignoring")
                
            # Validate text exists in transcript (basic check)
            if text_segment not in self.full_transcript:
                print(f"Warning: Text segment not found in transcript: {text_segment[:100]}...")
                continue
                
            self.parsed_annotations.append({
                'scene': primary_scene,
                'secondary_scenes': secondary_scenes,
                'text': text_segment,
                'brief_note': brief_note,
                'detailed_footnote': detailed_footnote
            })
        
        print(f"DEBUG: Successfully parsed {len(self.parsed_annotations)} valid annotations out of {len(matches)} total matches")
        return len(self.parsed_annotations)
    
    def find_best_scene_match(self, target_scene, available_scenes):
        """Find the best matching scene name using fuzzy string matching"""
        if not target_scene or not available_scenes:
            return None
            
        target_lower = target_scene.lower().strip()
        best_match = None
        best_score = 0
        
        for scene in available_scenes:
            scene_lower = scene.lower().strip()
            
            # Check for exact substring matches first
            if target_lower in scene_lower or scene_lower in target_lower:
                return scene
                
            # Check for word matches
            target_words = set(target_lower.split())
            scene_words = set(scene_lower.split())
            
            # Calculate word overlap score
            if target_words and scene_words:
                overlap = len(target_words.intersection(scene_words))
                score = overlap / len(target_words.union(scene_words))
                
                if score > best_score and score > 0.3:  # Minimum 30% similarity
                    best_score = score
                    best_match = scene
        
        return best_match
        
    def create_annotations_sequentially(self):
        """Create all annotations sequentially with progress dialog"""
        if not self.parsed_annotations:
            return
            
        # Create progress dialog
        progress = QProgressDialog("Creating annotations...", "Cancel", 0, len(self.parsed_annotations), self)
        progress.setWindowTitle("AI Annotation Creation")
        progress.setModal(True)
        progress.show()
        
        successful_count = 0
        failed_annotations = []
        
        for i, annotation_data in enumerate(self.parsed_annotations):
            if progress.wasCanceled():
                break
                
            progress.setLabelText(f"Creating annotation {i+1}/{len(self.parsed_annotations)}...")
            progress.setValue(i)
            QApplication.processEvents()  # Keep UI responsive
            
            try:
                # Create preserved_metadata with the brief note and detailed footnote
                preserved_metadata = {
                    'notes': annotation_data['brief_note'],
                    'notes_html': annotation_data['detailed_footnote'],
                    'secondary_scenes': annotation_data['secondary_scenes'],
                    'timestamp': datetime.now().isoformat()
                }
                
                # Use existing infrastructure to create annotation
                self.web_view.create_new_annotation_and_highlight(
                    text=annotation_data['text'],
                    scene=annotation_data['scene'],
                    selection_info=None,  # Let it find the text automatically
                    preserved_metadata=preserved_metadata
                )
                
                successful_count += 1
                print(f"Successfully created annotation {i+1}: {annotation_data['scene']}")
                
            except Exception as e:
                print(f"Failed to create annotation {i+1}: {str(e)}")
                failed_annotations.append({
                    'index': i+1,
                    'text': annotation_data['text'][:50] + "...",
                    'error': str(e)
                })
                
        progress.setValue(len(self.parsed_annotations))
        progress.close()
        
        # Show results
        self.show_creation_results(successful_count, failed_annotations)
        
        # Update theme view to show new annotations
        if successful_count > 0:
            print(f"DEBUG: Refreshing theme view after creating {successful_count} annotations")
            try:
                # Trigger theme view refresh to show new annotations immediately
                if hasattr(self.main_window, 'update_theme_view'):
                    self.main_window.update_theme_view(show_progress=False)
                    print("DEBUG: Theme view updated successfully")
                else:
                    print("DEBUG: update_theme_view method not found on main window")
            except Exception as e:
                print(f"DEBUG: Error updating theme view: {str(e)}")
        
        # Close dialog if successful
        if successful_count > 0:
            self.accept()
            
    def show_creation_results(self, successful_count, failed_annotations):
        """Show results of annotation creation"""
        if failed_annotations:
            # Some failures occurred
            msg = QMessageBox()
            msg.setWindowTitle("Annotation Creation Results")
            msg.setText(f"Created {successful_count} annotations successfully.")
            msg.setInformativeText(f"{len(failed_annotations)} annotations failed to create.")
            
            # Detailed error information
            error_details = "Failed annotations:\n\n"
            for failed in failed_annotations[:10]:  # Show first 10 failures
                error_details += f"#{failed['index']}: {failed['text']}\nError: {failed['error']}\n\n"
            
            if len(failed_annotations) > 10:
                error_details += f"... and {len(failed_annotations) - 10} more failures"
                
            msg.setDetailedText(error_details)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
        else:
            # All successful
            QMessageBox.information(
                self, 
                "Success!", 
                f"Successfully created {successful_count} annotations! 🎉\n\n"
                "The annotations are now visible in your Theme View and can be organized in the Script Editor."
            )


class AINotesGenerator(QDialog):
    """
    Dialog for generating AI notes for existing annotations that don't have notes.
    """
    
    def __init__(self, parent, web_view, main_window):
        super().__init__(parent)
        self.web_view = web_view
        self.main_window = main_window
        self.annotations_without_notes = []
        self.annotations_with_partial_notes = []  # New: annotations with notes but no notes_html or vice versa
        self.full_transcript = ""
        self.api_key = ""
        self.target_annotation_ids = None  # For targeted generation from right-click menu
        
        self.setWindowTitle("AI Generate Notes for Existing Annotations")
        self.setModal(False)  # Non-modal so users can continue working
        self.resize(1000, 850)  # Increased size for new UI elements
        
        self.setup_ui()
        self.load_transcript()
        self.load_api_key()
        self.load_transcript_data()
        self.scan_annotations()
        
    def setup_ui(self):
        """Setup the dialog UI with new user-driven design"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("<h2>AI Generate Notes & Commentary</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Info note
        info_note = QLabel(
            "<b>Customize AI note generation:</b> Provide context about your transcript and configure how AI should generate notes (brief identifiers) and commentary (detailed analysis) for your annotations."
        )
        info_note.setWordWrap(True)
        info_note.setStyleSheet("padding: 10px; background-color: #f0f8ff; border-radius: 5px; margin-bottom: 10px;")
        layout.addWidget(info_note)
        
        # Statistics and summary
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-weight: bold; color: #2c3e50; padding: 8px;")
        layout.addWidget(self.stats_label)
        
        # Create a tabbed interface for better organization
        from PyQt6.QtWidgets import QTabWidget, QSlider, QLineEdit, QTextEdit
        tab_widget = QTabWidget()
        
        # Tab 1: Transcript Context
        context_tab = QWidget()
        context_layout = QVBoxLayout(context_tab)
        
        # Transcript description
        desc_group = QGroupBox("Transcript Information")
        desc_layout = QFormLayout(desc_group)
        
        # Transcript type dropdown - moved to top
        self.transcript_type = QComboBox()
        self.transcript_type.addItems(["Video Editing Project", "Book/Article"])
        self.transcript_type.currentTextChanged.connect(self.on_transcript_type_changed)
        desc_layout.addRow("Transcript Type:", self.transcript_type)
        
        self.transcript_title = QLineEdit()
        self.transcript_title.setPlaceholderText("e.g., Interview with John Smith, Chapter 5: The Journey")
        desc_layout.addRow("Title:", self.transcript_title)
        
        self.transcript_description = QTextEdit()
        self.transcript_description.setMaximumHeight(60)
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
        desc_layout.addRow("Description:", self.transcript_description)
        
        # Add compact save button
        save_button_layout = QHBoxLayout()
        self.save_config_button = QPushButton("💾 Save Configuration")
        self.save_config_button.setMaximumWidth(150)
        self.save_config_button.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.save_config_button.clicked.connect(self.save_transcript_data)
        save_button_layout.addWidget(self.save_config_button)
        save_button_layout.addStretch()
        desc_layout.addRow("", save_button_layout)
        
        # Additional context for AI
        self.additional_context = QTextEdit()
        self.additional_context.setMaximumHeight(80)
        self.additional_context.setPlaceholderText("Additional context, instructions, or specific requirements for the AI to consider when generating notes...")
        self.additional_context.setStyleSheet("""
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
        desc_layout.addRow("Additional Context:", self.additional_context)
        
        context_layout.addWidget(desc_group)
        
        # Type-specific guidance
        self.type_guidance_label = QLabel()
        self.type_guidance_label.setWordWrap(True)
        self.type_guidance_label.setStyleSheet("padding: 10px; background-color: #f8f9fa; border-radius: 4px; margin: 10px;")
        self.update_type_guidance()
        context_layout.addWidget(self.type_guidance_label)
        
        context_layout.addStretch()
        tab_widget.addTab(context_tab, "Transcript Context")
        
        # Tab 2: Generation Settings
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # Commentary settings
        commentary_group = QGroupBox("Commentary Settings")
        commentary_layout = QVBoxLayout(commentary_group)
        
        from PyQt6.QtWidgets import QCheckBox
        self.generate_commentary = QCheckBox("Generate Commentary")
        self.generate_commentary.setChecked(True)
        self.generate_commentary.toggled.connect(self.on_commentary_toggled)
        commentary_layout.addWidget(self.generate_commentary)
        
        # Commentary length slider
        length_container = QWidget()
        length_layout = QFormLayout(length_container)
        
        self.commentary_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.commentary_length_slider.setMinimum(1)
        self.commentary_length_slider.setMaximum(4)
        self.commentary_length_slider.setValue(2)
        self.commentary_length_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.commentary_length_slider.setTickInterval(1)
        self.commentary_length_slider.valueChanged.connect(self.update_length_label)
        
        self.length_label = QLabel("1-2 sentences")
        length_layout.addRow("Commentary Length:", self.commentary_length_slider)
        length_layout.addRow("", self.length_label)
        
        commentary_layout.addWidget(length_container)
        settings_layout.addWidget(commentary_group)
        
        # Target annotations filter
        filter_group = QGroupBox("Target Specific Annotations (Optional)")
        filter_layout = QVBoxLayout(filter_group)
        
        filter_info = QLabel("Leave empty to process all annotations missing notes/commentary, or specify criteria to target specific ones:")
        filter_info.setWordWrap(True)
        filter_info.setStyleSheet("font-size: 11px; color: #666;")
        filter_layout.addWidget(filter_info)
        
        self.target_filter = QTextEdit()
        self.target_filter.setMaximumHeight(60)
        self.target_filter.setPlaceholderText("e.g., 'emotional moments', 'technical explanations', 'chapter introductions'")
        filter_layout.addWidget(self.target_filter)
        
        settings_layout.addWidget(filter_group)
        
        # AI Model settings
        ai_group = QGroupBox("AI Configuration")
        ai_layout = QFormLayout(ai_group)
        
        self.model_selector = QComboBox()
        self.model_selector.addItems(["gemini-2.5-pro", "gemini-2.5-flash"])
        ai_layout.addRow("Model:", self.model_selector)
        
        from PyQt6.QtWidgets import QSpinBox
        self.thinking_budget = QSpinBox()
        self.thinking_budget.setMinimum(1000)
        self.thinking_budget.setMaximum(20000)
        self.thinking_budget.setValue(2000)
        self.thinking_budget.setSuffix(" tokens")
        ai_layout.addRow("Thinking Budget:", self.thinking_budget)
        
        self.use_full_context = QCheckBox("Include full transcript context")
        self.use_full_context.setChecked(True)
        ai_layout.addRow("", self.use_full_context)
        
        settings_layout.addWidget(ai_group)
        settings_layout.addStretch()
        
        tab_widget.addTab(settings_tab, "Generation Settings")
        
        # Tab 3: Annotations Preview
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        
        self.annotations_display = QTextEdit()
        self.annotations_display.setReadOnly(True)
        self.annotations_display.setPlaceholderText("Scanning annotations...")
        preview_layout.addWidget(self.annotations_display)
        
        tab_widget.addTab(preview_tab, "Annotations Preview")
        
        layout.addWidget(tab_widget)
        
        # AI Response display area
        response_group = QGroupBox("AI Response")
        response_layout = QVBoxLayout(response_group)
        
        self.response_display = QTextEdit()
        self.response_display.setReadOnly(True)
        self.response_display.setMaximumHeight(150)
        self.response_display.setPlaceholderText("AI response will appear here during processing...")
        self.response_display.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        response_layout.addWidget(self.response_display)
        
        layout.addWidget(response_group)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
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
                    stop:0 #17a2b8, stop:0.5 #138496, stop:1 #17a2b8);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.process_button = QPushButton("Generate Notes")
        self.process_button.clicked.connect(self.process_with_ai)
        self.process_button.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.process_button.setDefault(True)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_processing)
        self.stop_button.setStyleSheet("font-weight: bold; padding: 8px 16px; background-color: #dc3545; color: white;")
        self.stop_button.hide()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.process_button)
        
        layout.addLayout(button_layout)
        
    def update_type_guidance(self):
        """Update guidance text based on selected transcript type"""
        if self.transcript_type.currentText() == "Video Editing Project":
            guidance = """<b>Video Editing Project:</b><br>
            • Notes will be brief identifiers (3-6 words) for quick reference<br>
            • Commentary will provide narrative value and emotional impact<br>
            • Focus on storytelling, pacing, and audience engagement"""
        else:
            guidance = """<b>Book/Article:</b><br>
            • Notes will be passage identifiers for skimming<br>
            • Commentary will provide analysis, explanation, and context<br>
            • Focus on comprehension, themes, and scholarly insights"""
        self.type_guidance_label.setText(guidance)
    
    def on_transcript_type_changed(self, text):
        """Handle transcript type change"""
        self.update_type_guidance()
    
    def on_commentary_toggled(self, checked):
        """Handle commentary checkbox toggle"""
        self.commentary_length_slider.setEnabled(checked)
        self.length_label.setEnabled(checked)
        if not checked:
            self.length_label.setText("Commentary disabled")
        else:
            self.update_length_label()
    
    def update_length_label(self):
        """Update the length label based on slider value"""
        value = self.commentary_length_slider.value()
        if value == 1:
            self.length_label.setText("1 sentence")
        elif value == 2:
            self.length_label.setText("1-2 sentences")
        elif value == 3:
            self.length_label.setText("1-3 sentences")
        else:
            self.length_label.setText("No length restriction")
        
    def load_transcript(self):
        """Load the full transcript from the web view"""
        if not self.web_view:
            return
        
        # Use the same method as the main AI annotation generator
        def handle_transcript(html):
            if html:
                from bs4 import BeautifulSoup
                
                # Parse HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove CSS and script elements
                for element in soup(["style", "script", "head"]):
                    element.decompose()
                
                # Extract text with speech titles included
                transcript_parts = []
                
                # Look for speech headers and content sections
                speech_headers = soup.find_all('div', class_='speech-header')
                
                if speech_headers:
                    # Process each speech header to get title and find corresponding content
                    for header in speech_headers:
                        title_elem = header.find(class_='speech-title')
                        
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            
                            # Find the corresponding speech content
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
                    # Fallback: get text content
                    text = soup.get_text(separator=' ', strip=True)
                    import re
                    text = re.sub(r'\s+', ' ', text).strip()
                    transcript_parts.append(text)
                
                self.full_transcript = '\n\n'.join(transcript_parts)
                print(f"DEBUG: Loaded transcript with {len(self.full_transcript)} characters for notes generation")
                
        # Get the HTML content
        self.web_view.page().toHtml(handle_transcript)
        
    def load_api_key(self):
        """Load API key from file"""
        import os
        
        try:
            # Try different possible locations
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
                        
            # If no key found, show message
            QMessageBox.information(self, "API Key Setup", 
                "Please ensure your Gemini API key is configured in data/api_key.txt")
                
        except Exception as e:
            print(f"Error loading API key: {e}")
            
    def load_transcript_data(self):
        """Load persistent transcript data from session file"""
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
            
            # Load saved values from session data
            title = session_data.get('ai_notes_title', '')
            description = session_data.get('ai_notes_description', '')
            additional_context = session_data.get('ai_notes_additional_context', '')
            transcript_type = session_data.get('ai_notes_transcript_type', 'Video Editing Project')
            
            # Set UI values
            self.transcript_title.setText(title)
            self.transcript_description.setPlainText(description)
            self.additional_context.setPlainText(additional_context)
            
            # Set transcript type
            type_index = self.transcript_type.findText(transcript_type)
            if type_index >= 0:
                self.transcript_type.setCurrentIndex(type_index)
            
            print(f"DEBUG: Loaded transcript data from session - title: '{title}', type: '{transcript_type}'")
        except Exception as e:
            print(f"Error loading transcript data: {e}")
    
    def save_transcript_data(self):
        """Save transcript data directly to session file"""
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
            
            # Update AI notes configuration fields
            session_data['ai_notes_title'] = self.transcript_title.text().strip()
            session_data['ai_notes_description'] = self.transcript_description.toPlainText().strip()
            session_data['ai_notes_additional_context'] = self.additional_context.toPlainText().strip()
            session_data['ai_notes_transcript_type'] = self.transcript_type.currentText()
            
            # Atomic write using temporary file for safety (same pattern as other session saves)
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
                
                print(f"DEBUG: Saved transcript data to session file - title: '{session_data['ai_notes_title']}', type: '{session_data['ai_notes_transcript_type']}'")
                
            finally:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                
        except Exception as e:
            print(f"Error saving transcript data: {e}")
    
    def set_target_annotations(self, annotation_ids):
        """Set specific annotation IDs to target for notes generation (from right-click menu)"""
        self.target_annotation_ids = annotation_ids
        print(f"DEBUG: Set target annotations: {annotation_ids}")
        
        # Update window title to reflect targeted mode
        count = len(annotation_ids)
        if count == 1:
            self.setWindowTitle("AI Generate Notes - 1 Selected Annotation")
        else:
            self.setWindowTitle(f"AI Generate Notes - {count} Selected Annotations")
        
        # Rescan annotations to only include targeted ones
        self.scan_annotations()
            
    def get_theme_search(self):
        """Get the ThemeViewSearch instance for filter checking"""
        if not hasattr(self, 'main_window') or not self.main_window:
            return None
        
        # Look for script_search attribute that contains ThemeViewSearch
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

    def scan_annotations(self):
        """Scan existing annotations to find those without notes or with partial notes, respecting active filters"""
        if not self.web_view or not hasattr(self.web_view, 'annotations'):
            self.stats_label.setText("❌ No annotations found")
            return
        
        self.annotations_without_notes = []
        self.annotations_with_partial_notes = []
        total_annotations = len(self.web_view.annotations)
        skipped_dividers = 0
        filtered_out = 0
        
        # Get theme search for filtering
        theme_search = self.get_theme_search()
        
        print(f"DEBUG CATEGORIZATION: Processing {total_annotations} total annotations...")
        if self.target_annotation_ids is not None:
            print(f"DEBUG CATEGORIZATION: Targeting {len(self.target_annotation_ids)} specific annotations: {self.target_annotation_ids}")
        elif theme_search:
            print("DEBUG CATEGORIZATION: Will respect current filter settings")
        else:
            print("DEBUG CATEGORIZATION: No filtering - will process all annotations")
        
        for annotation in self.web_view.annotations:
            # Skip dividers - they are structural elements, not content annotations
            if annotation.get('divider'):
                skipped_dividers += 1
                continue
            
            # If we have target annotation IDs, only process those specific annotations
            if self.target_annotation_ids is not None:
                annotation_id = annotation.get('id')
                if annotation_id not in self.target_annotation_ids:
                    continue  # Skip annotations not in our target list
            else:
                # Apply current filters if theme search is available (only when not targeting specific annotations)
                if theme_search and hasattr(theme_search, '_annotation_matches_current_filters'):
                    if not theme_search._annotation_matches_current_filters(annotation):
                        filtered_out += 1
                        continue  # Skip filtered out annotations
                
            # Check if annotation lacks notes or notes_html
            notes = annotation.get('notes', '').strip()
            notes_html = annotation.get('notes_html', '').strip()
            annotation_id = annotation.get('id', 'NO_ID')
            annotation_text = annotation.get('text', '')[:50] + "..." if len(annotation.get('text', '')) > 50 else annotation.get('text', '')
            
            print(f"DEBUG CATEGORIZATION: Annotation {annotation_id}: '{annotation_text}'")
            print(f"                      notes: {'EXISTS' if notes else 'MISSING'} ({len(notes)} chars)")
            print(f"                      notes_html: {'EXISTS' if notes_html else 'MISSING'} ({len(notes_html)} chars)")
            
            # Categorize annotations
            if not notes and not notes_html:
                # Both empty - add to without_notes
                self.annotations_without_notes.append(annotation)
                print(f"                      -> ADDED to annotations_without_notes (both missing)")
            elif not notes or not notes_html:
                # One is empty but not both - add to partial_notes
                annotation['_missing_notes'] = not notes  # Track which field is missing
                annotation['_missing_notes_html'] = not notes_html
                self.annotations_with_partial_notes.append(annotation)
                missing_field = "notes" if not notes else "notes_html"
                print(f"                      -> ADDED to annotations_with_partial_notes (missing {missing_field})")
            else:
                print(f"                      -> SKIPPED (both notes and notes_html exist)")
        
        count_without_notes = len(self.annotations_without_notes)
        count_partial_notes = len(self.annotations_with_partial_notes)
        content_annotations = total_annotations - skipped_dividers
        filtered_annotations = content_annotations - filtered_out
        
        print(f"DEBUG CATEGORIZATION SUMMARY:")
        print(f"  Total annotations: {total_annotations}")
        print(f"  Skipped dividers: {skipped_dividers}")
        print(f"  Content annotations: {content_annotations}")
        if filtered_out > 0:
            print(f"  Filtered out: {filtered_out}")
            print(f"  Visible (after filtering): {filtered_annotations}")
        print(f"  annotations_without_notes: {count_without_notes}")
        print(f"  annotations_with_partial_notes: {count_partial_notes}")
        print(f"  annotations with both notes+notes_html: {filtered_annotations - count_without_notes - count_partial_notes}")
        
        # Update stats label with filter/targeting information
        if self.target_annotation_ids is not None:
            target_count = len(self.target_annotation_ids)
            stats_text = f"🎯 Targeting {count_without_notes} annotations without notes/commentary, {count_partial_notes} with partial notes/commentary out of {target_count} selected annotations"
        elif filtered_out > 0:
            stats_text = f"📊 Found {count_without_notes} annotations without notes/commentary, {count_partial_notes} with partial notes/commentary out of {filtered_annotations} visible annotations ({filtered_out} filtered out)"
        else:
            stats_text = f"📊 Found {count_without_notes} annotations without notes/commentary, {count_partial_notes} with partial notes/commentary out of {content_annotations} content annotations"
        self.stats_label.setText(stats_text)
        
        # Update annotations display  
        if count_without_notes == 0 and count_partial_notes == 0:
            self.annotations_display.setHtml("<i>✅ All annotations already have complete notes and commentary!</i>")
            self.process_button.setEnabled(False)
        else:
            # Show preview of annotations
            html = ""
            
            if count_without_notes > 0:
                html += "<b>Annotations without notes or commentary:</b><br>"
                for i, annotation in enumerate(self.annotations_without_notes[:5]):  # Show first 5
                    text_preview = annotation.get('text', '')[:60]
                    if len(annotation.get('text', '')) > 60:
                        text_preview += "..."
                    scene = annotation.get('scene', 'Unknown')
                    html += f"• [{scene}] {text_preview}<br>"
                
                if count_without_notes > 5:
                    html += f"<i>... and {count_without_notes - 5} more</i><br>"
                html += "<br>"
            
            if count_partial_notes > 0:
                html += "<b>Annotations with incomplete notes/commentary:</b><br>"
                for i, annotation in enumerate(self.annotations_with_partial_notes[:5]):  # Show first 5
                    text_preview = annotation.get('text', '')[:60]
                    if len(annotation.get('text', '')) > 60:
                        text_preview += "..."
                    scene = annotation.get('scene', 'Unknown')
                    missing = []
                    if annotation.get('_missing_notes'):
                        missing.append("notes")
                    if annotation.get('_missing_notes_html'):
                        missing.append("commentary")
                    html += f"• [{scene}] {text_preview} <i>(missing: {', '.join(missing)})</i><br>"
                
                if count_partial_notes > 5:
                    html += f"<i>... and {count_partial_notes - 5} more</i>"
                
            self.annotations_display.setHtml(html)
        
        print(f"DEBUG: Found {count_without_notes} annotations without notes")
        
    def create_notes_prompt(self):
        """Create the AI prompt for generating notes based on user inputs"""
        thinking_budget = self.thinking_budget.value()
        use_context = self.use_full_context.isChecked()
        generate_commentary = self.generate_commentary.isChecked()
        transcript_type = self.transcript_type.currentText()
        transcript_title = self.transcript_title.text().strip()
        transcript_description = self.transcript_description.toPlainText().strip()
        additional_context = self.additional_context.toPlainText().strip()
        target_filter = self.target_filter.toPlainText().strip()
        commentary_length = self.commentary_length_slider.value()
        
        # Combine annotations needing processing
        annotations_to_process = self.annotations_without_notes + self.annotations_with_partial_notes
        
        print(f"DEBUG PROMPT CREATION: Combining annotations for AI processing")
        print(f"  From annotations_without_notes: {len(self.annotations_without_notes)} annotations")
        for i, ann in enumerate(self.annotations_without_notes):
            print(f"    {i+1}. {ann.get('id', 'NO_ID')} - '{ann.get('text', '')[:30]}...'")
        
        print(f"  From annotations_with_partial_notes: {len(self.annotations_with_partial_notes)} annotations")
        for i, ann in enumerate(self.annotations_with_partial_notes):
            missing_notes = ann.get('_missing_notes', False)
            missing_notes_html = ann.get('_missing_notes_html', False)
            missing_info = []
            if missing_notes:
                missing_info.append("notes")
            if missing_notes_html:
                missing_info.append("notes_html")
            print(f"    {i+1}. {ann.get('id', 'NO_ID')} - '{ann.get('text', '')[:30]}...' (missing: {', '.join(missing_info)})")
        
        print(f"  Total annotations_to_process: {len(annotations_to_process)}")
        
        if not annotations_to_process:
            return None
        
        # Build annotation data for prompt
        annotations_data = []
        for i, annotation in enumerate(annotations_to_process):
            # Get all relevant metadata
            tags = annotation.get('tags', [])
            tags_text = ', '.join(tags) if tags else 'None'
            
            data = {
                'index': i + 1,
                'text': annotation.get('text', ''),
                'scene': annotation.get('scene', ''),
                'tags': tags,
                'tags_text': tags_text,
                'theme': annotation.get('theme', ''),
                'id': annotation.get('id', ''),
                'has_notes': bool(annotation.get('notes', '').strip()),
                'has_notes_html': bool(annotation.get('notes_html', '').strip())
            }
            annotations_data.append(data)
        
        annotations_text = "\n".join([
            f"ANNOTATION {data['index']}:\n"
            f"Theme/Scene: {data['scene']}\n"
            f"Tags: {data['tags_text']}\n"
            f"Text: {data['text']}\n"
            f"ID: {data['id']}\n"
            f"Has existing notes: {'Yes' if data['has_notes'] else 'No'}\n"
            f"Has existing commentary: {'Yes' if data['has_notes_html'] else 'No'}\n"
            for data in annotations_data
        ])
        
        # Build context section based on user preference
        if use_context:
            context_section = f"""FULL TRANSCRIPT CONTEXT:
{self.full_transcript}

"""
            context_instruction = "Analyze each annotation within the context of the full transcript to understand its narrative purpose and how it connects to the broader story."
        else:
            context_section = ""
            context_instruction = "Analyze each annotation text independently to determine its content value and purpose for video creation."
        
        # Build commentary length instruction
        commentary_length_instruction = ""
        if generate_commentary:
            if commentary_length == 1:
                commentary_length_instruction = "Restrict commentary to exactly 1 sentence."
            elif commentary_length == 2:
                commentary_length_instruction = "Restrict commentary to 1-2 sentences maximum."
            elif commentary_length == 3:
                commentary_length_instruction = "Restrict commentary to 1-3 sentences maximum."
            else:
                commentary_length_instruction = "No length restriction for commentary."
        
        # Build targeting instructions
        targeting_instructions = ""
        if target_filter:
            targeting_instructions = f"""
TARGET SPECIFIC ANNOTATIONS ONLY:
The user has provided explicit instructions to only target and add notes/commentary to specific annotations that match the following criteria:
"{target_filter}"

IMPORTANT: Only generate notes/commentary for annotations that clearly match these criteria. Do NOT respond at all for annotations that don't fit these requirements - simply omit them from your response entirely.
"""

        # Build type-specific instructions
        if transcript_type == "Video Editing Project":
            type_instructions = """This is a VIDEO EDITING PROJECT transcript.
            
For notes: Create brief identifiers (3-6 words) that help editors quickly understand each segment's purpose.
For commentary: Focus on narrative value, emotional impact, and how each segment contributes to the video's story arc.

Consider:
- Storytelling potential and narrative function
- Emotional resonance and audience engagement
- Pacing and flow within the video structure
- Visual storytelling opportunities
- Character development and transformation"""
        else:  # Book/Article
            type_instructions = """This is a BOOK/ARTICLE transcript.
            
For notes: Create brief passage identifiers that help readers quickly skim and locate relevant content.
For commentary: Provide analysis, explanation, and scholarly context for deeper understanding.

Consider:
- Thematic significance and literary devices
- Academic or scholarly relevance
- Historical or cultural context
- Connections to broader concepts
- Critical analysis and interpretation"""

        prompt = f"""<thinking>
Budget: {thinking_budget} tokens for reasoning about content analysis.

TRANSCRIPT INFORMATION:
Title: {transcript_title if transcript_title else 'Not specified'}
Description: {transcript_description if transcript_description else 'Not specified'}
Additional Context: {additional_context if additional_context else 'Not specified'}

{type_instructions}

Analyze each annotation to generate appropriate notes and {'commentary' if generate_commentary else '(commentary generation disabled)'}.
</thinking>

You are generating notes and commentary for annotations in a {transcript_type.lower()}.

{context_section}ANNOTATIONS TO ANALYZE:
{annotations_text}

INSTRUCTIONS:
{context_instruction}

{type_instructions}
{targeting_instructions}
{commentary_length_instruction if generate_commentary else ''}

CRITICAL RULES:
1. ONLY generate fields that are missing for each annotation
2. If an annotation already has notes, DO NOT generate new notes for it
3. If an annotation already has commentary (notes_html), DO NOT generate new commentary for it
4. Check the "Has existing notes" and "Has existing commentary" fields for each annotation

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:
{'[[NOTES :: ANNOTATION_ID :: BRIEF_NOTES :: DETAILED_HTML_NOTES]]' if generate_commentary else '[[NOTES :: ANNOTATION_ID :: BRIEF_NOTES :: SKIP]]'}

FIELD EXPLANATIONS:
- ANNOTATION_ID: The exact ID from the annotation data (copy exactly)
- BRIEF_NOTES: {'Brief identifier (3-6 words). Use "SKIP" if annotation already has notes or doesn\'t match targeting criteria.' if generate_commentary else 'Brief identifier (3-6 words). Use "SKIP" if annotation already has notes or doesn\'t match targeting criteria.'}
- DETAILED_HTML_NOTES: {'Commentary/analysis. Use "SKIP" if annotation already has commentary, doesn\'t match targeting criteria, or if commentary generation is disabled.' if generate_commentary else 'Always use "SKIP" since commentary generation is disabled.'}

REQUIREMENTS:
- Brief notes must be concise (3-6 words maximum)
- Only generate missing fields - respect existing user content
- {commentary_length_instruction if generate_commentary else 'Commentary generation is disabled - always use "SKIP" for DETAILED_HTML_NOTES'}

Examples:
[[NOTES :: abc123-def456 :: Character motivation revealed :: {'This segment establishes authentic personality and core motivation.' if generate_commentary else 'SKIP'}]]
[[NOTES :: xyz789-abc012 :: SKIP :: {'Powerful transformation moment showing growth and vulnerability.' if generate_commentary else 'SKIP'}]] (if notes already exist but commentary doesn't)

Only provide notes in the specified format. No additional text or explanations."""

        return prompt
        
    def process_with_ai(self):
        """Process annotations with AI to generate notes"""
        # Check if we have any annotations to process
        total_to_process = len(self.annotations_without_notes) + len(self.annotations_with_partial_notes)
        if total_to_process == 0:
            QMessageBox.warning(self, "No Annotations", "No annotations found that need notes or commentary.")
            return
            
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            QMessageBox.warning(self, "API Key Required", "Please configure your Gemini API key first.")
            return
        
        # Validate user inputs (transcript title and description are optional per user feedback)
        
        # Check if full transcript context is enabled and transcript is large
        use_context = self.use_full_context.isChecked()
        if use_context and len(self.full_transcript) > 500000:
            msg = QMessageBox(self)
            msg.setWindowTitle("Large Transcript Warning")
            msg.setText("The transcript is very large (over 500,000 characters).")
            msg.setInformativeText("Using full transcript context will consume a significant number of tokens. Do you want to continue?")
            msg.setDetailedText(f"Transcript size: {len(self.full_transcript):,} characters\n\n"
                               f"This will consume substantial API tokens and may be expensive. "
                               f"Consider unchecking 'Include full transcript context' for a more economical approach.")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.No)
            msg.setIcon(QMessageBox.Icon.Warning)
            
            if msg.exec() == QMessageBox.StandardButton.No:
                return
        
        prompt = self.create_notes_prompt()
        if not prompt:
            return
        print("=" * 80)
        print(f"DEBUG: NOTES GENERATION PROMPT ({'WITH' if use_context else 'WITHOUT'} FULL TRANSCRIPT CONTEXT):")
        print("=" * 80)
        print(prompt)
        print("=" * 80)
            
        # Update UI for processing state
        self.process_button.hide()
        self.stop_button.show()
        
        # Show progress bar
        self.progress_bar.show()
        self.progress_bar.setFormat("AI is generating notes...")
        
        # Clear response display
        self.response_display.clear()
        
        # Start AI worker thread
        thinking_budget = self.thinking_budget.value()
        selected_model = self.model_selector.currentText()
        self.worker_thread = AIWorkerThread(prompt, self.api_key, selected_model, thinking_budget)
        self.worker_thread.response_received.connect(self.handle_ai_response)
        self.worker_thread.chunk_received.connect(self.handle_ai_chunk)
        self.worker_thread.error_occurred.connect(self.handle_ai_error)
        self.worker_thread.retry_suggested.connect(self.handle_retry_suggestion)
        self.worker_thread.finished.connect(self.cleanup_worker)
        self.worker_thread.start()
        
    def handle_ai_response(self, response_text):
        """Handle AI response and update annotations with notes"""
        try:
            # Parse AI response
            notes_count = self.parse_notes_response(response_text)
            
            if notes_count == 0:
                # Show detailed error in response area
                self.response_display.clear()
                error_info = f"❌ No Valid Notes Generated\n\nThe AI response was received but no valid notes were found.\n\nPossible issues:\n• AI response format doesn't match expected pattern\n• Annotation IDs don't match existing annotations\n• Response was truncated or incomplete\n\nRaw AI response (first 500 chars):\n{response_text[:500]}{'...' if len(response_text) > 500 else ''}"
                self.response_display.setPlainText(error_info)
                
                QMessageBox.warning(self, "No Notes Generated", "AI did not generate any valid notes. Check the AI response area for details.")
                return
                
            # Show confirmation dialog
            msg = QMessageBox(self)
            msg.setWindowTitle("Apply Notes?")
            msg.setText(f"AI generated notes for {notes_count} annotations.")
            msg.setInformativeText("Would you like to apply these notes to your annotations?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            if msg.exec() == QMessageBox.StandardButton.Yes:
                self.apply_notes_to_annotations()
            
        except Exception as e:
            # Show detailed error in response area
            self.response_display.clear()
            error_details = f"❌ Response Processing Error:\n\n{str(e)}\n\nThis error occurred while trying to process the AI response.\n\nRaw AI response:\n{response_text}"
            self.response_display.setPlainText(error_details)
            
            QMessageBox.critical(self, "Error", f"Failed to process AI response: {str(e)}\n\nCheck the AI response area for full details.")
    
    def handle_ai_chunk(self, chunk_text):
        """Handle streaming AI response chunks"""
        self.progress_bar.setFormat("📝 AI is generating notes...")
        
        # Append chunk to response display
        cursor = self.response_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk_text)
        self.response_display.setTextCursor(cursor)
        
        # Auto-scroll to bottom
        scrollbar = self.response_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
            
    def handle_ai_error(self, error_message):
        """Handle AI processing errors with detailed feedback"""
        # Also display error in the response area for user visibility
        self.response_display.clear()
        error_text = f"❌ AI Processing Error:\n\n{error_message}\n\nPlease check:\n• Your API key is valid\n• You have internet connection\n• The Gemini service is available"
        self.response_display.setPlainText(error_text)
        
        # Show critical error dialog
        QMessageBox.critical(self, "AI Error", f"AI processing failed:\n\n{error_message}")
        
    def handle_retry_suggestion(self, error_message):
        """Handle retryable errors with user-friendly message and retry option"""
        # Display error info in response area
        self.response_display.clear()
        retry_text = f"⚠️ Temporary AI Service Issue:\n\n{error_message}\n\nThis appears to be a temporary problem with the AI service. You can retry the operation."
        self.response_display.setPlainText(retry_text)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("AI Service Temporarily Unavailable")
        msg.setText("The AI service is currently experiencing issues.")
        msg.setInformativeText("Would you like to try again?")
        msg.setDetailedText(error_message)
        msg.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Retry)
        msg.setIcon(QMessageBox.Icon.Warning)
        
        if msg.exec() == QMessageBox.StandardButton.Retry:
            # User wants to retry - restart the process
            self.process_with_ai()
        else:
            # User cancelled - clean up
            self.cleanup_worker()
        
    def stop_processing(self):
        """Stop the AI processing"""
        if hasattr(self, 'worker_thread'):
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self.worker_thread.deleteLater()
        
        self.cleanup_worker()
        self.response_display.setText("Processing cancelled by user.")
        
    def cleanup_worker(self):
        """Clean up worker thread and reset UI"""
        self.process_button.show()
        self.stop_button.hide()
        self.progress_bar.hide()
        
        if hasattr(self, 'worker_thread'):
            self.worker_thread.deleteLater()
            
    def parse_notes_response(self, response_text):
        """Parse AI response and extract notes data"""
        self.parsed_notes = []
        
        # Find all notes blocks
        pattern = r'\[\[NOTES\s*::\s*([^:]+?)\s*::\s*([^:]+?)\s*::\s*([^\]]+?)\]\]'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        print(f"DEBUG: Found {len(matches)} notes matches in AI response")
        
        if len(matches) == 0:
            print(f"DEBUG: No matches found. Looking for pattern in response:")
            print(f"DEBUG: Response starts with: '{response_text[:200]}...'")
            print(f"DEBUG: Expected pattern: [[NOTES :: ANNOTATION_ID :: BRIEF_NOTES :: DETAILED_HTML_NOTES]]")
        
        failed_matches = []
        
        for i, match in enumerate(matches):
            annotation_id, brief_notes, detailed_notes = match
            annotation_id = annotation_id.strip()
            brief_notes = brief_notes.strip()
            detailed_notes = detailed_notes.strip()
            
            print(f"DEBUG: Processing notes {i+1}/{len(matches)}: ID='{annotation_id}'")
            print(f"DEBUG: Brief notes: '{brief_notes}'")
            print(f"DEBUG: Detailed notes ({len(detailed_notes)} chars): '{detailed_notes[:100]}{'...' if len(detailed_notes) > 100 else ''}'")
            
            # Find the corresponding annotation in both lists
            found_annotation = None
            found_in_list = None
            
            # First check annotations_without_notes
            for annotation in self.annotations_without_notes:
                if annotation.get('id') == annotation_id:
                    found_annotation = annotation
                    found_in_list = "annotations_without_notes"
                    break
            
            # If not found, check annotations_with_partial_notes
            if not found_annotation:
                for annotation in self.annotations_with_partial_notes:
                    if annotation.get('id') == annotation_id:
                        found_annotation = annotation
                        found_in_list = "annotations_with_partial_notes"
                        break
            
            if found_annotation:
                # Add debug info about current state
                current_notes = found_annotation.get('notes', '').strip()
                current_notes_html = found_annotation.get('notes_html', '').strip()
                
                self.parsed_notes.append({
                    'annotation_id': annotation_id,
                    'annotation': found_annotation,
                    'brief_notes': brief_notes,
                    'detailed_notes': detailed_notes
                })
                print(f"DEBUG: ✅ Successfully matched annotation {annotation_id} from {found_in_list}")
                print(f"DEBUG:    Current state - notes: {'EXISTS' if current_notes else 'MISSING'}, notes_html: {'EXISTS' if current_notes_html else 'MISSING'}")
                print(f"DEBUG:    Will add - notes: {'YES' if brief_notes != 'SKIP' and not current_notes else 'NO'}, notes_html: {'YES' if detailed_notes != 'SKIP' and not current_notes_html else 'NO'}")
            else:
                error_detail = f"Could not find annotation with ID '{annotation_id}'"
                failed_matches.append(error_detail)
                print(f"DEBUG: ❌ {error_detail}")
                print(f"DEBUG:    Searched {len(self.annotations_without_notes)} annotations_without_notes")
                print(f"DEBUG:    Searched {len(self.annotations_with_partial_notes)} annotations_with_partial_notes")
                
        if failed_matches:
            print(f"DEBUG: Failed to match {len(failed_matches)} annotations:")
            for error in failed_matches:
                print(f"DEBUG:   - {error}")
            print(f"DEBUG: Available annotation IDs in annotations_without_notes: {[a.get('id') for a in self.annotations_without_notes]}")
            print(f"DEBUG: Available annotation IDs in annotations_with_partial_notes: {[a.get('id') for a in self.annotations_with_partial_notes]}")
        
        print(f"DEBUG: Successfully parsed {len(self.parsed_notes)} valid notes")
        return len(self.parsed_notes)
    
    def apply_notes_to_annotations(self):
        """Apply the generated notes to the annotations"""
        if not self.parsed_notes:
            return
        
        successful_count = 0
        
        for note_data in self.parsed_notes:
            try:
                annotation = note_data['annotation']
                annotation_id = note_data['annotation_id']
                annotation_text = annotation.get('text', '')
                
                print(f"DEBUG: Updating annotation {annotation_id}")
                print(f"DEBUG: Brief notes (goes to 'notes'): '{note_data['brief_notes']}'")
                print(f"DEBUG: Detailed notes (goes to 'notes_html') - {len(note_data['detailed_notes'])} chars:")
                print(f"       '{note_data['detailed_notes']}'")
                
                # Verify the annotation exists and check current state
                current_notes = annotation.get('notes', '')
                current_notes_html = annotation.get('notes_html', '')
                print(f"DEBUG: Current annotation notes: '{current_notes}'")
                print(f"DEBUG: Current annotation notes_html: '{current_notes_html}'")
                
                # We need to update the annotation in the THEME VIEW (AnnotationListWidget), not order list!
                
                # Validation: Only update fields that are actually missing and where AI didn't return SKIP
                original_notes = annotation.get('notes', '').strip()
                original_notes_html = annotation.get('notes_html', '').strip()
                
                # Check if AI tried to modify existing user notes (this should be blocked)
                notes_changed = original_notes and note_data['brief_notes'] != "SKIP" and note_data['brief_notes'] != original_notes
                notes_html_changed = original_notes_html and note_data['detailed_notes'] != "SKIP" and note_data['detailed_notes'] != original_notes_html
                
                if notes_changed:
                    print(f"WARNING: AI tried to modify existing user notes for {annotation_id}. Blocking notes update.")
                    print(f"Original: '{original_notes}' -> AI wanted: '{note_data['brief_notes']}'")
                    note_data['brief_notes'] = "SKIP"  # Block the notes update
                
                if notes_html_changed:
                    print(f"WARNING: AI tried to modify existing user notes_html for {annotation_id}. Blocking notes_html update.")
                    print(f"Original: '{original_notes_html[:50]}...' -> AI wanted: '{note_data['detailed_notes'][:50]}...'")
                    note_data['detailed_notes'] = "SKIP"  # Block the notes_html update
                
                # Apply updates only for missing fields
                if not original_notes and note_data['brief_notes'] != "SKIP":
                    annotation['notes'] = note_data['brief_notes']
                    print(f"DEBUG: Added notes to annotation {annotation_id}: '{note_data['brief_notes']}'")
                else:
                    print(f"DEBUG: Skipped notes for {annotation_id} (already exists or SKIP)")
                
                if not original_notes_html and note_data['detailed_notes'] != "SKIP":
                    annotation['notes_html'] = note_data['detailed_notes']
                    print(f"DEBUG: Added notes_html to annotation {annotation_id}: '{note_data['detailed_notes'][:50]}...'")
                else:
                    print(f"DEBUG: Skipped notes_html for {annotation_id} (already exists or SKIP)")
                
                # Also update the main web_view.annotations list
                if hasattr(self.web_view, 'annotations'):
                    for main_annotation in self.web_view.annotations:
                        if main_annotation.get('id') == annotation_id:
                            # Only update missing fields
                            if not original_notes and note_data['brief_notes'] != "SKIP":
                                main_annotation['notes'] = note_data['brief_notes']
                            if not original_notes_html and note_data['detailed_notes'] != "SKIP":
                                main_annotation['notes_html'] = note_data['detailed_notes']
                            print(f"DEBUG: Updated main annotation data for {annotation_id}")
                            break
                
                # Update the theme view widget directly to show new notes immediately (only for non-SKIP values)
                notes_to_show = note_data['brief_notes'] if note_data['brief_notes'] != "SKIP" else None
                notes_html_to_show = note_data['detailed_notes'] if note_data['detailed_notes'] != "SKIP" else None
                
                # Only update theme view if we actually have new content to show
                # When SKIP, we preserve existing content by not calling the update method
                if notes_to_show is not None or notes_html_to_show is not None:
                    # Only pass non-None values to prevent overwriting existing content
                    if notes_to_show is not None and notes_html_to_show is not None:
                        # Both need updating
                        self.update_annotation_notes_in_theme_view(annotation_id, notes_to_show, notes_html_to_show)
                        print(f"DEBUG: Updated annotation display for {annotation_id} (both notes and notes_html)")
                    elif notes_to_show is not None:
                        # Only notes needs updating, preserve existing notes_html
                        current_notes_html = annotation.get('notes_html', '')
                        self.update_annotation_notes_in_theme_view(annotation_id, notes_to_show, current_notes_html)
                        print(f"DEBUG: Updated annotation display for {annotation_id} (notes only, preserved notes_html)")
                    elif notes_html_to_show is not None:
                        # Only notes_html needs updating, preserve existing notes
                        current_notes = annotation.get('notes', '')
                        self.update_annotation_notes_in_theme_view(annotation_id, current_notes, notes_html_to_show)
                        print(f"DEBUG: Updated annotation display for {annotation_id} (notes_html only, preserved notes)")
                else:
                    print(f"DEBUG: No UI updates needed for {annotation_id} (all values were SKIP)")
                    
                # Send comprehensive DOM update using annotation_updated signal
                if hasattr(self.web_view, 'annotation_updated'):
                    import json
                    
                    # Use current annotation values, only overriding with AI data if not SKIP
                    final_notes = annotation.get('notes', '') if note_data['brief_notes'] == "SKIP" else note_data['brief_notes']
                    final_notes_html = annotation.get('notes_html', '') if note_data['detailed_notes'] == "SKIP" else note_data['detailed_notes']
                    
                    update_payload = {
                        'id': annotation_id,
                        'text': annotation.get('text', ''),
                        'used': annotation.get('used', False),
                        'favorite': annotation.get('favorite', False),
                        'notes': final_notes,
                        'notes_html': final_notes_html,
                        'tags': annotation.get('tags', []),
                        'secondary_scenes': annotation.get('secondary_scenes', [])
                    }
                    print(f"DEBUG: Sending comprehensive DOM update:")
                    print(f"DEBUG: final_notes='{final_notes}' (AI: '{note_data['brief_notes']}')")
                    print(f"DEBUG: final_notes_html='{final_notes_html[:50]}...' (AI: '{note_data['detailed_notes'][:50]}...')")
                    print(f"DEBUG: SKIP protection - notes: {'PROTECTED' if note_data['brief_notes'] == 'SKIP' else 'UPDATED'}")
                    print(f"DEBUG: SKIP protection - notes_html: {'PROTECTED' if note_data['detailed_notes'] == 'SKIP' else 'UPDATED'}")
                    
                    self.web_view.annotation_updated.emit(json.dumps(update_payload))
                    print(f"DEBUG: Emitted annotation_updated signal with SKIP-protected payload")
                else:
                    print(f"DEBUG: annotation_updated signal not available")
                
                successful_count += 1
                print(f"Successfully updated notes for annotation {annotation_id}")
                
            except Exception as e:
                print(f"Failed to update annotation {note_data.get('annotation_id', 'unknown')}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Final theme view refresh to ensure all changes are visible
        if successful_count > 0:
            try:
                print(f"DEBUG: Final theme view refresh after updating {successful_count} annotations with notes")
                
                # Do a targeted refresh rather than full rebuild
                if hasattr(self.main_window, 'update_theme_view'):
                    print("DEBUG: Calling update_theme_view with show_progress=False")
                    self.main_window.update_theme_view(show_progress=False)
                    print("DEBUG: Theme view update completed")
                else:
                    print("DEBUG: main_window does not have update_theme_view method")
                
                # Mark changes as pending since we've modified annotations
                if hasattr(self.main_window, 'mark_changes_pending'):
                    self.main_window.mark_changes_pending()
                    print(f"DEBUG: Marked changes as pending after AI notes generation")
                else:
                    print("DEBUG: main_window does not have mark_changes_pending method")
                        
            except Exception as e:
                print(f"DEBUG: Error in final theme view update: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Show results with detailed feedback
        if successful_count > 0:
            success_msg = f"Successfully generated notes for {successful_count} annotations! 📝\n\nThe notes are now visible in your Theme View and annotation tooltips."
            
            if successful_count < len(self.parsed_notes):
                failed_count = len(self.parsed_notes) - successful_count
                success_msg += f"\n\nNote: {failed_count} annotations had update errors (check console for details)."
            
            # Also show success in response area
            self.response_display.clear()
            self.response_display.setPlainText(f"✅ Success!\n\n{success_msg}")
            
            QMessageBox.information(self, "Success!", success_msg)
        else:
            # All failed
            error_msg = f"Failed to update any annotations with notes.\n\nGenerated {len(self.parsed_notes)} notes but could not apply them.\n\nCheck the console output for detailed error information."
            
            self.response_display.clear()
            self.response_display.setPlainText(f"❌ Update Failed\n\n{error_msg}")
            
            QMessageBox.critical(self, "Update Failed", error_msg)
        
        # Close dialog
        if successful_count > 0:
            self.accept()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        super().closeEvent(event)
            
    def update_annotation_notes_in_theme_view(self, annotation_id, brief_notes, detailed_notes):
        """Update notes display for a specific annotation in theme view"""
        if not hasattr(self.main_window, 'scene_tabs') or not self.main_window.scene_tabs:
            print(f"DEBUG: No scene_tabs found, cannot update annotation {annotation_id}")
            return
            
        updated = False
        for i in range(self.main_window.scene_tabs.count()):
            list_widget = self.main_window.scene_tabs.widget(i)
            if hasattr(list_widget, 'count'):
                # Find the specific annotation item and update its notes display
                for j in range(list_widget.count()):
                    item = list_widget.item(j)
                    if item and item.data(Qt.ItemDataRole.UserRole) == annotation_id:
                        item_widget = list_widget.itemWidget(item)
                        if item_widget:
                            # Update notes field (brief notes in the QLabel)
                            from PyQt6.QtWidgets import QLabel
                            notes_edit = item_widget.findChild(QLabel, "notes_edit")
                            if notes_edit and hasattr(notes_edit, 'property'):
                                # Use the set_notes_text method that was defined in add_item_with_checkbox
                                notes_edit.setProperty('notes_text', brief_notes)
                                
                                # Convert markdown to plain text for display (same logic as add_item_with_checkbox)
                                def markdown_to_display_text(text):
                                    if not text:
                                        return "Double-click to add footnote..."
                                    import re
                                    display_text = text
                                    display_text = re.sub(r'\*\*(.*?)\*\*', r'\1', display_text)
                                    display_text = re.sub(r'\*(.*?)\*', r'\1', display_text)
                                    display_text = re.sub(r'`(.*?)`', r'\1', display_text)
                                    return display_text
                                
                                display_text = markdown_to_display_text(brief_notes)
                                notes_edit.setText(display_text)
                                
                                # Update styling based on content
                                if not brief_notes:
                                    notes_edit.setStyleSheet("""
                                        QLabel {
                                            border: 1px solid #e0e0e0;
                                            background-color: white;
                                            padding: 6px;
                                            border-radius: 4px;
                                            color: #aaa;
                                            font-style: italic;
                                        }
                                        QLabel:hover {
                                            border: 1px solid #ccc;
                                            background-color: #f9f9f9;
                                        }
                                    """)
                                else:
                                    notes_edit.setStyleSheet("""
                                        QLabel {
                                            border: 1px solid #e0e0e0;
                                            background-color: white;
                                            padding: 6px;
                                            border-radius: 4px;
                                        }
                                        QLabel:hover {
                                            border: 1px solid #ccc;
                                            background-color: #f9f9f9;
                                        }
                                    """)
                                
                                print(f"DEBUG: Updated notes QLabel to: '{brief_notes}'")
                            
                            # Update widget properties for notes_html
                            item_widget.setProperty('notes_html', detailed_notes)
                            item_widget.setProperty('notes', brief_notes)
                            print(f"DEBUG: Updated widget properties for {annotation_id}")
                            
                            # Update the book icon to active state since we now have notes_html
                            from PyQt6.QtWidgets import QPushButton
                            edit_notes_btn = item_widget.findChild(QPushButton, "editNotesButton")
                            if edit_notes_btn and hasattr(list_widget, '_cached_icons'):
                                # Use the same logic as add_item_with_checkbox to determine icon state
                                def is_notes_empty(notes_html_str):
                                    if not notes_html_str:
                                        return True
                                    from PyQt6.QtGui import QTextDocument
                                    doc = QTextDocument()
                                    doc.setHtml(notes_html_str)
                                    return doc.toPlainText().strip() == ""
                                
                                # Check if we have notes_html content
                                if detailed_notes and not is_notes_empty(detailed_notes):
                                    edit_notes_btn.setIcon(list_widget._cached_icons['notes']['active'])
                                    print(f"DEBUG: Set book icon to ACTIVE state for {annotation_id}")
                                else:
                                    edit_notes_btn.setIcon(list_widget._cached_icons['notes']['normal'])
                                    print(f"DEBUG: Set book icon to normal state for {annotation_id}")
                            else:
                                print(f"DEBUG: Could not find edit notes button or cached icons for {annotation_id}")
                            
                            updated = True
                            print(f"DEBUG: Successfully updated annotation {annotation_id} display in tab {i}")
                            break
        
        if not updated:
            print(f"DEBUG: Could not find annotation {annotation_id} in any theme view tab")
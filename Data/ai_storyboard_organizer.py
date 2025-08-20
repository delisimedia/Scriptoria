"""
AI Storyboard Organizer Module
Provides AI-powered organization of annotations into a logical storyboard structure.
"""

import os
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QProgressBar, QMessageBox, QSplitter, QListWidgetItem, QWidget,
    QCheckBox, QSpinBox, QGroupBox, QFormLayout, QComboBox, QTabWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("Warning: google.generativeai not available. AI features will be disabled.")


class AIWorkerThread(QThread):
    """Worker thread for AI processing to avoid blocking UI"""
    response_received = pyqtSignal(str)
    response_chunk = pyqtSignal(str)  # For streaming chunks
    error_occurred = pyqtSignal(str)
    
    def __init__(self, model, prompt, stream=False):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.stream = stream
    
    def run(self):
        try:
            print(f"[AI WORKER] Starting AI request with model: {self.model._model_name if hasattr(self.model, '_model_name') else 'unknown'}")
            print(f"[AI WORKER] Streaming enabled: {self.stream}")
            print(f"[AI WORKER] Prompt length: {len(self.prompt)} characters")
            
            # Debug: Show first 500 and last 500 characters of prompt to identify potential issues
            if len(self.prompt) > 1000:
                print(f"[AI WORKER] Prompt preview (first 500 chars): {self.prompt[:500]}...")
                print(f"[AI WORKER] Prompt preview (last 500 chars): ...{self.prompt[-500:]}")
            else:
                print(f"[AI WORKER] Full prompt: {self.prompt}")
            
            # Check for potential problematic content in prompt
            problematic_indicators = [
                "personal information", "private", "confidential", "password", "secret",
                "hack", "illegal", "violence", "harm", "dangerous", "explicit"
            ]
            found_indicators = [indicator for indicator in problematic_indicators if indicator.lower() in self.prompt.lower()]
            if found_indicators:
                print(f"[AI WORKER] WARNING: Potentially problematic content indicators found: {found_indicators}")
            else:
                print(f"[AI WORKER] No obvious problematic content indicators detected")
            
            if self.stream:
                # Streaming response
                print(f"[AI WORKER] Sending streaming request...")
                response = self.model.generate_content(self.prompt, stream=True)
                print(f"[AI WORKER] Stream response object created: {type(response)}")
                
                full_response = ""
                chunk_count = 0
                try:
                    blocked_reasons = []
                    safety_issues = []
                    
                    try:
                        for chunk in response:
                            # Check for text content first
                            try:
                                if hasattr(chunk, 'text') and chunk.text:
                                    print(f"[AI WORKER] Received chunk {chunk_count + 1}: {len(chunk.text)} chars")
                                    full_response += chunk.text
                                    self.response_chunk.emit(chunk.text)
                                    chunk_count += 1
                                    continue
                            except Exception as text_error:
                                print(f"[AI WORKER] Error accessing chunk.text: {text_error}")
                            
                            # If no text, check candidates for finish_reason and safety info
                            if hasattr(chunk, 'candidates') and chunk.candidates:
                                for candidate in chunk.candidates:
                                    if hasattr(candidate, 'finish_reason'):
                                        finish_reason = candidate.finish_reason
                                        print(f"[AI WORKER] Chunk finish_reason: {finish_reason}")
                                        
                                        # Map finish reasons to user-friendly messages
                                        if finish_reason == 1:  # STOP
                                            blocked_reasons.append("Content generation was stopped (finish_reason: STOP)")
                                        elif finish_reason == 2:  # MAX_TOKENS
                                            blocked_reasons.append("Maximum token limit reached")
                                        elif finish_reason == 3:  # SAFETY
                                            blocked_reasons.append("Content blocked by safety filters")
                                        elif finish_reason == 4:  # RECITATION
                                            blocked_reasons.append("Content blocked due to recitation concerns")
                                        elif finish_reason == 5:  # OTHER
                                            blocked_reasons.append("Content blocked for other reasons")
                                    
                                    if hasattr(candidate, 'safety_ratings'):
                                        safety_ratings = candidate.safety_ratings
                                        print(f"[AI WORKER] Safety ratings: {safety_ratings}")
                                        for rating in safety_ratings:
                                            if hasattr(rating, 'category') and hasattr(rating, 'probability'):
                                                if rating.probability in [3, 4]:  # MEDIUM or HIGH probability
                                                    safety_issues.append(f"{rating.category.name}: {rating.probability}")
                    
                    except StopIteration:
                        print(f"[AI WORKER] Stream ended (StopIteration) - this is normal behavior")
                        # StopIteration is normal when the stream ends, not an error
                        pass
                    except Exception as iteration_error:
                        print(f"[AI WORKER] Error during stream iteration: {iteration_error}")
                        # Only treat non-StopIteration exceptions as errors
                        error_msg = f"Streaming error: {iteration_error}"
                        if blocked_reasons:
                            error_msg += f"\n\nBlocked reasons: {'; '.join(blocked_reasons)}"
                        if safety_issues:
                            error_msg += f"\n\nSafety concerns: {'; '.join(safety_issues)}"
                        
                        self.error_occurred.emit(error_msg)
                        return
                
                except Exception as stream_e:
                    print(f"[AI WORKER] Outer streaming error: {stream_e}")
                    
                    # Create a more helpful error message
                    error_msg = f"Streaming setup error: {stream_e}"
                    if blocked_reasons:
                        error_msg += f"\n\nBlocked reasons: {'; '.join(blocked_reasons)}"
                    if safety_issues:
                        error_msg += f"\n\nSafety concerns: {'; '.join(safety_issues)}"
                    
                    self.error_occurred.emit(error_msg)
                    return
                
                print(f"[AI WORKER] Streaming complete. Total chunks: {chunk_count}, Total length: {len(full_response)}")
                print(f"[AI WORKER] Blocked reasons found: {blocked_reasons}")
                print(f"[AI WORKER] Safety issues found: {safety_issues}")
                
                if chunk_count == 0:
                    # No content was generated - provide detailed feedback
                    error_msg = "No response received from AI - the response was empty or blocked"
                    if blocked_reasons:
                        error_msg += f"\n\nBlocked reasons: {'; '.join(blocked_reasons)}"
                    if safety_issues:
                        error_msg += f"\n\nSafety concerns: {'; '.join(safety_issues)}"
                    
                    if blocked_reasons or safety_issues:
                        error_msg += "\n\nSuggestions:\n• Try rephrasing your request\n• Check if your content violates AI safety guidelines\n• Consider using a different approach or topic\n• Try using gemini-2.5-flash instead of gemini-2.5-pro\n• Reduce the thinking budget or simplify your prompt"
                    else:
                        error_msg += "\n\nSuggestions:\n• Check your API key and credits\n• Verify network connectivity\n• Try with a simpler request\n• Try using gemini-2.5-flash instead of gemini-2.5-pro\n• Reduce the transcript context or thinking budget"
                    
                    print(f"[AI WORKER] Emitting detailed error: {error_msg}")
                    self.error_occurred.emit(error_msg)
                else:
                    self.response_received.emit(full_response)
            else:
                # Single response
                print(f"[AI WORKER] Sending single request...")
                response = self.model.generate_content(self.prompt)
                print(f"[AI WORKER] Single response received: {type(response)}")
                
                try:
                    if hasattr(response, 'text') and response.text:
                        print(f"[AI WORKER] Response text length: {len(response.text)}")
                        self.response_received.emit(response.text)
                    else:
                        # Check for detailed response info
                        blocked_reasons = []
                        safety_issues = []
                        
                        if hasattr(response, 'candidates'):
                            for i, candidate in enumerate(response.candidates):
                                if hasattr(candidate, 'finish_reason'):
                                    finish_reason = candidate.finish_reason
                                    print(f"[AI WORKER] Candidate {i} finish_reason: {finish_reason}")
                                    
                                    # Map finish reasons to user-friendly messages
                                    if finish_reason == 1:  # STOP
                                        blocked_reasons.append("Content generation was stopped (finish_reason: STOP)")
                                    elif finish_reason == 2:  # MAX_TOKENS
                                        blocked_reasons.append("Maximum token limit reached")
                                    elif finish_reason == 3:  # SAFETY
                                        blocked_reasons.append("Content blocked by safety filters")
                                    elif finish_reason == 4:  # RECITATION
                                        blocked_reasons.append("Content blocked due to recitation concerns")
                                    elif finish_reason == 5:  # OTHER
                                        blocked_reasons.append("Content blocked for other reasons")
                                
                                if hasattr(candidate, 'safety_ratings'):
                                    safety_ratings = candidate.safety_ratings
                                    print(f"[AI WORKER] Safety ratings: {safety_ratings}")
                                    for rating in safety_ratings:
                                        if hasattr(rating, 'category') and hasattr(rating, 'probability'):
                                            if rating.probability in [3, 4]:  # MEDIUM or HIGH probability
                                                safety_issues.append(f"{rating.category.name}: {rating.probability}")
                        
                        # Create user-friendly error message
                        error_msg = "AI response was empty or blocked"
                        if blocked_reasons:
                            error_msg += f"\n\nBlocked reasons: {'; '.join(blocked_reasons)}"
                        if safety_issues:
                            error_msg += f"\n\nSafety concerns: {'; '.join(safety_issues)}"
                        
                        if blocked_reasons or safety_issues:
                            error_msg += "\n\nSuggestions:\n• Try rephrasing your request\n• Check if your content violates AI safety guidelines\n• Consider using a different approach or topic"
                        else:
                            error_msg += "\n\nSuggestions:\n• Check your API key and credits\n• Verify network connectivity\n• Try with a simpler request"
                        
                        print(f"[AI WORKER] {error_msg}")
                        self.error_occurred.emit(error_msg)
                        
                except Exception as response_error:
                    print(f"[AI WORKER] Error processing response: {response_error}")
                    self.error_occurred.emit(f"Error processing AI response: {response_error}")
                    
        except Exception as e:
            error_msg = str(e)
            print(f"[AI WORKER] Exception occurred: {error_msg}")
            print(f"[AI WORKER] Exception type: {type(e)}")
            
            # Handle empty error messages
            if not error_msg or error_msg.strip() == "":
                error_msg = f"Unknown error occurred (Exception type: {type(e).__name__})"
                print(f"[AI WORKER] Empty error message detected, using fallback: {error_msg}")
            
            # Add more context to common errors
            if "API_KEY" in error_msg.upper():
                error_msg = f"API Key Error: {error_msg}\nPlease check your API key in Data/api_key.txt"
            elif "PERMISSION" in error_msg.upper():
                error_msg = f"Permission Error: {error_msg}\nYour API key may not have access to this model"
            elif "QUOTA" in error_msg.upper() or "LIMIT" in error_msg.upper():
                error_msg = f"Quota/Rate Limit: {error_msg}\nYou may have exceeded your API limits"
            elif "NETWORK" in error_msg.upper() or "CONNECTION" in error_msg.upper():
                error_msg = f"Network Error: {error_msg}\nPlease check your internet connection"
            elif "SAFETY" in error_msg.upper():
                error_msg = f"Safety Filter: {error_msg}\nContent may have been blocked by AI safety systems"
            elif "MODEL" in error_msg.upper() and "NOT_FOUND" in error_msg.upper():
                error_msg = f"Model Not Found: {error_msg}\nThe AI model may not be available or accessible"
            elif "INVALID OPERATION" in error_msg.upper() or "RESPONSE.TEXT" in error_msg.upper():
                error_msg = f"Content Blocked: {error_msg}\nThe AI response was blocked by safety filters or other restrictions"
            elif "STOPITERATION" in error_msg.upper() or type(e).__name__ == "StopIteration":
                error_msg = f"Stream Ended Unexpectedly: The AI response stream ended without providing content\nThis may indicate content was blocked or the request was too complex"
            
            import traceback
            traceback.print_exc()
            
            # Ensure we never emit an empty error message
            if not error_msg or error_msg.strip() == "":
                error_msg = "An unknown error occurred during AI processing. Check the console for details."
            
            print(f"[AI WORKER] Final error message being emitted: '{error_msg}'")
            self.error_occurred.emit(error_msg)


class AIStoryboardOrganizer(QDialog):
    """
    Dialog for AI-powered storyboard organization with debug display.
    Shows AI response before applying changes.
    """
    
    def __init__(self, parent, web_view, main_window):
        super().__init__(parent)
        self.web_view = web_view
        self.main_window = main_window
        self.annotations = web_view.annotations if web_view else []
        self.parsed_updates = []
        self.ai_model = None
        self.worker_thread = None
        self.conversation_history = []
        self.last_response = ""
        
        self.setWindowTitle("AI Storyboard Organizer")
        self.setModal(True)
        self.resize(1200, 1000)
        
        self.setup_ui()
        self.load_api_key()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title and description
        title_label = QLabel("<h2>AI Generate Script</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Add informational note
        info_note = QLabel("📌 <b>Note:</b> You will need to highlight and create annotations first before generating a script. AI will only use user created annotations.")
        info_note.setWordWrap(True)
        info_note.setStyleSheet("""
            QLabel {
                background-color: #f0f9ff;
                border: 1px solid #bae6fd;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 5px 0px 10px 0px;
                color: #0c4a6e;
                font-size: 11px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(info_note)
        
        # Create main content splitter (left/right)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # LEFT SIDE: Video Goals and Context
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        goals_group = QGroupBox("Video Goals & Context")
        goals_layout = QVBoxLayout(goals_group)
        
        goals_desc = QLabel("Describe your video objectives and target audience to help the AI create better narrative flow:")
        goals_desc.setWordWrap(True)
        goals_desc.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 8px;")
        goals_layout.addWidget(goals_desc)
        
        self.user_notes = QTextEdit()
        self.user_notes.setPlaceholderText("What is the background, target audience, and goal of this video?")
        goals_layout.addWidget(self.user_notes)
        
        # Context settings
        context_layout = QHBoxLayout()
        self.full_transcript_checkbox = QCheckBox("Include full transcript (will use more tokens)")
        self.full_transcript_checkbox.setChecked(True)
        self.full_transcript_checkbox.setToolTip("Sends complete transcript for better context. Uncheck to use only annotation content without any transcript text.")
        context_layout.addWidget(self.full_transcript_checkbox)
        context_layout.addStretch()
        goals_layout.addLayout(context_layout)
        
        left_layout.addWidget(goals_group)
        main_splitter.addWidget(left_widget)
        
        # RIGHT SIDE: AI Configuration
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        ai_group = QGroupBox("AI Configuration")
        ai_layout = QFormLayout(ai_group)
        
        # Model selection
        self.model_selector = QComboBox()
        self.model_selector.addItems([
            "gemini-2.5-pro",
            # "gemini-2.5-flash"  # Commented out due to streaming and safety filter issues
        ])
        self.model_selector.setCurrentText("gemini-2.5-pro")
        self.model_selector.setToolTip("Pro: More reliable, better quality | Flash temporarily disabled due to content blocking issues")
        ai_layout.addRow("Model:", self.model_selector)
        
        # Thinking budget
        self.thinking_budget = QSpinBox()
        self.thinking_budget.setMinimum(1000)
        self.thinking_budget.setMaximum(20000)
        self.thinking_budget.setValue(5000)
        self.thinking_budget.setSuffix(" tokens")
        self.thinking_budget.setToolTip("Higher values allow more complex reasoning but take longer")
        ai_layout.addRow("Thinking Budget:", self.thinking_budget)
        
        # Structure options
        structure_group = QGroupBox("Narrative Structure")
        structure_layout = QVBoxLayout(structure_group)
        
        self.dividers_checkbox = QCheckBox("Add section dividers")
        self.dividers_checkbox.setChecked(True)
        self.dividers_checkbox.setToolTip("Allow AI to create colored section breaks")
        structure_layout.addWidget(self.dividers_checkbox)
        
        self.headers_checkbox = QCheckBox("Add production headers")
        self.headers_checkbox.setChecked(False)
        self.headers_checkbox.setToolTip("Allow AI to add editing notes like music cues, pauses, tone changes")
        structure_layout.addWidget(self.headers_checkbox)
        
        # Script length limit
        length_layout = QHBoxLayout()
        self.length_limit_checkbox = QCheckBox("Target script length:")
        self.length_limit_checkbox.setChecked(False)
        self.length_limit_checkbox.setToolTip("AI will aim for a specific script duration")
        length_layout.addWidget(self.length_limit_checkbox)
        
        self.length_minutes = QSpinBox()
        self.length_minutes.setMinimum(1)
        self.length_minutes.setMaximum(120)
        self.length_minutes.setValue(3)
        self.length_minutes.setSuffix("m")
        self.length_minutes.setToolTip("Target duration in minutes (average speaking pace)")
        length_layout.addWidget(self.length_minutes)
        
        self.length_seconds = QSpinBox()
        self.length_seconds.setMinimum(0)
        self.length_seconds.setMaximum(59)
        self.length_seconds.setValue(0)
        self.length_seconds.setSuffix("s")
        self.length_seconds.setToolTip("Additional seconds")
        length_layout.addWidget(self.length_seconds)
        
        length_layout.addStretch()
        structure_layout.addLayout(length_layout)
        
        structure_desc = QLabel("Dividers create clear sections. Headers add production notes for editing guidance.")
        structure_desc.setWordWrap(True)
        structure_desc.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        structure_layout.addWidget(structure_desc)
        
        right_layout.addWidget(ai_group)
        right_layout.addWidget(structure_group)
        main_splitter.addWidget(right_widget)
        
        # Set splitter proportions (60% left, 40% right)
        main_splitter.setSizes([600, 400])
        layout.addWidget(main_splitter)
        
        # Enable streaming by default (no UI control)
        self.streaming_checkbox = QCheckBox()
        self.streaming_checkbox.setChecked(True)
        self.streaming_checkbox.setVisible(False)  # Hidden but still functional
        
        # Process button
        self.process_btn = QPushButton("Process with AI")
        self.process_btn.setStyleSheet("""
            QPushButton {
                background-color: #9333EA;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7E22CE;
            }
            QPushButton:disabled {
                background-color: #D1D5DB;
            }
        """)
        self.process_btn.clicked.connect(self.process_with_ai)
        layout.addWidget(self.process_btn)
        
        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Results area with tabs
        self.results_tabs = QTabWidget()
        
        # AI Response Tab (primary - shown first)
        ai_response_tab = QWidget()
        ai_response_layout = QVBoxLayout(ai_response_tab)
        
        self.debug_display = QTextEdit()
        self.debug_display.setReadOnly(True)
        self.debug_display.setPlaceholderText("Raw AI response and reasoning will appear here...")
        self.debug_display.setStyleSheet("""
            QTextEdit {
                font-family: 'JetBrains Mono', 'Courier New', monospace;
                font-size: 11px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                padding: 10px;
                line-height: 1.3;
            }
        """)
        ai_response_layout.addWidget(self.debug_display)
        self.results_tabs.addTab(ai_response_tab, "🤖 AI Response")
        
        # Organization Tab (secondary - switched to after AI completes)
        parsed_tab = QWidget()
        parsed_layout = QVBoxLayout(parsed_tab)
        
        self.parsed_display = QTextEdit()
        self.parsed_display.setReadOnly(True)
        self.parsed_display.setPlaceholderText("AI-organized script structure will appear here...")
        self.parsed_display.setStyleSheet("""
            QTextEdit {
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                background-color: #f8fffe;
                border: 1px solid #ddd;
                padding: 10px;
                line-height: 1.4;
            }
        """)
        parsed_layout.addWidget(self.parsed_display)
        self.results_tabs.addTab(parsed_tab, "📋 Organization")
        
        layout.addWidget(self.results_tabs, 2)  # Give tabs more stretch factor for more height
        
        # Followup question area (initially hidden)
        self.followup_widget = QGroupBox("💬 Refine Script")
        self.followup_widget.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #fafafa;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                background-color: #fafafa;
            }
        """)
        followup_layout = QVBoxLayout(self.followup_widget)
        
        followup_desc = QLabel("Ask the AI to adjust the organization based on your feedback:")
        followup_desc.setStyleSheet("color: #666; font-size: 11px; font-weight: normal; margin-bottom: 8px;")
        followup_layout.addWidget(followup_desc)
        
        followup_input_layout = QHBoxLayout()
        self.followup_input = QTextEdit()
        self.followup_input.setMaximumHeight(50)
        self.followup_input.setPlaceholderText("e.g., 'Move emotional moments earlier', 'Add more dividers', 'Focus on training experience'...")
        self.followup_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
            }
        """)
        followup_input_layout.addWidget(self.followup_input)
        
        self.ask_followup_btn = QPushButton("Refine")
        self.ask_followup_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7C3AED;
            }
            QPushButton:pressed {
                background-color: #6D28D9;
            }
        """)
        self.ask_followup_btn.clicked.connect(self.ask_followup_question)
        followup_input_layout.addWidget(self.ask_followup_btn)
        
        followup_layout.addLayout(followup_input_layout)
        
        self.followup_widget.setVisible(False)
        layout.addWidget(self.followup_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.create_script_btn = QPushButton("✨ Apply Script")
        self.create_script_btn.setEnabled(False)
        self.create_script_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover:enabled {
                background-color: #059669;
            }
            QPushButton:disabled {
                background-color: #D1D5DB;
                color: #9CA3AF;
            }
        """)
        self.create_script_btn.clicked.connect(self.create_and_apply_script)
        button_layout.addWidget(self.create_script_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                font-weight: bold;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_api_key(self):
        """Load API key using the same method as other AI functions"""
        try:
            api_key_path = self._get_api_key_path()
            
            if os.path.exists(api_key_path):
                with open(api_key_path, 'r', encoding='utf-8') as f:
                    api_key = f.read().strip()
                    if api_key and genai:
                        genai.configure(api_key=api_key)
                        # Store API key for dynamic model reconfiguration
                        self.api_key = api_key
                        self.ai_model = None  # Will be created dynamically
                        self.status_label.setText("API key loaded successfully")
                    else:
                        self.status_label.setText("No API key found")
                        self.process_btn.setEnabled(False)
            else:
                self.status_label.setText("API key file not found")
                self.process_btn.setEnabled(False)
        except Exception as e:
            self.status_label.setText(f"Error loading API key: {str(e)}")
            self.process_btn.setEnabled(False)
    
    def _get_api_key_path(self):
        """Gets the full path for the API key file in the 'data' subfolder."""
        import sys
        try:
            # Get base path correctly for frozen (PyInstaller) or script execution
            if getattr(sys, 'frozen', False):
                # If the application is run as a bundle/frozen executable
                base_path = os.path.dirname(sys.executable)
            else:
                # If the application is run as a script
                base_path = os.path.dirname(os.path.abspath(__file__))
                # Go up one directory since this file is in Data/ subfolder
                base_path = os.path.dirname(base_path)

            data_folder = os.path.join(base_path, "data")
            # Create data folder if it doesn't exist (important for first run)
            os.makedirs(data_folder, exist_ok=True)
            return os.path.join(data_folder, "api_key.txt")
        except Exception as e:
            print(f"Error determining API key path: {e}")
            # Fallback to current working directory if path fails (less ideal)
            return os.path.join(os.getcwd(), "api_key.txt")
    
    def get_full_transcript(self):
        """Extract full transcript text from session data"""
        try:
            if hasattr(self.main_window, 'current_session_file') and self.main_window.current_session_file:
                with open(self.main_window.current_session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    return session_data.get('input', {}).get('text', '')
        except Exception as e:
            print(f"Error getting transcript: {e}")
        return ""
    
    def calculate_annotation_word_count(self, annotations_list):
        """Calculate total word count for a list of annotations, excluding headers and strikethrough"""
        import re
        total_words = 0
        
        for anno in annotations_list:
            # Skip dividers
            if anno.get('divider'):
                continue
                
            # Get text from storyboard if available, otherwise use original text
            if 'storyboard' in anno and 'text' in anno['storyboard']:
                html_text = anno['storyboard']['text']
            else:
                html_text = anno.get('text', '').replace('\n', '<br>')
            
            # Extract and remove header text (same patterns as WordCountTimer)
            header_patterns = [
                r'<div><b[^>]*>(.*?)</b></div>',                 # <div><b>Header</b></div>
                r'<p[^>]*><b[^>]*>(.*?)</b></p>',                # <p><b>Header</b></p>
                r'<b[^>]*>(.*?)</b>',                            # <b>Header</b>
                r'<span[^>]*style=[\'"][^"\']*font-weight:700[^"\']*[\'"]>(.*?)</span>',  # styled span with font-weight:700
                r'<h[1-6][^>]*>(.*?)</h[1-6]>'                   # <h1>-<h6> tags
            ]
            
            # Remove headers from text
            html_without_headers = html_text
            for pattern in header_patterns:
                html_without_headers = re.sub(pattern, '', html_without_headers)
            
            # Get all words by removing HTML tags
            plain_text = re.sub(r'<[^>]+>', '', html_without_headers)
            all_words = len(re.findall(r'\b\w+\b', plain_text))
            
            # Get strikethrough words to subtract
            strikethrough_words = 0
            strikethrough_segments = re.findall(r'<s style="color:#FF9999;">(.*?)</s>', html_without_headers)
            for segment in strikethrough_segments:
                clean_segment = re.sub(r'<[^>]+>', '', segment)
                words_in_segment = len(re.findall(r'\b\w+\b', clean_segment))
                strikethrough_words += words_in_segment
            
            # Calculate net words (excluding headers and strikethrough)
            words_in_annotation = all_words - strikethrough_words
            total_words += words_in_annotation
        
        return total_words
    
    def calculate_duration_from_words(self, word_count):
        """Calculate average speech duration from word count (uses 200 WPM like WordCountTimer)"""
        return (word_count / 200) * 60  # seconds
    
    def format_duration(self, seconds):
        """Format seconds into m:ss format"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m:{secs:02d}s"
    
    def format_annotations_for_ai(self):
        """Format annotations with IDs, text, notes, tags, favorites, and themes for AI (excluding dividers)"""
        formatted = []
        divider_count = 0
        
        for anno in self.annotations:
            # Skip dividers - they shouldn't be sent to AI
            if anno.get('divider'):
                divider_count += 1
                continue
                
            if anno.get('text'):
                # Get annotation text (truncate if too long)
                text = anno['text']
                if len(text) > 200:
                    text = text[:200] + "..."
                
                # Start with basic annotation entry
                entry = f"{anno['id']}: \"{text}\""
                
                # Add metadata in structured format
                metadata = []
                
                # Add notes if present
                notes = anno.get('notes', '').strip()
                if notes:
                    metadata.append(f"note: {notes}")
                
                # Add favorite status
                is_favorite = anno.get('favorite', False)
                metadata.append(f"favorite: {str(is_favorite).lower()}")
                
                # Add tags if present
                tags = anno.get('tags', [])
                if tags and isinstance(tags, list) and len(tags) > 0:
                    tags_str = ", ".join(tags)
                    metadata.append(f"tags: {tags_str}")
                
                # Add theme information (scene and secondary-scene)
                scene = anno.get('scene', '').strip()
                if scene:
                    metadata.append(f"theme: {scene}")
                
                secondary_scene = anno.get('secondary-scene', '').strip()
                if secondary_scene:
                    metadata.append(f"secondary-theme: {secondary_scene}")
                
                # Combine metadata
                if metadata:
                    entry += f" [{'; '.join(metadata)}]"
                
                formatted.append(entry)
                formatted.append("")  # Empty line for readability
        
        print(f"🚧🚧🚧 [AI STORYBOARD] Filtered out {divider_count} dividers from AI context 🚧🚧🚧")
        return "\n".join(formatted)
    
    def create_ai_model(self):
        """Create AI model with current settings"""
        if not hasattr(self, 'api_key') or not self.api_key:
            print("[AI MODEL] No API key available")
            return None
            
        selected_model = self.model_selector.currentText()
        thinking_budget = self.thinking_budget.value()
        
        print(f"[AI MODEL] Creating model: {selected_model}")
        print(f"[AI MODEL] Thinking budget: {thinking_budget}")
        
        # Adjust max output tokens based on model
        if selected_model == "gemini-2.5-pro":
            max_tokens = 8000
        else:  # gemini-2.5-flash
            max_tokens = 4000
        
        print(f"[AI MODEL] Max output tokens: {max_tokens}")
        
        try:
            generation_config = {
                "temperature": 0.3,
                "top_p": 0.8,
                "max_output_tokens": max_tokens
            }
            print(f"[AI MODEL] Generation config: {generation_config}")
            
            model = genai.GenerativeModel(
                model_name=selected_model,
                generation_config=generation_config
            )
            print(f"[AI MODEL] Model created successfully: {type(model)}")
            return model
        except Exception as e:
            print(f"[AI MODEL] Error creating model: {e}")
            print(f"[AI MODEL] Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_with_ai(self):
        """Send the request to AI for processing"""
        try:
            self.status_label.setText("Ensuring storyboard is open...")
            self.status_label.setStyleSheet("color: #0066cc;")
            
            # Ensure storyboard is open before processing (only toggle if closed)
            storyboard_is_open = (hasattr(self.main_window, 'storyboard_dialog') and 
                                self.main_window.storyboard_dialog is not None and
                                (self.main_window.storyboard_dialog.isVisible() or 
                                 hasattr(self.main_window.storyboard_dialog, 'is_collapsed') and 
                                 self.main_window.storyboard_dialog.is_collapsed()))
            
            if not storyboard_is_open:
                print("[AI STORYBOARD] Storyboard not open, opening it silently before processing...")
                if hasattr(self.main_window, 'toggle_storyboard_panel'):
                    # Open the storyboard
                    self.main_window.toggle_storyboard_panel()
                    
                    # Immediately hide it so it doesn't flash on screen
                    if (hasattr(self.main_window, 'storyboard_dialog') and 
                        self.main_window.storyboard_dialog is not None):
                        print("[AI STORYBOARD] Hiding storyboard to prevent screen flash...")
                        # Mark as manually hidden and hide it
                        self.main_window.storyboard_dialog.is_manually_hidden = True
                        self.main_window.storyboard_dialog.is_manually_minimized = False
                        
                        if hasattr(self.main_window.storyboard_dialog, 'hide_completely'):
                            self.main_window.storyboard_dialog.hide_completely()
                        else:
                            self.main_window.storyboard_dialog.hide()
                        
                        # Update the button state to show it's closed
                        if hasattr(self.main_window, 'storyboard_button'):
                            self.main_window.storyboard_button.setChecked(False)
                        
                        print("[AI STORYBOARD] Storyboard opened and hidden successfully")
                    else:
                        print("[AI STORYBOARD] Warning: Could not hide storyboard after opening")
                else:
                    error_msg = "Could not open storyboard dialog. Please open it manually first."
                    self.status_label.setText(f"❌ {error_msg}")
                    self.status_label.setStyleSheet("color: #EF4444;")
                    QMessageBox.warning(self, "Storyboard Required", error_msg)
                    return
            else:
                print("[AI STORYBOARD] Storyboard already open")
            
            self.status_label.setText("Initializing AI...")
            
            # Create AI model with current settings
            self.ai_model = self.create_ai_model()
            if not self.ai_model:
                error_msg = "AI model not configured. Please check your API key file."
                self.status_label.setText(f"❌ {error_msg}")
                self.status_label.setStyleSheet("color: #EF4444;")
                QMessageBox.warning(self, "Configuration Error", error_msg)
                return
            
            self.status_label.setText("Loading transcript...")
            
            # Get full transcript
            full_text = self.get_full_transcript()
            if not full_text:
                error_msg = "No transcript text found in current session. Please load a transcript file first."
                self.status_label.setText(f"❌ {error_msg}")
                self.status_label.setStyleSheet("color: #EF4444;")
                QMessageBox.warning(self, "Data Error", error_msg)
                return
            
            self.status_label.setText("Formatting annotations...")
            
            # Format annotations
            annotations_list = self.format_annotations_for_ai()
            if not annotations_list or not annotations_list.strip():
                error_msg = "No annotations found to organize. Please create some annotations first."
                self.status_label.setText(f"❌ {error_msg}")
                self.status_label.setStyleSheet("color: #EF4444;")
                QMessageBox.warning(self, "No Annotations Available", 
                    "No annotations are available for organization.\n\n"
                    "Please create some annotations in the transcript first, then try again.")
                return
                
        except Exception as e:
            error_msg = f"Initialization failed: {str(e)}"
            self.status_label.setText(f"❌ {error_msg}")
            self.status_label.setStyleSheet("color: #EF4444;")
            QMessageBox.critical(self, "Initialization Error", error_msg)
            return
        
        try:
            self.status_label.setText("Preparing AI prompt...")
            
            # Get user notes
            user_notes = self.user_notes.toPlainText().strip()
            
            # Get AI configuration settings
            use_full_transcript = self.full_transcript_checkbox.isChecked()
            thinking_budget = self.thinking_budget.value()
            use_dividers = self.dividers_checkbox.isChecked()
            use_headers = self.headers_checkbox.isChecked()
            use_length_limit = self.length_limit_checkbox.isChecked()
            target_minutes = self.length_minutes.value()
            target_seconds = self.length_seconds.value()
            total_target_seconds = (target_minutes * 60) + target_seconds
            
            # Prepare transcript context
            if use_full_transcript:
                transcript_context = full_text
                context_note = "(complete transcript provided for full context)"
            else:
                transcript_context = ""
                context_note = "(transcript context disabled - only using annotation content)"
            
            # Calculate current word count and duration info for length limit
            length_constraint_info = ""
            if use_length_limit:
                # Calculate word count of all available annotations
                total_word_count = self.calculate_annotation_word_count(self.annotations)
                current_duration_seconds = self.calculate_duration_from_words(total_word_count)
                current_duration_formatted = self.format_duration(current_duration_seconds)
                target_duration_formatted = self.format_duration(total_target_seconds)
                
                # Calculate target word count
                target_word_count = int((total_target_seconds / 60) * 200)  # 200 WPM
                
                length_constraint_info = f"""
SCRIPT LENGTH TARGET: {target_duration_formatted} (approximately {target_word_count} words)
Current available content: {total_word_count} words ({current_duration_formatted})

IMPORTANT: Select annotations to match the target duration. You can use fewer annotations than available to meet the length requirement.
"""
            
            # Create the enhanced prompt with thinking budget
            prompt = f"""<thinking>
You are organizing interview/transcript annotations into a coherent video script. Take time to analyze the content deeply and consider multiple narrative approaches.

Budget: {thinking_budget} tokens for reasoning about the best narrative structure.

Consider:
1. What are the key themes and emotional beats in this content?
2. How can we create a compelling opening that hooks the viewer?
3. What logical progression will build engagement and lead to a satisfying conclusion?
4. How do the user's annotations (with their notes, tags, favorites, and themes) guide the narrative?
5. What story arc will resonate most with the intended audience?
{f"6. How can we select the most impactful content to meet the target duration of {self.format_duration(total_target_seconds)}?" if use_length_limit else ""}

Think through multiple possible organizations before settling on the best one.
</thinking>

You are organizing interview/transcript annotations into a coherent video script.
{length_constraint_info}

{f"CONTEXT - Full transcript for reference {context_note}:\n{transcript_context}\n\n" if transcript_context else ""}AVAILABLE ANNOTATIONS TO ORGANIZE:
Each annotation includes: ID, quoted text, and metadata (notes, favorite status, tags, themes).
- note: User's explanatory comment about why this section was highlighted
- favorite: Whether user marked this as particularly important (true/false)
- tags: User-assigned categories for this content
- theme/secondary-theme: User-assigned thematic categories

{annotations_list}

USER'S VIDEO GOALS AND NOTES:
{user_notes if user_notes else "No specific goals provided - create a logical narrative flow"}

TASK: Create a logical narrative flow for a video. Consider:
- Opening hooks and context setting
- Natural topic transitions
- Building to key moments/climax
- Strong conclusions
- Pay special attention to favorited annotations (favorite: true) as key moments
- Use theme information to group related content
- User notes provide context about why each section was highlighted
{f"- CRITICAL: Select annotations that will result in approximately {target_word_count} words total to meet the {target_duration_formatted} target duration" if use_length_limit else ""}

{f'''
ADVANCED FEATURES ENABLED:
{f"""
HEADERS: You can add production notes to annotations for editing guidance. Use sparingly - only when they would genuinely help with video production. Examples: "Tonal Shift", "Pause", "Music shifts to be more uplifting", "Background music starts", "Energy builds", "Natural break", etc.
""" if use_headers else ""}
{f"""
DIVIDERS: Create section breaks by adding new divider objects. Use this format:
DIVIDER :: "Section Name" :: Order#X :: #color

Available colors: #fff4c9 (yellow), #d7ffb8 (green), #ffcccb (red), #e6ccff (purple), #ccf2ff (blue)

Examples:
- DIVIDER :: "Introduction" :: Order#0 :: #fff4c9
- DIVIDER :: "The Journey Begins" :: Order#5 :: #d7ffb8
- DIVIDER :: "Challenges and Growth" :: Order#10 :: #ffcccb
""" if use_dividers else ""}
''' if use_headers or use_dividers else ''}

RESPONSE FORMAT:
You can mix annotations, headers, and dividers. Respond with one of these per line:

For annotations (MOST COMMON):
annotation-id-here :: Order#0

{f"""
For annotations with headers (use sparingly):
annotation-id-here :: Order#1 :: HEADER :: "Production Note"
""" if use_headers else ""}
{f"""
For dividers:
DIVIDER :: "Section Name" :: Order#X :: #color
""" if use_dividers else ""}

{f"Remember: Use headers sparingly - only when they add genuine production value." if use_headers else ""}

Use actual annotation IDs from the list above. You don't need to use all annotations - only include the ones that fit the narrative.
Do not include any explanations, comments, or other text."""

            # Show progress
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.process_btn.setEnabled(False)
            self.status_label.setText("Sending request to AI...")
            self.debug_display.clear()
            self.parsed_display.clear()
            
            # Create and start worker thread with streaming option
            use_streaming = self.streaming_checkbox.isChecked()
            self.worker_thread = AIWorkerThread(self.ai_model, prompt, stream=use_streaming)
            self.worker_thread.response_received.connect(self.on_ai_response)
            self.worker_thread.response_chunk.connect(self.on_ai_response_chunk)
            self.worker_thread.error_occurred.connect(self.on_ai_error)
            self.worker_thread.start()
            
        except Exception as e:
            error_msg = f"Failed to start AI processing: {str(e)}"
            self.status_label.setText(f"❌ {error_msg}")
            self.status_label.setStyleSheet("color: #EF4444;")
            self.progress_bar.setVisible(False)
            self.process_btn.setEnabled(True)
            QMessageBox.critical(self, "Processing Error", f"{error_msg}\n\nPlease check your API key and network connection.")
            print(f"[AI STORYBOARD ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
    
    def on_ai_response_chunk(self, chunk_text):
        """Handle streaming AI response chunks"""
        # Append chunk to debug display
        current_text = self.debug_display.toPlainText()
        self.debug_display.setPlainText(current_text + chunk_text)
        
        # Auto-scroll to bottom
        cursor = self.debug_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.debug_display.setTextCursor(cursor)
    
    def on_ai_response(self, response_text):
        """Handle AI response"""
        # Hide progress
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        # Display raw response (for non-streaming or final complete response)
        if not self.streaming_checkbox.isChecked():
            self.debug_display.setPlainText(response_text)
        
        # Store the complete response for conversation history
        self.last_response = response_text
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text
        })
        
        # Parse the response
        self.parsed_updates = []
        self.parsed_headers = {}  # annotation_id -> header_text
        self.parsed_dividers = []  # (order, title, color)
        parsed_lines = []
        
        for line in response_text.strip().split('\n'):
            if '::' in line:
                try:
                    parts = [p.strip() for p in line.split('::')]
                    
                    # Handle dividers: DIVIDER :: "Section Name" :: Order#X :: #color
                    if parts[0] == 'DIVIDER' and len(parts) >= 4:
                        section_name = parts[1].strip('"')
                        order_str = parts[2].strip()
                        color = parts[3].strip()
                        order_num = int(order_str.replace('Order#', ''))
                        
                        self.parsed_dividers.append((order_num, section_name, color))
                        parsed_lines.append(f"📁 Divider #{order_num}: {section_name}")
                    
                    # Handle annotations with optional headers
                    elif len(parts) >= 2:
                        anno_id = parts[0].strip()
                        order_str = parts[1].strip()
                        order_num = int(order_str.replace('Order#', ''))
                        
                        # Check for header
                        header_text = None
                        if len(parts) >= 4 and parts[2].strip() == 'HEADER':
                            header_text = parts[3].strip('"')
                            # Handle case where AI incorrectly included HTML
                            if header_text.startswith('<div>') and header_text.endswith('</div>'):
                                # Extract text from <div><b style='background-color: #ffff7f;'>Text</b></div>
                                import re
                                match = re.search(r'<b[^>]*>([^<]+)</b>', header_text)
                                if match:
                                    header_text = match.group(1)
                            self.parsed_headers[anno_id] = header_text
                        
                        # Validate annotation ID exists
                        matching_anno = None
                        for anno in self.annotations:
                            if anno['id'] == anno_id:
                                matching_anno = anno
                                break
                        
                        if matching_anno:
                            self.parsed_updates.append((anno_id, order_num))
                            # Show preview with truncated text
                            preview_text = matching_anno['text'][:100] + "..." if len(matching_anno['text']) > 100 else matching_anno['text']
                            header_preview = f" [{header_text}]" if header_text else ""
                            parsed_lines.append(f"Order #{order_num}: {preview_text}{header_preview}")
                        else:
                            parsed_lines.append(f"⚠️ Unknown ID: {anno_id}")
                except Exception as e:
                    parsed_lines.append(f"⚠️ Parse error on line: {line}")
        
        # Display parsed results
        if parsed_lines:
            self.parsed_display.setPlainText("\n".join(parsed_lines))
        
        # Update status and enable Create Script button
        total_items = len(self.parsed_updates) + len(self.parsed_dividers)
        if total_items > 0:
            self.create_script_btn.setEnabled(True)
            status_parts = []
            if self.parsed_updates:
                status_parts.append(f"{len(self.parsed_updates)} annotations")
            if self.parsed_dividers:
                status_parts.append(f"{len(self.parsed_dividers)} dividers")
            if self.parsed_headers:
                status_parts.append(f"{len(self.parsed_headers)} headers")
            
            self.status_label.setText(f"✓ Found {', '.join(status_parts)}")
            self.status_label.setStyleSheet("color: #10B981;")
            # Show followup question area
            self.followup_widget.setVisible(True)
            
            # Auto-switch to Organization tab now that parsing is complete
            self.results_tabs.setCurrentIndex(1)  # Index 1 is the Organization tab
        else:
            self.status_label.setText("⚠️ No valid orderings found in response")
            self.status_label.setStyleSheet("color: #EF4444;")
    
    def on_ai_error(self, error_message):
        """Handle AI processing error"""
        self.progress_bar.setVisible(False)
        self.process_btn.setEnabled(True)
        
        # Provide more specific error messages
        detailed_msg = error_message
        user_msg = "AI processing failed"
        
        if "API" in error_message.upper():
            user_msg = "API Error - Check your API key"
            detailed_msg += "\n\nSuggestions:\n• Verify your API key in Data/api_key.txt\n• Check if you have API credits remaining\n• Ensure network connectivity"
        elif "TIMEOUT" in error_message.upper():
            user_msg = "Request Timeout"
            detailed_msg += "\n\nSuggestions:\n• Try again with a smaller thinking budget\n• Check your network connection\n• Use gemini-2.5-flash instead of Pro"
        elif "QUOTA" in error_message.upper() or "LIMIT" in error_message.upper():
            user_msg = "Rate Limit or Quota Exceeded"
            detailed_msg += "\n\nSuggestions:\n• Wait a few minutes and try again\n• Check your API quota limits\n• Consider using a smaller transcript context"
        elif "SAFETY" in error_message.upper():
            user_msg = "Content Safety Filter Triggered"
            detailed_msg += "\n\nSuggestions:\n• Review your transcript content\n• Try rephrasing your video goals\n• Some content may not be suitable for AI processing"
        
        self.status_label.setText(f"❌ {user_msg}")
        self.status_label.setStyleSheet("color: #EF4444;")
        
        # Also show the error in debug tab
        self.debug_display.setPlainText(f"ERROR: {error_message}\n\nFull details: {detailed_msg}")
        
        QMessageBox.critical(self, "AI Processing Error", detailed_msg)
        print(f"[AI STORYBOARD ERROR] {error_message}")
    
    def create_and_apply_script(self):
        """Generate and execute the update script after user reviews AI response"""
        if not self.parsed_updates:
            return
        
        # Check if storyboard already has content
        existing_items_count = 0
        if hasattr(self.main_window, 'storyboard_dialog') and self.main_window.storyboard_dialog:
            storyboard_dialog = self.main_window.storyboard_dialog
            if hasattr(storyboard_dialog, 'order_list'):
                existing_items_count = storyboard_dialog.order_list.count()
        
        # If storyboard has existing content, ask if user wants to clear it first
        if existing_items_count > 0:
            clear_msg = QMessageBox()
            clear_msg.setWindowTitle("Script Editor Not Empty")
            clear_msg.setText(f"The Script Editor currently contains {existing_items_count} items.")
            clear_msg.setInformativeText("Would you like to clear the existing script before applying the AI organization?")
            clear_msg.setDetailedText("Choose 'Yes' to clear the script first, or 'No' to cancel the operation.")
            clear_msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            clear_msg.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            if clear_msg.exec() == QMessageBox.StandardButton.Yes:
                # Clear the storyboard first
                print("🗑️ [AI STORYBOARD] User chose to clear existing storyboard before applying AI organization")
                if hasattr(storyboard_dialog, 'clear_final_order'):
                    # Call the clear method without showing the confirmation dialog
                    print("🗑️ [AI STORYBOARD] Clearing storyboard...")
                    storyboard_dialog.order_list.clear()
                    
                    # Clear order values from annotations (same logic as clear_final_order but without confirmation)
                    for annotation in self.main_window.web_view.annotations:
                        if 'order' in annotation:
                            annotation.pop('order')
                        if 'storyboard' in annotation and 'order' in annotation['storyboard']:
                            annotation['storyboard'].pop('order')
                        # Reset used status
                        if annotation.get('used', False):
                            annotation['used'] = False
                        # Reset storyboard text and clear strikethrough
                        if 'storyboard' in annotation and 'text' in annotation['storyboard']:
                            original_text = annotation.get('text', '').replace('\n', '<br>')
                            annotation['storyboard']['text'] = original_text
                        if 'storyboard' in annotation and 'strikethrough_segments' in annotation['storyboard']:
                            annotation['storyboard']['strikethrough_segments'] = {}
                        if 'storyboard' in annotation and 'positional_strikethrough' in annotation['storyboard']:
                            annotation['storyboard']['positional_strikethrough'] = {}
                    
                    # Clear DOM attributes
                    js_code = '''
                    (function() {
                        const spans = document.querySelectorAll('[data-annotation-id]');
                        spans.forEach(span => {
                            span.removeAttribute('data-order');
                            span.setAttribute('data-used', 'false');
                        });
                        return spans.length;
                    })();
                    '''
                    if hasattr(self.main_window, 'web_view'):
                        self.main_window.web_view.page().runJavaScript(js_code)
                    
                    print("✅ [AI STORYBOARD] Storyboard cleared, proceeding with AI organization")
                else:
                    print("❌ [AI STORYBOARD] Could not find clear_final_order method")
            else:
                print("🚫 [AI STORYBOARD] User canceled AI organization due to existing storyboard content")
                return
        
        # Show confirmation with preview
        msg = QMessageBox()
        msg.setWindowTitle("Apply AI Script Organization?")
        msg.setText(f"Apply ordering to {len(self.parsed_updates)} annotations?")
        msg.setInformativeText("This will update the script order based on the AI's suggestions.")
        msg.setDetailedText(self.debug_display.toPlainText())
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.apply_storyboard_updates()
    
    def apply_storyboard_updates(self):
        """Apply the parsed updates to DOM and Python model"""
        try:
            print(f"🎯🎯🎯 [AI STORYBOARD] Starting to apply {len(self.parsed_updates)} updates... 🎯🎯🎯")
            
            # Check for existing dividers and their order numbers to avoid conflicts
            print(f"🔍🔍🔍 [AI STORYBOARD] Checking for existing dividers... 🔍🔍🔍")
            divider_orders = []
            for anno in self.annotations:
                if anno.get('divider') and 'storyboard' in anno and 'order' in anno['storyboard']:
                    order_num = anno['storyboard']['order']
                    divider_orders.append(order_num)
                    print(f"🚧🚧🚧 [AI STORYBOARD] Found divider with order {order_num}: {anno['storyboard'].get('text', 'Unknown')} 🚧🚧🚧")
            
            if divider_orders:
                print(f"⚠️⚠️⚠️ [AI STORYBOARD] Found {len(divider_orders)} dividers with orders: {divider_orders} ⚠️⚠️⚠️")
                max_divider_order = max(divider_orders)
                print(f"📊📊📊 [AI STORYBOARD] Highest divider order: {max_divider_order} 📊📊📊")
                
                # Adjust all annotation orders to start after the highest divider
                print(f"🔧🔧🔧 [AI STORYBOARD] Adjusting annotation orders to start after {max_divider_order} 🔧🔧🔧")
                adjusted_updates = []
                for anno_id, order_num in self.parsed_updates:
                    new_order = max_divider_order + 1 + order_num
                    adjusted_updates.append((anno_id, new_order))
                    print(f"🔄🔄🔄 [AI STORYBOARD] Adjusted {anno_id}: order {order_num} -> {new_order} 🔄🔄🔄")
                
                self.parsed_updates = adjusted_updates
                print(f"✅✅✅ [AI STORYBOARD] All orders adjusted to avoid divider conflicts ✅✅✅")
            else:
                print(f"✅✅✅ [AI STORYBOARD] No dividers found, keeping original orders ✅✅✅")
            
            # Debug: Show what annotations we have access to
            print(f"🔍🔍🔍 [AI STORYBOARD] We have {len(self.annotations)} annotations in self.annotations 🔍🔍🔍")
            
            # Check if we can access main window annotations
            if hasattr(self.main_window, 'web_view') and hasattr(self.main_window.web_view, 'annotations'):
                main_annotations = self.main_window.web_view.annotations
                print(f"🌟🌟🌟 [AI STORYBOARD] Main window has {len(main_annotations)} annotations 🌟🌟🌟")
            else:
                print(f"⚠️⚠️⚠️ [AI STORYBOARD] Cannot access main window annotations ⚠️⚠️⚠️")
                main_annotations = None
            
            # Update DOM attributes
            print(f"🚀🚀🚀 [AI STORYBOARD] Starting DOM updates... 🚀🚀🚀")
            for anno_id, order_num in self.parsed_updates:
                js_code = f'''
                (function() {{
                    const spans = document.querySelectorAll('[data-annotation-id="{anno_id}"]');
                    let updated_count = 0;
                    spans.forEach(span => {{
                        const old_order = span.getAttribute('data-order');
                        span.setAttribute('data-order', '{order_num}');
                        updated_count++;
                        console.log('🎯 AI STORYBOARD: Set order {order_num} for annotation {anno_id} (was: ' + old_order + ')');
                    }});
                    return {{
                        spans_found: spans.length,
                        updated_count: updated_count,
                        annotation_id: "{anno_id}",
                        new_order: "{order_num}"
                    }};
                }})();
                '''
                
                def handle_dom_result(result):
                    if result:
                        print(f"🔍🔍🔍 [AI STORYBOARD] DOM UPDATE RESULT: {result} 🔍🔍🔍")
                        if result.get('spans_found', 0) > 0:
                            print(f"✅✅✅ [AI STORYBOARD] Successfully updated {result['spans_found']} DOM spans for {result['annotation_id']} -> order {result['new_order']} ✅✅✅")
                        else:
                            print(f"❌❌❌ [AI STORYBOARD] NO DOM SPANS FOUND for {result['annotation_id']} ❌❌❌")
                    else:
                        print(f"❌❌❌ [AI STORYBOARD] DOM update returned None for {anno_id} ❌❌❌")
                
                self.web_view.page().runJavaScript(js_code, handle_dom_result)
                print(f"📤📤📤 [AI STORYBOARD] DOM update sent: {anno_id} -> order {order_num} 📤📤📤")
            
            # Add a verification step to check that all DOM updates actually took effect
            print(f"🔍🔍🔍 [AI STORYBOARD] Verifying all DOM updates took effect... 🔍🔍🔍")
            verification_js = f'''
            (function() {{
                const updates = {json.dumps(self.parsed_updates)};
                const results = [];
                
                updates.forEach(([anno_id, expected_order]) => {{
                    const spans = document.querySelectorAll('[data-annotation-id="' + anno_id + '"]');
                    spans.forEach(span => {{
                        const actual_order = span.getAttribute('data-order');
                        results.push({{
                            annotation_id: anno_id,
                            expected_order: expected_order,
                            actual_order: actual_order,
                            matches: actual_order == expected_order,
                            span_text: span.textContent.substring(0, 50) + '...'
                        }});
                    }});
                }});
                
                return results;
            }})();
            '''
            
            def handle_verification_result(results):
                if results:
                    print(f"📊📊📊 [AI STORYBOARD] DOM VERIFICATION RESULTS ({len(results)} spans checked): 📊📊📊")
                    matches = 0
                    mismatches = 0
                    for result in results:
                        if result['matches']:
                            matches += 1
                            print(f"✅ {result['annotation_id']}: order {result['actual_order']} ✓ - {result['span_text']}")
                        else:
                            mismatches += 1
                            print(f"❌ {result['annotation_id']}: expected {result['expected_order']}, got {result['actual_order']} - {result['span_text']}")
                    
                    print(f"📈📈📈 [AI STORYBOARD] DOM VERIFICATION SUMMARY: {matches} matches, {mismatches} mismatches 📈📈📈")
                else:
                    print(f"❌❌❌ [AI STORYBOARD] DOM verification returned no results ❌❌❌")
            
            self.web_view.page().runJavaScript(verification_js, handle_verification_result)
            
            # Update Python model - try both annotation lists
            print(f"📝📝📝 [AI STORYBOARD] Starting Python model updates... 📝📝📝")
            updated_count = 0
            
            # First try self.annotations
            for anno_id, order_num in self.parsed_updates:
                found_in_self = False
                for anno in self.annotations:
                    if anno['id'] == anno_id:
                        print(f"🎯🎯🎯 [AI STORYBOARD] Found {anno_id} in self.annotations 🎯🎯🎯")
                        if 'storyboard' not in anno:
                            anno['storyboard'] = {}
                            print(f"🆕🆕🆕 [AI STORYBOARD] Created new storyboard dict for {anno_id} 🆕🆕🆕")
                        
                        old_order = anno['storyboard'].get('order', 'None')
                        anno['storyboard']['order'] = order_num
                        
                        # Add header if specified (following make_header pattern)
                        if anno_id in self.parsed_headers:
                            header_html = f"<div><b style='background-color: #ffff7f;'>{self.parsed_headers[anno_id]}</b></div>"
                            original_text = anno.get('text', '')
                            
                            # Check if storyboard already has text, use that as base
                            base_text = anno['storyboard'].get('text', original_text)
                            
                            # Remove any existing header from base text (prevent duplicates)
                            import re
                            clean_text = re.sub(r'^<div><b[^>]*>.*?</b></div>\s*', '', base_text, flags=re.DOTALL)
                            
                            # Add new header with clean text (following make_header pattern)
                            anno['storyboard']['text'] = f"{header_html}{clean_text}"
                            print(f"📝📝📝 [AI STORYBOARD] Added header to {anno_id}: {self.parsed_headers[anno_id]} 📝📝📝")
                        
                        updated_count += 1
                        found_in_self = True
                        print(f"✨✨✨ [AI STORYBOARD] Updated {anno_id}: order {old_order} -> {order_num} ✨✨✨")
                        break
                
                if not found_in_self:
                    print(f"❌❌❌ [AI STORYBOARD] {anno_id} NOT FOUND in self.annotations ❌❌❌")
            
            # Also try main window annotations if available
            if main_annotations:
                print(f"🔄🔄🔄 [AI STORYBOARD] Also updating main window annotations... 🔄🔄🔄")
                for anno_id, order_num in self.parsed_updates:
                    found_in_main = False
                    for anno in main_annotations:
                        if anno['id'] == anno_id:
                            print(f"🎯🎯🎯 [AI STORYBOARD] Found {anno_id} in main window annotations 🎯🎯🎯")
                            if 'storyboard' not in anno:
                                anno['storyboard'] = {}
                                print(f"🆕🆕🆕 [AI STORYBOARD] Created new storyboard dict in main for {anno_id} 🆕🆕🆕")
                            
                            old_order = anno['storyboard'].get('order', 'None')
                            anno['storyboard']['order'] = order_num
                            
                            # Add header if specified (following make_header pattern)
                            if anno_id in self.parsed_headers:
                                header_html = f"<div><b style='background-color: #ffff7f;'>{self.parsed_headers[anno_id]}</b></div>"
                                original_text = anno.get('text', '')
                                
                                # Check if storyboard already has text, use that as base
                                base_text = anno['storyboard'].get('text', original_text)
                                
                                # Remove any existing header from base text (prevent duplicates)
                                import re
                                clean_text = re.sub(r'^<div><b[^>]*>.*?</b></div>\s*', '', base_text, flags=re.DOTALL)
                                
                                # Add new header with clean text (following make_header pattern)
                                anno['storyboard']['text'] = f"{header_html}{clean_text}"
                                print(f"📝📝📝 [AI STORYBOARD] Added header to main {anno_id}: {self.parsed_headers[anno_id]} 📝📝📝")
                            
                            found_in_main = True
                            print(f"💫💫💫 [AI STORYBOARD] Updated in main {anno_id}: order {old_order} -> {order_num} 💫💫💫")
                            break
                    
                    if not found_in_main:
                        print(f"❌❌❌ [AI STORYBOARD] {anno_id} NOT FOUND in main window annotations ❌❌❌")
            
            print(f"🏁🏁🏁 [AI STORYBOARD] Updated {updated_count} annotations in self.annotations 🏁🏁🏁")
            
            # Create new dividers if specified - use proper storyboard method
            if self.parsed_dividers:
                print(f"📁📁📁 [AI STORYBOARD] Creating {len(self.parsed_dividers)} new dividers using storyboard method... 📁📁📁")
                
                # DEBUG: Check what dividers already exist before we create new ones
                print(f"🔍🔍🔍 [AI STORYBOARD DIVIDER DEBUG] Checking existing dividers before creation... 🔍🔍🔍")
                existing_divider_count = 0
                for anno in self.annotations:
                    if anno.get('divider'):
                        existing_divider_count += 1
                        order_val = anno.get('storyboard', {}).get('order', 'NO_ORDER')
                        text_val = anno.get('text', 'NO_TEXT')
                        print(f"🔍 EXISTING DIVIDER: '{text_val}' at order {order_val} (ID: {anno.get('id', 'NO_ID')})")
                
                if main_annotations:
                    main_existing_count = 0
                    for anno in main_annotations:
                        if anno.get('divider'):
                            main_existing_count += 1
                            order_val = anno.get('storyboard', {}).get('order', 'NO_ORDER')
                            text_val = anno.get('text', 'NO_TEXT')
                            print(f"🔍 MAIN EXISTING DIVIDER: '{text_val}' at order {order_val} (ID: {anno.get('id', 'NO_ID')})")
                    print(f"🔍🔍🔍 [AI STORYBOARD DIVIDER DEBUG] Found {existing_divider_count} in self.annotations, {main_existing_count} in main_annotations 🔍🔍🔍")
                else:
                    print(f"🔍🔍🔍 [AI STORYBOARD DIVIDER DEBUG] Found {existing_divider_count} in self.annotations, main_annotations is None 🔍🔍🔍")
                
                # Get access to the storyboard dialog and its order list
                if hasattr(self.main_window, 'storyboard_dialog') and self.main_window.storyboard_dialog:
                    storyboard_dialog = self.main_window.storyboard_dialog
                    order_list = storyboard_dialog.order_list
                    
                    # DEBUG: Check what's already in the UI before we add anything
                    print(f"🖼️🖼️🖼️ [AI STORYBOARD DIVIDER DEBUG] Current UI state before creating dividers... 🖼️🖼️🖼️")
                    ui_item_count = order_list.count()
                    ui_divider_count = 0
                    for i in range(ui_item_count):
                        item = order_list.item(i)
                        widget = order_list.itemWidget(item)
                        if widget and hasattr(widget, 'is_divider') and widget.is_divider:
                            ui_divider_count += 1
                            divider_text = getattr(widget, 'section_name', 'UNKNOWN')
                            print(f"🖼️ UI DIVIDER {i}: '{divider_text}'")
                    print(f"🖼️🖼️🖼️ [AI STORYBOARD DIVIDER DEBUG] Found {ui_divider_count} dividers in UI out of {ui_item_count} total items 🖼️🖼️🖼️")
                    
                    # Create dividers using the proper storyboard method (will be handled in safe_populate)
                    # Note: We create the annotation objects here but let safe_populate handle UI creation
                    for order_num, section_name, color in self.parsed_dividers:
                        print(f"➕➕➕ [AI STORYBOARD DIVIDER DEBUG] About to create divider '{section_name}' at order {order_num} with color {color} ➕➕➕")
                        
                        # Check if this exact divider already exists
                        duplicate_found = False
                        for anno in self.annotations:
                            if (anno.get('divider') and 
                                anno.get('text') == section_name and 
                                anno.get('storyboard', {}).get('order') == order_num):
                                duplicate_found = True
                                print(f"⚠️⚠️⚠️ [AI STORYBOARD DIVIDER DEBUG] DUPLICATE FOUND: '{section_name}' at order {order_num} already exists with ID {anno.get('id')} ⚠️⚠️⚠️")
                                break
                        
                        if duplicate_found:
                            print(f"🚫🚫🚫 [AI STORYBOARD DIVIDER DEBUG] SKIPPING creation of duplicate divider '{section_name}' 🚫🚫🚫")
                            continue
                        
                        import uuid
                        from datetime import datetime
                        
                        # Generate unique ID for the divider
                        divider_id = str(uuid.uuid4())
                        print(f"🆔 [AI STORYBOARD DIVIDER DEBUG] Generated new divider ID: {divider_id}")
                        
                        # Create the corresponding annotation object for session data
                        divider_obj = {
                            "id": divider_id,
                            "text": section_name,
                            "color": color,
                            "divider": True,
                            "storyboard": {
                                "order": order_num,
                                "text": section_name,
                                "color": color,
                                "divider": True
                            },
                            "notes_html": "",
                            "tags": [],
                            "speech_title": "",
                            "secondary_scenes": [],
                            "timestamp": datetime.now().isoformat(),
                            "notes": "",
                            "used": True
                        }
                        
                        # Add to annotation lists
                        print(f"📝 [AI STORYBOARD DIVIDER DEBUG] Adding divider to self.annotations...")
                        self.annotations.append(divider_obj)
                        if main_annotations:
                            print(f"📝 [AI STORYBOARD DIVIDER DEBUG] Adding divider to main_annotations...")
                            main_annotations.append(divider_obj)
                        else:
                            print(f"📝 [AI STORYBOARD DIVIDER DEBUG] main_annotations is None, not adding there")
                        
                        print(f"✅ Created divider annotation '{section_name}' with ID {divider_id} at order {order_num}")
                    
                    # DEBUG: Check what dividers exist after creation
                    print(f"🔍🔍🔍 [AI STORYBOARD DIVIDER DEBUG] Checking dividers after creation... 🔍🔍🔍")
                    after_creation_count = 0
                    for anno in self.annotations:
                        if anno.get('divider'):
                            after_creation_count += 1
                            order_val = anno.get('storyboard', {}).get('order', 'NO_ORDER')
                            text_val = anno.get('text', 'NO_TEXT')
                            print(f"🔍 AFTER CREATION: '{text_val}' at order {order_val} (ID: {anno.get('id', 'NO_ID')})")
                    
                    print(f"📊📊📊 [AI STORYBOARD DIVIDER DEBUG] Total dividers after creation: {after_creation_count} (was {existing_divider_count}) 📊📊📊")
                    
                    print(f"✅✅✅ [AI STORYBOARD] All dividers created using proper storyboard method ✅✅✅")
                else:
                    print(f"❌❌❌ [AI STORYBOARD] Cannot create dividers - storyboard dialog not available ❌❌❌")
            
            # Debug: Show final state of some annotations
            print(f"🔍🔍🔍 [AI STORYBOARD] Final state check... 🔍🔍🔍")
            for anno_id, order_num in self.parsed_updates[:3]:  # Check first 3
                for anno in self.annotations:
                    if anno['id'] == anno_id:
                        current_order = anno.get('storyboard', {}).get('order', 'MISSING')
                        print(f"🔍 Final check {anno_id}: order = {current_order}")
                        break
            
            # DEBUG: Check what ALL annotations look like after AI updates
            print(f"🕵️🕵️🕵️ [AI STORYBOARD] COMPREHENSIVE DEBUG - ALL ANNOTATIONS AFTER AI UPDATES: 🕵️🕵️🕵️")
            annotations_with_orders = 0
            for anno in self.annotations:
                if 'storyboard' in anno and 'order' in anno['storyboard']:
                    annotations_with_orders += 1
                    print(f"🕵️ ANNO {anno['id']}: storyboard.order = {anno['storyboard']['order']}")
                elif 'order' in anno:
                    annotations_with_orders += 1  
                    print(f"🕵️ ANNO {anno['id']}: root.order = {anno['order']}")
                else:
                    print(f"🕵️ ANNO {anno['id']}: NO ORDER VALUE FOUND")
            
            print(f"🕵️🕵️🕵️ [AI STORYBOARD] TOTAL ANNOTATIONS WITH ORDER VALUES: {annotations_with_orders} out of {len(self.annotations)} 🕵️🕵️🕵️")
            
            # Open storyboard dialog if not already open
            print(f"🏠🏠🏠 [AI STORYBOARD] Checking if storyboard dialog is open... 🏠🏠🏠")
            if not hasattr(self.main_window, 'storyboard_dialog') or not self.main_window.storyboard_dialog:
                print(f"🔓🔓🔓 [AI STORYBOARD] Storyboard dialog not open, trying to open it... 🔓🔓🔓")
                # Open the storyboard dialog
                if hasattr(self.main_window, 'toggle_storyboard'):
                    print(f"🚀🚀🚀 [AI STORYBOARD] Calling toggle_storyboard... 🚀🚀🚀")
                    self.main_window.toggle_storyboard()
                else:
                    print(f"❌❌❌ [AI STORYBOARD] No toggle_storyboard method found ❌❌❌")
                    QMessageBox.warning(self, "Warning", 
                        "Could not open storyboard dialog. Please open it manually to see the changes.")
            else:
                print(f"✅✅✅ [AI STORYBOARD] Storyboard dialog is already open ✅✅✅")
            
            # Trigger a safe storyboard refresh that reads the updated annotation data
            print(f"🔄🔄🔄 [AI STORYBOARD] Triggering safe storyboard refresh to display AI updates... 🔄🔄🔄")
            
            if hasattr(self.main_window, 'storyboard_dialog') and self.main_window.storyboard_dialog:
                print(f"🎯🎯🎯 [AI STORYBOARD] Storyboard dialog found, forcing refresh of UI... 🎯🎯🎯")
                
                # Method 1: Try to directly populate the order list without apply_changes_lite
                try:
                    # Set a flag to prevent apply_changes_lite from running during population
                    self.main_window.storyboard_dialog._ai_refresh_in_progress = True
                    print(f"🛡️🛡️🛡️ [AI STORYBOARD] Set AI refresh flag to prevent race condition 🛡️🛡️🛡️")
                    
                    # Force populate the order list with current annotation data
                    def safe_populate():
                        try:
                            print(f"🔥🔥🔥 [AI STORYBOARD] Executing SAFE storyboard populate NOW! 🔥🔥🔥")
                            # Clear and repopulate the storyboard with current annotation data
                            if hasattr(self.main_window.storyboard_dialog, 'order_list'):
                                order_list = self.main_window.storyboard_dialog.order_list
                                order_list.clear()
                                
                                # Add items with current order values (use main window annotations as the authoritative source)
                                sorted_annotations = []
                                processed_ids = set()  # Track IDs to prevent duplicates
                                
                                for anno in self.main_window.web_view.annotations:
                                    if 'storyboard' in anno and 'order' in anno['storyboard']:
                                        anno_id = anno.get('id')
                                        if anno_id not in processed_ids:
                                            sorted_annotations.append((anno['storyboard']['order'], anno))
                                            processed_ids.add(anno_id)
                                            print(f"🎯 [AI STORYBOARD SAFE_POPULATE] Added {anno_id} to sorted list (order {anno['storyboard']['order']})")
                                        else:
                                            print(f"⚠️ [AI STORYBOARD SAFE_POPULATE] SKIPPED DUPLICATE ID {anno_id} (order {anno['storyboard']['order']})")
                                
                                sorted_annotations.sort(key=lambda x: x[0])  # Sort by order
                                
                                for order_num, anno in sorted_annotations:
                                    print(f"🎯 [AI STORYBOARD SAFE_POPULATE] Adding to storyboard: {anno['id']} (order {order_num})")
                                    
                                    # Check if this is a divider
                                    if anno.get('divider', False):
                                        print(f"📁📁📁 [AI STORYBOARD SAFE_POPULATE] Processing divider: '{anno.get('text', 'Unnamed')}' with color {anno.get('color', '#fff4c9')} 📁📁📁")
                                        
                                        # DEBUG: Check if this divider already exists in UI
                                        existing_ui_dividers = []
                                        for i in range(order_list.count()):
                                            item = order_list.item(i)
                                            widget = order_list.itemWidget(item)
                                            if widget and hasattr(widget, 'is_divider') and widget.is_divider:
                                                existing_text = getattr(widget, 'section_name', 'UNKNOWN')
                                                existing_ui_dividers.append(existing_text)
                                        
                                        divider_text = anno.get('text', 'Section')
                                        if divider_text in existing_ui_dividers:
                                            print(f"⚠️⚠️⚠️ [AI STORYBOARD SAFE_POPULATE] UI DIVIDER '{divider_text}' ALREADY EXISTS - this will create a duplicate! ⚠️⚠️⚠️")
                                        else:
                                            print(f"✅ [AI STORYBOARD SAFE_POPULATE] UI divider '{divider_text}' is new, safe to create")
                                        
                                        print(f"📁 [AI STORYBOARD SAFE_POPULATE] Calling add_divider('{divider_text}', '{anno.get('color', '#fff4c9')}')")
                                        # Use the proper divider creation method
                                        divider_item = order_list.add_divider(
                                            divider_text, 
                                            anno.get('color', '#fff4c9')
                                        )
                                        if divider_item:
                                            # Ensure the divider has the correct annotation ID
                                            divider_item.setData(Qt.ItemDataRole.UserRole, anno['id'])
                                            print(f"✅✅✅ [AI STORYBOARD SAFE_POPULATE] Created divider widget for {anno['id']} ✅✅✅")
                                        else:
                                            print(f"❌❌❌ [AI STORYBOARD SAFE_POPULATE] Failed to create divider for {anno['id']} ❌❌❌")
                                    else:
                                        # Regular annotation - use standard item creation
                                        new_item = QListWidgetItem()
                                        new_item.setData(Qt.ItemDataRole.UserRole, anno['id'])
                                        order_list.addItem(new_item)
                                        
                                        # Create widget with the appropriate text (use storyboard text if available for headers)
                                        if 'storyboard' in anno and 'text' in anno['storyboard']:
                                            display_text = anno['storyboard']['text']
                                            print(f"📝 [AI STORYBOARD] Using storyboard text with headers for {anno['id']}")
                                        else:
                                            display_text = anno.get('text', '').replace('\n', '<br>')
                                            print(f"📝 [AI STORYBOARD] Using original text for {anno['id']}")
                                        
                                        # Ensure newlines are converted to <br> tags if not already done
                                        if '\n' in display_text and '<br>' not in display_text:
                                            display_text = display_text.replace('\n', '<br>')
                                            print(f"🔄 [AI STORYBOARD] Converted newlines to <br> tags for {anno['id']}")
                                        
                                        notes = anno.get('notes', '')
                                        
                                        if hasattr(order_list, 'create_item_widget'):
                                            widget, label = order_list.create_item_widget(
                                                display_text,
                                                anno['id'],
                                                order_num + 1,  # Item number (1-based)
                                                notes
                                            )
                                            new_item.setSizeHint(widget.sizeHint())
                                            order_list.setItemWidget(new_item, widget)
                                            print(f"✅ [AI STORYBOARD] Created annotation widget for {anno['id']}")
                                        else:
                                            print(f"❌ [AI STORYBOARD] create_item_widget method not found on order_list")
                                
                                print(f"✨✨✨ [AI STORYBOARD] Added {len(sorted_annotations)} items to storyboard! ✨✨✨")
                            
                        except Exception as e:
                            print(f"❌❌❌ [AI STORYBOARD] Error in safe populate: {e} ❌❌❌")
                        finally:
                            # Clear the flag
                            if hasattr(self.main_window.storyboard_dialog, '_ai_refresh_in_progress'):
                                delattr(self.main_window.storyboard_dialog, '_ai_refresh_in_progress')
                                print(f"🛡️🛡️🛡️ [AI STORYBOARD] Cleared AI refresh flag 🛡️🛡️🛡️")
                    
                    QTimer.singleShot(100, safe_populate)
                    
                except Exception as e:
                    print(f"❌❌❌ [AI STORYBOARD] Error setting up safe refresh: {e} ❌❌❌")
                    
                print(f"✅✅✅ [AI STORYBOARD] Safe refresh triggered ✅✅✅")
            else:
                print(f"❌❌❌ [AI STORYBOARD] Storyboard dialog not available for refresh ❌❌❌")
            
            # Show success message
            print(f"🎉🎉🎉 [AI STORYBOARD] Showing success message... 🎉🎉🎉")
            QMessageBox.information(self, "Success", 
                f"Successfully applied ordering to {len(self.parsed_updates)} annotations.\n"
                "The storyboard has been updated.")
            
            self.accept()  # Close dialog
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply updates: {str(e)}")
    
    def ask_followup_question(self):
        """Handle followup questions for AI conversation"""
        followup_text = self.followup_input.toPlainText().strip()
        if not followup_text:
            return
        
        # Add user question to conversation history
        self.conversation_history.append({
            "role": "user", 
            "content": followup_text
        })
        
        # Build conversation context
        conversation_context = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in self.conversation_history[-3:]  # Last 3 exchanges
        ])
        
        # Create followup prompt with header/divider support
        use_headers = self.headers_checkbox.isChecked()
        use_dividers = self.dividers_checkbox.isChecked()
        use_length_limit = self.length_limit_checkbox.isChecked()
        target_minutes = self.length_minutes.value()
        target_seconds = self.length_seconds.value()
        total_target_seconds = (target_minutes * 60) + target_seconds
        
        # Calculate length constraint info for followup
        length_constraint_followup = ""
        if use_length_limit:
            target_duration_formatted = self.format_duration(total_target_seconds)
            target_word_count = int((total_target_seconds / 60) * 200)
            length_constraint_followup = f"\nSCRIPT LENGTH TARGET: {target_duration_formatted} (approximately {target_word_count} words)"
        
        followup_prompt = f"""Continue our conversation about organizing video script annotations.{length_constraint_followup}

PREVIOUS CONVERSATION:
{conversation_context}

CURRENT ANNOTATION DATA:
{self.format_annotations_for_ai()}

CURRENT ORGANIZATION:
{self.last_response}

USER'S NEW REQUEST:
{followup_text}

{f'''
ADVANCED FEATURES AVAILABLE:
{f"- Headers: annotation-id :: Order#X :: HEADER :: \"Title\" (use sparingly)" if use_headers else ""}
{f"- Dividers: DIVIDER :: \"Section Name\" :: Order#X :: #color" if use_dividers else ""}
''' if use_headers or use_dividers else ''}

Please provide a new organization based on the user's feedback. You can use the same annotation IDs{f", add headers," if use_headers else ""}{f" or create dividers" if use_dividers else ""} as needed.

Only provide the new ordering, no explanations."""
        
        # Clear followup input
        self.followup_input.clear()
        
        # Show progress and process
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.ask_followup_btn.setEnabled(False)
        self.status_label.setText("Processing followup question...")
        
        # Create fresh AI model and start processing
        self.ai_model = self.create_ai_model()
        if not self.ai_model:
            QMessageBox.warning(self, "Error", "AI model not configured.")
            return
            
        # Create and start worker thread
        use_streaming = self.streaming_checkbox.isChecked()
        self.worker_thread = AIWorkerThread(self.ai_model, followup_prompt, stream=use_streaming)
        self.worker_thread.response_received.connect(self.on_followup_response)
        self.worker_thread.response_chunk.connect(self.on_ai_response_chunk)
        self.worker_thread.error_occurred.connect(self.on_followup_error)
        self.worker_thread.start()
    
    def on_followup_response(self, response_text):
        """Handle followup AI response"""
        # Re-enable controls
        self.progress_bar.setVisible(False)
        self.ask_followup_btn.setEnabled(True)
        
        # Display response (streaming already handled chunks)
        if not self.streaming_checkbox.isChecked():
            self.debug_display.setPlainText(response_text)
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text
        })
        self.last_response = response_text
        
        # Parse the new response (reuse existing parsing logic)
        self.on_ai_response(response_text)
    
    def on_followup_error(self, error_message):
        """Handle followup AI error"""
        self.progress_bar.setVisible(False)
        self.ask_followup_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_message}")
        self.status_label.setStyleSheet("color: #EF4444;")
        QMessageBox.critical(self, "AI Error", f"Error: {error_message}")



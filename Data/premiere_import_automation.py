"""
Premiere Import Automation Module

Provides automated sequential processing of all annotations for import into Premiere Pro.
Handles drag-and-drop functionality with automatic progression through the storyboard.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QTextEdit, QProgressBar, QCheckBox, QSpacerItem, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QCursor
import time


class PremiereImportDialog(QDialog):
    """Main dialog for automated Premiere Pro import process"""
    
    # Signals
    nextAnnotationRequested = pyqtSignal()  # Signal when user clicks Next Annotation
    previousAnnotationRequested = pyqtSignal(int)  # Signal when user clicks Previous Annotation (with index)
    processCompleted = pyqtSignal()         # Signal when all annotations are processed
    
    def __init__(self, total_annotations, parent=None):
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.total_annotations = total_annotations
        self.current_annotation_index = 0
        self.processed_count = 0
        self.skipped_count = 0
        self.is_processing = False
        
        self.setupUI()
        self.setWindowTitle("Premiere Pro Import Automation")
        self.setFixedSize(600, 450)
        self.centerOnScreen()
        
        # Ensure it stays on top and is visible
        self.raise_()
        self.activateWindow()
        
    def setupUI(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Premiere Pro Import Automation")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Explanation text
        explanation = QLabel()
        explanation.setWordWrap(True)
        explanation.setStyleSheet("""
            QLabel {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        explanation.setText("""🎬 POSITION THIS DIALOG OVER PREMIERE WINDOW 🎬

Quick Setup:
1. Make sure Premiere Pro is open
2. Drag this dialog over Premiere Pro window
3. Click "Begin Process" to start

How it works: Each annotation will be automatically searched in Premiere. Handle any segment dialogs that appear, then click "Next Annotation" to continue.""")
        layout.addWidget(explanation)
        
        # Progress section
        progress_layout = QVBoxLayout()
        
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(self.total_annotations)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        # Progress text
        self.progress_text = QLabel(f"0 of {self.total_annotations} annotations processed")
        self.progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_text.setStyleSheet("font-size: 12px; color: #6c757d;")
        progress_layout.addWidget(self.progress_text)
        
        layout.addLayout(progress_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.begin_btn = QPushButton("Begin Process")
        self.begin_btn.setFixedSize(120, 40)
        self.begin_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.begin_btn.clicked.connect(self.beginProcess)
        button_layout.addWidget(self.begin_btn)
        
        self.next_btn = QPushButton("Next Annotation")
        self.next_btn.setFixedSize(120, 40)
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e7e34;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.next_btn.clicked.connect(self.nextAnnotation)
        self.next_btn.hide()  # Hidden until process starts
        button_layout.addWidget(self.next_btn)
        
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setFixedSize(80, 40)
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.skip_btn.clicked.connect(self.skipCurrentAnnotation)
        self.skip_btn.hide()  # Hidden until process starts
        button_layout.addWidget(self.skip_btn)
        
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(80, 40)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
    def centerOnScreen(self):
        """Center the dialog on the screen"""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QCursor
        
        cursor_pos = QCursor.pos()
        for screen in QApplication.screens():
            if screen.geometry().contains(cursor_pos):
                screen_center = screen.geometry().center()
                dialog_rect = self.rect()
                dialog_rect.moveCenter(screen_center)
                self.move(dialog_rect.topLeft())
                return
                
        # Fallback to primary screen
        primary_screen = QApplication.primaryScreen()
        screen_center = primary_screen.geometry().center()
        dialog_rect = self.rect()
        dialog_rect.moveCenter(screen_center)
        self.move(dialog_rect.topLeft())
        
    def beginProcess(self):
        """Start the automation process"""
        self.is_processing = True
        self.current_annotation_index = 0
        
        # Update UI
        self.begin_btn.hide()
        self.next_btn.show()
        self.skip_btn.show()
        
        # Trigger the first annotation
        self.nextAnnotationRequested.emit()
        
    def nextAnnotation(self):
        """Move to the next annotation"""
        self.processed_count += 1
        
        # Update progress
        self.progress_bar.setValue(self.processed_count)
        self.progress_text.setText(f"{self.processed_count} of {self.total_annotations} annotations processed")
        
        # Always emit the signal - let the main script handle completion
        self.nextAnnotationRequested.emit()
            
    def skipCurrentAnnotation(self):
        """Skip the current annotation (for dividers, etc.)"""
        self.skipped_count += 1
        self.nextAnnotation()  # Still advance the counter
        
    def completeProcess(self):
        """Complete the automation process"""
        self.is_processing = False
        
        # Hide next button, show close button
        self.next_btn.hide()
        self.skip_btn.hide()
        self.cancel_btn.setText("Close")
        
        self.processCompleted.emit()
        
    def getCurrentAnnotationIndex(self):
        """Get the current annotation index being processed"""
        return self.current_annotation_index
        
        
    def skipCurrentAnnotation(self):
        """Skip the current annotation and move to next"""
        self.skipped_count += 1
        self.nextAnnotation()  # Still advance the counter
        


class TranscriptRequiredDialog(QDialog):
    """Dialog shown when full transcript is required for Premiere import"""
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(True)
        self.result_action = "cancel"  # Default action
        
        self.setFixedSize(550, 400)
        self.setupUI()
        self.centerOnCursorScreen()
    
    def setupUI(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("Full Transcript Required")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #dc3545;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title)
        
        # Explanation text
        explanation = QTextEdit()
        explanation.setReadOnly(True)
        explanation.setFixedHeight(200)
        explanation.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        explanation.setHtml("""
        <p><strong>The Premiere import process requires you to export Premiere's "Transcript" as a .txt file to ensure precise text matching in Premiere Pro.</strong></p>
        
        <p><strong>To proceed:</strong></p>
        <ol>
        <li>First ensure all audio that needs to be matched is in one sequence.</li>
        <li>Navigate to "Window > Text"</li>
        <li>In the "Text" Panel, click on the "Transcript" tab</li>
        <li>Click the top-right corner action menu and press Export > Export to text file...</li>
        <li>In Scriptoria's Script Editor, select "Add Full Transcription" and browse and select the created text file.</li>
        </ol>
        """)
        layout.addWidget(explanation)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Add Full Transcription button
        add_transcript_btn = QPushButton("Add Full Transcription")
        add_transcript_btn.setFixedSize(180, 40)
        add_transcript_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        add_transcript_btn.clicked.connect(self.addTranscription)
        button_layout.addWidget(add_transcript_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Style the dialog
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border-radius: 8px;
                border: 2px solid #dc3545;
            }
        """)
    
    def centerOnCursorScreen(self):
        """Center the dialog on the screen where the cursor is currently located"""
        from PyQt6.QtWidgets import QApplication
        
        cursor_pos = QCursor.pos()
        
        # Find which screen contains the cursor
        for screen in QApplication.screens():
            if screen.geometry().contains(cursor_pos):
                screen_center = screen.geometry().center()
                dialog_rect = self.rect()
                dialog_rect.moveCenter(screen_center)
                self.move(dialog_rect.topLeft())
                return
        
        # Fallback: center on primary screen if cursor screen not found
        primary_screen = QApplication.primaryScreen()
        screen_center = primary_screen.geometry().center()
        dialog_rect = self.rect()
        dialog_rect.moveCenter(screen_center)
        self.move(dialog_rect.topLeft())
    
    def addTranscription(self):
        """Handle add transcription button click"""
        self.result_action = "add_transcription"
        self.accept()
    
    def getAction(self):
        """Return the selected action"""
        return self.result_action
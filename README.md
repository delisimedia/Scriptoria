### **v3.5.1**

*Focus: Transcript creation preview and AI query dialog improvements.*

* New toggleable **"View Preview"** feature in the Create Transcript tab

  * Lets you preview the final transcript before creation
* Replaced default ibeam cursor in `QTextEdit` within **CreateTranscriptTextEdit**

  * Now uses a custom pixmap `paintEvent` ibeam cursor for better visibility and contrast
* **AIQueryDialog** improved UX and functionality:

  * Efficiently maintains context when handling follow-up questions
  * New **"Use Full Transcript"** checkbox to apply the entire transcript as context
  * Can now provide transcript quotes in hyperlinks that directly scroll to and locate them in the DOM

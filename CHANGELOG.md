# Full Changelog v3.X.X

### **v3.5.0**

*Focus: Major experimental AI features and Gemini integration improvements.*

* New experimental **"Generate Script"** option in the script editor action menu

  * Uses Gemini to populate the script editor with an arranged order of highlighted annotations
  * Can add its own dividers and headers if the user requests
* New experimental **"Generate Annotations"** option to automatically identify, highlight, and generate annotations
* New experimental **"Generate Notes"** option to generate notes and commentary on annotations
* New experimental **"Ask Gemini (Annotations)"** for asking questions and finding specific annotations with AI
* Added tilde hotkey to open **Ask Gemini (Full Chat)**
* Consolidated Preset Prompt ability into the main Ask Gemini full AI chat dialog

  * Removed the original dialog
* Added a separate **manage preset prompt dialog** to edit and create preset prompts
* Improved the markdown → HTML conversion during streaming and fixed formatting issues
* New **AI main window menu bar** consolidating several AI options
* Improved how Ask Gemini handles context when asking follow-ups (better token efficiency)
* Tweaked font and style of AI chat window
* AI chat now allows **"update chat context"** instead of clearing and rebuilding every time
* Fixed bug with `clear_final_order` not properly clearing/resetting metadata from annotations
* Other UX improvements to AI chat functionality

---

### **v3.4.5**

*Focus: Stability fixes, improved context handling, and TagListDialog enhancements.*

* Fixed dual clear/rebuild via `renumber_items` in script editor
* `dropEvent` no longer clears/rebuilds in script editor
* `toggle_theme_view` no longer requires `update_theme_view`
* Adding/removing headers optimized to not clear/rebuild
* Fixed major bug with reassignment context flag causing update issues
* New **TagListDialog** preset saving/loading functionality
* Improvements and optimization in context matching strategy in `improve_strikethrough_display`
* Tab overflow handled with a custom horizontal scrollbar
* On startup, `update_theme_view` captured by load progress dialog
* Line breaks in annotations carried over into script editor
* Tags moved to bottom-left corner of widget
* Speech-title truncation expanded from 50 → 125 chars
* Fixed bugs with item label and widget sizing (strikethroughs, headers)
* Fixed bug with tooltip expansion/pinning not triggering
* Fixed bug with filtering logic in theme view
* Fixed bug with undo functionality
* Fixed sticky headers persisting between sessions
* Fixed bug breaking HTML exports
* Fixed bug where gridview reorder in TagListDialog wasn’t updating visually
* Fixed bug where partial `remove_highlight` didn’t update annotations properly
* Fixed bugs with drag/drop in TagListDialog, added drop indicators
* Fixed bug where empty content placeholders in theme view didn’t trigger correctly
* Tags in tooltip are hoverable/selectable for filtering
* Tooltip scrolling no longer scrolls transcript
* Sort Annotations Chronologically now applies to all tabs
* Significant UX improvements to Process Captions tab
* And several other bug fixes

---

### **v3.4.0**

*Focus: Secondary themes, filtering improvements, and annotation UI upgrades.*

* Major Feature: **Secondary Themes**

  * Annotations can now contain multiple themes (Primary + Secondary)
  * New `secondary_scenes` and `data-secondary-scenes` attributes
  * New secondary scenes context menu option
* Theme filtering in DOM now accounts for secondary themes
* Theme filtering system added to Theme View
* Double-clicking on tabs filters the relevant theme
* Annotations in theme view show new indicators for secondary scenes
* Fixed scroll-to/select annotation in web view highlighting
* Fixed bugs in Edit Themes (renaming persistence, sticky headers)
* Tooltips now display theme colors and secondary scenes
* Fixed `remove_highlight` bug with missing `dbclick` listener
* Fixed edge case bugs when editing themes with filtering active
* UI/UX improvements to script editor + theme view widgets
* Replaced unicode favorites star with paintEvents
* Several other UI/UX improvements

---

### **v3.3.5**

*Focus: Navigation and scrollbar indicators.*

* New annotation indicators in scrollbar during web view filtering
* New "navigate next" and "navigate previous annotation" during filtering

---

### **v3.3.4**

*Focus: Performance optimization, drag/drop improvements, and new features in script editor.*

* Major optimization: `update_theme_view` no longer clears/rebuilds all tabs → much faster
* Adjusted methods to be compatible with new logic
* Improved mobile layout support for exported HTML
* Fixed bugs with exported HTML
* Exporting HTML now navigates directly to folder
* Added safeguards to `save_session` to prevent corruption if closed mid-save
* Added hover drag-enter overlay in Script Editor
* Drop indicators now correctly show during external drags
* Fixed sync issues with Script Editor and Theme View under filters
* Fixed placeholder text not showing in empty script editor
* New batch multi-select annotation removal in script editor
* Fixed missing context menu on script editor drag handle
* Fixed custom drop indicator positioning bugs
* Fixed annotation lookup in theme view failing when toggling view

---

### **v3.3.3**

*Focus: Sticky header overhaul and DOM filtering improvements.*

* Overhauled sticky theme header (JS-injected into web view)
* Sticky header now has settings menu and can be resized
* Sticky header can now be hidden/shown
* New **tag filtering** JS dialog in DOM
* New favorites/used JS filtering in DOM sticky header
* Options to refresh/clear DOM filters from sticky header menu
* Critical fix: removed unnecessary `update_theme_view` call in reassignment logic
* Improved session load times
* Fixed bug with bookmarks not loading on startup
* Fixed tooltip flashing on session load
* Fixed bugs with double-click annotation selection not persisting
* Fixed bug with previous selections not clearing on new annotation
* Updated HTML export to include tooltip/sticky header filtering changes
* Fixed bug where `save_session` saved hidden states caused by filtering

---

### **v3.3.2**

*Focus: Tag management overhaul and UI consistency.*

* New **Filter Headers** dialog (filter by `scene_title`)
* TagListDialog completely overhauled for better UX
* Tag renaming/deletion now updates all instances across DOM, theme view, storyboard
* `update_theme_view` now blocks UI to prevent errors
* Fixed tag and speech-title layout issues
* Tags truncate and fill available space
* Removed QTimer reliance (faster scroll/tooltips after load)
* `updateitemsizes` now runs in separate thread for UI responsiveness
* Tags in storyboard sync with updates in theme view
* Double-click selection in DOM now selects full annotation
* Selection highlight transparent to show highlight colors
* New DOM context menu options for navigating to storyboard/theme view
* Tooltips display speech-title of annotation
* Improved tooltip UI/UX
* Other minor UI/UX improvements

---

### **v3.3.1**

*Focus: Filtering/search fixes and state preservation.*

* Removed `update_theme_view` reliance when adding annotations while filtering/searching
* `populate_order_list` now fully synchronous in reassignment handling
* Fixed placeholders not updating under active filtering/searching
* Improved logic in `update_theme_view` to handle active filtering
* Fixed bugs with toggle\_theme\_view placeholder getting stuck
* Removed redundant logic in `populate_order_list`
* Added annotation selection logic in reassignment + removal handling
* Other minor UI/UX bug fixes in ThemeViewSearch
* Project loading dialog now modal and centered

---

### **v3.3.0**

*Focus: Tagging, filtering, and efficiency improvements.*

* Favorites/used toggling now synced across theme view + storyboard
* Eliminated unnecessary `update_theme_view` calls (faster)
* Searching/filtering no longer tied to expensive updates → faster
* Tags are now annotation data attributes and reflected in widgets
* New **scene-title** attribute for annotations
* New Pin/Expand buttons in tooltip
* New **Filter Tags** dialog in ThemeViewSearch
* Many UX improvements to tagging process (grid layouts, checkboxes, search, etc.)
* Added alphabetical sort button to tag list
* Progress overlay only during `toggle_theme_view`, not normal updates
* Newly added annotations auto-selected in theme view

---

### **v3.2.2**

*Focus: Performance and targeted annotation handling.*

* Fixed bug with bookmark description corrupting HTML
* Targeted annotation removal (no full theme view rebuilds)
* Faster theme view updates (no tab switching during finalization)
* Progress overlay added to `update_theme_view`

---

### **v3.2.1**

*Focus: Preset prompts and Gemini updates.*

* Added Preset Prompt option to Scriptoria AI
* Scroll position restored when favoriting in AnnotationListWidget
* Changed model reference from `germini-2.5-flash-lite-preview-06-17` → `germini-2.5-flash-lite`

---

### **v3.2.0**

*Focus: Sticky headers for transcripts and bug fixes.*

* Added sticky headers in transcript web view for themes
* Themes in sticky headers toggle to hide/unhide highlights
* Added `changes_pending` call to Edit Themes
* Fixed critical bugs in strikethrough handling

---

### **v3.1.7**

*Focus: Drag/drop styling and caption processing.*

* Added new pixmap drag/drop styling to AnnotationListWidget
* Alt+drag annotations from AnnotationListWidget
* Fixed add highlight hotkeys in TranscriptWebView
* Fixed formatting bugs in CreateTranscriptTextEdit and paste handling
* Copy Captions directly over highlighted text in TranscriptWebView
* Process Captions tab now accepts multiple `.txt` files in one drop
* Process Captions tab has new search bar

---

### **v3.1.6**

*Focus: Hotkey change and splash screen.*

* Changed alt+drag action → `Ctrl+Shift+F` (due to Adobe Premiere shortcut conflict)
* New splash screen image and faster startup logic

---

### **v3.1.5**

*Focus: Premiere integration and drag/drop improvements.*

* Major feature: drag/drop items from Script Editor directly into Premiere Pro
* Improved drag/drop visuals with new pixmaps and indicators
* Edge auto-scroll in script editor has greater trigger range
* Copy Captions improved for Premiere matching
* Bug fixes and AI voice chat improvements

---

### **v3.1.1**

*Focus: AI voice chat and quick explain options.*

* Added AI voice chat option
* Added Quick Explain AI chat option
* Bug fixes with AI functionality

---

### **v3.1.0**

*Focus: AskAI integration and live Gemini updates.*

* Added AskAI options in DOM context menu (select text → ask Gemini)
* Quick Summary and Chat with AI options
* Gemini responses now stream live as chunks
* New API Key management dialog
* Settings dialog added to File menu

---

### **v3.0.7**

*Focus: Stability and annotation performance.*

* Fixed duplicate updates in Script Editor
* Added annotation lookup cache (O(1) performance)
* Fixed stuck cursor bug in script editor
* Taskbar icon fixes for floating widgets
* Improved taskbar behavior for window restoration

---

### **v3.0.6**

*Focus: Bug fixes and Gemini update.*

* Fixed annotation sizing bug in theme view
* Script Editor no longer minimizes with main window
* Updated Gemini model

---

### **v3.0.5**

*Focus: Copy caption improvements.*

* New copy caption option in storyboard for Premiere compatibility
* Fixed missing visual selection in compact storyboard mode
* Removed Gemini 2.5 Pro from API dropdown

---

### **v3.0.4**

*Focus: Presets and theme handling.*

* Removed standard preset button (replaced with default theme preset)
* Create New Themes is now default in convert text dialog
* Manage Themes/Presets dialog now supports drag/reorder
* Fixed tooltip trigger bug
* Fixed disappearing text on header hover

---

### **v3.0.3**

*Focus: Script Editor enhancements and Gemini updates.*

* Added collapsible floating widget for Script Editor
* New "Copy Script Editor Text" option
* Optimizations to AnnotationListWidget
* Reduced visual updates in theme view
* Fixed bugs in highlight removal processes
* Fixed missing theme view navigation in DOM tooltips
* Updated Gemini API models
* Can now cancel Gemini API calls mid-processing
* Token calculations now round to whole numbers
* Thinking budget defaults to 8000
* Adjusted layout of copy transcript button

---

### **v3.0.2**

*Focus: Navigation and theme view fixes.*

* Added navigate-to-annotation in storyboard from DOM + theme view
* More prominent button for theme view navigation in tooltip
* Fixed window not maximizing on startup
* Fixed broken navigation when storyboard/theme view created mid-session

---

### **v3.0.1**

*Focus: Environment updates and minor fixes.*

* Downgraded to PyQt 6.8.0 (6.9.0 issues)
* Upgraded Python environment to 3.13.3
* Fixed margin and button width issues

---

### **Scriptoria v3.0 Changelog**

*Focus: Major overhaul with syntax highlighting, enhanced script editor, advanced annotation management, and UI redesign.*

#### Major New Features

* **Syntax Highlighting System**

  * Live text formatting (headers, dividers, orphaned text detection)
  * Real-time analysis with auto-fix options

* **Enhanced Script Editor & Storyboard System**

  * Word counter, script timer, search, PDF export
  * Text-to-speech, modern design, improved rendering

* **Storyboard Enhancements**

  * Advanced strikethrough system, mark all used/unused
  * Improved drag/drop and action menu
  * Red overlay preview for highlight removal

* **Advanced Annotation Management**

  * Multi-instance strikethrough dialog
  * Glasgow Block System (prevents overlap corruption)
  * Enhanced conflict resolution and state preservation

* **Import & Processing Tools**

  * EPUB import, PDF extraction, enhanced captions tools

* **Advanced Editing Features**

  * Auto wrap headers, paste formatting dialog
  * Preserve header options, reflow tools

* **User Interface Enhancements**

  * Interactive tooltips, table of contents, auto-fill footnotes
  * Enhanced DOM context menu, streamlined UI

#### Major Improvements & Fixes

* **Performance & Stability**

  * Syntax highlighter optimization
  * Better memory management and load feedback
  * Batch processing efficiency

* **Annotation & Highlighting**

  * Conflict resolution dialogs
  * Auto-fix options and better state preservation

* **User Experience**

  * Full dark mode consistency
  * Consolidated UI, improved error messages
  * Enhanced context menus

* **Visual & Interface Updates**

  * Cleaner design, improved typography, dynamic highlights
  * Streamlined toolbar and progress indicators

* **Notable Bug Fixes**

  * Strikethrough overhaul (fixed corruption)
  * Window management fixes
  * Annotation preservation during edits
  * Improved navigation and scroll memory

<img src="Img/splash-screen.png" alt="Splash Screen of Scriptoria" width="300" height="300">
# Scriptoria: A Text-Based Video Editing Companion, and General Purpose EReader with Theme-Centered Highlighting and Annotating, Gemini API integration

Scriptoria provides a text-based workflow for video editors to use AI to structure video captions into a structured and interactive text transcript. It is also a versatile tool for marking up and analyzing long-form documents like books and articles. Imported text gets automatically or manually formatted via a simple syntax system into a Scriptoria based format. Users then turn this into transcripts with custom themes/tags and highlight colors. Standout features include a Script Editor to create and arrange scripts, a robust tagging and filtering system, an interactive transcript with JS embedded functionality like tooltips that can be exported and delivered to clients as an HTML file, Adobe Premiere Pro drag and drop, Gemini API integration, and much more.

## The Main Problem It is Intended to Solve

For video editors working with interviews, documentaries, or event footage, the process of finding the right soundbites ("paper editing") can be slow and cumbersome. It often involves scrubbing through hours of footage or manually cross-referencing paper transcripts with timestamps. Video editors, like Adobe Premiere Pro are designed around video editing and as such the ability to structure narratives within the program is weighed down by a UI and UX that is designed to interact with video first and foremost. Not only that it is CPU and GPU intensive. Scriptoria circumvents that overhead and is designed to develop scripts and narrative in a more intuitive way.

Scriptoria streamlines this by allowing you to work with the transcript as the central element, giving you a bird's-eye view of your content and enabling you to build a story structure quickly and intuitively.

## How It Works: The Core Workflow

1.  **Process & Stylize Transcript:** Start with any text source. For video-editing, generate a caption text file in Adobe Premiere Pro (for example) and paste these captions into the Process Captions tab. Clean it and process it in an LLM of your choosing or directly in software with the integrated **Gemini API** to automatically structure the captions into a readable format using powerful AI prompts. You can also import text from **EPUBs**. Default prompts are provided, and a system is in place for you to write and store your own custom preset prompts.

2.  **Markup with Themes:** Instead of generic highlighting, you create custom **Themes** (e.g., "Emotional Moment," "Challenges," "Solutions"), each with a unique color and a keyboard hotkey (1-9, 0, -, +). As you read the transcript, select text and press the corresponding key to tag segments by theme. You can also create tags, secondary themes, footnotes, set favorites, and mark segments as "used" if you've already used it in the video. A robust filtering system is designed to make it easy to find text according to these metadata categories.

3.  **Arrange in the Script Editor:** Every highlight you create becomes a movable block or **Annotation** in the **Theme Panel**. Here, you can drag and drop these blocks into the **Script Editor** to arrange your narrative. You can also **strikethrough** parts of text that you will cut out, mark segments as "used" by your edit, see estimated script length in minutes, and export the script as a PDF file to share.

4.  **Integrate with Premiere Pro:** Once your narrative is structured, **Alt+Drag** a text block from Scriptoria's Script Editor and drop it onto your Premiere Pro project window. This action simulates a search command, which locates and scrubs to in the timeline that exact text segment within your Premiere sequence, ready for you to splice into your timeline.

## A General-Purpose Tool for Text

While designed for video editors, Scriptoria's feature set makes it a capable tool for anyone working with long-form text:

*   **E-Reader & Study Tool:** Import EPUBs directly into the program. 
*   **Content Curation:** Organize research and articles by theme for easy reference.
*   **Qualitative Analysis:** Use the tagging and filtering system to analyze text-based data for patterns.

## Key Features

*   **🤖 AI-Powered Caption Processing:** Utilize the embedded Gemini API to transform raw, timecoded caption files into clean, readable text formatted with Scriptoria's syntax. The tool includes default prompts optimized for interviews, and allows you to **create, save, and manage your own custom prompts** for any project.
*   **🎨 Thematic Highlighting:** Create up to 12 distinct **Themes**, each with its own color and hotkey. Annotations can also be assigned **Secondary Themes** for more detailed categorization.
*   **🏷️ Robust Tagging System:** Add an unlimited number of searchable tags (e.g., `#b-roll`, `#key-moment`) to any highlight for precise organization.
*   **⚙️ Preset System:** Save and load custom sets of Themes and Tags to maintain consistency across projects.
*   **🌐 Interactive HTML Export:** Export your final, stylized transcript as a self-contained interactive HTML file. This export includes a functional navigation sidebar, search, and filtering, making it ideal for client reviews.
*   **🔍 Advanced Filtering:** Filter your entire transcript to show only relevant highlights. You can filter by one or more **Themes**, **Tags**, **Favorites**, or **Used/Unused** status.
*   **✨ Intelligent Highlighting Engine:** Scriptoria features a robust system for managing highlights. When you modify or remove a portion of a highlight, it intelligently creates new, distinct annotations for the remaining parts, preserving all associated metadata like notes and tags.
*   **🧠 Integrated AI Assistant:** Go deeper into your text. Highlight any passage in the transcript viewer and ask questions directly via an embedded Gemini API interface. Get quick summaries, explanations, historical context, or simplify complex language on the fly, without ever leaving the application.

## Who Is This For?

*   Video editors and documentary filmmakers.
*   General readers who are reading complex text
*   Students and academics

## Installation & Setup

**Windows:**
Download the latest release from the [Releases page](https://github.com/your-username/Scriptoria/releases) and run the installer.

**macOS:**
This application is currently built for Windows and a macOS version is not available.


## Dependencies

This project utilizes the following open-source libraries:

*   **PyQt6**: GUI toolkit. Licensed under GPLv3.
    *   [PyQt6 Website](https://www.riverbankcomputing.com/software/pyqt/intro)
    *   License: `LICENSES/GPLv3.txt`

*   **pyaudio**: Python bindings for PortAudio. Licensed under MIT License.
    *   [PyAudio PyPI](https://pypi.org/project/PyAudio/)
    *   License: `LICENSES/MIT.txt`

*   **BeautifulSoup4 (bs4)**: HTML/XML parser. Licensed under MIT License.
    *   [BeautifulSoup4 PyPI](https://pypi.org/project/beautifulsoup4/)
    *   License: `LICENSES/MIT.txt`

*   **google-generativeai**: Google Generative AI Python SDK. Licensed under Apache 2.0 License.
    *   [google-generativeai PyPI](https://pypi.org/project/google-generativeai/)
    *   License: `LICENSES/APACHE2.0.txt`

*   **PyMuPDF (fitz)**: PDF and XPS document toolkit. Licensed under AGPLv3.0.
    *   [PyMuPDF Website](https://pymupdf.readthedocs.io/en/latest/)
    *   License: `LICENSES/AGPLv3.txt`

*   **pdfminer.six**: PDF parser and analyzer. Licensed under MIT License.
    *   [pdfminer.six PyPI](https://pypi.org/project/pdfminer.six/)
    *   License: `LICENSES/MIT.txt`

---
**Note on Licenses:**
This project is open-source and uses libraries under various open-source licenses. Please refer to the `LICENSES` directory for the full text of each license.



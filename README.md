   <div align="center">
     <img src="Img/splash-screen.png" alt="Splash Screen of Scriptoria" width="300" height="300">
   </div>

# Scriptoria: A Text-Based Video Editing Companion and General Purpose EReader with Theme-Centered Highlighting and Annotating, Gemini API integration

Scriptoria is primarily designed to create a text-based workflow for video editors that involves using AI to structure video captions into an interactive HTML text transcript. The transcript can then be marked up and arranged into a script to aide with video outlining and narrative structuring via theme-based highlighting, tagging, and note taking. There is functionality that allows for your script to easily link back with the captions in Adobe Premiere Pro, and a customized Gemini API assistant. There is also a robust filtering system to make it easy to find and locate specific highlights according to theme, tags, favorite, and used (whether it has been used yet in the video) status.

Secondarily it is also a versatile tool for reading and marking up any long-form document like books and articles. It has import support for EPUB files and any text you copy from the internet. Imported text gets automatically or manually formatted via a simple syntax system that Scriptoria recognizes. You can make use of all the various analytical features in the program to use it as an advanced e-reader.

<div style="text-align: center;">
  <img src="screenshot.png" width="1280" height="720" alt="Screenshot">
</div>

## What it solves

For video editors working with interviews, documentaries, or event footage, the process of finding the right soundbites ("paper editing") can be slow and cumbersome. It often involves scrubbing through hours of footage. Video editors, like Adobe Premiere Pro are designed around video editing and as such the ability to structure narratives within the program is weighed down by a UI and UX that is designed to interact with video first and foremost. Not only that it is CPU and GPU intensive. Scriptoria circumvents that overhead and is designed to develop scripts and narrative in a more intuitive way.

Scriptoria streamlines this by allowing you to work with the transcript as the central element, giving you a bird's-eye view of your content and enabling you to build a story structure quickly and intuitively.

## Core workflow for video editors:

1.  **Process & Stylize Transcript:** Start with any text source. For video-editing, generate a caption text file in Adobe Premiere Pro (for example) and paste these captions into the Process Captions tab. Process it by using the program provided prompt in an LLM of your choosing or directly in software with the integrated **Gemini API** to automatically structure the captions into Scriptoria's accepted syntax formatting. You can also import text from **EPUBs** or from the internet, and Scriptoria will automatically format based on the embedded HTML or Markdown tags in the epub file or clipboard. Default prompts are provided, and a system is in place for you to write and store your own custom preset prompts.

2.  **Markup with Themes:** Instead of generic highlighting, you create custom **Themes** (e.g., "Emotional Moment," "Challenges," "Solutions"), each with a unique color and a keyboard hotkey (1-9, 0, -, +). As you read the transcript, select text and highlight segments by theme. You can also create tags, secondary themes, footnotes, set favorites, and mark segments as "used" if you've already used it in the video. A robust filtering system is designed to make it easy to find text according to these metadata categories.

3.  **Arrange in the Script Editor:** Every highlight you create becomes a movable block or **Annotation** in the **Theme Panel**. Here, you can drag and drop these blocks into the **Script Editor** to arrange your narrative. You can also **strikethrough** parts of text that you will cut out, mark segments as "used" by your edit, see estimated script length in minutes, and export the script as a PDF file to share.

4.  **Integrate with Premiere Pro:** Once your narrative is structured, **Alt+Drag** a text block from Scriptoria's Script Editor and drop it onto your Premiere Pro project window. This action simulates a search command, which locates and scrubs to in the timeline that exact text segment within your Premiere sequence, ready for you to splice into your timeline.

## A General-Purpose Tool for Text

While designed for video editors, Scriptoria's feature set makes it a capable tool for anyone working with long-form text:

*   **E-Reader & Study Tool:** Import EPUBs directly into the program. 
*   **Academics:** Organize research and articles with theme-based highlighting and notes/commentary for easy reference.

## Key Features

*   **Re-format captions to readable paragraph form** Utilize the embedded Gemini API or use the provided prompt to transform raw, timecoded caption files into clean, readable text formatted with Scriptoria's syntax. The tool includes default prompts optimized for interviews, and allows you to **create, save, and manage your own custom prompts** 
*   **Thematic Highlighting:** Create up to 12 distinct **Themes**, each with its own color and hotkey. Annotations can also be assigned **Secondary Themes** for more detailed categorization.
*   **Robust Tagging System:** Add an unlimited number of searchable tags (e.g., `#Strong-Closing-Line`, `#key-moment`) to any highlight for precise organization.
*   **Preset System:** Save and load custom sets of Themes and Tags to maintain consistency across projects.
*   **Interactive HTML Export:** Export your final, stylized transcript as a self-contained interactive HTML file.
*   **Advanced Filtering:** Filter your entire transcript to show only relevant highlights. 
*   **Integrated Gemini Assistant:** Highlight any passage in the transcript viewer and ask questions directly via an embedded Gemini API interface. Or use it to completely assemble scripts for you.

## Installation & Setup

**Windows:**
Download the latest release from the [Releases page](https://github.com/delisimedia/Scriptoria/releases) and run the installer.

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

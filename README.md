Of course. Here is the updated GitHub README, integrating the AI features into the clear, direct structure we established.

---

# Scriptoria: A Text-Based Editing Companion for Adobe Premiere Pro

Scriptoria provides a text-based workflow for video editors to structure narratives from transcripts, seamlessly integrating with Adobe Premiere Pro. It is also a versatile tool for marking up and analyzing long-form documents like books and articles.

![Scriptoria Workflow Demo](https://raw.githubusercontent.com/anthony-delisi/Scriptoria/main/Img/scriptoria-workflow-demo.gif)
*(This GIF demonstrates the core workflow: processing a transcript, highlighting by theme, arranging in the Script Editor, and dragging directly into Premiere Pro.)*

## The Problem It Solves

For video editors working with interviews, documentaries, or event footage, the process of finding the right soundbites ("paper editing") can be slow and cumbersome. It often involves scrubbing through hours of footage or manually cross-referencing paper transcripts with timestamps.

Scriptoria streamlines this by allowing you to work with the transcript as the central element, giving you a bird's-eye view of your content and enabling you to build a story structure quickly and intuitively.

## How It Works: The Core Workflow

1.  **Process & Stylize Transcript:** Start with any text source. For video captions, you can use the integrated **Gemini API** to automatically clean timecodes and structure the dialogue into a readable format using powerful AI prompts. You can also import text from **PDFs** and **EPUBs**. Scriptoria's tools convert this raw text into a clean, formatted, and interactive HTML document.

2.  **Markup with Themes:** Instead of generic highlighting, you create custom **Themes** (e.g., "Key Point," "Emotional Moment," "Technical Detail"), each with a unique color and a keyboard hotkey (1-9, 0, -, +). As you read the transcript, select text and press the corresponding key to tag segments by theme.

3.  **Arrange in the Script Editor:** Every highlight you create becomes a movable block in the **Script Editor**. Here, you can drag and drop these blocks to arrange your narrative. You can also edit the text, add director's notes, mark segments as "used" in your edit, and refine the story's flow.

4.  **Integrate with Premiere Pro:** Once your narrative is structured, **Alt+Drag** a text block from Scriptoria's Script Editor and drop it onto your Premiere Pro project window. This action simulates a search command, which locates that exact text segment within your Premiere sequence's captions, ready for you to splice into your timeline.

## A General-Purpose Tool for Text

While designed for video editors, Scriptoria's feature set makes it a capable tool for anyone working with long-form text:

*   **E-Reader & Study Tool:** Import PDFs and EPUBs to highlight, tag, and annotate books and academic papers.
*   **Content Curation:** Organize research and articles by theme for easy reference.
*   **Qualitative Analysis:** Use the tagging and filtering system to analyze text-based data for patterns.

## Key Features

*   **🤖 AI-Powered Caption Processing:** Utilize the embedded Gemini API to transform raw, timecoded caption files into clean, readable text formatted with Scriptoria's syntax. The tool includes default prompts optimized for interviews, and allows you to **create, save, and manage your own custom prompts** for any project.
*   **🧠 Integrated AI Assistant:** Go deeper into your text. Highlight any passage in the transcript viewer and ask questions directly via an embedded Gemini API interface. Get quick summaries, explanations, historical context, or simplify complex language on the fly, without ever leaving the application.
*   **🎨 Thematic Highlighting:** Create up to 12 distinct **Themes**, each with its own color and hotkey. Annotations can also be assigned **Secondary Themes** for more detailed categorization.
*   **🏷️ Robust Tagging System:** Add an unlimited number of searchable tags (e.g., `#b-roll`, `#key-moment`) to any highlight for precise organization.
*   **⚙️ Preset System:** Save and load custom sets of Themes and Tags to maintain consistency across projects.
*   **🌐 Interactive HTML Export:** Export your final, stylized transcript as a self-contained interactive HTML file. This export includes a functional navigation sidebar, search, and filtering, making it ideal for client reviews.
*   **🔍 Advanced Filtering:** Filter your entire transcript to show only relevant highlights. You can filter by one or more **Themes**, **Tags**, **Favorites**, or **Used/Unused** status.
*   **✨ Intelligent Highlighting Engine:** Scriptoria features a robust system for managing highlights. When you modify or remove a portion of a highlight, it intelligently creates new, distinct annotations for the remaining parts, preserving all associated metadata like notes and tags.

## Who Is This For?

*   Video editors and documentary filmmakers.
*   Content creators and YouTubers structuring narratives from long recordings.
*   Journalists and researchers analyzing interview transcripts.
*   Students and academics marking up research papers and ebooks.

## Installation & Setup

**Windows:**
Download the latest release from the [Releases page](https://github.com/your-username/Scriptoria/releases) and run the installer.

**macOS:**
This application is currently built for Windows. A macOS version is possible but would require addressing the following:
1.  **Dependencies:** `pyaudio` requires the PortAudio C library. On macOS, this must be installed separately via a package manager like [Homebrew](https://brew.sh) (`brew install portaudio`).
2.  **OS-Specific Code:** The application uses some Windows-native functions for file handling (`os.startfile`) and taskbar integration (`ctypes`) that would need to be replaced with macOS equivalents (e.g., `subprocess.call(['open', ...])` and `Info.plist` configuration).

We welcome contributions to help create a native macOS version.

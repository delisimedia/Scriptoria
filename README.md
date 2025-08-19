
# Scriptoria: A Text-Based Video Editing Companion, and General Purpose EReader with Theme-Centered Highlighting and Annotating, Gemini API integration

Scriptoria provides a text-based workflow for video editors to structure narratives from transcripts, seamlessly integrating with Adobe Premiere Pro. It is also a versatile tool for marking up and analyzing long-form documents like books and articles. Imported text gets automatically or manually formatted via a simple syntax system into a Scriptoria based format. Users then turn this into transcripts with custom themes/tags and highlight colors. 

## The Problem It Solves

For video editors working with interviews, documentaries, or event footage, the process of finding the right soundbites ("paper editing") can be slow and cumbersome. It often involves scrubbing through hours of footage or manually cross-referencing paper transcripts with timestamps.

Scriptoria streamlines this by allowing you to work with the transcript as the central element, giving you a bird's-eye view of your content and enabling you to build a story structure quickly and intuitively.

## How It Works: The Core Workflow

1.  **Process & Stylize Transcript:** Start with any text source. For video-editing, generate a caption or SRT file in Adobe Premiere Pro (for example) and paste these captions into the Process Captions tab. You can use the integrated **Gemini API** to automatically clean timecodes and structure the dialogue into a readable format using powerful AI prompts. You can also import text from **PDFs** and **EPUBs**. Default prompts are provided, and a system is in place for you to write and store your own custom preset prompts. Scriptoria's tools convert this raw text into a clean, formatted, and interactive HTML document. 

2.  **Markup with Themes:** Instead of generic highlighting, you create custom **Themes** (e.g., "Key Point," "Emotional Moment," "Technical Detail"), each with a unique color and a keyboard hotkey (1-9, 0, -, +). As you read the transcript, select text and press the corresponding key to tag segments by theme.

3.  **Arrange in the Script Editor:** Every highlight you create becomes a movable block in the **Script Editor**. Here, you can drag and drop these blocks to arrange your narrative. You can also edit the text, add director's notes, mark segments as "used" in your edit, and refine the story's flow.

4.  **Integrate with Premiere Pro:** Once your narrative is structured, **Alt+Drag** a text block from Scriptoria's Script Editor and drop it onto your Premiere Pro project window. This action simulates a search command, which locates that exact text segment within your Premiere sequence's captions, ready for you to splice into your timeline.

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


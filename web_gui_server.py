#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Server-Aware Gradio Web Interface for Batch Asset Converter

This version includes path translation for Windows UNC paths to Linux mount points.
Use this version when running on a Linux server that mounts Windows network shares.

The regular web_gui.py should be used for local/workstation deployment.
"""

import gradio as gr
from pathlib import Path
import sys
import io
from contextlib import redirect_stdout
import time
import threading
import os

# Import all conversion functions from the main script
from batch_convert_assets import (
    walk_and_convert,
    parse_ext_list,
    normalize_prefix,
    AVIF_AVAILABLE,
    PDF2IMAGE_AVAILABLE,
)

# Import path translator if available
PATH_TRANSLATION_AVAILABLE = False
try:
    from server.path_translator import translate_path, get_translator
    PATH_TRANSLATION_AVAILABLE = True
except ImportError:
    print("⚠️  Path translation not available - running without path mapping")
    def translate_path(path):
        return path
    def get_translator():
        return None


def pick_folder(current_path: str = None) -> str:
    """
    Opens a folder picker dialog and returns the selected path.
    Note: On server deployment, this will open on the server, not the client.
    Users should enter paths directly when accessing remotely.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        initial_dir = None
        if current_path and current_path.strip() and current_path != ".":
            try:
                initial_dir = str(Path(current_path).expanduser().resolve())
            except:
                pass

        folder_path = filedialog.askdirectory(
            title="Ordner auswählen",
            initialdir=initial_dir
        )

        root.destroy()

        return folder_path if folder_path else (current_path or "")

    except Exception as e:
        print(f"Fehler beim Öffnen des Ordner-Dialogs: {e}")
        return current_path or ""


class TeeOutput:
    """Writes to both console and a string buffer for dual output."""
    def __init__(self, buffer, original):
        self.buffer = buffer
        self.original = original

    def write(self, text):
        self.buffer.write(text)
        self.original.write(text)
        self.original.flush()

    def flush(self):
        self.buffer.flush()
        self.original.flush()


def convert_batch(
    source_dir: str,
    output_dir: str,
    prefix: str,
    overwrite: bool,
    force_white_bg: bool,
    preserve_metadata: bool,
    use_filename_fallback: bool,
    enable_filters: bool,
    exclude_dir_pattern: str,
    filename_pattern: str,
    file_extensions: str,
    output_format: str,
    target_width: int,
    quality: int,
    pdf_zoom: float,
    progress=gr.Progress(),
):
    """
    Main conversion function with path translation for server deployment.
    """
    try:
        # Translate paths if translation is available
        if PATH_TRANSLATION_AVAILABLE:
            original_source = source_dir
            original_output = output_dir

            source_dir = translate_path(source_dir) if source_dir else source_dir
            output_dir = translate_path(output_dir) if output_dir else output_dir

            if source_dir != original_source:
                print(f"Path translation: {original_source} -> {source_dir}")
            if output_dir != original_output and output_dir:
                print(f"Path translation: {original_output} -> {output_dir}")

        # Validate source directory
        in_dir = Path(source_dir).expanduser().resolve()
        if not in_dir.exists() or not in_dir.is_dir():
            yield f"❌ Fehler: Quellordner '{in_dir}' existiert nicht."
            return

        # Set up output directory
        if not output_dir or output_dir.strip() == "":
            out_dir = in_dir / "output-web"
        else:
            out_dir = Path(output_dir).expanduser().resolve()

        # Normalize prefix
        normalized_prefix = normalize_prefix(prefix) if prefix else ""

        # Parse file extensions
        include_exts = parse_ext_list(file_extensions)

        # Apply filters only if enabled
        dir_filter = exclude_dir_pattern if enable_filters else ""
        file_filter = filename_pattern if enable_filters else ""

        # Validate format
        if output_format == "avif" and not AVIF_AVAILABLE:
            yield "❌ AVIF-Support nicht verfügbar. Installiere pillow-avif-plugin."
            return

        # Build status message header
        status_parts = [
            f"🚀 Starte Konvertierung...",
            f"📁 Quelle: {in_dir}",
            f"📂 Ziel: {out_dir}",
        ]

        if normalized_prefix:
            status_parts.append(f"🏷️ Prefix: '{normalized_prefix}'")

        status_parts.append(f"📝 Modus: {'Überschreiben' if overwrite else 'Neue Dateien mit Index'}")
        status_parts.append(f"🎨 Transparenz: {'Weißer Hintergrund' if force_white_bg else 'Erhalten'}")

        if enable_filters:
            if dir_filter:
                status_parts.append(f"🚫 Ausgeschlossene Ordner: '{dir_filter}'")
            if file_filter:
                status_parts.append(f"🔍 Dateifilter: '{file_filter}'")

        status_parts.extend([
            f"🎨 Format: {output_format.upper()}",
            f"📏 Breite: {target_width}px",
            f"⚙️ Qualität: {quality}",
            "",
            "=" * 60,
            ""
        ])

        header = "\n".join(status_parts)
        yield header
        progress(0, desc="Initialisiere...")

        # Set up buffer and tee output
        output_buffer = io.StringIO()
        original_stdout = sys.stdout
        tee = TeeOutput(output_buffer, original_stdout)

        # Thread-safe completion flag
        conversion_done = threading.Event()
        conversion_error = None

        def run_conversion():
            nonlocal conversion_error
            sys.stdout = tee
            try:
                walk_and_convert(
                    in_dir=in_dir,
                    out_dir=out_dir,
                    include_exts=include_exts,
                    out_fmt=output_format,
                    target_width=target_width,
                    quality=quality,
                    pdf_zoom=pdf_zoom,
                    prefix=normalized_prefix,
                    exclude_dir_pattern=dir_filter,
                    filename_pattern=file_filter,
                    overwrite=overwrite,
                    force_white_bg=force_white_bg,
                    preserve_metadata=preserve_metadata,
                    use_filename_fallback=use_filename_fallback,
                )
            except Exception as e:
                conversion_error = e
            finally:
                sys.stdout = original_stdout
                conversion_done.set()

        # Start conversion in background thread
        conversion_thread = threading.Thread(target=run_conversion)
        conversion_thread.start()

        # Monitor output and yield updates
        last_output = ""
        while not conversion_done.is_set():
            current_output = output_buffer.getvalue()
            if current_output != last_output:
                yield header + current_output
                last_output = current_output
            time.sleep(0.1)

        # Wait for thread to complete
        conversion_thread.join()

        # Get final output
        final_output = output_buffer.getvalue()
        progress(1.0, desc="Fertig!")

        if conversion_error:
            import traceback
            error_details = ''.join(traceback.format_exception(type(conversion_error), conversion_error, conversion_error.__traceback__))
            error_msg = f"{header}{final_output}\n{'=' * 60}\n❌ Fehler: {str(conversion_error)}\n\nDetails:\n{error_details}"
            print(f"\n❌ Fehler: {str(conversion_error)}")
            yield error_msg
        else:
            success_msg = f"{header}{final_output}\n{'=' * 60}\n✅ Konvertierung abgeschlossen!\n📂 Ausgabe: {out_dir}"
            yield success_msg

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = f"❌ Fehler: {str(e)}\n\nDetails:\n{error_details}"
        print(error_msg)
        yield error_msg


# Create Gradio interface
with gr.Blocks(
    title="pvma WordPress Asset Converter (Server)",
    theme=gr.themes.Monochrome(),
    css="""
        /* Auto-scroll helper */
        .scroll-to-output {
            scroll-margin-top: 20px;
        }

        /* Enhanced Monochrome theme with smooth transitions */
        .gradio-container {
            font-family: 'Georgia', 'Times New Roman', 'Merriweather', serif;
            transition: background-color 0.3s ease, color 0.3s ease;
        }

        /* Headers styling */
        h1, h2, h3 {
            font-weight: 600 !important;
        }

        /* Primary button with smooth hover effect */
        .primary {
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }

        .primary:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15) !important;
        }

        /* Input fields with smooth transitions */
        input, textarea {
            border-radius: 6px !important;
            transition: all 0.2s ease !important;
        }

        /* Remove scrollbar from single-line textboxes */
        .gradio-container input[type="text"] {
            overflow: hidden !important;
        }

        .gradio-container textarea[data-testid="textbox"] {
            overflow-y: auto !important;
        }

        /* Single-line textboxes should not wrap or scroll horizontally */
        .gradio-container .block:not(.scroll-to-output) textarea {
            overflow-x: hidden !important;
            white-space: nowrap !important;
            resize: none !important;
        }

        /* Dark mode toggle button styling */
        .theme-toggle {
            display: inline-block !important;
            padding: 8px 16px !important;
            border-radius: 6px !important;
            cursor: pointer !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
            border: 1px solid currentColor !important;
            background: transparent !important;
            vertical-align: middle !important;
            margin-left: auto !important;
        }

        .theme-toggle:hover {
            background: rgba(0, 0, 0, 0.05) !important;
        }

        .dark .theme-toggle:hover {
            background: rgba(255, 255, 255, 0.1) !important;
        }

        /* Status box improvements */
        .scroll-to-output textarea {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace !important;
            line-height: 1.6 !important;
        }

        /* Logo styling */
        .app-logo {
            height: 80px !important;
            width: auto !important;
            vertical-align: middle !important;
            margin-right: 15px !important;
            display: inline-block !important;
            transition: filter 0.3s ease !important;
        }

        .dark .app-logo {
            filter: invert(1) !important;
        }

        /* Header container */
        .header-container {
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            margin-bottom: 1rem !important;
        }

        .header-container .left-section {
            display: flex !important;
            align-items: center !important;
        }

        .header-container h1 {
            display: inline-block !important;
            vertical-align: middle !important;
            margin: 0 !important;
        }
    """,
    js="""
        function() {
            // Auto-scroll to status output when conversion starts
            let hasScrolledOnce = false;
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'characterData' || mutation.type === 'childList' || mutation.type === 'attributes') {
                        const statusElement = document.querySelector('.scroll-to-output textarea');
                        if (statusElement && statusElement.value && statusElement.value.length > 0) {
                            if (!hasScrolledOnce) {
                                statusElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                hasScrolledOnce = true;
                            }
                        }
                    }
                });
            });

            setTimeout(() => {
                const statusElement = document.querySelector('.scroll-to-output textarea');
                if (statusElement) {
                    observer.observe(statusElement, {
                        characterData: true,
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['value']
                    });
                }
            }, 1000);

            // Dark mode toggle
            function createThemeToggle() {
                const currentTheme = localStorage.getItem('gradio-theme') || 'light';

                if (currentTheme === 'dark') {
                    document.body.classList.add('dark');
                }

                const checkHeader = setInterval(() => {
                    const headerContainer = document.querySelector('.header-container');
                    if (headerContainer) {
                        clearInterval(checkHeader);

                        const toggleBtn = document.createElement('button');
                        toggleBtn.className = 'theme-toggle';
                        toggleBtn.innerHTML = currentTheme === 'dark' ? '☀️ Light' : '🌙 Dark';

                        toggleBtn.addEventListener('click', () => {
                            const isDark = document.body.classList.toggle('dark');
                            toggleBtn.innerHTML = isDark ? '☀️ Light' : '🌙 Dark';
                            localStorage.setItem('gradio-theme', isDark ? 'dark' : 'light');
                        });

                        headerContainer.appendChild(toggleBtn);
                    }
                }, 100);
            }

            setTimeout(createThemeToggle, 500);
        }
    """
) as app:
    server_notice = ""
    if PATH_TRANSLATION_AVAILABLE:
        server_notice = "\n        > **🖥️ Server Mode:** This instance is running with path translation enabled. You can use Windows UNC paths (e.g., `\\\\\\\\server\\\\share\\\\folder`)."

    gr.Markdown(
        f"""
        <div class="header-container">
            <div class="left-section">
                <img src="https://shots.rendertaxi.de/screenshots/pvma_Logo_smiling_puema_black.svg" class="app-logo" alt="PVMA Logo">
                <h1>Asset Converter WordPress (Server)</h1>
            </div>
        </div>

        <p>Konvertiere Bilder und PDFs in web-optimierte Formate mit WordPress-freundlichen Dateinamen.</p>
        {server_notice}
        > **💡 Remote-Zugriff:** Bei Zugriff über Netzwerk öffnet "Durchsuchen" den Dialog auf dem **Server**.
        > Geben Sie stattdessen den Pfad **auf dem Server** direkt in die Textfelder ein.
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Verzeichnisse")

            source_dir = gr.Textbox(
                label="Quellordner (Server-Pfad oder Windows UNC)",
                placeholder="z.B. /mnt/shares/projekte oder \\\\server\\share\\folder",
                value="",
                info="Windows UNC-Pfade werden automatisch übersetzt"
            )
            source_btn = gr.Button("📁 Durchsuchen", size="sm")

            output_dir = gr.Textbox(
                label="Zielordner (optional)",
                placeholder="Leer lassen für automatisch: <Quelle>/output-web",
                value="",
                info="Windows UNC-Pfade werden automatisch übersetzt"
            )
            output_btn = gr.Button("📁 Durchsuchen", size="sm")

            gr.Markdown("### Dateinamen")
            prefix = gr.Textbox(
                label="Dateinamen-Prefix (optional)",
                placeholder="z.B. ABC123 oder Project-001",
                value="",
                info="Wird allen Ausgabedateien vorangestellt"
            )

            overwrite = gr.Checkbox(
                label="Existierende Dateien überschreiben",
                value=False,
                info="Wenn deaktiviert: Neue Dateien mit Index (-01, -02, ...)"
            )

            force_white_bg = gr.Checkbox(
                label="Transparenz durch weißen Hintergrund ersetzen",
                value=True,
                info="Alpha-Kanal entfernen und durch weißen Hintergrund ersetzen"
            )

            gr.Markdown("### Metadaten")
            preserve_metadata = gr.Checkbox(
                label="Metadaten aus Quellbildern übernehmen (EXIF/IPTC)",
                value=True,
                info="Copyright, Autor, Bildunterschriften usw."
            )

            use_filename_fallback = gr.Checkbox(
                label="Dateinamen als Bildunterschrift verwenden (Fallback)",
                value=True,
                info="Wenn keine Metadaten vorhanden"
            )

        with gr.Column(scale=1):
            gr.Markdown("### Konvertierungseinstellungen")

            file_extensions = gr.Textbox(
                label="Dateierweiterungen (kommagetrennt)",
                value="tif,jpg,jpeg,png,pdf",
                info="Welche Dateitypen sollen verarbeitet werden?"
            )

            output_format = gr.Dropdown(
                label="Zielformat",
                choices=["webp", "avif", "png", "jpg"],
                value="webp",
                info="WebP: Beste Balance, AVIF: Kleinste Dateien"
            )

            target_width = gr.Slider(
                label="Maximale Größe der längsten Seite (Pixel)",
                minimum=320,
                maximum=3840,
                value=1920,
                step=80,
                info="Maximale Größe für Breite oder Höhe"
            )

            quality = gr.Slider(
                label="Qualität",
                minimum=0,
                maximum=100,
                value=80,
                step=5,
                info="0-100 (höher = besser, größere Dateien)"
            )

            pdf_zoom = gr.Slider(
                label="PDF-Render-Zoom (Auflösung)",
                minimum=0.5,
                maximum=4.0,
                value=3.0,
                step=0.1,
                info="Höherer Wert = schärfere PDFs"
            )

            gr.Markdown("### Filter")
            enable_filters = gr.Checkbox(
                label="Erweiterte Filter aktivieren",
                value=False,
                info="Ordner und Dateien filtern"
            )

            exclude_dir_pattern = gr.Textbox(
                label="Ordner ausschließen (Muster, kommagetrennt)",
                placeholder="z.B. backup,excl,temp",
                value="",
                visible=False,
                info="Ordner mit diesen Mustern überspringen"
            )

            filename_pattern = gr.Textbox(
                label="Nur Dateien mit Muster (kommagetrennt)",
                placeholder="z.B. _web,final",
                value="",
                visible=False,
                info="Nur Dateien mit diesen Mustern verarbeiten"
            )

    # Folder picker button handlers
    source_btn.click(
        fn=pick_folder,
        inputs=[source_dir],
        outputs=[source_dir]
    )

    output_btn.click(
        fn=pick_folder,
        inputs=[output_dir],
        outputs=[output_dir]
    )

    # Toggle filter visibility
    def toggle_filters(enabled):
        return {
            exclude_dir_pattern: gr.update(visible=enabled),
            filename_pattern: gr.update(visible=enabled),
        }

    enable_filters.change(
        fn=toggle_filters,
        inputs=[enable_filters],
        outputs=[exclude_dir_pattern, filename_pattern]
    )

    # Reset function
    def reset_to_defaults():
        return {
            source_dir: gr.update(value=""),
            output_dir: gr.update(value=""),
            prefix: gr.update(value=""),
            overwrite: gr.update(value=False),
            force_white_bg: gr.update(value=True),
            preserve_metadata: gr.update(value=True),
            use_filename_fallback: gr.update(value=True),
            enable_filters: gr.update(value=False),
            exclude_dir_pattern: gr.update(value="", visible=False),
            filename_pattern: gr.update(value="", visible=False),
            file_extensions: gr.update(value="tif,jpg,jpeg,png,pdf"),
            output_format: gr.update(value="webp"),
            target_width: gr.update(value=1920),
            quality: gr.update(value=80),
            pdf_zoom: gr.update(value=3.0),
        }

    # Buttons
    with gr.Row():
        convert_btn = gr.Button("🚀 Konvertierung starten", variant="primary", size="lg", scale=3)
        reset_btn = gr.Button("🔄 Auf Standard zurücksetzen", size="lg", scale=1)

    output_status = gr.Textbox(
        label="Status",
        lines=15,
        max_lines=25,
        interactive=False,
        show_copy_button=True,
        autoscroll=True,
        show_label=True,
        elem_classes="scroll-to-output"
    )

    # Wire up conversion
    convert_btn.click(
        fn=convert_batch,
        inputs=[
            source_dir,
            output_dir,
            prefix,
            overwrite,
            force_white_bg,
            preserve_metadata,
            use_filename_fallback,
            enable_filters,
            exclude_dir_pattern,
            filename_pattern,
            file_extensions,
            output_format,
            target_width,
            quality,
            pdf_zoom,
        ],
        outputs=output_status,
    )

    # Wire up reset
    reset_btn.click(
        fn=reset_to_defaults,
        inputs=[],
        outputs=[
            source_dir,
            output_dir,
            prefix,
            overwrite,
            force_white_bg,
            preserve_metadata,
            use_filename_fallback,
            enable_filters,
            exclude_dir_pattern,
            filename_pattern,
            file_extensions,
            output_format,
            target_width,
            quality,
            pdf_zoom,
        ]
    )

    # Footer
    gr.Markdown(
        """
        ---
        💡 **Server-Tipps:**
        - Windows UNC-Pfade (\\\\\\\\server\\\\share) werden automatisch übersetzt
        - Linux-Pfade (/mnt/shares/...) funktionieren direkt
        - Durchsuchen-Button funktioniert nur lokal auf dem Server
        - WebP bietet die beste Balance zwischen Qualität und Größe

        📚 [GitHub Repository](https://github.com/pipedreams-zz/asset-converter-wordpress)
        """
    )


if __name__ == "__main__":
    # Ensure UTF-8 encoding
    if sys.platform != 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    print("🌐 Starting Server-Aware Gradio Web Interface...")
    print("📂 Working Directory:", Path.cwd())
    print("\n" + "="*50)

    # Display path translation status
    if PATH_TRANSLATION_AVAILABLE:
        translator = get_translator()
        mappings = translator.get_all_mappings()

        if mappings:
            print("📋 Active Path Mappings:")
            for smb_path, local_path in mappings.items():
                print(f"  {smb_path} -> {local_path}")
        else:
            print("⚠️  No path mappings configured")
            print("   Edit /etc/asset-converter/path-mapping.conf to add mappings")
    else:
        print("ℹ️  Running without path translation")

    # Check optional dependencies
    if not AVIF_AVAILABLE:
        print("⚠️  AVIF support not available")
    if not PDF2IMAGE_AVAILABLE:
        print("⚠️  PDF support not available")

    print("="*50 + "\n")

    # Launch
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=False,  # Don't open browser on server
    )

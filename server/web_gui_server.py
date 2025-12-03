#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Server-aware Web Interface for Batch Asset Converter

This is a wrapper around the main web_gui that adds path translation
for Windows UNC paths to local Linux mount points.

Usage:
    python server/web_gui_server.py

The server will:
1. Load path mappings from /etc/asset-converter/path-mapping.conf
2. Translate Windows paths (\\server\share\path) to Linux paths (/mnt/shares/...)
3. Run the conversion with translated paths
"""

import sys
from pathlib import Path

# Add parent directory to path to import main modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
from web_gui import (
    convert_batch as original_convert_batch,
    pick_folder,
    TeeOutput,
    app as original_app
)

# Import path translator
from server.path_translator import translate_path, get_translator


def convert_batch_with_translation(
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
    Wrapper for convert_batch that translates Windows paths to Linux paths.
    """
    # Log original paths
    print(f"Original source path: {source_dir}")
    print(f"Original output path: {output_dir}")

    # Translate paths
    translated_source = translate_path(source_dir) if source_dir else source_dir
    translated_output = translate_path(output_dir) if output_dir else output_dir

    # Log translated paths
    if translated_source != source_dir:
        print(f"Translated source path: {translated_source}")
    if translated_output != output_dir:
        print(f"Translated output path: {translated_output}")

    # Call original convert_batch with translated paths
    yield from original_convert_batch(
        source_dir=translated_source,
        output_dir=translated_output,
        prefix=prefix,
        overwrite=overwrite,
        force_white_bg=force_white_bg,
        preserve_metadata=preserve_metadata,
        use_filename_fallback=use_filename_fallback,
        enable_filters=enable_filters,
        exclude_dir_pattern=exclude_dir_pattern,
        filename_pattern=filename_pattern,
        file_extensions=file_extensions,
        output_format=output_format,
        target_width=target_width,
        quality=quality,
        pdf_zoom=pdf_zoom,
        progress=progress,
    )


# Monkey-patch the convert_batch function in the app
# We need to reconnect the button to use our translation wrapper
def create_server_app():
    """
    Create a modified version of the Gradio app with path translation.
    """
    # Import the original app components
    from web_gui import (
        source_dir, output_dir, prefix, overwrite, force_white_bg,
        preserve_metadata, use_filename_fallback, enable_filters,
        exclude_dir_pattern, filename_pattern, file_extensions,
        output_format, target_width, quality, pdf_zoom,
        convert_btn, output_status
    )

    # Reconnect the convert button with our wrapper
    convert_btn.click(
        fn=convert_batch_with_translation,
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

    return original_app


if __name__ == "__main__":
    # Ensure UTF-8 encoding for console
    if sys.platform != 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    print("🌐 Starting Server-Aware Gradio Web Interface...")
    print("📂 Working Directory:", Path.cwd())
    print("\n" + "="*50)

    # Load and display path mappings
    translator = get_translator()
    mappings = translator.get_all_mappings()

    if mappings:
        print("📋 Loaded Path Mappings:")
        for smb_path, local_path in mappings.items():
            print(f"  {smb_path} -> {local_path}")
    else:
        print("⚠️  No path mappings configured - running in local mode")
        print("   Configure mappings in /etc/asset-converter/path-mapping.conf")

    print("="*50 + "\n")

    # Check optional dependencies
    from batch_convert_assets import AVIF_AVAILABLE, PDF2IMAGE_AVAILABLE
    if not AVIF_AVAILABLE:
        print("⚠️  AVIF support not available (pillow-avif-plugin missing)")
    if not PDF2IMAGE_AVAILABLE:
        print("⚠️  PDF support not available (pdf2image/Poppler missing)")

    print("="*50 + "\n")

    # Launch the app with path translation
    app = create_server_app()
    app.launch(
        server_name="0.0.0.0",  # Allow network access
        server_port=7860,
        share=False,
        inbrowser=False,  # Don't open browser on server
    )

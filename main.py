#!/usr/bin/env python

"""
Simple Auto BeatSage Script

This script automates the process of generating Beat Saber custom levels using BeatSage.com.
It can process multiple audio files in a directory and generate Beat Saber maps for each one.

Usage Examples:
    # Process all audio files in a directory
    python main.py /path/to/audio/files
    
    # Process files with custom settings
    python main.py --input /path/to/audio/files \
                  --output /path/to/output \
                  --difficulties Hard,Expert \
                  --modes Standard,90Degree \
                  --events DotBlocks,Obstacles \
                  --environment DefaultEnvironment \
                  --model_tag v2

Error Handling:
    The script handles various error conditions:
    - FileNotFoundError: When input directory doesn't exist
    - RuntimeError: When file processing fails
    - requests.exceptions.RequestException: Network-related errors
    - json.JSONDecodeError: Invalid API responses
    - Other unexpected errors during processing

    Error messages are printed to stderr and the script exits with code 1 on error.
"""

import argparse
import json
import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import zipfile

import browsercookie
import requests
from tinytag import TinyTag

# Check if terminal supports colors
use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

# Define color codes
GREEN = '\033[92m' if use_colors else ''
YELLOW = '\033[93m' if use_colors else ''
BLUE = '\033[94m' if use_colors else ''
CYAN = '\033[96m' if use_colors else ''
BOLD = '\033[1m' if use_colors else ''
RESET = '\033[0m' if use_colors else ''

# Define emojis
MUSIC = '🎵'
UPLOAD = '📤'
PROCESS = '⚙️'
DOWNLOAD = '📥'
EXTRACT = '📂'
CHECK = '✅'
DONE = '✨'
WARNING = '⚠️'
SKIP = '⏭️'
ERROR = '❌'
SUCCESS = '🎉'

# API Configuration
base_url = 'https://beatsage.com'
create_url = base_url + "/beatsaber_custom_level_create"

# Headers for BeatSage API requests
headers_beatsage = {
    'authority': 'beatsage.com',
    'method': 'POST',
    'path': '/beatsaber_custom_level_create',
    'scheme': 'https',
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'zh-CN,zh;q=0.9',
    'origin': base_url,
    'pragma': 'no-cache',
    'referer': base_url,
    'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'x-kl-ajax-request': 'Ajax_Request'
}

def get_mp3_tag(file: Union[str, Path]) -> Tuple[str, str, bytes]:
    """
    Extract metadata from an audio file using TinyTag.
    
    Args:
        file: Path to the audio file
        
    Returns:
        Tuple containing:
        - title: Audio file title (empty string if not found)
        - artist: Audio file artist (empty string if not found)
        - cover_art: Cover art image data (empty bytes if not found)
        
    Raises:
        RuntimeError: If the file cannot be read or metadata cannot be extracted
    """
    try:
        tag = TinyTag.get(file, image=True)
        title = tag.title or ''
        artist = tag.artist or ''
        cover = tag.images.any.data or b''
        return title, artist, cover
    except Exception as e:
        raise RuntimeError(f"Failed to read MP3 tags from {file}: {str(e)}")

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be used as a filename.
    
    Args:
        filename: The string to sanitize
        
    Returns:
        A sanitized string safe for use as a filename
    """
    # Replace invalid characters with underscores
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    # Replace multiple spaces with single space
    filename = ' '.join(filename.split())
    return filename

def get_output_filename(file: Union[str, Path]) -> str:
    """
    Get the output filename based on ID3 tags.
    
    Args:
        file: Path to the audio file
        
    Returns:
        A sanitized filename in the format "Track - Artist"
    """
    title, artist, _ = get_mp3_tag(file)
    
    # If either tag is missing, use the original filename
    if not title or not artist:
        return Path(file).stem
    
    # Sanitize both title and artist
    title = sanitize_filename(title)
    artist = sanitize_filename(artist)
    
    return f"{title} - {artist}"

def get_map(file: Union[str, Path], outputdir: Union[str, Path], diff: str, modes: str, 
           events: str, env: str, tag: str) -> None:
    """
    Generate a Beat Saber map for an audio file using BeatSage.
    
    Args:
        file: Path to the audio file
        outputdir: Directory to save the generated map
        diff: Comma-separated difficulties to generate
        modes: Comma-separated game modes to generate
        events: Comma-separated event types to include
        env: Environment name for the map
        tag: Model version tag to use
        
    Raises:
        RuntimeError: If map generation fails for any reason
        requests.exceptions.RequestException: If network requests fail
        json.JSONDecodeError: If API responses are invalid
        
    The function will:
    1. Extract metadata from the audio file
    2. Upload the file to BeatSage
    3. Monitor the generation progress
    4. Download the generated map
    5. Save it to the output directory
    """
    try:
        audio_title, audio_artist, cover_art = get_mp3_tag(file)
        original_filename = Path(file).stem
        output_filename = get_output_filename(file)
        
        # If we're using the original filename, let the user know
        if output_filename == original_filename:
            print(f"{YELLOW}{WARNING} No valid ID3 tags found, using original filename: {BLUE}{original_filename}{RESET}")
        
        payload = {
            'audio_metadata_title': audio_title or original_filename,
            'audio_metadata_artist': audio_artist or 'Unknown Artist',
            'difficulties': diff,
            'modes': modes,
            'events': events,
            'environment': env,
            'system_tag': tag
        }

        files: Dict[str, Tuple[str, bytes, str]] = {
            "audio_file": ("audio_file", Path(file).read_bytes(), "audio/mpeg")
        }
        if cover_art:
            files["cover_art"] = ("cover_art", cover_art, "image/jpeg")

        # load cookies from all supported/findable browsers
        cj = browsercookie.load()
        session = requests.Session()
        session.cookies.update(cj)
        
        print(f"{YELLOW}{UPLOAD} Uploading audio file to BeatSage...{RESET}", end='', flush=True)
        response = session.post(create_url, headers=headers_beatsage, data=payload, files=files)
        print(f" {GREEN}{CHECK} DONE{RESET}")
        
        if response.status_code == 413:
            raise RuntimeError("File size or song length limit exceeded (32MB, 10min for non-Patreon supporters)")
            
        response.raise_for_status()
        
        map_id = json.loads(response.text)['id']
        heart_url = f"{base_url}/beatsaber_custom_level_heartbeat/{map_id}"
        download_url = f"{base_url}/beatsaber_custom_level_download/{map_id}"
        
        print(f"{YELLOW}{PROCESS} Generating map...{RESET}", end='', flush=True)
        max_attempts = 75  # 17.5 minutes maximum
        attempt = 0
        
        while attempt < max_attempts:
            heartbeat_response = session.get(heart_url, headers=headers_beatsage)
            heartbeat_response.raise_for_status()
            status_data = json.loads(heartbeat_response.text)
            status = status_data['status']
            
            if status == "DONE":
                print(f" {GREEN}{CHECK} DONE{RESET}")
                break
            elif status == "ERROR":
                raise RuntimeError("Map generation failed")

            # No progress info available
            print('.', end='', flush=True)
                    
            time.sleep(14)
            attempt += 1
        else:
            raise RuntimeError("Map generation timed out")
            
        print(f"{YELLOW}{DOWNLOAD} Downloading generated map...{RESET}", end='', flush=True)
        response = session.get(download_url, headers=headers_beatsage, stream=True)
        response.raise_for_status()
        
        # Get content length if available
        total_size = int(response.headers.get('content-length', 0))
        
        # Write the zip file first
        output_path = Path(outputdir) / f"{output_filename}.zip"
        
        if total_size > 0:
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
        else:
            # If content length is unknown, just save the file
            output_path.write_bytes(response.content)
            
        print(f" {GREEN}{CHECK} DONE{RESET}")
        
        # Create the extraction directory with the same basename
        extract_dir = Path(outputdir) / output_filename
        
        # Extract the zip file
        print(f"{YELLOW}{EXTRACT} Extracting map files...{RESET}", end='', flush=True)
        with zipfile.ZipFile(output_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # Remove the original zip file if extraction was successful
        if extract_dir.exists():
            output_path.unlink()
            
        print(f" {GREEN}{CHECK} DONE{RESET}")
        print(f"{GREEN}{MUSIC} Map generation complete, {BLUE}{output_filename}{RESET} saved in {CYAN}{extract_dir}{RESET} {DONE}")
        print(f"{BOLD}---------------------------{RESET}")
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error occurred: {str(e)}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error: {str(e)}")

def get_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Namespace containing parsed arguments
        
    The function handles both full argument parsing and the special case
    where a single argument is provided (assumed to be the input path).
    """
    parser = argparse.ArgumentParser(description='Simple auto beatsage from local files by rote66')
    parser.add_argument('--input', '-i', type=Path, required=True,
                       help='Input folder containing audio files')
    parser.add_argument('--output', '-o', type=Path, default=None,
                       help='Output folder for generated maps (defaults to input folder)')
    parser.add_argument('--difficulties', '-d', type=str, default='Hard,Expert,ExpertPlus,Normal',
                       help='Comma-separated difficulties: Hard,Expert,ExpertPlus,Normal')
    parser.add_argument('--modes', '-m', type=str, default='Standard,90Degree,NoArrows,OneSaber',
                       help='Comma-separated modes: Standard,90Degree,NoArrows,OneSaber')
    parser.add_argument('--events', '-e', type=str, default='DotBlocks,Obstacles,Bombs',
                       help='Comma-separated events: DotBlocks,Obstacles,Bombs')
    parser.add_argument('--environment', '-env', type=str, default='DefaultEnvironment',
                       help='Environment name: DefaultEnvironment, Origins, Triangle, BigMirror, NiceEnvironment, KDAEnvironment, MonstercatEnvironment, DragonsEnvironment, CrabRave, PanicEnvironment, RocketEnvironment, GreenDay, GreenDayGrenadeEnvironment, TimbalandEnvironment, FitBeat, LinkinParkEnvironment, BTSEnvironment, KaleidoscopeEnvironment, InterscopeEnvironment, SkrillexEnvironment, BillieEnvironment, HalloweenEnvironment, GagaEnvironment')
    parser.add_argument('--model_tag', '-t', type=str, default='v2',
                       help='Model version: v1, v2, v2-flow')
    
    # Handle the case where a single argument is provided (assumed to be input path)
    if len(sys.argv) == 2 and Path(sys.argv[1]).exists():
        return parser.parse_args(['-i', sys.argv[1]])
    return parser.parse_args()

def process_files(args: argparse.Namespace) -> None:
    """
    Process all audio files in the input directory.
    
    Args:
        args: Parsed command line arguments
        
    Raises:
        FileNotFoundError: If input directory doesn't exist
        RuntimeError: If processing fails for any file
        
    The function will:
    1. Validate input and output directories
    2. Find all supported audio files
    3. Process each file, skipping existing outputs
    4. Handle errors for individual files without stopping the entire process
    """
    if not args.input.exists():
        raise FileNotFoundError(f"Input directory does not exist: {args.input}")
        
    if args.output is None:
        args.output = args.input
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        
    # Define supported audio extensions
    audio_extensions = {'.opus', '.flac', '.webm', '.weba', '.wav', '.ogg', 
                       '.m4a', '.mp3', '.oga', '.mid', '.amr', '.aac', '.wma'}
    
    # Find all audio files
    audio_files = [f for f in args.input.iterdir() 
                  if f.suffix.lower() in audio_extensions]
    
    if not audio_files:
        print(f"No audio files found in {args.input}")
        return
        
    total_files = len(audio_files)
    
    for idx, file in enumerate(audio_files, 1):
        output_filename = get_output_filename(file)
        output_zip = args.output / f"{output_filename}.zip"
        output_dir = args.output / output_filename
        if output_zip.exists() or output_dir.exists():
            print(f"{YELLOW}{SKIP} Skipping {file.name} - output already exists{RESET}")
            continue
            
        print(f"\n{BOLD}Processing file {idx}/{total_files}: {BLUE}{file.name}{RESET}")
        try:
            get_map(file, args.output, args.difficulties, args.modes,
                   args.events, args.environment, args.model_tag)
        except Exception as e:
            print(f"{YELLOW}{WARNING} Error processing {file.name}: {str(e)}{RESET}")
            continue

if __name__ == '__main__':
    try:
        args = get_args()
        process_files(args)
        print(f"\n{GREEN}{SUCCESS} All files processed! {DONE}{RESET}")
    except Exception as e:
        print(f"{YELLOW}{ERROR} Error: {str(e)}{RESET}", file=sys.stderr)
        sys.exit(1)

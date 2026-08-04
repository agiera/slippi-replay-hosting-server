#!/usr/bin/env python3
"""
Test SLP replay file structure and metadata extraction.
The SLP format typically has:
- RAW events
- Metadata (UBJSON for older versions, but can also be JSON in footer)
"""
import struct
import sys
import json

def read_slp_file(filepath):
    """Read and analyze SLP file structure."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"File: {filepath}")
    print(f"File size: {len(data)} bytes\n")
    
    # Check the last bytes
    print("Last 50 bytes (hex):")
    print(data[-50:].hex())
    print()
    print("Last 50 bytes (repr):")
    print(repr(data[-50:]))
    print()
    
    # Check if there's a JSON footer at the end (common in newer Slippi replays)
    # Look for '}}' at the end
    if data.endswith(b'}}'):
        print("Found '}}' at end - likely JSON footer\n")
        
        # Try to find the start of JSON
        # JSON should start with '{' 
        # Look backwards for the first '{'
        for i in range(len(data) - 1, -1, -1):
            if data[i:i+1] == b'{' and i > 100:  # Make sure there's data before it
                json_start = i
                print(f"Found potential JSON start at offset {json_start}")
                
                json_data = data[json_start:]
                print(f"JSON footer size: {len(json_data)} bytes\n")
                print("JSON footer (first 500 chars):")
                try:
                    print(json_data[:500].decode('utf-8', errors='replace'))
                except:
                    print(json_data[:500])
                print()
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(json_data)
                    print("Successfully parsed as JSON!")
                    print(f"Keys: {list(parsed.keys())}")
                    print("\nJSON structure (pretty):")
                    print(json.dumps(parsed, indent=2)[:1000])
                except json.JSONDecodeError as e:
                    print(f"Failed to parse as JSON: {e}")
                break
    
    # Also check for UBJSON metadata before any JSON
    # UBJSON typically starts with '{'  (0x7B)
    print("\n\nLooking for UBJSON markers...")
    
    # Count various marker bytes
    markers = {
        0x7b: '{',  # object start
        0x7d: '}',  # object end
        0x5b: '[',  # array start
        0x5d: ']',  # array end
        0x43: 'C',  # Problematic type!
    }
    
    for byte_val, name in markers.items():
        count = data.count(bytes([byte_val]))
        print(f"Marker 0x{byte_val:02x} ({name}): {count} occurrences")

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else '/home/agiera/Downloads/20120130T074801Z_babs-919_vs_p2_s28_7d33dfbe.slp'
    read_slp_file(filepath)

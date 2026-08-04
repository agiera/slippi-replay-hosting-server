#!/usr/bin/env python3
"""
Detailed UBJSON footer analysis - identify C type usage patterns.
"""
import sys
import json

def analyze_ubjson_footer(filepath):
    """Analyze UBJSON footer in detail."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"File: {filepath}\n")
    
    # Find JSON/UBJSON footer
    if data.endswith(b'}}'):
        for i in range(len(data) - 1, -1, -1):
            if data[i:i+1] == b'{' and i > 100:
                footer_start = i
                footer = data[footer_start:]
                break
    else:
        print("No footer found")
        return
    
    print(f"Footer starts at offset: {footer_start}")
    print(f"Footer size: {len(footer)} bytes")
    print()
    
    # UBJSON type markers
    ubjson_types = {
        0x7b: 'object_start',
        0x7d: 'object_end',
        0x5b: 'array_start',
        0x5d: 'array_end',
        0x69: 'int32',
        0x49: 'uint32',
        0x6c: 'int64',
        0x4c: 'uint64',
        0x64: 'float64',
        0x66: 'float32',
        0x53: 'string_optimized',
        0x73: 'string',
        0x43: 'char',           # <-- The problematic type
        0x54: 'true',
        0x46: 'false',
        0x5a: 'null',
        0x55: 'uint8',
        0x63: 'uint8_compact',  # 'c'
    }
    
    print("UBJSON type breakdown in footer:")
    type_counts = {}
    for byte_val, type_name in ubjson_types.items():
        count = footer.count(bytes([byte_val]))
        if count > 0:
            type_counts[type_name] = count
            print(f"  {type_name:20} (0x{byte_val:02x}): {count:4} occurrences")
    
    print()
    print("Analyzing 'C' (char) type usage:")
    print("-" * 60)
    
    # Find contexts where 'C' appears
    c_positions = []
    pos = 0
    while True:
        pos = footer.find(0x43, pos)
        if pos == -1:
            break
        c_positions.append(pos)
        pos += 1
    
    print(f"Total 'C' markers: {len(c_positions)}")
    print()
    
    # Sample some contexts
    print("Sample C contexts (byte before and after):")
    sample_indices = [0, len(c_positions)//4, len(c_positions)//2, 3*len(c_positions)//4, -1]
    seen = set()
    
    for idx in sample_indices:
        if idx < 0:
            idx = len(c_positions) + idx
        if idx < 0 or idx >= len(c_positions):
            continue
        
        pos = c_positions[idx]
        if pos in seen:
            continue
        seen.add(pos)
        
        before = footer[pos-1:pos]
        after = footer[pos+1:pos+2] if pos+1 < len(footer) else b''
        
        before_hex = before.hex() if before else '??'
        after_hex = after.hex() if after else '??'
        
        before_name = ubjson_types.get(before[0] if before else None, '?') if before else '?'
        after_name = ubjson_types.get(after[0] if after else None, '?') if after else '?'
        
        print(f"  Pos {pos:5}: [{before_hex}({before_name:15})] [43(char)] [{after_hex}({after_name:15})]")
    
    print()
    print("Checking if 'C' is being used as a string marker (not a type marker):")
    print("-" * 60)
    
    # In UBJSON, strings can be optimized with header (Sstr_len) 
    # But 'C' followed by a byte could be interpreted as char type
    c_as_char_count = 0
    
    for pos in c_positions[:min(20, len(c_positions))]:
        if pos + 1 < len(footer):
            next_byte = footer[pos+1]
            # Char should be followed by one byte
            if pos + 2 < len(footer):
                after_byte = footer[pos+2]
                # Check if this looks like a char (single byte value)
                if next_byte < 128 and 32 <= next_byte < 127:
                    print(f"  Pos {pos}: 0x43 0x{next_byte:02x} ({chr(next_byte)}) 0x{after_byte:02x}")
                else:
                    print(f"  Pos {pos}: 0x43 0x{next_byte:02x} (??) 0x{after_byte:02x}")
    
    print()
    print("Raw footer dump (first 200 bytes):")
    print(footer[:200])
    print()
    print("Raw footer dump hex (first 200 bytes):")
    print(footer[:200].hex())

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else '/home/agiera/Downloads/20120130T074801Z_babs-919_vs_p2_s28_7d33dfbe.slp'
    analyze_ubjson_footer(filepath)

import struct, re

with open('OBJ/JX_FLY.htm', 'r', errors='replace') as f:
    content = f.read()
print(f'File size: {len(content)}')

# Find the Frame B emit section - look for the pattern where frame type 0x02 is set
# and where payload_len is calculated
for kw in ['FRAME B', 'FRAME 0x02', '0xAA 0xBB']:
    idx = content.find(kw)
    if idx >= 0:
        print(f'Found "{kw}" at {idx}:')
        print(content[max(0,idx-50):idx+300])
        print('---')
        break

# Also search the AXF binary for patterns near the send_data frame emit
with open('OBJ/JX_FLY.axf', 'rb') as f:
    axf = f.read()

# Find the instruction that loads the payload length for Frame B
# The ARM code near the Frame B emit should have sequences like:
# LDRB r0, [rX, #offset]  ; load frame type
# MOVS/MOVW rY, #298       ; load payload length
# The constant 0x2A = 42 decimal might be embedded

# Find occurrences of 0x2A near other significant bytes
print(f'\nAXF size: {len(axf)}')
# Look for "LDRB" or "MOV" patterns that set small constants
# For now just print the addresses of potential frame data
for i in range(len(axf)-20):
    if axf[i:i+2] == b'\xaa\xbb':
        print(f'AXF sync at offset {i}: {axf[i:i+16].hex()}')

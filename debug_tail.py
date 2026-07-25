import serial, time, struct

s = serial.Serial(port='COM3', baudrate=115200, timeout=1.0)
buf = bytearray()
t_end = time.monotonic() + 3
while time.monotonic() < t_end:
    buf += s.read(4096)
s.close()

# Find Frame B and decode tail bytes
# main_len = 4 * max_num_basis + 52 floats * 4 bytes = 16N+208 bytes
# For N=6: main_len = 16*6+208 = 304 bytes
# tail starts at offset main_len within payload
for i in range(len(buf)-305):
    if buf[i]==0xAA and buf[i+1]==0xBB and buf[i+2]==0x02:
        plen = (buf[i+3]<<8)|buf[i+4]
        if plen == 298:
            mnb = buf[i+5]
            main_len = (4 * mnb + 52) * 4
            data_start = i + 6
            tail_start = data_start + main_len
            tail_end = data_start + plen
            print(f'mnb={mnb} main_len={main_len} tail_start={tail_start} tail_end={tail_end}')
            tail = bytes(buf[tail_start:tail_end])
            print(f'Tail bytes ({len(tail)}): {tail.hex()}')
            
            # Try the known v3 layout
            try:
                vals = struct.unpack_from('BfffffBf', tail, 0)
                print(f'v3 layout: apm={vals[0]} twc_x={vals[1]:.4f} twc_y={vals[2]:.4f} twc_z={vals[3]:.4f} sin_t={vals[4]:.4f} circ={vals[5]:.4f} arr={vals[6]} vbat={vals[7]:.3f}')
            except Exception as e:
                print(f'v3 unpack failed: {e}')
            
            # Unknown extra bytes
            extra = tail[20:]
            print(f'Extra bytes ({len(extra)}): {extra.hex()}')
            if len(extra) >= 4:
                print(f'  extra[0:4] as float32: {struct.unpack_from("f", extra, 0)[0]:.6f}')
            break


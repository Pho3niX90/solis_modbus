
def decode_serial(registers):
    serial = ""
    for reg in registers:
        # Assuming High Byte first (Big Endian per register)
        # Check if 0 to skip
        b1 = (reg >> 8) & 0xFF
        b2 = reg & 0xFF
        if b1: serial += chr(b1)
        if b2: serial += chr(b2)
    return serial.strip()

# Example: "1402..."
# '1' = 0x31, '4' = 0x34 -> 0x3134 = 12596
# '0' = 0x30, '2' = 0x32 -> 0x3032 = 12338

registers = [12596, 12338]
decoded = decode_serial(registers)
print(f"Registers: {registers}")
print(f"Decoded: {decoded}")

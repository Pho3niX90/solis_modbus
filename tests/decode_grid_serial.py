
def decode_grid_serial(registers):
    # Registers: [0x4321, 0x8765, 0xCBA9, 0x0FED]
    # Expected: 123456789ABCDEF0
    
    serial = ""
    for reg in registers:
        # Convert to hex string, e.g. "4321"
        # Hex representation without 0x, padded to 4 chars
        hex_val = f"{reg:04X}"
        # Reverse it: "1234"
        reversed_hex = hex_val[::-1]
        serial += reversed_hex
    return serial

registers = [0x4321, 0x8765, 0xCBA9, 0x0FED]
decoded = decode_grid_serial(registers)
print(f"Registers: {[hex(x) for x in registers]}")
print(f"Decoded: {decoded}")

expected = "123456789ABCDEF0"
assert decoded == expected, f"Expected {expected}, got {decoded}"
print("Assertion Passed")

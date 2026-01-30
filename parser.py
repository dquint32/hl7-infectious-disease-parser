from hl7apy.parser import parse_message
import sys

def parse_hl7_file(file_path):
    try:
        with open(file_path, "r") as f:
            raw = f.read()

        msg = parse_message(raw)

        print("\n=== HL7 MESSAGE TYPE ===")
        print(msg.MSH.MSH_9.to_er7())

        print("\n=== SEGMENTS ===")
        for segment in msg.children:
            print(f"\n[{segment.name}]")
            for field in segment.children:
                print(f"  {field.name}: {field.to_er7()}")

    except Exception as e:
        print("\nERROR: Unable to parse HL7 message.")
        print(f"Details: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parser.py <hl7_file>")
        sys.exit(1)

    parse_hl7_file(sys.argv[1])

def remove_blank_lines(input_file, output_file):
    with open(input_file, 'r') as infile:
        lines = infile.readlines()
    
    non_blank_lines = []
    for line in lines:
        stripped = line.strip()
        # Check if line is empty OR contains only spaces and a # (empty comment)
        if stripped == '' or stripped == '#':
            continue  # Skip this line
        non_blank_lines.append(line)
    
    with open(output_file, 'w') as outfile:
        outfile.writelines(non_blank_lines)

# Usage
input_py = input("Input file: ")
output_py = input("Output file: ")

remove_blank_lines(input_py, output_py)
print(f"Blank lines removed from {input_py} and saved to {output_py}.")
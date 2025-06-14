import os

def print_file_contents(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            contents = f.read()
            print(f"<<<<START of file {file_path}:>>>>")
            print(contents)
            print(f"<<<<END of file {file_path}:>>>>")
    except UnicodeDecodeError:
        # Binary file, ignore
        pass
    print()  # Separate files with an extra newline

def process_path(path):
    if os.path.isfile(path):
        print_file_contents(path)
    elif os.path.isdir(path):
        for root, _, files in os.walk(path):
            for filename in files:
                file_path = os.path.join(root, filename)
                print_file_contents(file_path)
    else:
        print(f"Path not found: {path}")
        print()

def main():
    # Multi-line string with each line as a file or directory path.
    paths_str = """
/Users/segalmax/Documents/python_projects/telegram_zoomer/app
"""
    # Process each non-empty line.
    paths = [line.strip() for line in paths_str.strip().splitlines() if line.strip()]
    for path in paths:
        process_path(path)

if __name__ == "__main__":
    main()

import os


def write_output_to_file(output, directory, uuid):
    # Ensure directory exists
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Define the file path using the directory and UUID
    file_path = os.path.join(directory, f"{uuid}.yaml")

    # Write the output to the file
    with open(file_path, "w", encoding="utf-8") as file: #added explicit utf-8 encoding due to all greek characters MFJ 2024-12-19
        file.write(output)

    print(f"Output written to {file_path}")
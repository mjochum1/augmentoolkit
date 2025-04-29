import os
from datetime import datetime
import pandas as pd
import tkinter as tk
from tkinter import filedialog
import sys

def get_directory():
    print("\nSelect directory: \n1. GUI picker\n2. Manual entry")
    if input("Choice (1/2): ").strip() == "1":
        root = tk.Tk()
        root.withdraw()
        directory = filedialog.askdirectory(title="Select Augmentoolkit Output Directory")
        return directory if directory else sys.exit()
    
    while True:
        directory = os.path.normpath(input("\nDirectory path: ").strip().strip('"\'').rstrip('\\'))
        if os.path.isdir(directory):
            return directory
        print("Invalid path. Try again.")

def get_model_name(directory, model_type="SMALL_MODEL"):
    try:
        with open(os.path.join(directory, "config.yaml"), 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and f"{model_type}:" in line:
                    if not line.split(f"{model_type}:")[0].strip().startswith('#'):
                        return line.split(f"{model_type}:", 1)[1].strip().split("#")[0].strip()
    except Exception:
        pass
    return "model-unknown"

def analyze_folder_runtime(directory):
    if not os.path.exists(directory):
        return None
        
    times = [datetime.fromtimestamp(os.path.getmtime(os.path.join(directory, f))) 
             for f in os.listdir(directory) 
             if os.path.isfile(os.path.join(directory, f))]
    
    return round((max(times) - min(times)).total_seconds() / 60) if times else None

def analyze_folder_stats(directory, folder_path):
    if not os.path.exists(folder_path):
        return None
    
    file_count = len([f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))])
    runtime = analyze_folder_runtime(folder_path)
    
    return {
        'total_files': file_count,
        'runtime_minutes': runtime
    }

def analyze_step_folders(directory, base_folder, subfolders):
    base_path = os.path.join(directory, base_folder)
    if not os.path.exists(base_path):
        return None
    
    results = {}
    for folder in subfolders:
        folder_path = os.path.join(base_path, folder)
        stats = analyze_folder_stats(directory, folder_path)
        if stats:
            results[folder] = stats
    
    return results if results else None

def analyze_judge_paragraph_generations(directory):
    saved_readable_path = os.path.join(directory, "judge_paragraph_generations", "saved_readable_generations")
    if not os.path.exists(saved_readable_path):
        return None
        
    files = [f for f in os.listdir(saved_readable_path) if os.path.isfile(os.path.join(saved_readable_path, f))]
    files_over_1kb = sum(1 for f in files if os.path.getsize(os.path.join(saved_readable_path, f)) > 1024)
    
    return {
        'total_files': len(files),
        'accepted_files': files_over_1kb,
        'runtime_minutes': analyze_folder_runtime(saved_readable_path)
    }

def analyze_jsonl_files(directory):
    results = []
    start_time = end_time = None
    
    for filename in [f for f in os.listdir(directory) if f.endswith('.jsonl')]:
        file_path = os.path.join(directory, filename)
        file_stats = os.stat(file_path)
        file_modified = datetime.fromtimestamp(file_stats.st_mtime)
        
        if filename == 'pretraining.jsonl':
            start_time = file_modified
        elif filename == 'master_list.jsonl':
            end_time = file_modified
        
        results.append({
            'filename': filename,
            'size_kb': round(file_stats.st_size / 1024),
            'line_count': len(open(file_path, 'r', encoding='utf-8').readlines()),
            'modified': file_modified
        })
    
    if not results:
        return pd.DataFrame(), None
    
    return (pd.DataFrame(results), 
            (end_time - start_time).total_seconds() / 60 if start_time and end_time else None)

def format_time(minutes):
    if minutes is None:
        return "unknown time"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{int(hours)}hrs {int(mins)} minutes"
    return f"{int(mins)} minutes"

def create_cell_content(lines):
    """Helper function to create properly formatted cell content with CRLF line breaks for Excel"""
    return os.linesep.join(lines)

def format_output(directory):
    # Create dictionary for single row
    row = {}
    
    # Judge Paragraph Generation (Column 1)
    jpg_stats = analyze_judge_paragraph_generations(directory)
    if jpg_stats:
        lines = [
            "Step: judge_paragraph_generations",
            f"{get_model_name(directory, 'SMALL_MODEL')}",
            f"{jpg_stats['accepted_files']} of {jpg_stats['total_files']} passed",
            f"{format_time(jpg_stats['runtime_minutes'])}"
        ]
        row['Step1'] = create_cell_content(lines)
    
    # Question Generation (Column 2)
    qgen_stats = analyze_step_folders(directory, "question_generation_generations", 
                                    ["question_generation_generations", "raw_qatuples_saved"])
    if qgen_stats:
        lines = [
            "Step:",
            "question_generation_generations",
            get_model_name(directory, "LARGE_MODEL")
        ]
        if "question_generation_generations" in qgen_stats:
            stats = qgen_stats["question_generation_generations"]
            lines.extend([
                "question_generation_generations:",
                f"{stats['total_files']} Files",
                format_time(stats['runtime_minutes'])
            ])
        if "raw_qatuples_saved" in qgen_stats:
            stats = qgen_stats["raw_qatuples_saved"]
            lines.extend([
                "raw_qatuples_saved:",
                f"{stats['total_files']} paragraphs",
                format_time(stats['runtime_minutes'])
            ])
        row['Step2'] = create_cell_content(lines)
    
    # QA Verification (Column 3)
    qa_folders = ["check_question_generations", "check_answer_accuracy_generations",
                 "check_answer_relevancy_generations", "qatuples_filtered"]
    qa_stats = {folder: analyze_folder_stats(directory, os.path.join(directory, folder))
                for folder in qa_folders}
    if any(qa_stats.values()):
        lines = [
            "Step: QA Verification",
            f"{get_model_name(directory, 'SMALL_MODEL')}"
        ]
        for folder in qa_folders:
            if folder in qa_stats and qa_stats[folder]:
                stats = qa_stats[folder]
                lines.extend([
                    f"{folder}:",
                    f"{stats['total_files']} Files",
                    format_time(stats['runtime_minutes'])
                ])
        row['Step3'] = create_cell_content(lines)
    
    # Context Revision (Column 4)
    context_stats = analyze_step_folders(directory, "question_context_revision_generations",
                                       ["revised_qatuples_intermediates", "revised_qatuples_saved"])
    if context_stats:
        lines = [
            "Step:",
            "question_context_revision_generations",
            get_model_name(directory, "LARGE_MODEL")
        ]
        for folder, stats in context_stats.items():
            lines.extend([
                f"{folder}:",
                f"{stats['total_files']} Files",
                format_time(stats['runtime_minutes'])
            ])
        row['Step4'] = create_cell_content(lines)
    
    # Multi-turn Conversations (Column 5)
    mtc_stats = analyze_step_folders(directory, "multi_turn_convs",
                                   ["intermediate_generations", "saved_readable_generations"])
    if mtc_stats:
        lines = [
            "Step: multi_turn_convs",
            get_model_name(directory, "LARGE_MODEL")
        ]
        for folder, stats in mtc_stats.items():
            lines.extend([
                f"{folder}:",
                f"{stats['total_files']} Files",
                format_time(stats['runtime_minutes'])
            ])
        row['Step5'] = create_cell_content(lines)
    
    # Final Generations (Column 6)
    df, total_runtime = analyze_jsonl_files(directory)
    if not df.empty:
        lines = ["Final Generations:"]
        if total_runtime is not None:
            hours = int(total_runtime // 60)
            minutes = int(total_runtime % 60)
            lines.append(f"Total runtime: {hours}h {minutes}m")
        
        for _, r in df.sort_values('size_kb', ascending=False).iterrows():
            lines.append(f"{r['filename']}: {int(r['size_kb']):,}KB, {r['line_count']} lines")
        row['Step6'] = create_cell_content(lines)
    
    # Create single-row DataFrame
    return pd.DataFrame([row])

def main():
    print("Augmentoolkit Output Analyzer")
    print("=" * 40)
    
    directory = get_directory()
    print(f"\nAnalyzing files in: {directory}")
    print("-" * 40)
    
    # Get output in DataFrame format
    output_df = format_output(directory)
    
    # Save CSV with quotes to preserve line breaks
    csv_file = os.path.join(directory, "augmentoolkit_analysis.csv")
    output_df.to_csv(csv_file, index=False, quoting=1)
    
    # Also save a clipboard-friendly version
    clipboard_file = os.path.join(directory, "augmentoolkit_analysis_clipboard.txt")
    with open(clipboard_file, 'w', newline='') as f:
        for col in output_df.columns:
            if not pd.isna(output_df[col].iloc[0]):
                f.write(output_df[col].iloc[0])
                f.write('\t')  # Tab between columns for Excel
        f.write('\n')
    
    # For console display and text file
    txt_output = []
    for col in output_df.columns:
        if not pd.isna(output_df[col].iloc[0]):
            txt_output.extend([output_df[col].iloc[0], ''])
    
    # Display in console
    print("\n" + "\n".join(txt_output) + "\n")
    
    # Save text file
    txt_file = os.path.join(directory, "augmentoolkit_analysis.txt")
    with open(txt_file, 'w') as f:
        f.write("\n".join(txt_output))
    
    print(f"Analysis saved to: {txt_file}, {csv_file}, and clipboard-friendly version: {clipboard_file}")
    print("\nTo paste into Excel with proper formatting:")
    print("1. Open augmentoolkit_analysis_clipboard.txt")
    print("2. Select all (Ctrl+A) and copy (Ctrl+C)")
    print("3. Paste into Excel (Ctrl+V)")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
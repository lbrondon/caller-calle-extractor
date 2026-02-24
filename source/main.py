# from github_repo_search import save_links_to_file
from clone_repositories import download_repositories_entry
from directory_manager import get_project_dirs_and_output
from program_snc import SrcMLAnalyzer
from csv_display import display_csv  


def main():
    # print("Starting the process of saving GitHub repository links to a .txt file...")
    # save_links_to_file()     # Save GitHub repository links to a file
    
    print("Starting the process of downloading repositories...")
    download_repositories_entry()     # Download repositories from GitHub

    # print("Getting project directories and output CSV file path...")
    # project_dirs, output_csv = get_project_dirs_and_output()     # Get project directories and CSV output path
    
    # print(f"Found project directories: {project_dirs}")
    # print(f"Output CSV file will be saved at: {output_csv}")
    
    # print("Initializing SrcMLAnalyzer with the project directories...")
    # analyzer = SrcMLAnalyzer(project_dirs, output_csv)      # Create an instance of SrcMLAnalyzer 
    # analyzer.process_projects()

    # print("Process completed successfully!")

    # print("Showing data set")
    # display_csv("/home/lucas/Documents/call_graph_extractor/C-Code-Function-Call-Analyzer/output/function_call_graph.csv", 1000)

if __name__ == "__main__":
    main()
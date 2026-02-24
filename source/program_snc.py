import os
import subprocess
import csv
import sys
from pathlib import Path
from directory_manager import CLONED_PROJECTS_DIR, extract_relative_path
import xml.etree.ElementTree as ET
import logging

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Define a variable that stores the name of the "output" folder
OUTPUT_DIR = "output"

class SrcMLAnalyzer:
    def __init__(self, project_dirs, output_csv):
        self.project_dirs = project_dirs
        self.output_csv = output_csv

        # Ensure that the output CSV directory exists
        output_dir = os.path.dirname(self.output_csv)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        print(f"Initialized SrcMLAnalyzer with output CSV: {self.output_csv}")

    def process_projects(self):
        output_dir = os.path.dirname(self.output_csv)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        print(f"Processing projects. Output CSV directory: {output_dir}")

        try:
            with open(self.output_csv, mode="w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["Project", "File", "Caller", "Callee"])
                print(f"CSV file initialized: {self.output_csv}")

                for project_dir in self.project_dirs:
                    try:
                        self.process_project(project_dir, writer)
                    except Exception as e:
                        LOGGER.exception('Error processing %s: %s', project_dir, e)
                        # Continue processing other projects instead of exiting
                        continue
        except IOError as e:
            print(f"Error opening/creating CSV file: {e}")
            sys.exit(1)

    def process_project(self, project_dir, writer):
        c_files = list(Path(project_dir).rglob("*.c"))
        if not c_files:
            print(f"No .c files found in project: {project_dir}")
            return

        project_name = os.path.basename(project_dir)
        print(f"Found {len(c_files)} .c files in project: {project_name}")

        for c_file in c_files:
            xml_output_path = os.path.join(project_dir, f"{os.path.basename(c_file)}.xml")
            self.generate_srcml(c_file, xml_output_path)
            self.extract_call_graph(xml_output_path, project_name, c_file, writer)

    def generate_srcml(self, c_file_path, xml_output_path):
        """Convert .c file to XML using srcML."""
        result = subprocess.run(['srcml', c_file_path, '-o', xml_output_path], capture_output=True, text=True)
        if result.returncode != 0:
            LOGGER.warning('srcml failed for %s: %s', c_file_path, result.stderr)
            raise RuntimeError(f'srcml failed for {c_file_path}: {result.stderr}')

    def extract_call_graph(self, xml_output_path, project_name, c_file, writer):
        """Extract caller-callee pairs from the srcML XML."""
        tree = ET.parse(xml_output_path)
        root = tree.getroot()

        namespaces = {'src': 'http://www.srcML.org/srcML/src'}
        caller_callee_pairs = []

        # Traverse the XML to find functions and calls
        for function in root.findall('.//src:function', namespaces):
            name_elem = function.find('src:name', namespaces)
            if name_elem is None or name_elem.text is None:
                # unnamed/anonymous function — skip or mark as <anonymous>
                caller = '<anonymous>'
            else:
                caller = name_elem.text.strip()

            for call_name in function.findall('.//src:call/src:name', namespaces):
                if call_name is None or call_name.text is None:
                    callee = '<unknown>'
                else:
                    callee = call_name.text.strip()
                try:
                    writer.writerow([project_name, extract_relative_path(str(c_file)), caller, callee])
                except Exception:
                    LOGGER.exception('Failed writing CSV row for %s %s -> %s', project_name, caller, callee)

    def _save_csv(self, data, project_name, c_file, writer):
        pass  # Not needed in srcML version

# Example usage
# if __name__ == "__main__":
#     project_dirs = ['/home/lucas/Documents/call_graph_extractor/C-Code-Function-Call-Analyzer/source/projects/']  # Replace with actual project directory paths
#     output_csv = '/home/lucas/Documents/call_graph_extractor/C-Code-Function-Call-Analyzer/output/caller_callee.csv'
#     analyzer = SrcMLAnalyzer(project_dirs, output_csv)
#     analyzer.process_projects()

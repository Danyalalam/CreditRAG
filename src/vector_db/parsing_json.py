import json
import csv
from pprint import pprint

def test_json_parsing(file_path: str, output_csv: str):
    """
    Parses JSON and exports credit scores to a CSV file.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    credit_scores = data.get('report', {}).get('creditScores', [])
    extracted_data = []

    for cs in credit_scores:
        entry = {
            'ID': cs.get('id'),
            'Credit Score': cs.get('credit_score'),
            'Type': cs.get('type'),
            'Reporting Agency': cs.get('credit_reporting_agency', {}).get('name')
        }
        extracted_data.append(entry)
        pprint(entry)

    # Write to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ID', 'Credit Score', 'Type', 'Reporting Agency']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for data in extracted_data:
            writer.writerow(data)

if __name__ == "__main__":
    input_file = 'src/sample_json/smartcredit_3.json'
    output_file = 'src/output/credit_scores.csv'
    test_json_parsing(input_file, output_file)
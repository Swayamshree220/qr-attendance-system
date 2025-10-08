import csv
from faker import Faker

def generate_student_data(num_students=5000):
    """Generates a CSV file with dummy student data for B.Tech, Batch 2022."""
    fake = Faker()
    file_name = 'btech_2022_students.csv'
    
    # Use a set to track emails and ensure uniqueness
    generated_emails = set()

    with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Student ID', 'Name', 'Degree', 'Batch', 'Gmail Account']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        
        for i in range(1, num_students + 1):
            student_id = f'S{i:05d}'  # e.g., S00001
            name = fake.name()
            
            # Generate a unique Gmail account
            email = fake.email()
            while email in generated_emails:
                email = fake.email()
            generated_emails.add(email)
            
            # Change the domain to gmail.com
            gmail_account = email.split('@')[0] + '@gmail.com'

            writer.writerow({
                'Student ID': student_id,
                'Name': name,
                'Degree': 'B.Tech',  # Fixed value
                'Batch': 2022,       # Fixed value
                'Gmail Account': gmail_account
            })

    print(f"Successfully generated {num_students} student records in '{file_name}'.")

if __name__ == '__main__':
    generate_student_data()
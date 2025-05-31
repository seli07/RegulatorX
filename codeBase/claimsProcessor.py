import sqlite3
import datetime
import os
import random
import re
import sys
from datetime import datetime

# Configuration
DB_PATH = 'institutional_claims.db'
OUTPUT_DIR = 'output_837i_files'

# Constants for X12 formatting
ISA_CONTROL_VERSION = '00501'
GS_VERSION = '005010X223A2'  # 837I version
SEGMENT_TERMINATOR = '~'
ELEMENT_SEPARATOR = '*'
SUB_ELEMENT_SEPARATOR = ':'
LINE_BREAK = '\n'

# Constants for Medicaid Kentucky specific requirements
ky_medicaid_requirements = {
    'sender_id': 'KYSUBMITTER',      # Sender ID assigned by KY Medicaid (replace with actual)
    'receiver_id': 'KYMEDICAID',      # KY Medicaid receiver ID
    'transaction_set_purpose_code': '00',  # KY Medicaid only processes claims with "00"
    'transaction_type_codes': ['CH', 'RP']  # KY Medicaid only processes claims with "CH" or "RP"
}

# Validation error levels
class ErrorLevel:
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

class ValidationError:
    def __init__(self, claim_id, level, message, field=None):
        self.claim_id = claim_id
        self.level = level
        self.message = message
        self.field = field
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"{self.timestamp} - [{self.level}] Claim {self.claim_id}: {self.message}" + \
               (f" (Field: {self.field})" if self.field else "")

def connect_to_db():
    """Connect to the SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        sys.exit(1)

def fetch_claims_data(conn):
    """Fetch all necessary data for generating 837I files"""
    cursor = conn.cursor()
    
    # Get all claims with related data
    cursor.execute('''
    SELECT c.*, 
           p.first_name as patient_first_name, p.last_name as patient_last_name,
           p.gender as patient_gender, p.dob as patient_dob,
           p.address_line_1 as patient_address_line_1, p.city as patient_city,
           p.state as patient_state, p.zip_code as patient_zip_code,
           prov.npi as provider_npi, prov.organization_name as provider_org_name,
           prov.provider_first_name, prov.provider_last_name,
           prov.taxonomy_code as provider_taxonomy_code,
           prov.address_line_1 as provider_address_line_1, 
           prov.city as provider_city, prov.state as provider_state,
           prov.zip_code as provider_zip_code, prov.legacy_provider_id,
           pay.payer_name, pay.payer_id_code,
           s.insured_first_name, s.insured_last_name, s.insured_id,
           s.relationship_code, s.policy_number, s.group_number
    FROM claims c
    JOIN patients p ON c.patient_id = p.patient_id
    JOIN providers prov ON c.provider_id = prov.provider_id
    JOIN payers pay ON c.payer_id = pay.payer_id
    JOIN subscribers s ON c.subscriber_id = s.subscriber_id
    ''')
    
    claims = cursor.fetchall()
    
    # Fetch service lines for each claim
    for i, claim in enumerate(claims):
        cursor.execute('''
        SELECT * FROM service_lines WHERE claim_id = ?
        ''', (claim['claim_id'],))
        service_lines = cursor.fetchall()
        claims[i] = dict(claim)  # Convert row to dict
        claims[i]['service_lines'] = [dict(line) for line in service_lines]
    
    return claims

def validate_claims(claims):
    """Validate claims against KY Medicaid requirements"""
    validation_results = []
    valid_claims = []
    
    for claim in claims:
        claim_errors = []
        
        # Check transaction type code (BHT06)
        if claim['transaction_type_code'] not in ky_medicaid_requirements['transaction_type_codes']:
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid transaction type code: {claim['transaction_type_code']}. KY Medicaid only accepts 'CH' or 'RP'.",
                    'transaction_type_code'
                )
            )
        
        # Check claim filing indicator code (2000B SBR09)
        if claim['claim_filing_indicator_code'] != 'MC':
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid claim filing indicator code: {claim['claim_filing_indicator_code']}. KY Medicaid only accepts 'MC'.",
                    'claim_filing_indicator_code'
                )
            )
        
        # Check entity type qualifier (2010BA NM102)
        if claim['entity_type_qualifier'] != '1':
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid entity type qualifier: {claim['entity_type_qualifier']}. KY Medicaid requires '1' (Person).",
                    'entity_type_qualifier'
                )
            )
        
        # Check assignment of benefits indicator (2300 CLM07)
        if claim['provider_accept_assignment_code'] != 'A':
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid provider accept assignment code: {claim['provider_accept_assignment_code']}. KY Medicaid only accepts 'A'.",
                    'provider_accept_assignment_code'
                )
            )
        
        # Check benefits assignment cert indicator (2300 CLM08)
        if claim['benefits_assignment_cert_indicator'] != 'Y':
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid benefits assignment cert indicator: {claim['benefits_assignment_cert_indicator']}. KY Medicaid only accepts 'Y'.",
                    'benefits_assignment_cert_indicator'
                )
            )
        
        # Check release of information code (2300 CLM09)
        if claim['release_info_code'] != 'Y':
            claim_errors.append(
                ValidationError(
                    claim['claim_id'], 
                    ErrorLevel.ERROR, 
                    f"Invalid release of information code: {claim['release_info_code']}. KY Medicaid only accepts 'Y'.",
                    'release_info_code'
                )
            )
        
        # Check procedure code qualifier for each service line (2400 SV202-1)
        for i, line in enumerate(claim['service_lines']):
            if line['procedure_code_qualifier'] != 'HC':
                claim_errors.append(
                    ValidationError(
                        claim['claim_id'], 
                        ErrorLevel.WARNING, 
                        f"Service line {line['line_number']}: Invalid procedure code qualifier: {line['procedure_code_qualifier']}. KY Medicaid requires 'HC'.",
                        'procedure_code_qualifier'
                    )
                )
        
        # Add HI segment validation (Principal Procedure and Other Procedure Information)
        # In a real implementation, we would check actual HI segment data
        # As a placeholder, we'll add informational warnings
        
        # Rule 13: For Principal Procedure Information (BR vs BP)
        claim_errors.append(
            ValidationError(
                claim['claim_id'],
                ErrorLevel.INFO,
                "HI Segment: KY Medicaid only uses HI01-2 when HI01-1 equals BR. If BP is used, value in HI01-2 won't be processed.",
                'HI_segment_principal_procedure'
            )
        )
        
        # Rule 14: For Other Procedure Information (BQ vs BO)
        claim_errors.append(
            ValidationError(
                claim['claim_id'],
                ErrorLevel.INFO,
                "HI Segment: KY Medicaid only uses HI01-2 when HI01-1 equals BQ. If BO is used, value in HI01-2 won't be processed.",
                'HI_segment_other_procedure'
            )
        )
        
        # Add warning about HCPCS codes in HI segment
        claim_errors.append(
            ValidationError(
                claim['claim_id'],
                ErrorLevel.WARNING,
                "HI Segment: KY Medicaid prefers HCPCS codes at detail level (SV202-2) with SV202-1='HC'. " +
                "If HCPCS codes are in HI segment, claim won't fail compliance but may not process correctly.",
                'HI_segment_HCPCS'
            )
        )
        
        # Store validation results
        validation_results.extend(claim_errors)
        
        # If no errors, add to valid claims
        if not any(e.level == ErrorLevel.ERROR for e in claim_errors):
            valid_claims.append(claim)
        
    return valid_claims, validation_results

def generate_control_numbers():
    """Generate X12 control numbers"""
    isa_control_number = str(random.randint(1, 999999)).zfill(9)
    gs_control_number = str(random.randint(1, 999999)).zfill(9)
    st_control_number = str(random.randint(1, 9999)).zfill(4)
    return isa_control_number, gs_control_number, st_control_number

def format_date(date_str, format_in='%Y-%m-%d', format_out='%Y%m%d'):
    """Convert date format"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, format_in)
        return dt.strftime(format_out)
    except ValueError:
        return date_str

def generate_837i_file(claims, batch_size=100):
    """Generate X12 837I file for KY Medicaid"""
    if not claims:
        print("No valid claims to process")
        return []
    
    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Process claims in batches
    batches = [claims[i:i+batch_size] for i in range(0, len(claims), batch_size)]
    file_paths = []
    
    for batch_num, batch in enumerate(batches):
        # Generate control numbers
        isa_control_number, gs_control_number, st_control_number = generate_control_numbers()
        
        # Current date and time in appropriate formats
        now = datetime.now()
        now_date = now.strftime('%Y%m%d')
        now_time = now.strftime('%H%M')
        
        # File naming
        file_name = f"837I_KY_MEDICAID_{now_date}_{batch_num+1}.txt"
        file_path = os.path.join(OUTPUT_DIR, file_name)
        file_paths.append(file_path)
        
        with open(file_path, 'w') as f:
            # ISA - Interchange Control Header
            isa = f"ISA{ELEMENT_SEPARATOR}00{ELEMENT_SEPARATOR}          {ELEMENT_SEPARATOR}00{ELEMENT_SEPARATOR}          "
            isa += f"{ELEMENT_SEPARATOR}ZZ{ELEMENT_SEPARATOR}{ky_medicaid_requirements['sender_id'].ljust(15)}"
            isa += f"{ELEMENT_SEPARATOR}ZZ{ELEMENT_SEPARATOR}{ky_medicaid_requirements['receiver_id'].ljust(15)}"
            isa += f"{ELEMENT_SEPARATOR}{now_date}{ELEMENT_SEPARATOR}{now_time}"
            isa += f"{ELEMENT_SEPARATOR}^{ELEMENT_SEPARATOR}{ISA_CONTROL_VERSION}{ELEMENT_SEPARATOR}{isa_control_number}"
            isa += f"{ELEMENT_SEPARATOR}0{ELEMENT_SEPARATOR}P{ELEMENT_SEPARATOR}{SUB_ELEMENT_SEPARATOR}{SEGMENT_TERMINATOR}{LINE_BREAK}"
            f.write(isa)
            
            # GS - Functional Group Header
            gs = f"GS{ELEMENT_SEPARATOR}HC{ELEMENT_SEPARATOR}{ky_medicaid_requirements['sender_id']}"
            gs += f"{ELEMENT_SEPARATOR}{ky_medicaid_requirements['receiver_id']}"
            gs += f"{ELEMENT_SEPARATOR}{now_date}{ELEMENT_SEPARATOR}{now_time}"
            gs += f"{ELEMENT_SEPARATOR}{gs_control_number}{ELEMENT_SEPARATOR}X{ELEMENT_SEPARATOR}{GS_VERSION}{SEGMENT_TERMINATOR}{LINE_BREAK}"
            f.write(gs)
            
            # ST - Transaction Set Header
            st = f"ST{ELEMENT_SEPARATOR}837{ELEMENT_SEPARATOR}{st_control_number}{ELEMENT_SEPARATOR}{GS_VERSION}{SEGMENT_TERMINATOR}{LINE_BREAK}"
            f.write(st)
            
            # BHT - Beginning of Hierarchical Transaction
            bht = f"BHT{ELEMENT_SEPARATOR}0019{ELEMENT_SEPARATOR}00{ELEMENT_SEPARATOR}{batch[0]['claim_control_number']}"
            bht += f"{ELEMENT_SEPARATOR}{now_date}{ELEMENT_SEPARATOR}{now_time}"
            bht += f"{ELEMENT_SEPARATOR}{batch[0]['transaction_type_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}"
            f.write(bht)
            
            # 1000A Submitter Loop
            f.write(f"NM1{ELEMENT_SEPARATOR}41{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}{ky_medicaid_requirements['sender_id']}")
            f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}46")
            f.write(f"{ELEMENT_SEPARATOR}KYSUBMIT{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # Submitter EDI Contact Information
            f.write(f"PER{ELEMENT_SEPARATOR}IC{ELEMENT_SEPARATOR}SUBMITTER CONTACT{ELEMENT_SEPARATOR}TE")
            f.write(f"{ELEMENT_SEPARATOR}8005551234{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # 1000B Receiver Loop
            f.write(f"NM1{ELEMENT_SEPARATOR}40{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}KYMEDICAID")
            f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}46")
            f.write(f"{ELEMENT_SEPARATOR}KYMEDICAID{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # Loop counter for hierarchical IDs
            hierarchical_id = 1
            
            # Process each claim
            for claim in batch:
                # 2000A Billing Provider Hierarchical Level
                f.write(f"HL{ELEMENT_SEPARATOR}{hierarchical_id}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}20")
                f.write(f"{ELEMENT_SEPARATOR}1{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                provider_hierarchical_id = hierarchical_id
                hierarchical_id += 1
                
                # Billing Provider Name
                if claim['provider_org_name']:
                    # Organization
                    f.write(f"NM1{ELEMENT_SEPARATOR}85{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}{claim['provider_org_name']}")
                else:
                    # Individual
                    f.write(f"NM1{ELEMENT_SEPARATOR}85{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{claim['provider_last_name']}")
                    f.write(f"{ELEMENT_SEPARATOR}{claim['provider_first_name']}")
                
                f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}XX")
                f.write(f"{ELEMENT_SEPARATOR}{claim['provider_npi']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Billing Provider Address
                f.write(f"N3{ELEMENT_SEPARATOR}{claim['provider_address_line_1']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                f.write(f"N4{ELEMENT_SEPARATOR}{claim['provider_city']}{ELEMENT_SEPARATOR}{claim['provider_state']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['provider_zip_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Billing Provider Taxonomy
                f.write(f"PRV{ELEMENT_SEPARATOR}BI{ELEMENT_SEPARATOR}PXC{ELEMENT_SEPARATOR}{claim['provider_taxonomy_code']}")
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # 2000B Subscriber Hierarchical Level
                f.write(f"HL{ELEMENT_SEPARATOR}{hierarchical_id}{ELEMENT_SEPARATOR}{provider_hierarchical_id}")
                f.write(f"{ELEMENT_SEPARATOR}22{ELEMENT_SEPARATOR}0{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                hierarchical_id += 1
                
                # Subscriber Information
                f.write(f"SBR{ELEMENT_SEPARATOR}P{ELEMENT_SEPARATOR}{claim['relationship_code']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['group_number'] or ''}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}")
                f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{claim['claim_filing_indicator_code']}")
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Subscriber Name (2010BA)
                f.write(f"NM1{ELEMENT_SEPARATOR}IL{ELEMENT_SEPARATOR}{claim['entity_type_qualifier']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['insured_last_name']}{ELEMENT_SEPARATOR}{claim['insured_first_name']}")
                f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}MI")
                f.write(f"{ELEMENT_SEPARATOR}{claim['insured_id']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Subscriber Address
                f.write(f"N3{ELEMENT_SEPARATOR}{claim['patient_address_line_1']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                f.write(f"N4{ELEMENT_SEPARATOR}{claim['patient_city']}{ELEMENT_SEPARATOR}{claim['patient_state']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['patient_zip_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Subscriber Demographic Info
                subscriber_dob = format_date(claim['patient_dob'])
                f.write(f"DMG{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{subscriber_dob}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['patient_gender']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Payer Name (2010BB)
                f.write(f"NM1{ELEMENT_SEPARATOR}PR{ELEMENT_SEPARATOR}2{ELEMENT_SEPARATOR}KYMEDICAID")
                f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}PI")
                f.write(f"{ELEMENT_SEPARATOR}KYMEDICAID{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # 2300 Claim Information
                f.write(f"CLM{ELEMENT_SEPARATOR}{claim['patient_control_number']}{ELEMENT_SEPARATOR}{claim['claim_amount']}")
                f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}")
                f.write(f"{claim['provider_accept_assignment_code']}{ELEMENT_SEPARATOR}{claim['benefits_assignment_cert_indicator']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['release_info_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Facility Type Code & Claim Frequency
                f.write(f"CL1{ELEMENT_SEPARATOR}{claim['place_of_service_code']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['claim_frequency_type_code']}")
                f.write(f"{ELEMENT_SEPARATOR}{claim['patient_status_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Admission Date and Hour
                admission_date = format_date(claim['admission_date'])
                discharge_date = format_date(claim['discharge_date'])
                f.write(f"DTP{ELEMENT_SEPARATOR}435{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{admission_date}")
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Discharge Date and Hour
                f.write(f"DTP{ELEMENT_SEPARATOR}096{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{discharge_date}")
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Statement Date Range
                statement_from = format_date(claim['statement_from_date'])
                statement_to = format_date(claim['statement_to_date'])
                f.write(f"DTP{ELEMENT_SEPARATOR}434{ELEMENT_SEPARATOR}RD8{ELEMENT_SEPARATOR}{statement_from}-{statement_to}")
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Institutional Claim Code Structure (Diagnoses)
                # Principal Diagnosis
                f.write(f"HI{ELEMENT_SEPARATOR}ABK:{claim['principal_diagnosis_code']}")
                
                # Secondary Diagnoses if present
                if claim['secondary_diagnosis_codes']:
                    secondary_codes = claim['secondary_diagnosis_codes'].split(',')
                    for i, code in enumerate(secondary_codes):
                        if i < 8:  # Up to 8 secondary diagnoses in HI segment
                            f.write(f"{ELEMENT_SEPARATOR}ABF:{code.strip()}")
                
                f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # Service lines
                for line in claim['service_lines']:
                    # 2400 Service Line
                    f.write(f"LX{ELEMENT_SEPARATOR}{line['line_number']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                    
                    # Service Line Information
                    f.write(f"SV2{ELEMENT_SEPARATOR}{line['revenue_code']}{ELEMENT_SEPARATOR}")
                    f.write(f"{line['procedure_code_qualifier']}:{line['procedure_code']}")
                    f.write(f"{ELEMENT_SEPARATOR}{line['charge_amount']}{ELEMENT_SEPARATOR}UN{ELEMENT_SEPARATOR}{line['units']}")
                    f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                    
                    # Line Item Service Date
                    service_date = format_date(line['service_date'])
                    f.write(f"DTP{ELEMENT_SEPARATOR}472{ELEMENT_SEPARATOR}D8{ELEMENT_SEPARATOR}{service_date}")
                    f.write(f"{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # If referring provider NPI exists, add it
                if claim['referring_provider_npi']:
                    f.write(f"NM1{ELEMENT_SEPARATOR}DN{ELEMENT_SEPARATOR}1")
                    f.write(f"{ELEMENT_SEPARATOR}REFERRING{ELEMENT_SEPARATOR}PROVIDER")
                    f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}XX")
                    f.write(f"{ELEMENT_SEPARATOR}{claim['referring_provider_npi']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                
                # If attending provider NPI exists, add it
                if claim['attending_provider_npi']:
                    f.write(f"NM1{ELEMENT_SEPARATOR}71{ELEMENT_SEPARATOR}1")
                    f.write(f"{ELEMENT_SEPARATOR}ATTENDING{ELEMENT_SEPARATOR}PROVIDER")
                    f.write(f"{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}{ELEMENT_SEPARATOR}XX")
                    f.write(f"{ELEMENT_SEPARATOR}{claim['attending_provider_npi']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
                    
                    # Attending Provider Specialty
                    f.write(f"PRV{ELEMENT_SEPARATOR}AT{ELEMENT_SEPARATOR}PXC")
                    f.write(f"{ELEMENT_SEPARATOR}{claim['provider_taxonomy_code']}{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # SE - Transaction Set Trailer
            f.write(f"SE{ELEMENT_SEPARATOR}[COUNT]{ELEMENT_SEPARATOR}{st_control_number}{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # GE - Functional Group Trailer
            f.write(f"GE{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{gs_control_number}{SEGMENT_TERMINATOR}{LINE_BREAK}")
            
            # IEA - Interchange Control Trailer
            f.write(f"IEA{ELEMENT_SEPARATOR}1{ELEMENT_SEPARATOR}{isa_control_number}{SEGMENT_TERMINATOR}")
        
        # Now go back and replace [COUNT] with actual segment count
        # This is a simplified approach; in practice, you'd want to count segments during generation
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Count segments (adjust based on actual format if needed)
        segment_count = content.count(SEGMENT_TERMINATOR)
        
        # Replace placeholder with count
        content = content.replace(f"SE{ELEMENT_SEPARATOR}[COUNT]", f"SE{ELEMENT_SEPARATOR}{segment_count}")
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"Generated 837I file: {file_path} with {len(batch)} claims")
    
    return file_paths

def validate_subscriber_info(claims):
    """Validate subscriber information based on KY Medicaid requirements"""
    validation_results = []
    
    for claim in claims:
        # Rule 15: SBR01 based on number of other payers
        # This would require fetching the 2320 loop data, which we'd implement here
        # As a placeholder, we'll just add a warning for now
        validation_results.append(
            ValidationError(
                claim['claim_id'],
                ErrorLevel.INFO,
                "Subscriber information validation: Should check SBR01 value based on number of other payers",
                'SBR01'
            )
        )
    
    return validation_results

def main():
    print("Kentucky Medicaid 837I Processor")
    print("-" * 50)
    
    # Connect to database
    print("Connecting to database...")
    conn = connect_to_db()
    
    # Fetch claims data
    print("Fetching claims data...")
    claims = fetch_claims_data(conn)
    print(f"Retrieved {len(claims)} claims")
    
    # Validate claims against KY Medicaid requirements
    print("Validating claims...")
    valid_claims, validation_results = validate_claims(claims)
    
    # Additional validation for subscriber information
    subscriber_validation = validate_subscriber_info(valid_claims)
    validation_results.extend(subscriber_validation)
    
    # Print validation results
    print(f"Validation complete. {len(valid_claims)} of {len(claims)} claims are valid.")
    error_count = sum(1 for e in validation_results if e.level == ErrorLevel.ERROR)
    warning_count = sum(1 for e in validation_results if e.level == ErrorLevel.WARNING)
    info_count = sum(1 for e in validation_results if e.level == ErrorLevel.INFO)
    print(f"Validation results: {error_count} errors, {warning_count} warnings, {info_count} info messages")
    
    # Generate 837I files
    print("Generating 837I files...")
    output_files = generate_837i_file(valid_claims)
    
    # Write validation results to log file
    log_file = os.path.join(OUTPUT_DIR, f"validation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    with open(log_file, 'w') as f:
        f.write("Kentucky Medicaid 837I Validation Log\n")
        f.write("-" * 80 + "\n")
        f.write(f"Date/Time: {datetime.now()}\n")
        f.write(f"Total Claims: {len(claims)}\n")
        f.write(f"Valid Claims: {len(valid_claims)}\n")
        f.write("-" * 80 + "\n\n")
        
        for result in validation_results:
            f.write(f"{result}\n")
    
    print(f"Validation log written to {log_file}")
    print(f"Processing complete. Generated {len(output_files)} 837I files in {OUTPUT_DIR}.")
    
    conn.close()
    return 0

if __name__ == "__main__":
    sys.exit(main()) 